"""单例 WSClient 工厂。"""
from aibot import WSClient, WSClientOptions

from .config import WeComConfig


def build_ws_client(cfg: WeComConfig | None = None) -> WSClient:
    cfg = cfg or WeComConfig.from_env()
    # ws_url 留 None：让 SDK 用 aibot.ws.DEFAULT_WS_URL，避免拼错路径。
    options = WSClientOptions(
        bot_id=cfg.bot_id,
        secret=cfg.secret,
        ws_url=cfg.ws_url,
    )
    return WSClient(options)
