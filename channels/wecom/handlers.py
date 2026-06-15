"""
WeCom 渠道的事件注册：把 SDK 的事件名映射到 bridge 里的处理函数。
"""
import logging

from aibot import WSClient

from .bridge import build_user_content, stream_agent_reply

logger = logging.getLogger(__name__)


def _thread_id_for(chat_id: str | None) -> str:
    # LangGraph checkpointer 的 thread_id；同一会话复用，保证多轮记忆
    return f"wecom:{chat_id or 'default'}"


def _extract_chat_id(frame: dict) -> str | None:
    body = frame.get("body") or {}
    frm = body.get("from") or {}
    return (
        body.get("chat_id")
        or body.get("chatid")
        or frm.get("chat_id")
        or frm.get("userid")     # 单聊：from.userid
    )


async def _dispatch(ws_client: WSClient, frame: dict) -> None:
    """
    通用分发：解析 body → 构造 LLM content → 调 stream_agent_reply。
    text / image / mixed 全部走这里。
    """
    body = frame.get("body") or {}
    chat_id = _extract_chat_id(frame)
    msgtype = body.get("msgtype", "text")
    logger.info("收到 %s 消息 chat=%s", msgtype, chat_id)

    try:
        user_content = await build_user_content(ws_client, body)
    except Exception as e:
        logger.exception("build_user_content failed")
        return

    if isinstance(user_content, str) and not user_content:
        return  # 空文本直接忽略

    await stream_agent_reply(
        ws_client, frame, user_content, _thread_id_for(chat_id)
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
        await _dispatch(ws_client, frame)

    @ws_client.on("message.image")
    async def _on_image(frame):
        await _dispatch(ws_client, frame)

    @ws_client.on("message.mixed")
    async def _on_mixed(frame):
        await _dispatch(ws_client, frame)

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
