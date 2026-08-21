"""MOSS upload: path guards, skip-when-unconfigured, and mocked S3."""
from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from artifacts.detector import attach_moss_urls
from tools.moss_upload import (
    MossSettings,
    build_object_key,
    build_public_url,
    moss_settings,
    resolve_upload_path,
    upload_local_file,
)

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "workspace" / "skills" / "upload-to-moss"


@pytest.fixture
def ws_root():
    """Writable workspace root; avoid pytest tmp_path when the user temp dir is locked."""
    base = ROOT / "tmp" / "pytest-moss-upload"
    base.mkdir(parents=True, exist_ok=True)
    root = base / uuid.uuid4().hex[:8]
    root.mkdir()
    yield root
    shutil.rmtree(root, ignore_errors=True)


class _FakeS3:
    def __init__(self) -> None:
        self.puts: list[dict] = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        return {"ETag": '"etag"'}


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 8, 21, 8, 0, 0, tzinfo=tz or timezone.utc)


def _configured_env(monkeypatch) -> None:
    monkeypatch.setenv("MOSS_ENDPOINT", "https://moss.lesso.com")
    monkeypatch.setenv("MOSS_REGION", "fs")
    monkeypatch.setenv("MOSS_BUCKET", "rag-uat-dev")
    monkeypatch.setenv("MOSS_ACCESS_KEY", "ak")
    monkeypatch.setenv("MOSS_SECRET_KEY", "sk")
    monkeypatch.setenv("MOSS_KEY_PREFIX", "quan")


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        raise AssertionError("SKILL.md must start with YAML frontmatter")
    end = text.find("\n---", 3)
    if end < 0:
        raise AssertionError("SKILL.md frontmatter is not closed")
    block = text[3:end].strip()
    data: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def test_unconfigured_skips_upload(monkeypatch, ws_root: Path):
    monkeypatch.setenv("MOSS_ACCESS_KEY", "")
    monkeypatch.setenv("MOSS_SECRET_KEY", "")
    output = ws_root / "output"
    output.mkdir()
    (output / "a.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr("artifacts.detector.OUTPUT_DIR", output)

    artifacts = [{
        "name": "a.pdf",
        "path": "a.pdf",
        "url": "/output/a.pdf",
        "mime": "application/pdf",
        "size": 4,
    }]
    out = attach_moss_urls(artifacts)
    assert out[0]["url"] == "/output/a.pdf"
    assert "mossUrl" not in out[0]


def test_configured_swaps_url_for_moss_link(monkeypatch, ws_root: Path):
    _configured_env(monkeypatch)
    fake = _FakeS3()
    monkeypatch.setattr("tools.moss_upload._s3_client", lambda settings: fake)
    monkeypatch.setattr("tools.moss_upload.datetime", _FrozenDateTime)
    monkeypatch.setattr(
        "tools.moss_upload.uuid.uuid4",
        lambda: uuid.UUID("12345678-1234-5678-1234-567812345678"),
    )

    output = ws_root / "output"
    output.mkdir()
    report = output / "report.pdf"
    report.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr("artifacts.detector.OUTPUT_DIR", output)

    artifacts = [{
        "name": "report.pdf",
        "path": "report.pdf",
        "url": "/output/report.pdf",
        "mime": "application/pdf",
        "size": report.stat().st_size,
    }]
    out = attach_moss_urls(artifacts)
    expected = "https://moss.lesso.com/rag-uat-dev/quan/2026/08/21/12345678/report.pdf"
    assert out[0]["url"] == expected
    assert out[0]["mossUrl"] == expected
    assert len(fake.puts) == 1
    assert fake.puts[0]["Bucket"] == "rag-uat-dev"
    assert fake.puts[0]["Key"] == "quan/2026/08/21/12345678/report.pdf"


def test_configured_uploads_html_and_svg_independently(monkeypatch, ws_root: Path):
    """MOSS receives both diagram deliverables, not just the first artifact."""
    _configured_env(monkeypatch)
    fake = _FakeS3()
    monkeypatch.setattr("tools.moss_upload._s3_client", lambda settings: fake)
    monkeypatch.setattr("tools.moss_upload.datetime", _FrozenDateTime)
    monkeypatch.setattr(
        "tools.moss_upload.uuid.uuid4",
        lambda: uuid.UUID("12345678-1234-5678-1234-567812345678"),
    )

    output = ws_root / "output"
    output.mkdir()
    html = output / "diagram.html"
    svg = output / "diagram.svg"
    html.write_text("<html><svg></svg></html>", encoding="utf-8")
    svg.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>", encoding="utf-8")
    monkeypatch.setattr("artifacts.detector.OUTPUT_DIR", output)

    artifacts = [
        {
            "name": html.name,
            "path": html.name,
            "url": f"/output/{html.name}",
            "mime": "text/html",
            "size": html.stat().st_size,
        },
        {
            "name": svg.name,
            "path": svg.name,
            "url": f"/output/{svg.name}",
            "mime": "image/svg+xml",
            "size": svg.stat().st_size,
        },
    ]
    out = attach_moss_urls(artifacts)

    assert [item["name"] for item in out] == ["diagram.html", "diagram.svg"]
    assert all(item["mossUrl"].startswith("https://moss.lesso.com/") for item in out)
    assert len(fake.puts) == 2
    assert {item["Key"].split("/")[-1] for item in fake.puts} == {"diagram.html", "diagram.svg"}


def test_upload_failure_keeps_local_url(monkeypatch, ws_root: Path):
    _configured_env(monkeypatch)

    class _Boom:
        def put_object(self, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr("tools.moss_upload._s3_client", lambda settings: _Boom())
    output = ws_root / "output"
    output.mkdir()
    (output / "a.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr("artifacts.detector.OUTPUT_DIR", output)

    artifacts = [{
        "name": "a.pdf",
        "path": "a.pdf",
        "url": "/output/a.pdf",
        "mime": "application/pdf",
        "size": 4,
    }]
    out = attach_moss_urls(artifacts)
    assert out[0]["url"] == "/output/a.pdf"
    assert "mossUrl" not in out[0]


def test_reject_directory(ws_root: Path):
    (ws_root / "output").mkdir()
    with pytest.raises(ValueError, match="普通文件"):
        resolve_upload_path(ws_root / "output", allowed_subdirs=("output",), workspace_root=ws_root)


def test_reject_traversal(ws_root: Path):
    (ws_root / "output").mkdir()
    secret = ws_root.parent / f"secret-{uuid.uuid4().hex[:8]}.txt"
    secret.write_text("nope", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="工作区"):
            resolve_upload_path(secret, allowed_subdirs=("output",), workspace_root=ws_root)
    finally:
        secret.unlink(missing_ok=True)


def test_reject_disallowed_subdir(ws_root: Path):
    (ws_root / "output").mkdir()
    skills = ws_root / "skills"
    skills.mkdir()
    target = skills / "SKILL.md"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="只允许"):
        resolve_upload_path(
            "skills/SKILL.md",
            allowed_subdirs=("output", "tmp", "uploads"),
            workspace_root=ws_root,
        )


def test_upload_local_file_unconfigured_skips(monkeypatch, ws_root: Path):
    monkeypatch.setenv("MOSS_ACCESS_KEY", "")
    monkeypatch.setenv("MOSS_SECRET_KEY", "")
    output = ws_root / "output"
    output.mkdir()
    target = output / "a.txt"
    target.write_text("hi", encoding="utf-8")
    result = upload_local_file(target, workspace_root=ws_root)
    assert result.ok is False
    assert result.skipped is True


def test_build_public_url_encodes_object_key():
    settings = MossSettings(
        endpoint="https://moss.lesso.com",
        region="fs",
        bucket="rag-uat-dev",
        access_key="ak",
        secret_key="sk",
        key_prefix="quan",
    )
    url = build_public_url("quan/2026/08/21/abcd1234/季度 汇报.pdf", settings=settings)
    assert url.startswith("https://moss.lesso.com/rag-uat-dev/")
    assert " " not in url
    assert "%20" in url or "%E5" in url


def test_build_object_key_uses_prefix_and_safe_name(monkeypatch):
    monkeypatch.setattr("tools.moss_upload.datetime", _FrozenDateTime)
    monkeypatch.setattr(
        "tools.moss_upload.uuid.uuid4",
        lambda: uuid.UUID("12345678-1234-5678-1234-567812345678"),
    )
    settings = moss_settings({
        "MOSS_ENDPOINT": "https://moss.lesso.com",
        "MOSS_BUCKET": "rag-uat-dev",
        "MOSS_ACCESS_KEY": "ak",
        "MOSS_SECRET_KEY": "sk",
        "MOSS_KEY_PREFIX": "quan",
    })
    key = build_object_key("a/b.pdf", settings=settings)
    assert key == "quan/2026/08/21/12345678/b.pdf"


def test_bucket_falls_back_to_upload_bucket():
    settings = moss_settings({
        "MOSS_ENDPOINT": "https://moss.lesso.com",
        "MOSS_UPLOAD_BUCKET": "rag-uat-dev",
        "MOSS_ACCESS_KEY": "ak",
        "MOSS_SECRET_KEY": "sk",
    })
    assert settings.bucket == "rag-uat-dev"
    assert settings.key_prefix == "quan"
    assert settings.configured is True


def test_skill_md_frontmatter_parses():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    meta = _frontmatter(text)
    assert meta.get("name") == "upload-to-moss"
    description = meta.get("description", "")
    assert "MOSS" in description or "moss" in description.lower()
    assert "execute" in meta.get("allowed-tools", "")


def test_skill_script_help_runs():
    script = SKILL / "scripts" / "upload.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "--file" in proc.stdout
