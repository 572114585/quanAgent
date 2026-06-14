"""WeCom 渠道入口：python run_wecom.py"""
import logging

from channels.wecom.client import build_ws_client
from channels.wecom.handlers import register


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ws = build_ws_client()
    register(ws)
    # SDK 内部管理事件循环，阻塞运行
    ws.run()


if __name__ == "__main__":
    main()
