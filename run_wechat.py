"""个人微信渠道入口 shim。实际实现见 entrypoints/wechat.py。

用法：
    python run_wechat.py --add        # 添加新账号（扫码）
    python run_wechat.py --list       # 列出所有已绑定账号
    python run_wechat.py              # 默认使用最近账号
"""
from entrypoints.wechat import main

if __name__ == "__main__":
    main()
