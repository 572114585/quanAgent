"""multimodal helpers + web chat content assembly."""

from __future__ import annotations

import base64
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_core.multimodal import (
    build_user_content,
    file_to_data_url,
    is_image_mime,
    to_image_part,
)


# 1x1 PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class MultimodalHelpersTests(unittest.TestCase):
    def test_file_to_data_url(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.png"
            p.write_bytes(_PNG)
            url = file_to_data_url(p)
            self.assertTrue(url.startswith("data:image/png;base64,"))
            part = to_image_part(p)
            self.assertEqual(part["type"], "image_url")
            self.assertEqual(part["image_url"]["url"], url)

    def test_build_user_content_with_images(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.png"
            p.write_bytes(_PNG)
            content = build_user_content("hello", [p])
            self.assertIsInstance(content, list)
            self.assertEqual(content[-1]["type"], "text")
            self.assertEqual(content[-1]["text"], "hello")
            self.assertEqual(content[0]["type"], "image_url")

    def test_is_image_mime(self) -> None:
        self.assertTrue(is_image_mime("image/png"))
        self.assertFalse(is_image_mime("application/pdf"))


class WebChatContentTests(unittest.TestCase):
    def test_vision_on_builds_image_parts(self) -> None:
        import tempfile

        import agent_core.config as cfg
        from entrypoints.web import Attachment, _build_chat_user_content

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            uploads = ws / "uploads"
            uploads.mkdir()
            img = uploads / "ref.png"
            img.write_bytes(_PNG)

            att = Attachment(
                id="att-1",
                name="ref.png",
                mime="image/png",
                size=len(_PNG),
                remoteUrl="/uploads/ref.png",
            )
            old = cfg.WORKSPACE_ROOT
            cfg.WORKSPACE_ROOT = ws
            try:
                with patch("agent_core.llm.llm_supports_vision", return_value=True):
                    content = _build_chat_user_content("做成 3D", [att])
            finally:
                cfg.WORKSPACE_ROOT = old

            self.assertIsInstance(content, list)
            types = [p["type"] for p in content]
            self.assertIn("image_url", types)
            self.assertEqual(types[-1], "text")
            self.assertIn("做成 3D", content[-1]["text"])

    def test_vision_off_stays_text(self) -> None:
        from entrypoints.web import Attachment, _build_chat_user_content

        att = Attachment(
            id="att-2",
            name="ref.png",
            mime="image/png",
            size=10,
            remoteUrl="/uploads/ref.png",
        )
        with patch("agent_core.llm.llm_supports_vision", return_value=False):
            content = _build_chat_user_content("hi", [att])
        self.assertIsInstance(content, str)
        self.assertIn("不支持图片视觉", content)


if __name__ == "__main__":
    unittest.main()
