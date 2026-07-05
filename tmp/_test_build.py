"""最小测试:模拟 run.py 启动时的 import 链,不启动 server。"""
from agent_core.runtime import build_agent

agent = build_agent(hitl=False)
print("BUILD OK")
print("subagents:", [s.get("name") for s in agent.builder.subagents] if hasattr(agent, "builder") else "n/a")
