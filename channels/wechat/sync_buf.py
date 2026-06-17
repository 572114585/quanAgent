"""sync_buf 游标持久化：长轮询的同步点"""
from pathlib import Path

DATA_DIR = Path.home() / ".wechat-agent"
SYNC_BUF_PATH = DATA_DIR / "sync_buf.txt"


def load_sync_buf() -> str:
    """读取上次保存的 sync_buf"""
    try:
        return SYNC_BUF_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def save_sync_buf(buf: str) -> None:
    """持久化 sync_buf"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SYNC_BUF_PATH.write_text(buf, encoding="utf-8")
