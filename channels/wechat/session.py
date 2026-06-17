"""会话管理：微信用户 → LangGraph thread_id 映射"""
import json
import logging
from pathlib import Path

from agent_runtime import new_thread_id

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".wechat-agent"


class SessionStore:
    """微信用户 ID → LangGraph thread_id 的持久化映射

    key 格式: {account_id}:{user_id}，多账号下隔离会话。
    """

    def __init__(self, account_id: str = ""):
        self._account_id = account_id
        self._path = DATA_DIR / "sessions.json"
        self._sessions: dict[str, str] = self._load()

    def _key(self, user_id: str) -> str:
        if self._account_id:
            return f"{self._account_id}:{user_id}"
        return user_id

    def _load(self) -> dict[str, str]:
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._sessions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_or_create(self, user_id: str) -> str:
        """获取已有 thread_id 或创建新的"""
        key = self._key(user_id)
        if key not in self._sessions:
            self._sessions[key] = new_thread_id("wechat")
            self._save()
            logger.info("New session for %s: %s", key, self._sessions[key])
        return self._sessions[key]

    def reset(self, user_id: str) -> str:
        """重置用户会话，返回新 thread_id"""
        key = self._key(user_id)
        self._sessions[key] = new_thread_id("wechat")
        self._save()
        logger.info("Session reset for %s: %s", key, self._sessions[key])
        return self._sessions[key]
