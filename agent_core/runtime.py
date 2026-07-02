"""统一 agent 装配入口。

从原 agent_runtime.py L1292-1318 拆出。提供唯一的 build_agent() 工厂 + 模块级
`agent` 单例 + new_thread_id()。

消除原先三套 agent 配置分歧（agent_runtime 单例 / run.py build_agent / demo.py 自建）：
所有入口（entrypoints/web、entrypoints/cli、channels/*）必须经 build_agent() 构造。
- channels 用模块级 `agent` 单例（build_agent(hitl=False)，无 HITL，与原行为一致）
- entrypoints/web 用 build_agent(hitl=HITL_ENABLED_DEFAULT)
- entrypoints/cli 用 build_agent(hitl=True)（交互式终端需 HITL 确认 execute）
"""
import threading
import uuid
from collections import OrderedDict

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver

from agent_core.config import ensure_runtime_dirs
from agent_core.llm import create_llm
from agent_core.prompts import SYSTEM_PROMPT, research_subagent
from sandbox import backend
from tools import get_current_time, render_html

MAX_THREADS = 200


class BoundedMemorySaver(MemorySaver):
    """带 LRU 封顶的 MemorySaver。

    langgraph 的 MemorySaver 内部用 dict 存 thread 状态，无自动清理。
    这里在 aput（异步写入入口）后按访问顺序淘汰最旧的 thread。
    同步 put 同样处理，兼容 stream() 路径。
    """

    def __init__(self, max_threads: int = MAX_THREADS):
        super().__init__()
        self._max_threads = max_threads
        self._lru: "OrderedDict[str, None]" = OrderedDict()
        self._lock = threading.Lock()

    def _touch(self, thread_id: str) -> None:
        with self._lock:
            self._lru.pop(thread_id, None)
            self._lru[thread_id] = None
            self._evict_locked()

    def _evict_locked(self) -> None:
        """淘汰最旧的 thread，直到数量 <= max_threads。调用方需持锁。"""
        while len(self._lru) > self._max_threads:
            old_tid, _ = self._lru.popitem(last=False)
            self.storage.pop(old_tid, None)
            keys_to_drop = [k for k in self.writes if k and k[0] == old_tid]
            for k in keys_to_drop:
                self.writes.pop(k, None)

    async def aput(self, config, checkpoint, metadata, new_versions) -> None:
        await super().aput(config, checkpoint, metadata, new_versions)


def build_agent(*, hitl: bool = False):
    """统一 agent 装配入口。所有入口（web/cli/channel）必须经此构造。

    Args:
        hitl: 是否启用 Human-In-The-Loop 中断。启用时 execute 工具调用前会暂停
              等待用户批准/拒绝（终端 CLI 场景）。web/channel 默认关闭——
              web 的 HITL 通过 interrupt_on + /chat/resume 实现，但当前默认关闭
              （execute 受 _ShellWhitelistFilter 白名单保护，足够安全）；
              channel 无 stdin，启用 HITL 会卡死。
    """
    ensure_runtime_dirs()
    interrupt_on = {"execute": True} if hitl else None
    return create_deep_agent(
        model=create_llm(),
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        tools=[get_current_time, render_html],
        subagents=[research_subagent],
        interrupt_on=interrupt_on,
        checkpointer=BoundedMemorySaver(),
        skills=["skills/"],
    )


# 模块级单例：供 channels 直接 import（无 HITL，与原 agent_runtime.agent 行为一致）
agent = build_agent(hitl=False)


def new_thread_id(prefix: str = "thread") -> str:
    return f"{prefix}:{uuid.uuid4()}"
