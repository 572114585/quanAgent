"""加载 workspace 内图片供 vision 模型查看。

OpenAI 兼容接口通常要求图片出现在 user 角色消息中；因此本工具通过
Command 注入 ToolMessage（文字确认）+ HumanMessage（image_url），
而不是只把 data URL 塞进 ToolMessage 字符串。
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command

# 允许查看的相对 workspace 顶层目录
_ALLOWED_TOP = frozenset({"uploads", "tmp", "output"})


def _resolve_workspace_image(path: str) -> Path:
    from agent_core.config import WORKSPACE_ROOT

    raw = (path or "").strip().replace("\\", "/")
    if not raw or "\x00" in raw:
        raise ValueError("path 为空或非法")

    # 沙箱虚拟路径 /uploads /tmp /output
    if raw.startswith("/"):
        raw = raw.lstrip("/")

    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = WORKSPACE_ROOT / raw

    try:
        resolved = candidate.resolve()
        ws = WORKSPACE_ROOT.resolve()
        rel = resolved.relative_to(ws)
    except (OSError, ValueError) as e:
        raise ValueError(f"path 必须位于 workspace 内: {path}") from e

    parts = rel.parts
    if not parts or parts[0] not in _ALLOWED_TOP:
        raise ValueError(
            f"path 仅允许 uploads/、tmp/、output/ 下的图片，拒绝: {path}"
        )

    if not resolved.is_file():
        raise FileNotFoundError(f"图片不存在: {path}")

    suffix = resolved.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        raise ValueError(f"不支持的图片类型: {suffix or '(无扩展名)'}")

    return resolved


@tool
def view_image(
    path: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """加载一张 workspace 内的图片，供当前视觉模型直接查看。

    在 object-sculptor 等需要对比参考图 / render_html 截图 / compare 对比图时调用。
    路径须位于 uploads/、tmp/ 或 output/ 下（如 tmp/sculpt/run/review/blockout-comparison.png）。

    参数：
    - path: 相对 workspace 的图片路径，或 /uploads/xxx.png 形式

    返回：工具确认 + 注入多模态图片消息（模型下一轮即可看见该图）。
    """
    from agent_core.llm import get_llm_model_name, get_llm_provider, llm_supports_vision
    from agent_core.multimodal import to_image_part

    if not llm_supports_vision():
        msg = (
            "当前配置不支持图片视觉（llm_supports_vision=false）。"
            "请设置 LLM_PROVIDER=siliconflow（默认 Qwen/Qwen3.6-35B-A3B）"
            "或显式 LLM_SUPPORTS_VISION=true，并使用支持 image_url 的模型。"
            f" 当前 provider={get_llm_provider()}, model={get_llm_model_name()}。"
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(content=msg, tool_call_id=tool_call_id, name="view_image"),
                ]
            }
        )

    try:
        resolved = _resolve_workspace_image(path)
        part = to_image_part(resolved)
    except (ValueError, FileNotFoundError, OSError) as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"view_image 失败: {e}",
                        tool_call_id=tool_call_id,
                        name="view_image",
                    ),
                ]
            }
        )

    rel = path.strip().replace("\\", "/")
    confirm = f"已加载图片供视觉检查: {rel}（{resolved.name}）"
    human_content: list[dict[str, Any]] = [
        {"type": "text", "text": f"[view_image] {rel}"},
        part,
    ]
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=confirm,
                    tool_call_id=tool_call_id,
                    name="view_image",
                ),
                HumanMessage(content=human_content),
            ]
        }
    )
