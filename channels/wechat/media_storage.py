"""媒体文件存储管理：路径分配、临时文件清理、存储统计"""
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional

from .config import MediaConfig

logger = logging.getLogger(__name__)


class MediaStorage:
    """媒体文件存储管理器

    目录结构：
      {media_dir}/
        image/    - 图片文件
        voice/    - 语音文件
        file/     - 文档文件
        video/    - 视频文件
        thumb/    - 缩略图
    """

    SUBDIRS = ("image", "voice", "file", "video", "thumb")

    def __init__(self, config: MediaConfig | None = None):
        self._config = config or MediaConfig()
        self._media_dir = Path(self._config.media_dir)
        self._temp_dir = Path(self._config.temp_dir) if self._config.temp_dir else Path(tempfile.gettempdir()) / "wechat-agent"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """确保所有子目录存在"""
        for subdir in self.SUBDIRS:
            (self._media_dir / subdir).mkdir(parents=True, exist_ok=True)
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    # ── 路径分配 ──────────────────────────────────────────────

    def get_save_path(self, category: str, filename: str, user_id: str = "") -> Path:
        """获取媒体文件的保存路径

        Args:
            category: image/voice/file/video/thumb
            filename: 原始文件名
            user_id: 用户ID（可选，用于隔离不同用户的文件）

        Returns:
            完整保存路径（文件名冲突时自动加序号）
        """
        if category not in self.SUBDIRS:
            category = "file"

        base = self._media_dir / category
        if user_id:
            base = base / user_id
            base.mkdir(parents=True, exist_ok=True)

        target = base / filename
        if target.exists():
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            seq = 1
            while target.exists():
                target = base / f"{stem}_{seq}{suffix}"
                seq += 1

        return target

    def get_temp_path(self, filename: str) -> Path:
        """获取临时文件路径"""
        return self._temp_dir / filename

    # ── 文件保存 ──────────────────────────────────────────────

    def save_bytes(self, data: bytes, category: str, filename: str, user_id: str = "") -> Path:
        """保存二进制数据到媒体目录"""
        path = self.get_save_path(category, filename, user_id)
        path.write_bytes(data)
        logger.info("Saved %s: %s (%d bytes)", category, path.name, len(data))
        return path

    def save_to_temp(self, data: bytes, filename: str) -> Path:
        """保存到临时目录"""
        path = self.get_temp_path(filename)
        path.write_bytes(data)
        return path

    # ── 格式验证 ──────────────────────────────────────────────

    def validate_extension(self, filename: str, category: str) -> bool:
        """验证文件扩展名是否在白名单内"""
        ext = Path(filename).suffix.lower()
        formats_map = {
            "image": self._config.formats.image_formats,
            "voice": self._config.formats.voice_formats,
            "file": self._config.formats.file_formats,
            "video": self._config.formats.video_formats,
        }
        allowed = formats_map.get(category)
        if allowed is None:
            return True  # 未知类别不拦截
        return ext in allowed

    def validate_size(self, size: int, category: str) -> bool:
        """验证文件大小是否在限制内"""
        limits_map = {
            "image": self._config.limits.image_max_size,
            "voice": self._config.limits.voice_max_size,
            "file": self._config.limits.file_max_size,
            "video": self._config.limits.video_max_size,
        }
        max_size = limits_map.get(category, self._config.limits.file_max_size)
        return size <= max_size

    # ── 自动清理 ──────────────────────────────────────────────

    def cleanup_expired(self) -> int:
        """清理过期的临时文件，返回清理数量"""
        cutoff = time.time() - (self._config.auto_cleanup_hours * 3600)
        cleaned = 0

        # 仅清理临时目录
        cleaned += self._cleanup_dir(self._temp_dir, cutoff)

        if cleaned:
            logger.info("Cleaned up %d expired temp files", cleaned)
        return cleaned

    def _cleanup_dir(self, dir_path: Path, cutoff: float) -> int:
        """清理目录中修改时间早于 cutoff 的文件"""
        if not dir_path.exists():
            return 0
        cleaned = 0
        for f in dir_path.rglob("*"):
            if f.is_file() and f.stat().st_mtime < cutoff:
                try:
                    f.unlink()
                    cleaned += 1
                except OSError:
                    pass
        return cleaned

    # ── 存储统计 ──────────────────────────────────────────────

    def get_storage_stats(self) -> dict:
        """获取存储使用统计"""
        stats = {}
        total_size = 0
        total_files = 0

        for subdir in self.SUBDIRS:
            dir_path = self._media_dir / subdir
            size = 0
            count = 0
            if dir_path.exists():
                for f in dir_path.rglob("*"):
                    if f.is_file():
                        size += f.stat().st_size
                        count += 1
            stats[subdir] = {"size_mb": round(size / 1024 / 1024, 2), "count": count}
            total_size += size
            total_files += count

        stats["total"] = {"size_mb": round(total_size / 1024 / 1024, 2), "count": total_files}
        return stats

    # ── 文件安全 ──────────────────────────────────────────────

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名，移除路径遍历等危险字符"""
        # 去除路径分隔符和特殊字符
        safe = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
        # 限制文件名长度
        stem = Path(safe).stem[:100]
        suffix = Path(safe).suffix[:20]
        return stem + suffix if suffix else stem


def detect_image_mime(data: bytes) -> str:
    """根据文件头检测图片 MIME 类型（公共工具函数）"""
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
