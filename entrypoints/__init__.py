"""入口实现包。

每个模块提供同步 main() 供根级薄 shim 委派：
- web:    FastAPI + SSE Web Bridge（原 run.py）
- wechat: 个人微信渠道（原 run_wechat.py）
- wecom:  企业微信渠道（原 run_wecom.py）
- cli:    交互式终端（原 demo.py，收敛到 build_agent）

根级 run.py / run_wechat.py / run_wecom.py / demo.py 仅 2-3 行 shim。
"""
