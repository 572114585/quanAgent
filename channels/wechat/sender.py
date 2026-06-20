"""消息发送器：文本/图片/文件/视频消息 + "正在输入"状态"""
import asyncio
import base64
import logging
import time
from pathlib import Path
from typing import Callable

from .api import WeChatApi
from .media import upload_file, is_image_file, is_video_file
from .types import MessageType, MessageState, MessageItemType, TypingStatus, UploadMediaType

logger = logging.getLogger(__name__)

TYPING_KEEPALIVE = 5.0  # "正在输入" keepalive 间隔（秒）
TICKET_TTL = 24 * 3600  # typing_ticket 缓存 24 小时
MAX_CHARS_PER_MSG = 4000  # ilink 单条消息最大字符数


class Sender:
    def __init__(self, api: WeChatApi, bot_account_id: str):
        self._api = api
        self._bot_account_id = bot_account_id
        self._client_counter = 0
        self._ticket_cache: dict[str, tuple[str, float]] = {}

    def _generate_client_id(self) -> str:
        self._client_counter += 1
        return f"wcc-{int(time.time() * 1000)}-{self._client_counter}"

    async def _get_typing_ticket(self, user_id: str, context_token: str = "") -> str:
        """获取 typing_ticket（带缓存）"""
        cached = self._ticket_cache.get(user_id)
        if cached and time.monotonic() - cached[1] < TICKET_TTL:
            return cached[0]
        try:
            resp = await self._api.get_config(user_id, context_token or None)
            if resp.get("ret") == 0 and resp.get("typing_ticket"):
                ticket = resp["typing_ticket"]
                self._ticket_cache[user_id] = (ticket, time.monotonic())
                return ticket
        except Exception as e:
            logger.warning("getConfig failed: %s", e)
        return ""

    def start_typing(self, user_id: str, context_token: str = "") -> Callable[[], None]:
        """
        启动"正在输入"状态，返回 stop 函数。
        调用 stop() 取消状态。
        """
        cancelled = False

        async def _loop():
            ticket = await self._get_typing_ticket(user_id, context_token)
            if not ticket or cancelled:
                return
            try:
                await self._api.send_typing(user_id, ticket, TypingStatus.TYPING)
            except Exception as e:
                logger.debug("sendTyping start failed: %s", e)
                return

            while not cancelled:
                await asyncio.sleep(TYPING_KEEPALIVE)
                if cancelled:
                    break
                try:
                    await self._api.send_typing(user_id, ticket, TypingStatus.TYPING)
                except Exception:
                    break

            # 发送 CANCEL 告知微信输入结束
            try:
                await self._api.send_typing(user_id, ticket, TypingStatus.CANCEL)
            except Exception:
                pass

        task = asyncio.create_task(_loop())

        def stop():
            nonlocal cancelled
            cancelled = True
            task.cancel()

        return stop

    async def send_text(self, to_user_id: str, context_token: str, text: str) -> None:
        """发送文本消息"""
        client_id = self._generate_client_id()
        msg = {
            "from_user_id": self._bot_account_id,
            "to_user_id": to_user_id,
            "client_id": client_id,
            "message_type": MessageType.BOT,
            "message_state": MessageState.FINISH,
            "context_token": context_token,
            "item_list": [
                {
                    "type": MessageItemType.TEXT,
                    "text_item": {"text": text},
                }
            ],
        }
        logger.info("Sending text to %s (%d chars)", to_user_id, len(text))
        await self._api.send_message(msg)
        logger.info("Text sent to %s", to_user_id)

    async def send_text_chunked(
        self, to_user_id: str, context_token: str, text: str, max_length: int = MAX_CHARS_PER_MSG
    ) -> int:
        """
        自动分段发送长文本。返回发送的消息条数。
        ilink API 单条消息约 4000 字符限制，超长文本需拆分。
        """
        if len(text) <= max_length:
            await self.send_text(to_user_id, context_token, text)
            return 1

        chunks: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break
            # 在 max_length 附近找换行符作为分割点
            split_at = remaining.rfind("\n", 0, max_length)
            if split_at <= max_length // 2:
                # 没有合适的换行符，硬切
                split_at = max_length
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip("\n")

        for i, chunk in enumerate(chunks):
            logger.info("Sending chunk %d/%d to %s (%d chars)", i + 1, len(chunks), to_user_id, len(chunk))
            await self.send_text(to_user_id, context_token, chunk)

        return len(chunks)

    async def send_file(self, to_user_id: str, context_token: str, file_path: str) -> None:
        """发送图片或文件消息"""
        path = Path(file_path.replace("~", str(Path.home())))
        if not path.exists():
            await self.send_text(to_user_id, context_token, f"文件不存在: {path}")
            return

        try:
            media = await upload_file(self._api, to_user_id, str(path))
        except Exception as e:
            logger.error("Failed to upload file: %s", e)
            await self.send_text(to_user_id, context_token, f"发送文件失败: {e}")
            return

        client_id = self._generate_client_id()
        # aes_key_hex → base64（与原项目一致：Buffer.from(hexString).toString("base64")）
        aes_key_base64 = base64.b64encode(media["aes_key_hex"].encode()).decode("ascii")

        if media["media_type"] == "image":
            item = {
                "type": MessageItemType.IMAGE,
                "image_item": {
                    "media": {
                        "encrypt_query_param": media["encrypt_query_param"],
                        "aes_key": aes_key_base64,
                        "encrypt_type": 1,
                    },
                    "mid_size": media["file_size"],
                },
            }
        elif media["media_type"] == "video":
            item = {
                "type": MessageItemType.VIDEO,
                "video_item": {
                    "media": {
                        "encrypt_query_param": media["encrypt_query_param"],
                        "aes_key": aes_key_base64,
                        "encrypt_type": 1,
                    },
                },
            }
        else:
            item = {
                "type": MessageItemType.FILE,
                "file_item": {
                    "media": {
                        "encrypt_query_param": media["encrypt_query_param"],
                        "aes_key": aes_key_base64,
                        "encrypt_type": 1,
                    },
                    "file_name": media["file_name"],
                    "len": str(media["raw_size"]),
                },
            }

        msg = {
            "from_user_id": self._bot_account_id,
            "to_user_id": to_user_id,
            "client_id": client_id,
            "message_type": MessageType.BOT,
            "message_state": MessageState.FINISH,
            "context_token": context_token,
            "item_list": [item],
        }
        logger.info("Sending file to %s: %s", to_user_id, media["file_name"])
        await self._api.send_message(msg)
        logger.info("File sent to %s: %s", to_user_id, media["file_name"])

    async def send_media(self, to_user_id: str, context_token: str, file_path: str) -> None:
        """智能发送媒体文件：根据文件扩展名自动选择发送方式

        send_file 已能根据上传返回的 media_type 正确处理图片/视频/文件，
        无需按扩展名分流。
        """
        await self.send_file(to_user_id, context_token, file_path)
