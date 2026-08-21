"""Focused coverage for QuanAgent's PPT Master adaptation layer."""
from __future__ import annotations

import base64
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from artifacts import detector
from sandbox.path_rewriter import _discover_skill_scripts
from tools.review_ppt_images import review_ppt_images


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_ppt_master_snapshot_has_attribution_and_host_contract() -> None:
    root = Path("workspace/skills/ppt-master")
    assert (root / "LICENSE").is_file()
    assert (root / "SPONSORS.md").is_file()
    assert (root / "SPONSORS_CN.md").is_file()
    host = (root / "references/quanagent-host.md").read_text(encoding="utf-8")
    assert "workspace/tmp/ppt-master-projects" in host
    assert "review_ppt_images" in host
    assert "Agent Plan" in host


def test_nested_ppt_scripts_are_discovered() -> None:
    found = _discover_skill_scripts(Path("workspace"))
    assert "skills/ppt-master/scripts/confirm_ui/server.py" in found
    assert "skills/ppt-master/scripts/svg_editor/server.py" in found


def test_review_ppt_images_builds_isolated_qwen_request(tmp_path: Path, monkeypatch) -> None:
    import agent_core.config as cfg

    (tmp_path / "output").mkdir()
    image = tmp_path / "output" / "slide.png"
    image.write_bytes(_PNG)
    old_root = cfg.WORKSPACE_ROOT
    cfg.WORKSPACE_ROOT = tmp_path
    client = MagicMock()
    client.invoke.return_value = SimpleNamespace(content="Clear hierarchy; enlarge labels.")
    try:
        with patch("tools.review_ppt_images._vision_client", return_value=client):
            result = review_ppt_images.invoke(
                {"paths": ["output/slide.png"], "task": "check readability", "detail": "high"}
            )
    finally:
        cfg.WORKSPACE_ROOT = old_root

    assert result == "Clear hierarchy; enlarge labels."
    messages = client.invoke.call_args.args[0]
    assert messages[0].content[-1]["type"] == "text"
    assert "check readability" in messages[0].content[-1]["text"]


@pytest.mark.parametrize("count", [0, 9])
def test_review_ppt_images_enforces_image_count(count: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 8"):
        review_ppt_images.func(["output/a.png"] * count, "review")


def test_image_generation_is_hard_locked_to_volcengine() -> None:
    script_dir = Path("workspace/skills/ppt-master/scripts").resolve()
    import sys

    sys.path.insert(0, str(script_dir))
    try:
        import image_gen

        old_backend = os.environ.get("IMAGE_BACKEND")
        old_allowed = os.environ.get("PPT_ALLOWED_IMAGE_BACKENDS")
        os.environ["IMAGE_BACKEND"] = "openai"
        os.environ["PPT_ALLOWED_IMAGE_BACKENDS"] = "openai"
        try:
            with pytest.raises(SystemExit) as error:
                image_gen._resolve_backend()
        finally:
            if old_backend is None:
                os.environ.pop("IMAGE_BACKEND", None)
            else:
                os.environ["IMAGE_BACKEND"] = old_backend
            if old_allowed is None:
                os.environ.pop("PPT_ALLOWED_IMAGE_BACKENDS", None)
            else:
                os.environ["PPT_ALLOWED_IMAGE_BACKENDS"] = old_allowed
        assert error.value.code == 1
    finally:
        sys.path.remove(str(script_dir))


def test_agent_plan_seedream_request_uses_expected_endpoint_and_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import sys

    script_dir = Path("workspace/skills/ppt-master/scripts").resolve()
    sys.path.insert(0, str(script_dir))
    try:
        from image_backends import backend_volcengine

        response = MagicMock(status_code=200)
        response.json.return_value = {"data": [{"url": "https://example.test/image.png"}]}
        monkeypatch.setenv("VOLCENGINE_OUTPUT_FORMAT", "png")
        with patch.object(backend_volcengine.requests, "post", return_value=response) as post:
            with patch.object(backend_volcengine, "download_image", return_value="saved.png"):
                result = backend_volcengine._generate_image(
                    api_key="not-a-real-key",
                    prompt="presentation visual",
                    aspect_ratio="16:9",
                    image_size="2K",
                    output_dir=str(tmp_path),
                )
    finally:
        sys.path.remove(str(script_dir))

    assert result == "saved.png"
    assert post.call_args.args[0] == "https://ark.cn-beijing.volces.com/api/plan/v3/images/generations"
    payload = post.call_args.kwargs["json"]
    assert payload["model"] == "doubao-seedream-5.0-lite"
    assert payload["size"] == "2K"
    assert payload["output_format"] == "png"
    assert payload["response_format"] == "url"
    assert payload["watermark"] is False
    assert payload["sequential_image_generation"] == "disabled"


def test_pptx_is_detected_as_downloadable_artifact(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setattr(detector, "OUTPUT_DIR", output)
    before = detector.snapshot_output_dir()
    (output / "deck.pptx").write_bytes(b"PK\x03\x04")
    artifacts = detector.detect_new_artifacts(before)
    assert artifacts == [
        {
            "name": "deck.pptx",
            "path": "deck.pptx",
            "url": "/output/deck.pptx",
            "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "size": 4,
        }
    ]
