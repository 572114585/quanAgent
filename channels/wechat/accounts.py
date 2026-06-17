"""账号凭证管理：保存/加载扫码登录后的 bot_token"""
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".wechat-agent"
ACCOUNTS_DIR = DATA_DIR / "accounts"


@dataclass
class AccountData:
    bot_token: str
    account_id: str
    base_url: str
    user_id: str
    created_at: str


def _account_path(account_id: str) -> Path:
    # 防路径遍历
    safe_id = account_id.replace("/", "").replace("\\", "").replace("..", "")
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    return ACCOUNTS_DIR / f"{safe_id}.json"


def save_account(data: AccountData) -> None:
    path = _account_path(data.account_id)
    path.write_text(json.dumps(asdict(data), ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Account saved: %s", data.account_id)


def load_account(account_id: str) -> AccountData | None:
    path = _account_path(account_id)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AccountData(**raw)
    except Exception as e:
        logger.warning("Failed to load account %s: %s", account_id, e)
        return None


def load_latest_account() -> AccountData | None:
    """加载最近修改的账号"""
    if not ACCOUNTS_DIR.exists():
        return None
    files = sorted(ACCOUNTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        return None
    account_id = files[0].stem
    return load_account(account_id)


def load_all_accounts() -> list[AccountData]:
    """加载所有已保存的账号，按修改时间倒序"""
    if not ACCOUNTS_DIR.exists():
        return []
    files = sorted(ACCOUNTS_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    accounts = []
    for f in files:
        acc = load_account(f.stem)
        if acc:
            accounts.append(acc)
    return accounts


def delete_account(account_id: str) -> bool:
    """删除指定账号"""
    path = _account_path(account_id)
    if path.exists():
        path.unlink()
        logger.info("Account deleted: %s", account_id)
        return True
    return False
