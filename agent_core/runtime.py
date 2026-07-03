"""统一 agent 装配入口。

从原 agent_runtime.py L1292-1318 拆出。提供唯一的 build_agent() 工厂 + 模块级
`agent` 单例 + new_thread_id()。

消除原先三套 agent 配置分歧（agent_runtime 单例 / run.py build_agent / demo.py 自建）：
所有入口（entrypoints/web、entrypoints/cli、channels/*）必须经 build_agent() 构造。
- channels 用模块级 `agent` 单例（build_agent(hitl=False)，无 HITL，与原行为一致）
- entrypoints/web 用 build_agent(hitl=HITL_ENABLED_DEFAULT)
- entrypoints/cli 用 build_agent(hitl=True)（交互式终端需 HITL 确认 execute）
"""
import asyncio
import sqlite3
import threading
import uuid

from deepagents import create_deep_agent
from langgraph.checkpoint.sqlite import SqliteSaver

from agent_core.config import CHECKPOINT_DB_PATH, ensure_runtime_dirs
from agent_core.llm import create_llm
from agent_core.prompts import SYSTEM_PROMPT, research_subagent
from sandbox import backend
from tools import get_current_time, render_html


class DualSqliteSaver(SqliteSaver):
    """同时支持 sync 和 async 调用的 SQLite checkpointer。

    为什么不直接用 AsyncSqliteSaver：它需要 aiosqlite.Connection（async 创建），
    无法在同步 build_agent 里构造（模块级 `agent = build_agent()` 在 import 时执行）。
    为什么不直接用 SqliteSaver：它的 async 方法（aput/aget_tuple 等）显式抛
    NotImplementedError，而 web 的 astream / channel 的 astream_events 走 async 路径，
    langgraph pregel 会直接 `await checkpointer.aget_tuple(...)`，没有 to_thread 兜底。

    本类继承 SqliteSaver（保留 sync 接口给 cli 的 stream/get_state），override
    async 方法用 asyncio.to_thread 包对应 sync 方法（给 web/channel 的 async 路径）。
    全局 threading.Lock 串行所有 sqlite 访问，避免并发写 "database is locked"；
    WAL 模式 + busy_timeout 进一步提升并发与稳健性。

    DB 落 workspace/state/checkpoints.sqlite，进程重启后 thread 状态（messages /
    todos / files / pending interrupts）可恢复，HITL resume 也能跨重启生效。
    """

    def __init__(self, conn: sqlite3.Connection):
        super().__init__(conn)
        self._lock = threading.Lock()
        # WAL 提升读写并发；busy_timeout 在锁竞争时等待而非立即报错。
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")

    # ---- sync 接口加锁（cli 的 stream / get_state 路径）----
    def put(self, *args, **kwargs):
        with self._lock:
            return super().put(*args, **kwargs)

    def put_writes(self, *args, **kwargs):
        with self._lock:
            return super().put_writes(*args, **kwargs)

    def get_tuple(self, *args, **kwargs):
        with self._lock:
            return super().get_tuple(*args, **kwargs)

    def list(self, *args, **kwargs):
        with self._lock:
            return super().list(*args, **kwargs)

    # ---- async 接口：to_thread 包 sync（web 的 astream / channel 的 astream_events）----
    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(
            self.put, config, checkpoint, metadata, new_versions
        )

    async def aput_writes(self, config, writes, task_id):
        return await asyncio.to_thread(self.put_writes, config, writes, task_id)

    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        return await asyncio.to_thread(
            lambda: list(self.list(config, filter=filter, before=before, limit=limit))
        )


# 模块级单例 checkpointer：所有 build_agent() 共用，避免多实例指向同一 SQLite 文件
# 引发单写者并发问题。check_same_thread=False：web 的 uvicorn 多协程 + to_thread
# 会在不同线程访问同一连接，必须放宽 sqlite3 的线程限制（_lock 保证串行）。
_checkpointer: DualSqliteSaver | None = None


def get_checkpointer() -> DualSqliteSaver:
    """惰性创建模块级 DualSqliteSaver 单例并建表。

    setup() 同步建 checkpoints / writes 两张表。单例保证 web/cli/channel 三处
    build 共用同一 DB 文件、同一连接。
    """
    global _checkpointer
    if _checkpointer is None:
        conn = sqlite3.connect(str(CHECKPOINT_DB_PATH), check_same_thread=False)
        saver = DualSqliteSaver(conn)
        saver.setup()  # 同步建表（checkpoints / writes）
        _checkpointer = saver
    return _checkpointer


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
        checkpointer=get_checkpointer(),
        skills=["skills/"],
    )


# 模块级单例：供 channels 直接 import（无 HITL，与原 agent_runtime.agent 行为一致）
agent = build_agent(hitl=False)


def new_thread_id(prefix: str = "thread") -> str:
    return f"{prefix}:{uuid.uuid4()}"
