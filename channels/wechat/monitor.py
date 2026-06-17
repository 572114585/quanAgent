"""长轮询消息监听器"""
import asyncio
import logging
from typing import Callable, Awaitable

from .api import WeChatApi
from .sync_buf import load_sync_buf, save_sync_buf
from .types import WeixinMessage, parse_message, MessageType

logger = logging.getLogger(__name__)

SESSION_EXPIRED_ERRCODE = -14
SESSION_EXPIRED_PAUSE = 3600  # 1 小时
BACKOFF_THRESHOLD = 3
BACKOFF_LONG = 30.0
BACKOFF_SHORT = 3.0
MAX_MSG_IDS = 1000


class Monitor:
    """长轮询消息监听器"""

    def __init__(
        self,
        api: WeChatApi,
        on_message: Callable[[WeixinMessage], Awaitable[None]],
        on_session_expired: Callable[[], None] | None = None,
    ):
        self._api = api
        self._on_message = on_message
        self._on_session_expired = on_session_expired
        self._stopped = False
        self._recent_ids: set[int] = set()

    def stop(self):
        self._stopped = True

    async def run(self) -> None:
        """主循环：长轮询 + 消息分发"""
        consecutive_failures = 0

        while not self._stopped:
            try:
                buf = load_sync_buf()
                resp = await self._api.get_updates(buf or None)

                # 会话过期
                if resp.get("ret") == SESSION_EXPIRED_ERRCODE:
                    logger.warning("Session expired, pausing for 1 hour")
                    if self._on_session_expired:
                        self._on_session_expired()
                    await asyncio.sleep(SESSION_EXPIRED_PAUSE)
                    consecutive_failures = 0
                    continue

                # 保存游标
                new_buf = resp.get("get_updates_buf", "")
                if new_buf:
                    save_sync_buf(new_buf)

                # 处理消息
                for raw_msg in resp.get("msgs") or []:
                    msg = parse_message(raw_msg)

                    # 去重
                    if msg.message_id and msg.message_id in self._recent_ids:
                        continue
                    if msg.message_id:
                        self._recent_ids.add(msg.message_id)
                        if len(self._recent_ids) > MAX_MSG_IDS:
                            # 淘汰最旧的一半
                            to_remove = list(self._recent_ids)[: MAX_MSG_IDS // 2]
                            for mid in to_remove:
                                self._recent_ids.discard(mid)

                    # 只处理用户消息（不处理自己发的 BOT 消息）
                    if msg.message_type != MessageType.USER:
                        continue

                    # fire-and-forget：不阻塞轮询循环
                    asyncio.create_task(self._safe_on_message(msg))

                consecutive_failures = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._stopped:
                    break
                consecutive_failures += 1
                logger.error(
                    "Monitor error: %s: %s (failures=%d)",
                    type(e).__name__, e, consecutive_failures,
                )
                backoff = BACKOFF_LONG if consecutive_failures >= BACKOFF_THRESHOLD else BACKOFF_SHORT
                logger.info("Backing off %.0fs", backoff)
                await asyncio.sleep(backoff)

        logger.info("Monitor stopped")

    async def _safe_on_message(self, msg: WeixinMessage) -> None:
        """安全调用 on_message 回调"""
        try:
            await self._on_message(msg)
        except Exception as e:
            logger.error("Error processing message %s: %s", msg.message_id, e)
