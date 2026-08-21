"""Shell 安全层。

从原 agent_runtime.py L39-1238 拆出。两层结构：
- 内层 _SkillsShellBackend（backend.py）：token 级路径改写 + 编码兼容 + 写路径边界
- 外层 _ShellWhitelistFilter（whitelist.py）：删除命令硬拒绝 + cwd 边界

注意：这是字符串策略 + 路径边界，不是 OS 级进程沙盒。

模块级 `backend` 单例由两层组装而成，供 agent_core.runtime.build_agent() 注入
create_deep_agent(backend=...)。
"""
from sandbox.whitelist import backend, _ShellWhitelistFilter
from sandbox.backend import _SkillsShellBackend
from sandbox.trust import execute_trust, get_execute_trust_level

__all__ = [
    "backend",
    "_ShellWhitelistFilter",
    "_SkillsShellBackend",
    "execute_trust",
    "get_execute_trust_level",
]
