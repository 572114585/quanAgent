"""个人微信渠道配置：从 .env 读取"""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"

# 默认媒体存储根目录
DEFAULT_MEDIA_DIR = str(Path.home() / ".wechat-agent" / "media")


@dataclass(frozen=True)
class MediaLimits:
    """各类媒体文件的大小限制（字节）"""
    image_max_size: int = 10 * 1024 * 1024       # 10MB
    voice_max_size: int = 20 * 1024 * 1024        # 20MB
    file_max_size: int = 50 * 1024 * 1024         # 50MB
    video_max_size: int = 100 * 1024 * 1024       # 100MB
    upload_max_size: int = 25 * 1024 * 1024       # 上传上限 25MB（CDN 限制）


@dataclass(frozen=True)
class MediaFormats:
    """支持的媒体格式白名单"""
    image_formats: frozenset[str] = frozenset(
        {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".tiff", ".tif"}
    )
    voice_formats: frozenset[str] = frozenset(
        {".amr", ".mp3", ".wav", ".aac", ".m4a", ".ogg", ".wma", ".flac", ".silk"}
    )
    file_formats: frozenset[str] = frozenset(
        {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
         ".txt", ".csv", ".json", ".xml", ".html", ".md",
         ".zip", ".rar", ".7z", ".tar", ".gz"}
    )
    video_formats: frozenset[str] = frozenset(
        {".mp4", ".mov", ".avi", ".wmv", ".flv", ".mkv", ".webm", ".mpeg", ".3gp"}
    )


@dataclass(frozen=True)
class MediaConfig:
    """媒体处理完整配置"""
    limits: MediaLimits = field(default_factory=MediaLimits)
    formats: MediaFormats = field(default_factory=MediaFormats)
    media_dir: str = DEFAULT_MEDIA_DIR
    temp_dir: str = ""  # 空=系统临时目录
    auto_cleanup_hours: int = 24  # 临时文件自动清理时间（小时）
    image_max_dimension: int = 2048  # 图片最大边长（像素），超过则压缩
    image_quality: int = 85  # 图片压缩质量（1-100）
    voice_sample_rate: int = 16000  # 语音重采样率（用于 ASR）
    video_thumbnail_time: float = 1.0  # 视频缩略图提取时间点（秒）


@dataclass(frozen=True)
class WechatConfig:
    base_url: str = DEFAULT_BASE_URL
    media: MediaConfig = field(default_factory=MediaConfig)

    @classmethod
    def from_env(cls) -> "WechatConfig":
        return cls(
            base_url=os.getenv("WECHAT_ILINK_BASE_URL", DEFAULT_BASE_URL),
            media=MediaConfig(
                media_dir=os.getenv("WECHAT_MEDIA_DIR", DEFAULT_MEDIA_DIR),
                temp_dir=os.getenv("WECHAT_TEMP_DIR", ""),
                auto_cleanup_hours=_env_int("WECHAT_MEDIA_CLEANUP_HOURS", 24),
                image_max_dimension=_env_int("WECHAT_IMAGE_MAX_DIMENSION", 2048),
                image_quality=_env_int("WECHAT_IMAGE_QUALITY", 85),
                limits=MediaLimits(
                    image_max_size=_env_int("WECHAT_IMAGE_MAX_SIZE", 10 * 1024 * 1024),
                    voice_max_size=_env_int("WECHAT_VOICE_MAX_SIZE", 20 * 1024 * 1024),
                    file_max_size=_env_int("WECHAT_FILE_MAX_SIZE", 50 * 1024 * 1024),
                    video_max_size=_env_int("WECHAT_VIDEO_MAX_SIZE", 100 * 1024 * 1024),
                ),
            ),
        )


def _env_int(key: str, default: int) -> int:
    """从环境变量读取整数，解析失败时返回默认值"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("环境变量 %s=%r 不是有效整数，使用默认值 %d", key, value, default)
        return default
