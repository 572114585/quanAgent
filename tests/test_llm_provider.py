"""LLM provider factory + vision capability flags."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from agent_core.llm import (
    create_llm,
    get_llm_model_name,
    get_llm_provider,
    llm_supports_vision,
)


class SiliconflowProviderTests(unittest.TestCase):
    def test_siliconflow_defaults(self) -> None:
        env = {
            "LLM_PROVIDER": "siliconflow",
            "SILICONFLOW_API_KEY": "sk-test",
        }
        # Ensure defaults kick in
        clear_keys = [
            "SILICONFLOW_MODEL",
            "SILICONFLOW_BASE_URL",
            "LLM_ENABLE_THINKING",
            "LLM_THINKING_BUDGET",
            "LLM_TEMPERATURE",
            "LLM_MAX_TOKENS",
            "LLM_TIMEOUT",
            "LLM_SUPPORTS_VISION",
        ]
        with patch.dict(os.environ, env, clear=False):
            for k in clear_keys:
                os.environ.pop(k, None)
            self.assertEqual(get_llm_provider(), "siliconflow")
            self.assertEqual(get_llm_model_name(), "Qwen/Qwen3.6-35B-A3B")
            self.assertTrue(llm_supports_vision())

            client = create_llm()
            model = getattr(client, "model_name", None) or getattr(client, "model", None)
            self.assertEqual(model, "Qwen/Qwen3.6-35B-A3B")
            base = getattr(client, "openai_api_base", None) or str(
                getattr(client, "base_url", "")
            )
            self.assertIn("siliconflow.cn", str(base))

    def test_vision_override_false_on_siliconflow(self) -> None:
        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "siliconflow", "LLM_SUPPORTS_VISION": "false"},
            clear=False,
        ):
            self.assertFalse(llm_supports_vision())

    def test_agnes_vision_default_false(self) -> None:
        with patch.dict(os.environ, {"LLM_PROVIDER": "agnes"}, clear=False):
            os.environ.pop("LLM_SUPPORTS_VISION", None)
            self.assertFalse(llm_supports_vision())

    def test_enable_thinking_extra_body(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "siliconflow",
                "SILICONFLOW_API_KEY": "sk-test",
                "LLM_ENABLE_THINKING": "true",
                "LLM_THINKING_BUDGET": "2048",
            },
            clear=False,
        ):
            client = create_llm()
            extra = getattr(client, "extra_body", None) or {}
            self.assertEqual(extra.get("enable_thinking"), True)
            self.assertEqual(extra.get("thinking_budget"), 2048)

    def test_siliconflow_token_alias(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "siliconflow",
                "SILICONFLOW_API_KEY": "",
                "SILICONFLOW_TOKEN": "sk-from-token",
            },
            clear=False,
        ):
            os.environ.pop("SILICONFLOW_API_KEY", None)
            client = create_llm()
            # langchain stores secret; just ensure construction succeeds with token alias
            self.assertIsNotNone(client)

    def test_missing_key_raises(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "siliconflow",
                "SILICONFLOW_API_KEY": "",
                "SILICONFLOW_TOKEN": "",
            },
            clear=False,
        ):
            os.environ.pop("SILICONFLOW_API_KEY", None)
            os.environ.pop("SILICONFLOW_TOKEN", None)
            with self.assertRaises(ValueError) as ctx:
                create_llm()
            self.assertIn("SILICONFLOW_API_KEY", str(ctx.exception))

    def test_volcengine_defaults_and_alias(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "ark",
                "VOLCENGINE_API_KEY": "ark-test-key",
                "VOLCENGINE_MODEL": "",
                "VOLCENGINE_BASE_URL": "",
            },
            clear=False,
        ):
            os.environ.pop("VOLCENGINE_MODEL", None)
            os.environ.pop("VOLCENGINE_BASE_URL", None)
            self.assertEqual(get_llm_provider(), "volcengine")
            self.assertEqual(get_llm_model_name(), "doubao-seed-2.1-turbo")
            client = create_llm()
            model = getattr(client, "model_name", None) or getattr(client, "model", None)
            self.assertEqual(model, "doubao-seed-2.1-turbo")
            base = getattr(client, "openai_api_base", None) or str(
                getattr(client, "base_url", "")
            )
            self.assertIn("ark.cn-beijing.volces.com", str(base))
            self.assertIn("/api/plan/v3", str(base))


if __name__ == "__main__":
    unittest.main()
