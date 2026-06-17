"""微信端命令路由：/help、/clear、/status 等"""
import logging
from dataclasses import dataclass

from .sender import Sender
from .session import SessionStore

logger = logging.getLogger(__name__)

HELP_TEXT = """📋 可用命令：
/help - 显示帮助
/clear - 清除当前会话，开始新对话
/status - 查看当前会话状态
/reset - 完全重置（包括会话等设置）

直接发消息即可与 AI 对话，无需加命令前缀。"""


@dataclass
class CommandResult:
    handled: bool  # 是否已处理（不再转发给 agent）
    response: str = ""  # 回复内容


def route_command(
    text: str,
    sender: Sender,
    sessions: SessionStore,
    user_id: str,
    context_token: str,
) -> CommandResult | None:
    """
    路由微信端命令。返回 CommandResult 表示已处理，返回 None 表示不是命令。
    """
    text = text.strip()
    if not text.startswith("/"):
        return None

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/help":
        return CommandResult(handled=True, response=HELP_TEXT)

    if cmd == "/clear":
        new_thread = sessions.reset(user_id)
        return CommandResult(handled=True, response="✅ 会话已清除，开始新对话")

    if cmd == "/status":
        thread_id = sessions.get_or_create(user_id)
        return CommandResult(handled=True, response=f"📊 会话ID: {thread_id}")

    if cmd == "/reset":
        new_thread = sessions.reset(user_id)
        return CommandResult(handled=True, response="✅ 已完全重置")

    # 未知命令
    return CommandResult(
        handled=True,
        response=f"❓ 未知命令: {cmd}\n\n{HELP_TEXT}",
    )
