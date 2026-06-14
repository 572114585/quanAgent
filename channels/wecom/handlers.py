"""
WeCom 渠道的事件注册：把 SDK 的事件名映射到 bridge 里的处理函数。
"""
import logging

from aibot import WSClient

from .bridge import stream_agent_reply

logger = logging.getLogger(__name__)


def _thread_id_for(chat_id: str | None) -> str:
    # LangGraph checkpointer 的 thread_id；同一会话复用，保证多轮记忆
    return f"wecom:{chat_id or 'default'}"


def _extract_chat_id(frame: dict) -> str | None:
    body = frame.get("body") or {}
    return (
        body.get("chat_id")
        or body.get("chatid")
        or (body.get("from") or {}).get("chat_id")
    )


def register(ws_client: WSClient) -> None:
    @ws_client.on("authenticated")
    def _on_auth():
        logger.info("WeCom 认证成功")

    @ws_client.on("ready")
    def _on_ready():
        logger.info("WeCom 长连接已就绪，可以收消息了")

    @ws_client.on("message.text")
    async def _on_text(frame):
        body = frame.get("body") or {}
        user_text = (body.get("text") or {}).get("content", "")
        if not user_text:
            return
        chat_id = _extract_chat_id(frame)
        logger.info("收到文本 chat=%s text=%r", chat_id, user_text)
        await stream_agent_reply(
            ws_client, frame, user_text, _thread_id_for(chat_id)
        )

    @ws_client.on("event.enter_chat")
    async def _on_enter(frame):
        try:
            await ws_client.reply_welcome(
                frame,
                {
                    "msgtype": "text",
                    "text": {"content": "你好，我是小权 ✨ 有什么可以帮你的？"},
                },
            )
        except Exception:
            logger.exception("reply_welcome failed")
