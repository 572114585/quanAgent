"""扫码登录：获取二维码 → 等待微信扫码确认 → 返回 bot_token"""
import asyncio
import logging

import httpx
import qrcode

from .accounts import AccountData, save_account
from .config import DEFAULT_BASE_URL

logger = logging.getLogger(__name__)

QR_CODE_URL = f"{DEFAULT_BASE_URL}/ilink/bot/get_bot_qrcode?bot_type=3"
QR_STATUS_URL = f"{DEFAULT_BASE_URL}/ilink/bot/get_qrcode_status"
POLL_INTERVAL = 3.0  # 轮询间隔（秒）


async def start_qr_login() -> tuple[str, str]:
    """
    获取登录二维码。
    返回 (qrcode_url, qrcode_id)
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(QR_CODE_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    if data.get("ret") != 0 or not data.get("qrcode_img_content") or not data.get("qrcode"):
        raise RuntimeError(f"获取二维码失败 (ret={data.get('ret')})")

    qrcode_id = data["qrcode"]
    qrcode_url = data["qrcode_img_content"]
    logger.info("QR code obtained: %s", qrcode_id)

    # 终端打印二维码
    print("\n请用微信扫描以下二维码：\n")
    qr = qrcode.QRCode(border=1)
    qr.add_data(qrcode_url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    print()

    return qrcode_url, qrcode_id


async def wait_for_qr_scan(qrcode_id: str) -> AccountData:
    """
    轮询等待用户扫码确认。
    二维码过期时抛出异常，调用方可重新获取。
    """
    while True:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                QR_STATUS_URL,
                params={"qrcode": qrcode_id},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

        status = data.get("status", "")
        logger.debug("QR status: %s", status)

        if status in ("wait", "scaned"):
            await asyncio.sleep(POLL_INTERVAL)
            continue

        if status == "confirmed":
            bot_token = data.get("bot_token")
            ilink_bot_id = data.get("ilink_bot_id")
            ilink_user_id = data.get("ilink_user_id")
            if not all([bot_token, ilink_bot_id, ilink_user_id]):
                raise RuntimeError("扫码确认成功但返回数据不完整")

            from datetime import datetime
            account = AccountData(
                bot_token=bot_token,
                account_id=ilink_bot_id,
                base_url=data.get("baseurl") or DEFAULT_BASE_URL,
                user_id=ilink_user_id,
                created_at=datetime.now().isoformat(),
            )
            save_account(account)
            print("\n✅ 微信绑定成功！\n")
            return account

        if status == "expired":
            raise RuntimeError("二维码已过期，请重新获取")

        # 其他错误状态
        retmsg = data.get("retmsg", "")
        if retmsg:
            raise RuntimeError(f"扫码失败: {retmsg}")
        if status:
            raise RuntimeError(f"扫码失败: {status}")

        await asyncio.sleep(POLL_INTERVAL)
