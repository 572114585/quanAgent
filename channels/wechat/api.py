"""ilink Bot API 封装：所有与 ilinkai.weixin.qq.com 的 HTTP 交互"""
import asyncio
import logging
from typing import Any

import httpx

from .config import DEFAULT_BASE_URL

logger = logging.getLogger(__name__)


def _generate_uin() -> str:
    """生成随机 base64 标识"""
    import base64, os
    return base64.b64encode(os.urandom(4)).decode("ascii")


class WeChatApi:
    """ilink Bot API 客户端"""

    MIN_SEND_INTERVAL = 2.5  # 每用户最小发送间隔（秒）

    def __init__(self, token: str, base_url: str = DEFAULT_BASE_URL):
        # 安全校验 base_url
        base_url = self._validate_base_url(base_url)
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.uin = _generate_uin()
        self._next_send_time: dict[str, float] = {}

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        """只允许 weixin.qq.com / wechat.com 域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            allowed = ("weixin.qq.com", "wechat.com")
            hostname = parsed.hostname or ""
            is_allowed = any(
                hostname == h or hostname.endswith("." + h) for h in allowed
            )
            if parsed.scheme != "https" or not is_allowed:
                logger.warning("Untrusted baseUrl, using default: %s", base_url)
                return DEFAULT_BASE_URL
        except Exception:
            logger.warning("Invalid baseUrl, using default: %s", base_url)
            return DEFAULT_BASE_URL
        return base_url

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": self.uin,
        }

    async def _request(
        self,
        path: str,
        body: Any = None,
        timeout_ms: int = 15_000,
    ) -> Any:
        url = f"{self.base_url}/{path}"
        logger.debug("API request: %s", url)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=body or {},
                headers=self._headers(),
                timeout=httpx.Timeout(timeout_ms / 1000),
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text}")
            data = resp.json()
            logger.debug("API response: ret=%s", data.get("ret"))
            return data

    # ── 消息接收 ──────────────────────────────────────────────

    async def get_updates(self, buf: str | None = None) -> dict:
        """长轮询获取新消息，35s 超时"""
        body = {"get_updates_buf": buf} if buf else {}
        return await self._request("ilink/bot/getupdates", body, 35_000)

    # ── 消息发送 ──────────────────────────────────────────────

    async def send_message(self, msg: dict) -> None:
        """发送消息，含限流和重试"""
        user_id = msg.get("msg", {}).get("to_user_id")
        if user_id:
            await self._rate_limit(user_id)

        max_retries = 2
        delay = 3.0
        for attempt in range(max_retries + 1):
            resp = await self._request("ilink/bot/sendmessage", {"msg": msg})
            if resp.get("ret") == -2:
                # 限流
                if user_id:
                    import time
                    self._next_send_time[user_id] = time.monotonic() + delay + self.MIN_SEND_INTERVAL
                if attempt == max_retries:
                    raise RuntimeError(f"sendMessage rate-limited after {max_retries} retries")
                logger.warning("sendMessage rate-limited, retry %d in %.0fs", attempt, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 15.0)
                continue
            return

    async def _rate_limit(self, user_id: str) -> None:
        """每用户发送限流"""
        import time
        now = time.monotonic()
        next_available = self._next_send_time.get(user_id, 0) + self.MIN_SEND_INTERVAL
        wait = max(0, next_available - now)
        if wait > 0:
            logger.debug("Rate limiter waiting %.1fs for %s", wait, user_id)
            await asyncio.sleep(wait)
        self._next_send_time[user_id] = max(now, next_available)

    # ── "正在输入"状态 ────────────────────────────────────────

    async def send_typing(
        self, ilink_user_id: str, typing_ticket: str, status: int
    ) -> None:
        """发送"正在输入"状态。status: 1=TYPING, 2=CANCEL"""
        await self._request(
            "ilink/bot/sendtyping",
            {
                "ilink_user_id": ilink_user_id,
                "typing_ticket": typing_ticket,
                "status": status,
            },
            10_000,
        )

    # ── 获取配置（含 typing_ticket）──────────────────────────

    async def get_config(
        self, ilink_user_id: str, context_token: str | None = None
    ) -> dict:
        return await self._request(
            "ilink/bot/getconfig",
            {"ilink_user_id": ilink_user_id, "context_token": context_token},
            10_000,
        )

    # ── CDN 上传 ──────────────────────────────────────────────

    async def get_upload_url(self, req: dict) -> dict:
        """获取 CDN 预签名上传地址"""
        return await self._request("ilink/bot/getuploadurl", req)
