"""LLM 工厂。

根据 .env 中的 LLM_PROVIDER 创建 OpenAI 兼容的 ChatOpenAI 实例
（agnes / deepseek / sensenova / siliconflow / volcengine）。
模块级 `llm` 单例保留，供直接复用。
"""
from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# siliconflow 默认支持 vision；其余 provider 默认否（可被 LLM_SUPPORTS_VISION 覆盖）
_DEFAULT_VISION_PROVIDERS = frozenset({"siliconflow"})

# A global ``LLM_SUPPORTS_VISION=true`` is convenient when switching between
# vision-capable models, but it must not make a known text-only model receive
# ``image_url`` parts.  Such requests are rejected by the OpenAI-compatible
# APIs before the agent can return a useful response.  Keep this deliberately
# narrow: model names for actual vision variants (for example ``*-vl``) are
# not listed here and may still be enabled explicitly.
_TEXT_ONLY_MODEL_NAMES = frozenset(
    {
        "deepseek-v4-flash",
        "mimo-v2.5-pro",
    }
)


def get_llm_provider() -> str:
    raw = os.getenv("LLM_PROVIDER", "agnes").strip().lower() or "agnes"
    # 别名：ark / doubao / 火山方舟 → volcengine
    if raw in {"ark", "doubao", "huoshan", "火山", "火山方舟"}:
        return "volcengine"
    if raw in {"xiaomi", "xiaomimimo", "mimo"}:
        return "mimo"
    return raw


def _provider_specs() -> dict[str, dict[str, str]]:
    """各 provider 的 env 键与默认值（model / base_url / api_key）。"""
    return {
        "agnes": {
            "model_env": "AGNES_MODEL",
            "model_default": "agnes-2.0-flash",
            "base_url_env": "AGNES_BASE_URL",
            "base_url_default": "https://apihub.agnes-ai.com/v1/chat/completions",
            "api_key_env": "AGNES_API_KEY",
        },
        "deepseek": {
            "model_env": "DEEPSEEK_MODEL",
            "model_default": "deepseek-chat",
            "base_url_env": "DEEPSEEK_BASE_URL",
            "base_url_default": "https://api.deepseek.com",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
        "sensenova": {
            "model_env": "SENSENOVA_MODEL",
            "model_default": "sensenova-6.7-flash-lite",
            "base_url_env": "SENSENOVA_BASE_URL",
            "base_url_default": "https://token.sensenova.cn/v1",
            "api_key_env": "SENSENOVA_API_KEY",
        },
        "siliconflow": {
            "model_env": "SILICONFLOW_MODEL",
            "model_default": "Qwen/Qwen3.6-35B-A3B",
            "base_url_env": "SILICONFLOW_BASE_URL",
            "base_url_default": "https://api.siliconflow.cn/v1",
            "api_key_env": "SILICONFLOW_API_KEY",
            "api_key_aliases": "SILICONFLOW_TOKEN",
        },
        # 火山方舟（豆包）：OpenAI 兼容；本账号实测可用 /api/plan/v3
        # 文档: https://www.volcengine.com/docs/82379/
        "volcengine": {
            "model_env": "VOLCENGINE_MODEL",
            "model_default": "doubao-seed-2.1-turbo",
            "base_url_env": "VOLCENGINE_BASE_URL",
            "base_url_default": "https://ark.cn-beijing.volces.com/api/plan/v3",
            "api_key_env": "VOLCENGINE_API_KEY",
            "api_key_aliases": "ARK_API_KEY,VOLCENGINE_TOKEN,ARK_TOKEN",
        },
        "mimo": {
            "model_env": "MIMO_MODEL",
            "model_default": "mimo-v2.5-pro",
            "base_url_env": "MIMO_BASE_URL",
            "base_url_default": "https://token-plan-cn.xiaomimimo.com/v1",
            "api_key_env": "MIMO_API_KEY",
            "api_key_aliases": "MIMO_TOKEN",
        },
    }


def _resolve_api_key(spec: dict[str, str]) -> str:
    """读取 API Key / Token；支持 api_key_aliases（逗号分隔的备用 env 名）。"""
    primary = (os.getenv(spec["api_key_env"]) or "").strip()
    if primary:
        return primary
    aliases = (spec.get("api_key_aliases") or "").strip()
    for name in aliases.split(","):
        name = name.strip()
        if not name:
            continue
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def get_llm_model_name(provider: str | None = None) -> str:
    provider = (provider or get_llm_provider()).lower()
    specs = _provider_specs()
    spec = specs.get(provider) or specs["agnes"]
    return os.getenv(spec["model_env"], spec["model_default"])


def _parse_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    text = raw.strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def llm_supports_vision() -> bool:
    """当前配置是否应按多模态 vision 处理图片。

    已知文本模型始终返回 False；其余优先读 LLM_SUPPORTS_VISION，未设置时
    siliconflow 默认 True、其余 False。
    """
    model = get_llm_model_name().strip().lower()
    if model in _TEXT_ONLY_MODEL_NAMES:
        return False

    override = _parse_bool(os.getenv("LLM_SUPPORTS_VISION"))
    if override is not None:
        return override
    return get_llm_provider() in _DEFAULT_VISION_PROVIDERS


def _common_chat_kwargs(*, provider: str) -> dict[str, Any]:
    """各 provider 共用的可选 ChatOpenAI 参数（空 env 则不传）。"""
    kwargs: dict[str, Any] = {}
    temp = os.getenv("LLM_TEMPERATURE", "").strip()
    if temp:
        kwargs["temperature"] = float(temp)
    max_tokens = os.getenv("LLM_MAX_TOKENS", "").strip()
    if max_tokens:
        kwargs["max_tokens"] = int(max_tokens)
    timeout = os.getenv("LLM_TIMEOUT", "").strip()
    if timeout:
        kwargs["timeout"] = float(timeout)

    # 429 / TPM：OpenAI 兼容 SDK 会对 RateLimitError 做指数退避重试。
    # 硅基流动 TPM 窗口通常约 1 分钟，默认多试几次；见
    # https://api-docs.siliconflow.cn/docs/userguide/faqs/rate-limit-and-upgradation
    retries_raw = os.getenv("LLM_MAX_RETRIES", "").strip()
    if retries_raw:
        kwargs["max_retries"] = max(0, int(retries_raw))
    else:
        kwargs["max_retries"] = 3

    extra_body: dict[str, Any] = {}
    enable_thinking = _parse_bool(os.getenv("LLM_ENABLE_THINKING"))
    if enable_thinking is True:
        extra_body["enable_thinking"] = True
        budget = os.getenv("LLM_THINKING_BUDGET", "").strip()
        if budget:
            extra_body["thinking_budget"] = int(budget)
    elif enable_thinking is False or enable_thinking is None:
        # 显式关闭：对硅基/Qwen 等混合推理模型有意义（省 TPM）
        extra_body["enable_thinking"] = False

    if extra_body:
        kwargs["extra_body"] = extra_body
    return kwargs


def create_llm(provider: str | None = None):
    """根据 .env 中的 LLM_PROVIDER 创建对应的 LLM 实例。"""
    provider = (provider or get_llm_provider()).strip().lower()
    specs = _provider_specs()
    if provider not in specs:
        provider = "agnes"
    spec = specs[provider]

    api_key = _resolve_api_key(spec)
    if not api_key:
        names = [spec["api_key_env"]]
        aliases = (spec.get("api_key_aliases") or "").strip()
        if aliases:
            names.extend(n.strip() for n in aliases.split(",") if n.strip())
        raise ValueError(
            f"LLM_PROVIDER={provider} 但未配置 API Key/Token。"
            f"请在 .env 中设置 {' 或 '.join(names)}。"
        )

    kwargs: dict[str, Any] = {
        "model": os.getenv(spec["model_env"], spec["model_default"]),
        "base_url": os.getenv(spec["base_url_env"], spec["base_url_default"]),
        "api_key": api_key,
    }
    kwargs.update(_common_chat_kwargs(provider=provider))
    return ChatOpenAI(**kwargs)


class _LazyLLM:
    """Construct the configured model at first use instead of module import."""

    _instance: ChatOpenAI | None = None

    def _get(self) -> ChatOpenAI:
        if self._instance is None:
            self._instance = create_llm()
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._get(), name)


llm = _LazyLLM()
