"""Upload workspace files to Lesso MOSS (S3-compatible) and return a public URL.

Used by artifact auto-upload (output/ only) and the upload-to-moss skill
(output/, tmp/, uploads/). Missing credentials skip upload instead of failing
the conversation. boto3 is imported lazily so tests can mock the S3 client.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)

_DEFAULT_ENDPOINT = "https://moss.lesso.com"
_DEFAULT_REGION = "fs"
_DEFAULT_PREFIX = "quan"
_SKILL_ALLOWED_SUBDIRS: tuple[str, ...] = ("output", "tmp", "uploads")
_AUTO_ALLOWED_SUBDIRS: tuple[str, ...] = ("output",)


@dataclass(frozen=True)
class MossSettings:
    endpoint: str
    region: str
    bucket: str
    access_key: str
    secret_key: str
    key_prefix: str

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.bucket and self.access_key and self.secret_key)


@dataclass(frozen=True)
class MossUploadResult:
    ok: bool
    download_url: str = ""
    bucket: str = ""
    object_key: str = ""
    error: str = ""
    skipped: bool = False


def moss_settings(environ: Mapping[str, str] | None = None) -> MossSettings:
    """Read MOSS settings at call time so tests can monkeypatch env."""
    values = os.environ if environ is None else environ
    endpoint = str(values.get("MOSS_ENDPOINT", _DEFAULT_ENDPOINT)).strip().rstrip("/")
    region = str(values.get("MOSS_REGION", _DEFAULT_REGION)).strip() or _DEFAULT_REGION
    bucket = (
        str(values.get("MOSS_BUCKET", "")).strip()
        or str(values.get("MOSS_UPLOAD_BUCKET", "")).strip()
    )
    prefix = str(values.get("MOSS_KEY_PREFIX", _DEFAULT_PREFIX)).strip().strip("/") or _DEFAULT_PREFIX
    return MossSettings(
        endpoint=endpoint or _DEFAULT_ENDPOINT,
        region=region,
        bucket=bucket,
        access_key=str(values.get("MOSS_ACCESS_KEY", "")).strip(),
        secret_key=str(values.get("MOSS_SECRET_KEY", "")).strip(),
        key_prefix=prefix,
    )


def resolve_workspace_root(workspace_root: Path | None = None) -> Path:
    """Prefer configured WORKSPACE_ROOT; fall back to cwd when the skill runs inside it."""
    if workspace_root is not None:
        return Path(workspace_root).resolve()
    from agent_core.config import WORKSPACE_ROOT

    root = Path(WORKSPACE_ROOT)
    if not root.is_absolute():
        root = root.resolve()
    if (root / "output").exists() or (root / "skills").exists():
        return root
    cwd = Path.cwd().resolve()
    if (cwd / "output").exists() or (cwd / "skills").exists():
        return cwd
    return root


def resolve_upload_path(
    path: str | Path,
    *,
    allowed_subdirs: tuple[str, ...] = _SKILL_ALLOWED_SUBDIRS,
    workspace_root: Path | None = None,
) -> Path:
    """Resolve and validate a local file under allowed workspace subtrees."""
    root = resolve_workspace_root(workspace_root)
    text = str(path or "").strip().strip('"').strip("'")
    if not text:
        raise ValueError("路径为空")
    if text.startswith("/"):
        text = text.lstrip("/")

    candidate = Path(text)
    search = [candidate] if candidate.is_absolute() else [root / candidate, Path.cwd() / candidate]
    resolved: Path | None = None
    for cand in search:
        try:
            if cand.exists():
                resolved = cand.resolve()
                break
        except OSError as exc:
            raise ValueError(f"无法解析路径: {exc}") from exc
    if resolved is None:
        raise ValueError(f"文件不存在: {text}")

    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("路径必须位于工作区内") from exc

    parts = rel.parts
    if not parts or parts[0] not in allowed_subdirs:
        allowed = "、".join(f"{name}/" for name in allowed_subdirs)
        raise ValueError(f"只允许上传 {allowed} 下的普通文件")

    if resolved.is_symlink():
        raise ValueError("拒绝符号链接")
    if not resolved.is_file():
        raise ValueError("路径不是普通文件")
    if not os.access(resolved, os.R_OK):
        raise ValueError("文件不可读")
    return resolved


def build_object_key(file_name: str, *, settings: MossSettings | None = None, now: datetime | None = None) -> str:
    cfg = settings or moss_settings()
    stamp = now or datetime.now(timezone.utc)
    safe_name = Path(file_name).name.strip().replace("\\", "_").replace("/", "_")
    if not safe_name:
        raise ValueError("文件名为空")
    return f"{cfg.key_prefix}/{stamp:%Y/%m/%d}/{uuid.uuid4().hex[:8]}/{safe_name}"


def build_public_url(object_key: str, *, settings: MossSettings | None = None) -> str:
    cfg = settings or moss_settings()
    encoded_key = quote(object_key.strip(), safe="/")
    return f"{cfg.endpoint.rstrip('/')}/{cfg.bucket.strip('/')}/{encoded_key}"


def _s3_client(settings: MossSettings):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint,
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        region_name=settings.region,
        config=Config(
            signature_version="s3",
            s3={"addressing_style": "path", "payload_signing_enabled": False},
            retries={"max_attempts": 3, "mode": "legacy"},
        ),
        verify=False,
    )


def upload_local_file(
    path: str | Path,
    *,
    allowed_subdirs: tuple[str, ...] = _AUTO_ALLOWED_SUBDIRS,
    workspace_root: Path | None = None,
    settings: MossSettings | None = None,
) -> MossUploadResult:
    """Upload one local file. Soft-fails when MOSS is unconfigured or S3 errors."""
    cfg = settings or moss_settings()
    if not cfg.configured:
        return MossUploadResult(ok=False, skipped=True, error="MOSS 未配置")
    try:
        local = resolve_upload_path(
            path,
            allowed_subdirs=allowed_subdirs,
            workspace_root=workspace_root,
        )
        object_key = build_object_key(local.name, settings=cfg)
        mime_type = mimetypes.guess_type(local.name)[0] or "application/octet-stream"
        size_bytes = local.stat().st_size
        with local.open("rb") as handle:
            _s3_client(cfg).put_object(
                Bucket=cfg.bucket,
                Key=object_key,
                Body=handle,
                ContentType=mime_type,
                ContentLength=size_bytes,
            )
        download_url = build_public_url(object_key, settings=cfg)
        logger.info("MOSS uploaded %s -> %s", local.name, download_url)
        return MossUploadResult(
            ok=True,
            download_url=download_url,
            bucket=cfg.bucket,
            object_key=object_key,
        )
    except ValueError as exc:
        logger.warning("MOSS upload rejected: %s", exc)
        return MossUploadResult(ok=False, error=str(exc))
    except ModuleNotFoundError as exc:
        logger.warning("MOSS upload failed: missing dependency %s (pip install boto3)", exc.name)
        return MossUploadResult(ok=False, error=f"缺少依赖: {exc.name}")
    except Exception as exc:
        logger.warning("MOSS upload failed: %s", exc)
        return MossUploadResult(ok=False, error=f"MOSS 文件上传失败: {exc}")


def try_upload_output_file(
    path: str | Path,
    *,
    workspace_root: Path | None = None,
    settings: MossSettings | None = None,
) -> str:
    """Return the public URL, or empty string when upload is skipped/failed."""
    result = upload_local_file(
        path,
        allowed_subdirs=_AUTO_ALLOWED_SUBDIRS,
        workspace_root=workspace_root,
        settings=settings,
    )
    return result.download_url if result.ok else ""
