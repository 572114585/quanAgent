"""多模态消息组装：本地图片 / URL → OpenAI 兼容 image_url content parts。

供 Web / CLI / view_image 共用。硅基流动等 OpenAI 兼容接口接受
`data:{mime};base64,...` 形式的 image_url。

视觉图会按 LLM_VISION_MAX_EDGE / LLM_VISION_JPEG_QUALITY 压缩，降低 TPM
（大图 base64 极易打满硅基流动 tokens-per-minute 限额）。
"""
from __future__ import annotations

import base64
import io
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.request import urlopen

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def guess_image_mime(path_or_url: str, fallback: str = "image/jpeg") -> str:
    mime, _ = mimetypes.guess_type(path_or_url)
    if mime and mime.startswith("image/"):
        return mime
    return fallback


def _vision_max_edge() -> int:
    raw = os.getenv("LLM_VISION_MAX_EDGE", "1280").strip()
    try:
        return max(256, int(raw))
    except ValueError:
        return 1280


def _vision_jpeg_quality() -> int:
    raw = os.getenv("LLM_VISION_JPEG_QUALITY", "85").strip()
    try:
        return min(95, max(40, int(raw)))
    except ValueError:
        return 85


def compress_image_bytes(data: bytes, *, source_mime: str | None = None) -> tuple[bytes, str]:
    """压缩图片为 JPEG，限制最长边，减少多模态请求的 token 占用。

    无 Pillow 或解码失败时原样返回。
    """
    try:
        from PIL import Image
    except ImportError:
        mime = source_mime or "image/jpeg"
        return data, mime

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:  # noqa: BLE001
        mime = source_mime or "image/jpeg"
        return data, mime

    # 统一 RGB（去掉 alpha，JPEG 不支持）
    if img.mode in ("RGBA", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        alpha = img.split()[-1]
        rgb = img.convert("RGBA") if img.mode == "LA" else img
        background.paste(rgb, mask=alpha)
        img = background
    elif img.mode == "P":
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    max_edge = _vision_max_edge()
    w, h = img.size
    longest = max(w, h)
    if longest > max_edge:
        scale = max_edge / float(longest)
        img = img.resize(
            (max(1, int(w * scale)), max(1, int(h * scale))),
            Image.Resampling.LANCZOS,
        )

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_vision_jpeg_quality(), optimize=True)
    out = buf.getvalue()
    if len(out) < len(data) or longest > max_edge:
        logger.debug(
            "vision image compressed %dB -> %dB size=%sx%s",
            len(data),
            len(out),
            img.size[0],
            img.size[1],
        )
        return out, "image/jpeg"
    # 压缩后更大则保留原图（常见于已很小的 JPEG）
    mime = source_mime or "image/jpeg"
    return data, mime


def bytes_to_data_url(data: bytes, mime: str | None = None) -> str:
    use_mime = mime or "image/jpeg"
    compressed, use_mime = compress_image_bytes(data, source_mime=use_mime)
    b64 = base64.b64encode(compressed).decode("ascii")
    return f"data:{use_mime};base64,{b64}"


def file_to_data_url(path: Path, mime: str | None = None) -> str:
    """把本地图片文件编码为 data URL（自动压缩）。"""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"图片不存在: {path}")
    data = resolved.read_bytes()
    if not data:
        raise ValueError(f"图片为空文件: {path}")
    use_mime = mime or guess_image_mime(str(resolved))
    return bytes_to_data_url(data, use_mime)


def to_image_part(
    ref: str | Path,
    *,
    mime: str | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """将 data URL / http(s) URL / 本地路径转为 image_url content part。"""
    if isinstance(ref, Path):
        data_url = file_to_data_url(ref, mime=mime)
        return {"type": "image_url", "image_url": {"url": data_url}}

    text = (ref or "").strip()
    if not text:
        raise ValueError("图片引用为空")

    if text.startswith("data:"):
        # 已有 data URL：解码后压缩再编码，避免历史大图反复烧 TPM
        try:
            header, b64 = text.split(",", 1)
            raw_mime = "image/jpeg"
            if header.startswith("data:") and ";base64" in header:
                raw_mime = header[5:].split(";", 1)[0] or raw_mime
            raw = base64.b64decode(b64)
            return {
                "type": "image_url",
                "image_url": {"url": bytes_to_data_url(raw, mime or raw_mime)},
            }
        except Exception:  # noqa: BLE001
            return {"type": "image_url", "image_url": {"url": text}}

    if text.startswith(("http://", "https://")):
        data = urlopen(text, timeout=10).read()
        use_mime = mime or guess_image_mime(text)
        return {
            "type": "image_url",
            "image_url": {"url": bytes_to_data_url(data, use_mime)},
        }

    # 本地路径：相对 workspace 或绝对路径
    path = Path(text)
    if not path.is_absolute() and workspace_root is not None:
        # /uploads/x → uploads/x
        normalized = text.lstrip("/").replace("\\", "/")
        path = workspace_root / normalized
    data_url = file_to_data_url(path, mime=mime)
    return {"type": "image_url", "image_url": {"url": data_url}}


def build_user_content(
    text: str,
    image_refs: list[str | Path] | None = None,
    *,
    workspace_root: Path | None = None,
) -> str | list[dict[str, Any]]:
    """纯文本，或 [image_url..., text] 多模态 user content。"""
    refs = list(image_refs or [])
    if not refs:
        return text
    parts = [to_image_part(r, workspace_root=workspace_root) for r in refs]
    parts.append({"type": "text", "text": text or "(见附图)"})
    return parts


def is_image_mime(mime: str) -> bool:
    return bool(mime) and mime.startswith("image/")


def is_image_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in _IMAGE_SUFFIXES
