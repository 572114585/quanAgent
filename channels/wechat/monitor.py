"""长轮询消息监听器"""
import asyncio
import logging
from collections import OrderedDict
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
        # 用 OrderedDict 维护插入顺序，淘汰最旧的一半时才是真正的 FIFO，
        # 避免 set 无序导致"随机淘汰"→ 同一条消息被重复处理。
        self._recent_ids: "OrderedDict[int, None]" = OrderedDict()
        # 持有 pending task 引用，防止被 GC 提前回收（Python 文档明确警告）
        self._pending: set[asyncio.Task] = set()

    def stop(self):
        self._stopped = True

    def _remember_message_id(self, msg_id: int) -> None:
        """记录已处理消息 id，超限时按 FIFO 淘汰最旧的一半。"""
        self._recent_ids.pop(msg_id, None)
        self._recent_ids[msg_id] = None
        if len(self._recent_ids) > MAX_MSG_IDS:
            # 真正的 FIFO 淘汰：popitem(last=False) 取最旧的
            remove_n = MAX_MSG_IDS // 2
            for _ in range(remove_n):
                self._recent_ids.popitem(last=False)

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

                # 处理消息：per-message try/except，单条解析失败不丢弃同批其它消息
                for raw_msg in resp.get("msgs") or []:
                    try:
                        msg = parse_message(raw_msg)
                    except Exception:
                        logger.exception("parse_message failed, skipping one msg: %r", raw_msg)
                        continue

                    # 去重
                    if msg.message_id and msg.message_id in self._recent_ids:
                        continue
                    if msg.message_id:
                        self._remember_message_id(msg.message_id)

                    # 只处理用户消息（不处理自己发的 BOT 消息）
                    if msg.message_type != MessageType.USER:
                        continue

                    # fire-and-forget：不阻塞轮询循环
                    task = asyncio.create_task(self._safe_on_message(msg))
                    self._pending.add(task)
                    task.add_done_callback(self._pending.discard)

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
