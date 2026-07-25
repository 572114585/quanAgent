"""LLM / 上游 API 错误文案规范化（尤其 429 TPM）。"""
from __future__ import annotations


def format_llm_stream_error(exc: BaseException) -> str:
    """把异常转成给前端的可读中文；429 提示等待后继续，会话未销毁。"""
    name = type(exc).__name__
    text = str(exc) or name
    lowered = text.lower()

    is_rate = (
        name in {"RateLimitError", "ResourceExhausted"}
        or "rate limit" in lowered
        or "rate_limit" in lowered
        or "tpm" in lowered
        or "rpm" in lowered
        or "429" in text
        or "50602" in text
    )
    if is_rate:
        return (
            "上游模型触发速率限制（429 / TPM：每分钟 token 额度用尽）。"
            "本轮已结束，会话仍保留——请等待约 60 秒后再发一条消息继续。"
            "建议：关闭 LLM_ENABLE_THINKING、减少同轮 view_image 次数、"
            "或提高账户用量级别。"
            "说明见 https://api-docs.siliconflow.cn/docs/userguide/faqs/rate-limit-and-upgradation"
        )
    return f"{name}: {text}"
