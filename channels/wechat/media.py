"""CDN 下载/上传 + 媒体文件处理

本模块负责：
1. CDN 下载/解密（download_and_decrypt）
2. 各类型媒体的下载入口（download_image, download_voice, download_file, download_video）
3. CDN 上传（upload_file）
4. 媒体处理入口（process_media_item）— 调用 media_processor 进行具体处理
"""
import hashlib
import logging
import os
import tempfile
from pathlib import Path

import httpx

from .api import WeChatApi
from .config import MediaConfig
from .crypto import (
    generate_aes_key,
    aes_key_hex,
    aes_ecb_padded_size,
    encrypt_aes_ecb,
    decrypt_aes_ecb,
    decode_aes_key,
)
from .media_storage import MediaStorage, detect_image_mime
from .media_processor import (
    ProcessedMedia,
    process_image,
    process_voice,
    process_file,
    process_video,
)
from .types import UploadMediaType, MessageItem, MessageItemType

logger = logging.getLogger(__name__)

CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB（上传 CDN 限制）
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"}

# 全局单例（由 run_wechat.py 初始化）
_media_config: MediaConfig | None = None
_media_storage: MediaStorage | None = None


def init_media(config: MediaConfig | None = None) -> None:
    """初始化媒体配置和存储管理器（启动时调用一次）"""
    global _media_config, _media_storage
    _media_config = config or MediaConfig()
    _media_storage = MediaStorage(_media_config)
    logger.info("Media module initialized: dir=%s", _media_config.media_dir)


def get_media_config() -> MediaConfig:
    """获取当前媒体配置"""
    return _media_config or MediaConfig()


def get_media_storage() -> MediaStorage:
    """获取当前存储管理器"""
    return _media_storage or MediaStorage()


# ── CDN 下载 ──────────────────────────────────────────────

def _build_cdn_download_url(encrypt_query_param: str) -> str:
    return f"{CDN_BASE_URL}/download?encrypted_query_param={encrypt_query_param}"


async def download_and_decrypt(encrypt_query_param: str, aes_key_base64: str) -> bytes:
    """从 CDN 下载并解密文件"""
    url = _build_cdn_download_url(encrypt_query_param)
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        encrypted = resp.content

    aes_key = decode_aes_key(aes_key_base64)
    decrypted = decrypt_aes_ecb(aes_key, encrypted)
    logger.info("CDN download and decrypt: %d bytes", len(decrypted))
    return decrypted


# ── 各类型媒体下载入口 ──────────────────────────────────────

async def download_voice(item: MessageItem) -> bytes | None:
    """
    下载 CDN 语音，解密后返回原始字节。
    失败返回 None。
    """
    voice_item = item.voice_item
    if not voice_item:
        return None

    aes_key_b64 = voice_item.aes_key
    encrypt_query_param = voice_item.encrypt_query_param

    if not aes_key_b64 or not encrypt_query_param:
        logger.warning("Voice item has no usable CDN data")
        return None

    try:
        decrypted = await download_and_decrypt(encrypt_query_param, aes_key_b64)
        logger.info("Voice downloaded: %d bytes", len(decrypted))
        return decrypted
    except Exception as e:
        logger.warning("Failed to download voice: %s", e)
        return None


async def download_video(item: MessageItem) -> bytes | None:
    """
    下载 CDN 视频，解密后返回原始字节。
    失败返回 None。
    """
    video_item = item.video_item
    if not video_item:
        return None

    aes_key_b64 = _resolve_aes_key(video_item.aes_key, video_item.aeskey)
    encrypt_query_param = video_item.encrypt_query_param

    if not aes_key_b64 or not encrypt_query_param:
        logger.warning("Video item has no usable CDN data")
        return None

    try:
        decrypted = await download_and_decrypt(encrypt_query_param, aes_key_b64)
        logger.info("Video downloaded: %d bytes", len(decrypted))
        return decrypted
    except Exception as e:
        logger.warning("Failed to download video: %s", e)
        return None


# ── 媒体处理入口（bridge.py 调用）──────────────────────────

async def process_media_item(
    item: MessageItem,
    user_id: str = "",
) -> ProcessedMedia:
    """处理单个媒体消息项，返回 ProcessedMedia

    这是 bridge.py 调用的统一入口：
    1. 从 CDN 下载 + 解密
    2. 调用 media_processor 进行具体处理
    3. 返回处理结果
    """
    config = get_media_config()
    storage = get_media_storage()

    if item.type == MessageItemType.IMAGE:
        data = await download_image_raw(item)
        if data is None:
            return ProcessedMedia(media_type="image", error="图片下载失败")
        return process_image(data, "image.jpg", config, storage, user_id)

    elif item.type == MessageItemType.VOICE:
        data = await download_voice(item)
        if data is None:
            # 语音下载失败时，尝试使用微信已识别的文字
            voice_text = item.voice_item.text if item.voice_item else ""
            if voice_text:
                return ProcessedMedia(media_type="voice", text_content=voice_text)
            return ProcessedMedia(media_type="voice", error="语音下载失败")
        voice_text = item.voice_item.text if item.voice_item else ""
        ext = ".amr"  # 微信语音默认格式
        return process_voice(data, f"voice{ext}", config, storage, user_id, voice_text)

    elif item.type == MessageItemType.FILE:
        data = await download_file_raw(item)
        if data is None:
            file_name = item.file_item.file_name if item.file_item else "unknown"
            return ProcessedMedia(media_type="file", error=f"文件下载失败: {file_name}")
        file_name = item.file_item.file_name if item.file_item else "file.bin"
        return process_file(data, file_name, config, storage, user_id)

    elif item.type == MessageItemType.VIDEO:
        data = await download_video(item)
        if data is None:
            return ProcessedMedia(media_type="video", error="视频下载失败")
        return process_video(data, "video.mp4", config, storage, user_id)

    else:
        return ProcessedMedia(media_type="unknown", error=f"不支持的消息类型: {item.type}")


async def download_image_raw(item: MessageItem) -> bytes | None:
    """下载图片原始字节（供 process_media_item 使用）"""
    image_item = item.image_item
    if not image_item:
        return None

    aes_key_b64 = _resolve_aes_key(image_item.aes_key, image_item.aeskey)
    encrypt_query_param = image_item.encrypt_query_param

    if not aes_key_b64 or not encrypt_query_param:
        return None

    try:
        return await download_and_decrypt(encrypt_query_param, aes_key_b64)
    except Exception as e:
        logger.warning("Failed to download image raw: %s", e)
        return None


async def download_file_raw(item: MessageItem) -> bytes | None:
    """下载文件原始字节（供 process_media_item 使用）"""
    file_item = item.file_item
    if not file_item:
        return None

    aes_key_b64 = file_item.aes_key
    encrypt_query_param = file_item.encrypt_query_param

    if not aes_key_b64 or not encrypt_query_param:
        return None

    try:
        return await download_and_decrypt(encrypt_query_param, aes_key_b64)
    except Exception as e:
        logger.warning("Failed to download file raw: %s", e)
        return None


# ── CDN 上传 ──────────────────────────────────────────────

def is_image_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".wmv", ".flv", ".mkv", ".webm", ".mpeg", ".3gp"}


def is_video_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in VIDEO_EXTENSIONS


def _classify_media_type(file_path: str) -> UploadMediaType:
    """根据文件扩展名判断上传媒体类型"""
    if is_image_file(file_path):
        return UploadMediaType.IMAGE
    if is_video_file(file_path):
        return UploadMediaType.VIDEO
    return UploadMediaType.FILE


async def upload_file(
    api: WeChatApi,
    to_user_id: str,
    file_path: str,
) -> dict:
    """
    上传文件到 CDN，返回上传结果 dict：
    { media_type, encrypt_query_param, aes_key_hex, file_name, file_size, raw_size }
    """
    path = Path(file_path)
    raw_data = path.read_bytes()
    raw_size = len(raw_data)

    if raw_size > MAX_FILE_SIZE:
        raise RuntimeError(f"文件过大 ({raw_size / 1024 / 1024:.1f}MB)，最大支持 25MB")

    file_name = path.name
    media_type = _classify_media_type(file_path)

    # 计算哈希和加密
    raw_file_md5 = hashlib.md5(raw_data).hexdigest()
    file_size = aes_ecb_padded_size(raw_size)
    file_key = os.urandom(16).hex()  # 32-hex-char string
    aes_key = generate_aes_key()
    aes_key_hex_str = aes_key_hex(aes_key)

    # 获取上传地址
    logger.info("Requesting upload URL: %s (%d bytes)", file_name, raw_size)
    upload_resp = await api.get_upload_url({
        "filekey": file_key,
        "media_type": int(media_type),
        "to_user_id": to_user_id,
        "rawsize": raw_size,
        "rawfilemd5": raw_file_md5,
        "filesize": file_size,
        "no_need_thumb": True,
        "aeskey": aes_key_hex_str,
        "base_info": {
            "channel_version": "2.0.0",
            "bot_agent": "wechat-agent",
        },
    })

    if not upload_resp.get("upload_full_url") and not upload_resp.get("upload_param"):
        raise RuntimeError(f"获取上传地址失败: {upload_resp}")

    # 加密文件
    encrypted = encrypt_aes_ecb(aes_key, raw_data)

    # 构造上传 URL
    if upload_resp.get("upload_full_url"):
        upload_url = upload_resp["upload_full_url"]
    else:
        upload_url = (
            f"{CDN_BASE_URL}/upload?"
            f"encrypted_query_param={upload_resp['upload_param']}"
            f"&filekey={file_key}"
        )

    # 上传到 CDN
    encrypt_query_param = await _upload_to_cdn(upload_url, encrypted)
    logger.info("CDN upload succeeded: %s", file_name)

    return {
        "media_type": "image" if media_type == UploadMediaType.IMAGE else "video" if media_type == UploadMediaType.VIDEO else "file",
        "encrypt_query_param": encrypt_query_param,
        "aes_key_hex": aes_key_hex_str,
        "file_name": file_name,
        "file_size": file_size,
        "raw_size": raw_size,
    }


async def _upload_to_cdn(url: str, encrypted: bytes) -> str:
    """上传加密数据到 CDN，返回 encrypt_query_param"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    content=encrypted,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=60,
                )
            if 400 <= resp.status_code < 500:
                raise RuntimeError(f"CDN 上传失败 (4xx): {resp.status_code} {resp.text[:200]}")
            if resp.status_code >= 500:
                logger.warning("CDN upload 5xx, retry %d", attempt)
                continue

            # 从响应头获取下载参数
            param = resp.headers.get("x-encrypted-param")
            if not param:
                raise RuntimeError("CDN 上传成功但未返回 x-encrypted-param")
            return param

        except httpx.TimeoutException:
            raise RuntimeError("CDN 上传超时")
    raise RuntimeError("CDN 上传失败: 多次重试后仍失败")


# ── 工具函数 ──────────────────────────────────────────────

def _resolve_aes_key(aes_key: str, aeskey: str) -> str:
    """解析 AES key，兼容 aes_key (base64) 和 aeskey (hex) 两种格式"""
    if aes_key:
        return aes_key
    if aeskey:
        return base64_hex_to_b64(aeskey)
    return ""


def base64_hex_to_b64(hex_key: str) -> str:
    """hex 格式的 AES key → base64 格式"""
    import base64
    raw = bytes.fromhex(hex_key)
    return base64.b64encode(raw).decode("ascii")
