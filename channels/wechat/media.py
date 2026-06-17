"""CDN 下载/上传 + 媒体文件处理"""
import hashlib
import logging
import os
import tempfile
from pathlib import Path

import httpx

from .api import WeChatApi
from .crypto import (
    generate_aes_key,
    aes_key_hex,
    aes_ecb_padded_size,
    encrypt_aes_ecb,
    decrypt_aes_ecb,
    decode_aes_key,
)
from .types import UploadMediaType, MessageItem, MessageItemType

logger = logging.getLogger(__name__)

CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"}


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


def _detect_mime(data: bytes) -> str:
    """根据文件头检测 MIME 类型"""
    if len(data) < 2:
        return "image/jpeg"
    if data[0] == 0x89 and data[1] == 0x50:
        return "image/png"
    if data[0] == 0xFF and data[1] == 0xD8:
        return "image/jpeg"
    if data[0] == 0x47 and data[1] == 0x49:
        return "image/gif"
    if data[0] == 0x52 and data[1] == 0x49:
        return "image/webp"
    if data[0] == 0x42 and data[1] == 0x4D:
        return "image/bmp"
    return "image/jpeg"


async def download_image(item: MessageItem) -> str | None:
    """
    下载 CDN 图片，解密后返回 base64 data URI。
    失败返回 None。
    """
    image_item = item.image_item
    if not image_item:
        return None

    # 提取 CDN 参数
    aes_key_b64 = ""
    encrypt_query_param = ""

    if image_item.aes_key and image_item.encrypt_query_param:
        aes_key_b64 = image_item.aes_key
        encrypt_query_param = image_item.encrypt_query_param
    elif image_item.aeskey and image_item.encrypt_query_param:
        # aeskey 是 hex 格式，需要转 base64
        aes_key_b64 = base64_hex_to_b64(image_item.aeskey)
        encrypt_query_param = image_item.encrypt_query_param

    if not aes_key_b64 or not encrypt_query_param:
        logger.warning("Image item has no usable CDN data")
        return None

    try:
        decrypted = await download_and_decrypt(encrypt_query_param, aes_key_b64)
        import base64 as b64mod
        mime = _detect_mime(decrypted)
        b64 = b64mod.b64encode(decrypted).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        logger.warning("Failed to download image: %s", e)
        return None


async def download_file(item: MessageItem) -> str | None:
    """
    下载 CDN 文件，解密后保存到临时目录。
    返回本地文件路径，失败返回 None。
    """
    file_item = item.file_item
    if not file_item:
        return None

    aes_key_b64 = file_item.aes_key
    encrypt_query_param = file_item.encrypt_query_param

    if not aes_key_b64 or not encrypt_query_param:
        logger.warning("File item has no usable CDN data")
        return None

    try:
        decrypted = await download_and_decrypt(encrypt_query_param, aes_key_b64)
        tmp_dir = Path(tempfile.gettempdir()) / "wechat-agent"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        file_name = file_item.file_name or f"file-{os.getpid()}.bin"
        file_path = tmp_dir / file_name
        file_path.write_bytes(decrypted)
        logger.info("File downloaded: %s (%d bytes)", file_path, len(decrypted))
        return str(file_path)
    except Exception as e:
        logger.warning("Failed to download file: %s", e)
        return None


# ── CDN 上传 ──────────────────────────────────────────────

def is_image_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS


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
    is_image = is_image_file(file_path)
    media_type = UploadMediaType.IMAGE if is_image else UploadMediaType.FILE

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
        "media_type": "image" if is_image else "file",
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


def base64_hex_to_b64(hex_key: str) -> str:
    """hex 格式的 AES key → base64 格式"""
    import base64
    raw = bytes.fromhex(hex_key)
    return base64.b64encode(raw).decode("ascii")
