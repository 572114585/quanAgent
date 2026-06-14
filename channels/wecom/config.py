"""企业微信渠道配置：仅从 .env 读。"""
import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class WeComConfig:
    bot_id: str
    secret: str
    # 必须与 aibot.ws.DEFAULT_WS_URL 保持一致（wss://openws.work.weixin.qq.com，无路径）
    # 留 None 时由 SDK 内部使用默认地址，避免我们写错。
    ws_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> "WeComConfig":
        bot_id = os.environ.get("WECHAT_BOT_ID")
        secret = os.environ.get("WECHAT_BOT_SECRET")
        if not bot_id or not secret:
            raise RuntimeError(
                "缺少 WECHAT_BOT_ID / WECHAT_BOT_SECRET，请在 .env 中配置"
            )
        return cls(bot_id=bot_id, secret=secret)
