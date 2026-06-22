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

多媒体消息处理流程：
1. 遍历 item_list，按类型分发到 process_media_item
2. 图片/视频缩略图 → base64 data URI → LLM 多模态输入
3. 语音 → ASR 转文字 → LLM 文本输入
4. 文件 → 内容提取 → LLM 文本输入
5. 处理失败时降级为文本占位符

产物自动投递：
- agent 产出最终文件落 workspace/output/（由 SYSTEM_PROMPT 约定）
- handle_message 通过目录快照 diff 检测新增/变更的文件
- 自动通过 sender.send_file 投递给用户
"""
import logging
from pathlib import Path
from typing import Any

from agent_runtime import agent

from .sender import Sender
from .types import WeixinMessage, MessageItemType
from .media import process_media_item
from .media_processor import ProcessedMedia
from .commands import route_command
from .session import SessionStore

logger = logging.getLogger(__name__)

# 单条消息最大字符数（ilink API 限制约 4000 字符）
MAX_CHARS_PER_MSG = 4000

# agent 产出目录（快照 diff 目标）
_WORKSPACE = Path("workspace")
_OUTPUT_DIR = _WORKSPACE / "output"


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


def _snapshot(d: Path) -> dict[Path, tuple[float, int]]:
    """扫描目录，返回 {文件路径: (mtime, size)} 快照。

    用于方案 A：在 agent 调用前后各拍一次快照，diff 出本轮新增/变更的产物。
    """
    if not d.exists():
        return {}
    return {
        p: (p.stat().st_mtime, p.stat().st_size)
        for p in d.rglob("*")
        if p.is_file()
    }


def _diff_artifacts(
    before: dict[Path, tuple[float, int]],
    after: dict[Path, tuple[float, int]],
) -> list[Path]:
    """对比两次快照，返回本轮新增或被改写的文件路径（按 mtime 升序）。"""
    changed = [
        p
        for p, sig in after.items()
        if p not in before or before[p] != sig
    ]
    # 新文件优先（mtime 更晚的），稳定的排序便于日志观察
    changed.sort(key=lambda p: after[p][0])
    return changed


def build_user_content(msg: WeixinMessage) -> str | list[dict]:
    """
    把 ilink 消息转成 LLM user content（同步版本，不含媒体下载）。
    仅提取文本内容，媒体下载在 async_build_user_content 中处理。
    """
    text_parts: list[str] = []

    for item in msg.item_list:
        if item.type == MessageItemType.TEXT:
            if item.text_item and item.text_item.text:
                text_parts.append(item.text_item.text)
        elif item.type == MessageItemType.VOICE:
            if item.voice_item and item.voice_item.text:
                text_parts.append(item.voice_item.text)
        elif item.type == MessageItemType.IMAGE:
            text_parts.append("[图片]")
        elif item.type == MessageItemType.FILE:
            name = item.file_item.file_name if item.file_item else "文件"
            text_parts.append(f"[文件: {name}]")
        elif item.type == MessageItemType.VIDEO:
            text_parts.append("[视频]")

    return "\n".join(text_parts)


async def async_build_user_content(msg: WeixinMessage) -> str | list[dict]:
    """
    把 ilink 消息转成 LLM user content（异步版本，含完整媒体处理）。

    处理流程：
    1. 遍历所有消息项
    2. 对每种媒体类型调用 process_media_item（下载+处理）
    3. 汇总结果：
       - 纯文本 → str
       - 含图片/视频缩略图 → list[dict]（多模态）
    """
    text_parts: list[str] = []
    image_parts: list[dict] = []  # 图片/视频缩略图的 data URI
    user_id = msg.from_user_id

    for item in msg.item_list:
        # 纯文本：直接提取
        if item.type == MessageItemType.TEXT:
            if item.text_item and item.text_item.text:
                text_parts.append(item.text_item.text)
            continue

        # 媒体类型：统一走 process_media_item
        try:
            result = await process_media_item(item, user_id)
        except Exception as e:
            logger.exception("process_media_item failed for type=%s: %s", item.type, e)
            result = ProcessedMedia(
                media_type="unknown",
                error=f"媒体处理异常: {e}",
            )

        # 处理结果
        if result.error:
            # 处理失败：降级为文本占位
            text_parts.append(f"[媒体处理失败: {result.error}]")
            continue

        # 成功：收集内容
        if result.text_content:
            text_parts.append(result.text_content)

        if result.image_data_uris:
            for uri in result.image_data_uris:
                image_parts.append({
                    "type": "image_url",
                    "image_url": {"url": uri},
                })

    # 构造最终内容
    if image_parts:
        # 有图片/缩略图 → 多模态格式
        image_parts.append({
            "type": "text",
            "text": "\n".join(text_parts) or "请分析以上内容",
        })
        return image_parts

    # 纯文本
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
    2. 构造 user content（含多媒体处理）
    3. 启动"正在输入"状态
    4. 调用 agent，等待完整回复
    5. 一次性发送结果（过长则分段）
    """
    user_id = msg.from_user_id
    context_token = msg.context_token

    # 构造 user content（异步，含媒体下载+处理）
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
        # 调用前拍 output/ 快照（方案 A：按请求维度配对，不跨请求）
        before = _snapshot(_OUTPUT_DIR)

        # 非流式调用 agent
        result = await _invoke_agent(user_content, thread_id)

        if not result:
            await sender.send_text(user_id, context_token, "（没有可回复的内容）")
            return

        # 分段发送文本（ilink 单条消息约 4000 字符限制）
        await sender.send_text_chunked(user_id, context_token, result)

        # diff 出本轮新增/变更的产物，逐个投递
        artifacts = _diff_artifacts(before, _snapshot(_OUTPUT_DIR))
        if artifacts:
            logger.info("Detected %d artifact(s) in output/", len(artifacts))
        # 发送顺序：图片（PNG/JPG 等）优先，HTML 等其他文件在后。
        # 原因：图片在微信里即时内联显示，让用户立刻看到设计效果；HTML 走文件
        # 下载，是供用户后续在浏览器里交互的源文件。先看图、再拿源文件，体验更顺。
        # 同级内仍按 mtime 升序（先改的先发），保持稳定可观察。
        _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
        artifacts.sort(key=lambda p: (0 if p.suffix.lower() in _IMAGE_EXTS else 1, p.stat().st_mtime))
        for path in artifacts:
            try:
                await sender.send_file(user_id, context_token, str(path))
            except Exception:
                logger.exception("send artifact failed: %s", path)

    except Exception as e:
        logger.exception("handle_message failed")
        try:
            await sender.send_text(user_id, context_token, f"⚠️ 出错了: {e}")
        except Exception:
            logger.exception("error notification failed")
    finally:
        stop_typing()
