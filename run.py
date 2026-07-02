"""Agent Web Bridge 入口 shim。实际实现见 entrypoints/web.py。

启动：
    python run.py            # 默认 8000 端口
    PORT=9000 python run.py  # 自定义端口
"""
from entrypoints.web import main

if __name__ == "__main__":
    main()
