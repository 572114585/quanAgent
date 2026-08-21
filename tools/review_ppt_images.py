"""Dedicated, read-only visual review for PPT Master assets.

This tool intentionally does not use the primary agent model.  It keeps PPT
image QA on the SiliconFlow Qwen3-VL endpoint and never injects image bytes
into the main conversation history.
"""
from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from agent_core.config import (
    PPT_VISION_MAX_TOKENS,
    PPT_VISION_MODEL,
    PPT_VISION_TIMEOUT,
    WORKSPACE_ROOT,
)
from agent_core.multimodal import build_user_content
from tools.view_image import _resolve_workspace_image

_MAX_IMAGES = 8


def _vision_client(timeout_seconds: float | None = None) -> ChatOpenAI:
    """Build the isolated Qwen3-VL client without affecting global LLM config."""
    import os

    api_key = os.getenv("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PPT image review requires SILICONFLOW_API_KEY.")
    return ChatOpenAI(
        model=PPT_VISION_MODEL,
        base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
        api_key=api_key,
        timeout=timeout_seconds if timeout_seconds is not None else PPT_VISION_TIMEOUT,
        max_tokens=PPT_VISION_MAX_TOKENS,
        max_retries=0,
    )


def _response_text(response: object) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        ).strip()
    return str(content).strip()


@tool
def review_ppt_images(
    paths: list[str],
    task: str,
    detail: Literal["low", "high"] = "high",
    timeout_seconds: float | None = None,
) -> str:
    """Review 1–8 PPT images with SiliconFlow Qwen3-VL.

    Every path must be an existing image beneath workspace/uploads, tmp, or
    output. Use it for visual QA and revision guidance; it never writes files.
    """
    if not isinstance(paths, list) or not 1 <= len(paths) <= _MAX_IMAGES:
        raise ValueError(f"paths must contain between 1 and {_MAX_IMAGES} images.")
    if not isinstance(task, str) or not task.strip():
        raise ValueError("task must be a non-empty review instruction.")

    resolved = [_resolve_workspace_image(path) for path in paths]
    prompt = (
        "You are the visual QA reviewer for a presentation workflow. "
        f"Review level: {detail}. Task: {task.strip()}\n\n"
        "Assess composition, legibility, slide suitability, visual defects, "
        "and concrete revisions. State observations separately from suggestions."
    )
    content = build_user_content(prompt, resolved, workspace_root=WORKSPACE_ROOT)
    try:
        response = _vision_client(timeout_seconds).invoke([HumanMessage(content=content)])
    except Exception as exc:  # provider errors should be actionable to the agent
        raise RuntimeError(f"SiliconFlow Qwen3-VL review failed: {exc}") from exc
    text = _response_text(response)
    if not text:
        raise RuntimeError("SiliconFlow Qwen3-VL returned an empty review.")
    return text
