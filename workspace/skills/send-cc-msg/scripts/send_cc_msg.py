#!/usr/bin/env python3
"""发送 CC 消息。配置从 CC_MSG_* 环境变量读取。"""

import argparse
import base64
import json
import logging
import os
import re
import sys

import requests


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_token(login_url: str, username: str, password: str) -> str | None:
    try:
        response = requests.post(
            login_url,
            json={"username": username, "passwd": password},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        result = response.json()
        if result.get("error_code") == 0:
            return result.get("token")
        logger.error("获取 CC token 失败，错误码: %s", result.get("error_code"))
    except Exception as exc:  # noqa: BLE001
        logger.error("获取 CC token 时发生异常: %s", exc)
    return None


def build_cc_message(
    message: str,
    title: str | None = None,
    banner_url: str | None = None,
    thumbnail_url: str | None = None,
    thumbnail_text: str | None = None,
    thumbnail_urls: str | None = None,
) -> str:
    banner = banner_url or "http://pic.fastdfs.lesso.com/PIC/M00/61/C0/wKgEUWnEoxKEe49GAAAAAAtbiP0797.png"
    msg_title = title or "大人，您有新的通知/进展~"
    cc_msg = (
        f"[banner_img_B]{banner}[banner_img_E]"
        f"[title_B]{msg_title}[title_E]"
        f"[version_B]2[version_E]"
        f"{message}"
    )

    link_text = thumbnail_text or "点击查看图片"
    if thumbnail_urls:
        urls = [url.strip() for url in thumbnail_urls.split(",") if url.strip()]
        if len(urls) == 1:
            cc_msg += (
                f"\n[url_B]{urls[0]}[url_E]"
                f"[issso_B]false[issso_E][param_B][param_E]"
                f"[url_show_B]{link_text}[url_show_E]"
            )
        elif len(urls) > 1:
            cc_msg += (
                f"\n[url_B]{urls[0]}[url_E]"
                f"[issso_B]false[issso_E][param_B][param_E]"
                f"[url_show_B]{link_text}1[url_show_E]"
            )
            for index, url in enumerate(urls[1:], 2):
                cc_msg += f"\n{link_text}{index}：{url}"
    elif thumbnail_url:
        cc_msg += (
            f"\n[url_B]{thumbnail_url}[url_E]"
            f"[issso_B]false[issso_E][param_B][param_E]"
            f"[url_show_B]{link_text}[url_show_E]"
        )
    return cc_msg


def send_cc_message(
    receiver_id: str,
    message: str,
    login_url: str,
    send_url: str,
    username: str,
    password: str,
    title: str | None = None,
    banner_url: str | None = None,
    thumbnail_url: str | None = None,
    thumbnail_text: str | None = None,
    thumbnail_urls: str | None = None,
) -> dict:
    if not receiver_id:
        return {"success": False, "receiver_id": receiver_id, "message": "接收者ID不能为空"}
    if not message:
        return {"success": False, "receiver_id": receiver_id, "message": "消息内容不能为空"}

    try:
        token = get_token(login_url, username, password)
        if not token:
            return {"success": False, "receiver_id": receiver_id, "message": "获取 CC 登录 token 失败"}

        cc_message = build_cc_message(
            message=message,
            title=title,
            banner_url=banner_url,
            thumbnail_url=thumbnail_url,
            thumbnail_text=thumbnail_text,
            thumbnail_urls=thumbnail_urls,
        )
        encoded = base64.b64encode(cc_message.encode("utf-8")).decode("utf-8")
        double_encoded = base64.b64encode(encoded.encode("utf-8")).decode("utf-8")
        receiver_ids = [rid.strip() for rid in receiver_id.replace("，", ",").split(",") if rid.strip()]

        for receiveridtype in range(1, 4):
            payload = {
                "userid": username,
                "token": token,
                "senderid": username,
                "senderidtype": "1",
                "receiveridtype": receiveridtype,
                "msgtype": "1",
                "dataisbase64": "1",
                "msgdata": double_encoded,
                "receiverids": receiver_ids,
            }
            try:
                response = requests.post(
                    send_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )
                match = re.search(r'"error_code"\s*:\s*(\d+)', response.text)
                if match and int(match.group(1)) == 0:
                    return {
                        "success": True,
                        "receiver_id": receiver_id,
                        "message": "CC 消息发送成功",
                        "receiveridtype": receiveridtype,
                    }
                logger.warning("发送失败，receiveridtype=%s", receiveridtype)
            except Exception as exc:  # noqa: BLE001
                logger.error("发送消息时发生异常，receiveridtype=%s: %s", receiveridtype, exc)

        return {"success": False, "receiver_id": receiver_id, "message": "所有 receiveridtype 都尝试失败"}
    except Exception as exc:  # noqa: BLE001
        logger.error("发送 CC 消息失败: %s", exc)
        return {"success": False, "receiver_id": receiver_id, "message": f"发送失败: {exc}"}


def main() -> None:
    parser = argparse.ArgumentParser(description="发送 CC 消息")
    parser.add_argument("--receiver_id", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--title")
    parser.add_argument("--banner_url")
    parser.add_argument("--thumbnail_url")
    parser.add_argument("--thumbnail_text")
    parser.add_argument("--thumbnail_urls")
    args = parser.parse_args()

    config = {
        "login_url": os.getenv("CC_MSG_LOGIN_URL"),
        "send_url": os.getenv("CC_MSG_SEND_URL"),
        "username": os.getenv("CC_MSG_USERNAME"),
        "password": os.getenv("CC_MSG_PASSWORD"),
    }
    if not all(config.values()):
        logger.error("缺少必要环境变量：CC_MSG_LOGIN_URL、CC_MSG_SEND_URL、CC_MSG_USERNAME、CC_MSG_PASSWORD")
        sys.exit(1)

    result = send_cc_message(
        receiver_id=args.receiver_id,
        message=args.message,
        title=args.title,
        banner_url=args.banner_url,
        thumbnail_url=args.thumbnail_url,
        thumbnail_text=args.thumbnail_text,
        thumbnail_urls=args.thumbnail_urls,
        **config,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
