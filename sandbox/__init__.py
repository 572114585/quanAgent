"""Shell 沙箱安全层。

从原 agent_runtime.py L39-1238 拆出（约 1200 行）。两层结构：
- 内层 _SkillsShellBackend（backend.py）：token 级路径改写 + 编码兼容 + 写路径沙箱
- 外层 _ShellWhitelistFilter（whitelist.py）：命令替换/白名单/-c/cd 越界/curl host 拦截

模块级 `backend` 单例由两层组装而成，供 agent_core.runtime.build_agent() 注入
create_deep_agent(backend=...)。
"""
from sandbox.whitelist import backend, _ShellWhitelistFilter
from sandbox.backend import _SkillsShellBackend

__all__ = ["backend", "_ShellWhitelistFilter", "_SkillsShellBackend"]
