"""
核心桥接层：流式版本（REPLACE 语义）。

WeCom 智能机器人长连接的流式协议是「in-place replacement」：
每次 reply_stream 都会用本次 content **整体替换** 上一帧的内容。
所以必须自己维护 accumulated 全文，每帧把累积文本发出去。
"""
import logging
import time
from typing import Any

from aibot import generate_req_id

from agent_runtime import agent

logger = logging.getLogger(__name__)

# 节流阈值
MIN_CHARS = 20        # 累积新增 ≥N 个字符再发
MIN_INTERVAL = 0.4    # 距离上次发送 ≥M 秒


def _extract_text(chunk: Any) -> str:
    """从 AIMessageChunk 抠出纯文本（兼容 str / list[dict]）。"""
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


async def stream_agent_reply(
    ws_client,
    frame: dict,
    user_text: str,
    thread_id: str,
) -> None:
    """
    - frame:  SDK 收到的原始帧（reply_stream 内部用它取 req_id 做串行）
    - user_text: 用户原始消息
    - thread_id: LangGraph checkpointer 的 thread_id
    """
    stream_id = generate_req_id("stream")
    config = {
        "configurable": {"thread_id": thread_id},
        # "callbacks": [langfuse_handler],  # 需要时打开
    }

    # 累积文本（REPLACE 语义下，每帧都发这个）
    accumulated = "💭 思考中…"
    last_sent = accumulated              # 上一帧实际发出去的内容
    last_send_ts = time.monotonic()

    # 第一帧：占位
    await ws_client.reply_stream(frame, stream_id, last_sent, finish=False)

    try:
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": user_text}]},
            config=config,
            version="v2",
        ):
            ev = event["event"]

            if ev == "on_tool_start":
                tool_name = event.get("name") or "tool"
                accumulated += f"\n\n🔧 调用工具 `{tool_name}` …\n\n"
                # 工具切换：立即推送一次（让用户看到进度）
                if accumulated != last_sent:
                    await ws_client.reply_stream(
                        frame, stream_id, accumulated, finish=False
                    )
                    last_sent = accumulated
                    last_send_ts = time.monotonic()
                continue

            if ev == "on_chat_model_stream":
                chunk = (event.get("data") or {}).get("chunk")
                text = _extract_text(chunk)
                if not text:
                    continue
                accumulated += text

                now = time.monotonic()
                grew = len(accumulated) - len(last_sent)
                if grew >= MIN_CHARS or (now - last_send_ts) >= MIN_INTERVAL:
                    await ws_client.reply_stream(
                        frame, stream_id, accumulated, finish=False
                    )
                    last_sent = accumulated
                    last_send_ts = now
                continue

        # 收尾：finish=True 关闭流
        # 如果最后没新字符累积了，发一帧等价于"无新增"的 finish=True 让服务端落锤
        if not accumulated or accumulated == "💭 思考中…":
            await ws_client.reply_stream(
                frame, stream_id, "（没有可回复的内容）", finish=True
            )
        else:
            await ws_client.reply_stream(
                frame, stream_id, accumulated, finish=True
            )

    except Exception as e:
        logger.exception("stream_agent_reply failed")
        try:
            await ws_client.reply_stream(
                frame, stream_id, f"\n\n⚠️ 出错了: {e}", finish=True
            )
        except Exception:
            logger.exception("finalize failed")
