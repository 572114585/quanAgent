"""WeCom 渠道入口：python run_wecom.py"""
import logging
import sys

from channels.wecom.client import build_ws_client
from channels.wecom.handlers import register

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ws = build_ws_client()
    register(ws)
    # 兜底异常 + 优雅退出：容器化部署被 SIGTERM 时能干净断开 WS
    try:
        # SDK 内部管理事件循环，阻塞运行
        ws.run()
    except KeyboardInterrupt:
        logger.info("收到 KeyboardInterrupt，正在关闭")
    except Exception:
        logger.exception("WeCom WS 运行异常，退出")
        sys.exit(1)
    finally:
        # 尽量优雅关闭 WS（SDK 可能叫 close/stop/aclose，用 getattr 兜容）
        closer = getattr(ws, "aclose", None) or getattr(ws, "close", None) or getattr(ws, "stop", None)
        if callable(closer):
            try:
                result = closer()
                # 若是协程，无法在这里 await（可能已在事件循环外），交给 SDK 内部处理
                import inspect
                if inspect.iscoroutine(result):
                    result.close()
            except Exception:
                logger.exception("关闭 WS 时异常")


if __name__ == "__main__":
    main()
