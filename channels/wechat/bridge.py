"""
核心桥接层：ilink 消息 → agent → ilink 回复（非流式）。

ilink Bot API 不支持流式输出（无 REPLACE 语义）：
- 每次 sendmessage 都会产生一条独立的新消息
- 没有像 WeCom 那样的 reply_stream in-place 更新机制
- message_state 的 GENERATING/FINISH 只是状态标记，不是流式替换

因此采用非流式策略：
1. 收到用户消息 → 启动"正在输入"状态
2. 同步调用 agent，收集完整回复
3. 一次性发送最终结果
4. 如果回复过长，分段发送（sendTextChunked）
"""
import logging
from typing import Any

from agent_runtime import agent

from .sender import Sender
from .types import WeixinMessage, MessageItemType
from .media import download_image, download_file
from .commands import route_command
from .session import SessionStore

logger = logging.getLogger(__name__)

# 单条消息最大字符数（ilink API 限制约 4000 字符）
MAX_CHARS_PER_MSG = 4000


def _extract_text_from_chunk(chunk: Any) -> str:
    """从 AIMessageChunk 抠出纯文本"""
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            p.get("text", "")
            for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        return "".join(parts)
    return ""


def build_user_content(msg: WeixinMessage) -> str | list[dict]:
    """
    把 ilink 消息转成 LLM user content（同步版本，不含图片下载）。
    图片下载在 async_build_user_content 中处理。
    """
    text_parts: list[str] = []
    has_image = False

    for item in msg.item_list:
        if item.type == MessageItemType.TEXT:
            if item.text_item and item.text_item.text:
                text_parts.append(item.text_item.text)
        elif item.type == MessageItemType.VOICE:
            if item.voice_item and item.voice_item.text:
                text_parts.append(item.voice_item.text)
        elif item.type == MessageItemType.IMAGE:
            has_image = True
        elif item.type == MessageItemType.FILE:
            text_parts.append(f"[用户发送了文件: {item.file_item.file_name}]" if item.file_item else "[文件]")

    if not has_image:
        return "\n".join(text_parts)

    return "\n".join(text_parts) if text_parts else "[图片]"


async def async_build_user_content(msg: WeixinMessage) -> str | list[dict]:
    """
    把 ilink 消息转成 LLM user content（异步版本，含图片下载）。
    纯文本 → str；含图片 → list[dict]（多模态）
    """
    text_parts: list[str] = []
    image_parts: list[dict] = []

    for item in msg.item_list:
        if item.type == MessageItemType.TEXT:
            if item.text_item and item.text_item.text:
                text_parts.append(item.text_item.text)
        elif item.type == MessageItemType.VOICE:
            if item.voice_item and item.voice_item.text:
                text_parts.append(item.voice_item.text)
        elif item.type == MessageItemType.IMAGE:
            data_uri = await download_image(item)
            if data_uri:
                image_parts.append({
                    "type": "image_url",
                    "image_url": {"url": data_uri},
                })
            else:
                text_parts.append("[图片]")
        elif item.type == MessageItemType.FILE:
            local_path = await download_file(item)
            if local_path and item.file_item:
                text_parts.append(f"[用户发送了文件: {item.file_item.file_name}]")
            else:
                text_parts.append("[文件]")

    if image_parts:
        image_parts.append({
            "type": "text",
            "text": "\n".join(text_parts) or "请描述这张图",
        })
        return image_parts

    return "\n".join(text_parts)


async def _invoke_agent(user_content: str | list[dict], thread_id: str) -> str:
    """
    非流式调用 agent，收集完整回复文本。
    使用 astream_events 收集所有文本片段，但不推送中间结果。
    """
    accumulated = ""
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 100,
    }

    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": user_content}]},
        config=config,
        version="v2",
    ):
        ev = event["event"]

        if ev == "on_tool_start":
            tool_name = event.get("name") or "tool"
            accumulated += f"\n\n🔧 调用工具 `{tool_name}` …\n\n"
            continue

        if ev == "on_chat_model_stream":
            chunk = (event.get("data") or {}).get("chunk")
            text = _extract_text_from_chunk(chunk)
            if text:
                accumulated += text
            continue

    return accumulated


async def handle_message(
    msg: WeixinMessage,
    sender: Sender,
    sessions: SessionStore,
) -> None:
    """
    处理一条微信消息（非流式）：
    1. 检查是否为命令
    2. 构造 user content
    3. 启动"正在输入"状态
    4. 调用 agent，等待完整回复
    5. 一次性发送结果（过长则分段）
    """
    user_id = msg.from_user_id
    context_token = msg.context_token

    # 构造 user content（异步，含图片下载）
    user_content = await async_build_user_content(msg)
    if not user_content:
        return

    # 命令路由（仅对纯文本消息）
    if isinstance(user_content, str):
        cmd_result = route_command(user_content, sender, sessions, user_id, context_token)
        if cmd_result and cmd_result.handled:
            await sender.send_text(user_id, context_token, cmd_result.response)
            return

    # 获取 thread_id
    thread_id = sessions.get_or_create(user_id)

    # 启动"正在输入"
    stop_typing = sender.start_typing(user_id, context_token)

    try:
        # 非流式调用 agent
        result = await _invoke_agent(user_content, thread_id)

        if not result:
            await sender.send_text(user_id, context_token, "（没有可回复的内容）")
            return

        # 分段发送（ilink 单条消息约 4000 字符限制）
        await sender.send_text_chunked(user_id, context_token, result)

    except Exception as e:
        logger.exception("handle_message failed")
        try:
            await sender.send_text(user_id, context_token, f"⚠️ 出错了: {e}")
        except Exception:
            logger.exception("error notification failed")
    finally:
        stop_typing()
