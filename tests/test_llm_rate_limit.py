"""Tests for LLM rate-limit error formatting and vision compression."""

from __future__ import annotations

import base64
import io
import os
import unittest
from unittest.mock import patch

from agent_core.llm_errors import format_llm_stream_error
from agent_core.multimodal import bytes_to_data_url, compress_image_bytes


def _big_png(size: int = 2000) -> bytes:
    from PIL import Image

    img = Image.new("RGB", (size, size), (30, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class RateLimitErrorFormatTests(unittest.TestCase):
    def test_tpm_message(self) -> None:
        class RateLimitError(Exception):
            pass

        msg = format_llm_stream_error(
            RateLimitError(
                "Error code: 429 - {'code': 50602, 'message': "
                "'Request was rejected due to rate limiting. Details: TPM limit reached.'}"
            )
        )
        self.assertIn("速率限制", msg)
        self.assertIn("60 秒", msg)
        self.assertIn("会话仍保留", msg)

    def test_other_error_passthrough(self) -> None:
        msg = format_llm_stream_error(ValueError("boom"))
        self.assertIn("ValueError", msg)
        self.assertIn("boom", msg)


class VisionCompressTests(unittest.TestCase):
    def test_compresses_large_png(self) -> None:
        raw = _big_png(1600)
        with patch.dict(
            os.environ,
            {"LLM_VISION_MAX_EDGE": "640", "LLM_VISION_JPEG_QUALITY": "70"},
            clear=False,
        ):
            out, mime = compress_image_bytes(raw, source_mime="image/png")
        self.assertEqual(mime, "image/jpeg")
        self.assertLess(len(out), len(raw))
        url = bytes_to_data_url(raw, "image/png")
        self.assertTrue(url.startswith("data:image/jpeg;base64,"))
        # decoded payload should be smaller than original png
        b64 = url.split(",", 1)[1]
        self.assertLess(len(base64.b64decode(b64)), len(raw))


if __name__ == "__main__":
    unittest.main()
