"""view_image tool path checks and vision gating."""

from __future__ import annotations

import base64
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command

from tools.view_image import _resolve_workspace_image, view_image


_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class ResolvePathTests(unittest.TestCase):
    def test_allows_uploads_tmp_output(self) -> None:
        import tempfile

        import agent_core.config as cfg

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            for top in ("uploads", "tmp", "output"):
                (ws / top).mkdir()
            img = ws / "tmp" / "a.png"
            img.write_bytes(_PNG)
            old = cfg.WORKSPACE_ROOT
            cfg.WORKSPACE_ROOT = ws
            try:
                resolved = _resolve_workspace_image("tmp/a.png")
                self.assertEqual(resolved, img.resolve())
            finally:
                cfg.WORKSPACE_ROOT = old

    def test_rejects_outside_allowed_tops(self) -> None:
        import tempfile

        import agent_core.config as cfg

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            skills = ws / "skills"
            skills.mkdir()
            img = skills / "x.png"
            img.write_bytes(_PNG)
            old = cfg.WORKSPACE_ROOT
            cfg.WORKSPACE_ROOT = ws
            try:
                with self.assertRaises(ValueError):
                    _resolve_workspace_image("skills/x.png")
            finally:
                cfg.WORKSPACE_ROOT = old


class ViewImageToolTests(unittest.TestCase):
    def test_vision_off_returns_error_toolmessage(self) -> None:
        with patch("agent_core.llm.llm_supports_vision", return_value=False):
            result = view_image.invoke(
                {
                    "name": "view_image",
                    "type": "tool_call",
                    "id": "call-1",
                    "args": {"path": "tmp/a.png"},
                }
            )
        self.assertIsInstance(result, Command)
        msgs = result.update["messages"]
        self.assertEqual(len(msgs), 1)
        self.assertIsInstance(msgs[0], ToolMessage)
        self.assertIn("不支持图片视觉", msgs[0].content)

    def test_vision_on_injects_human_image(self) -> None:
        import tempfile

        import agent_core.config as cfg

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "output").mkdir()
            img = ws / "output" / "shot.png"
            img.write_bytes(_PNG)
            old = cfg.WORKSPACE_ROOT
            cfg.WORKSPACE_ROOT = ws
            try:
                with patch("agent_core.llm.llm_supports_vision", return_value=True):
                    result = view_image.invoke(
                        {
                            "name": "view_image",
                            "type": "tool_call",
                            "id": "call-2",
                            "args": {"path": "output/shot.png"},
                        }
                    )
            finally:
                cfg.WORKSPACE_ROOT = old

        self.assertIsInstance(result, Command)
        msgs = result.update["messages"]
        self.assertEqual(len(msgs), 2)
        self.assertIsInstance(msgs[0], ToolMessage)
        self.assertIsInstance(msgs[1], HumanMessage)
        human = msgs[1].content
        self.assertIsInstance(human, list)
        self.assertEqual(human[1]["type"], "image_url")
        self.assertTrue(human[1]["image_url"]["url"].startswith("data:image/png"))


if __name__ == "__main__":
    unittest.main()
