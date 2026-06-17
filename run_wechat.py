"""个人微信渠道入口

用法:
  python run_wechat.py              # 默认使用最近账号
  python run_wechat.py --add        # 添加新账号（扫码）
  python run_wechat.py --list       # 列出所有已绑定账号
  python run_wechat.py --account ID # 使用指定账号
  python run_wechat.py --all        # 同时运行所有账号
  python run_wechat.py --remove ID  # 删除指定账号
"""
import argparse
import asyncio
import logging
import signal
import sys

from channels.wechat.api import WeChatApi
from channels.wechat.login import start_qr_login, wait_for_qr_scan
from channels.wechat.accounts import (
    load_latest_account,
    load_all_accounts,
    load_account,
    delete_account,
)
from channels.wechat.monitor import Monitor
from channels.wechat.sender import Sender
from channels.wechat.bridge import handle_message
from channels.wechat.session import SessionStore


def cmd_list() -> None:
    """列出所有已绑定账号"""
    accounts = load_all_accounts()
    if not accounts:
        print("暂无已绑定的微信账号。使用 --add 添加。")
        return
    print(f"共 {len(accounts)} 个已绑定账号：\n")
    for i, acc in enumerate(accounts, 1):
        print(f"  {i}. 账号ID: {acc.account_id}")
        print(f"     用户ID: {acc.user_id}")
        print(f"     绑定时间: {acc.created_at}")
        print()


async def cmd_add() -> None:
    """添加新账号（扫码登录）"""
    print("请用微信扫描以下二维码：\n")
    try:
        _, qrcode_id = await start_qr_login()
        account = await wait_for_qr_scan(qrcode_id)
        print(f"已绑定账号: {account.account_id}")
    except RuntimeError as e:
        print(f"\n登录失败: {e}")
        sys.exit(1)


def cmd_remove(account_id: str) -> None:
    """删除指定账号"""
    acc = load_account(account_id)
    if not acc:
        print(f"账号 {account_id} 不存在。使用 --list 查看所有账号。")
        sys.exit(1)
    if delete_account(account_id):
        print(f"已删除账号: {account_id}")
    else:
        print(f"删除失败: {account_id}")


async def run_single_account(account, sessions: SessionStore) -> None:
    """为单个账号启动监听"""
    api = WeChatApi(account.bot_token, account.base_url)
    sender = Sender(api, account.account_id)
    account_sessions = SessionStore(account_id=account.account_id)

    async def on_message(msg):
        await handle_message(msg, sender, account_sessions)

    def on_session_expired():
        print(f"⚠️ 账号 {account.account_id} 会话已过期，请重新扫码")

    monitor = Monitor(api, on_message, on_session_expired)
    print(f"🟢 账号 {account.account_id} 已启动监听")
    await monitor.run()


async def run_accounts(accounts: list) -> None:
    """并发运行多个账号"""
    if not accounts:
        print("没有可运行的账号。使用 --add 添加。")
        sys.exit(1)

    if len(accounts) == 1:
        await run_single_account(accounts[0], SessionStore())
        return

    # 多账号并发
    tasks = [asyncio.create_task(run_single_account(acc, SessionStore())) for acc in accounts]
    print(f"🟢 已启动 {len(accounts)} 个账号的监听")

    # 优雅退出
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: [t.cancel() for t in tasks])
        except NotImplementedError:
            pass

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="个人微信渠道")
    parser.add_argument("--add", action="store_true", help="添加新账号（扫码登录）")
    parser.add_argument("--list", action="store_true", help="列出所有已绑定账号")
    parser.add_argument("--account", type=str, help="使用指定账号ID")
    parser.add_argument("--all", action="store_true", help="同时运行所有账号")
    parser.add_argument("--remove", type=str, metavar="ID", help="删除指定账号")
    args = parser.parse_args()

    # 命令路由
    if args.list:
        cmd_list()
        return

    if args.add:
        await cmd_add()
        return

    if args.remove:
        cmd_remove(args.remove)
        return

    # 运行模式
    if args.all:
        accounts = load_all_accounts()
        if not accounts:
            print("暂无已绑定账号。使用 --add 添加。")
            sys.exit(1)
        await run_accounts(accounts)
        return

    if args.account:
        account = load_account(args.account)
        if not account:
            print(f"账号 {args.account} 不存在。使用 --list 查看所有账号。")
            sys.exit(1)
    else:
        account = load_latest_account()
        if not account:
            print("未检测到微信绑定，请先添加账号：\n")
            print("  python run_wechat.py --add\n")
            sys.exit(1)

    print(f"已绑定账号: {account.account_id}")
    await run_accounts([account])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已退出")
