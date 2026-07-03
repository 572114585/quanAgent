# 任务计划持久化 —— SQLite 方案

## 摘要

把 agent 的 checkpointer 从纯内存 `BoundedMemorySaver` 替换为 `AsyncSqliteSaver`，让 thread 状态（messages / todos / files / pending interrupts）落到 SQLite 文件。进程重启后，前端用原 sessionId 继续对话即可无缝恢复，HITL 中断也能跨重启 resume。

**核心改动只在 3 个文件**：`agent_core/config.py`（加路径常量）、`agent_core/runtime.py`（换 checkpointer 实现并提升为模块级单例）、`requirement.txt`（加依赖）。其它入口点（web/cli/wechat/wecom）零改动即自动获益。

---

## 现状分析

### 当前 checkpointer
[agent_core/runtime.py](file:///workspace/agent_core/runtime.py#L28-L86)
- L17 `from langgraph.checkpoint.memory import MemorySaver`
- L25 `MAX_THREADS = 200`
- L28-58 `BoundedMemorySaver(MemorySaver)` —— 内存 LRU
- L80 `build_agent()` 内 `checkpointer=BoundedMemorySaver()` —— **每次 build 都新建一个**
- L86 模块级 `agent = build_agent(hitl=False)` 单例

### 关键问题
1. **纯内存，重启即丢**：进程重启后 thread 状态全丢，前端用旧 sessionId 发 `/chat` 时 agent"失忆"，长任务无法恢复。
2. **多实例不共享**：`entrypoints/web.py` 的 `get_agent()` 与 `agent_core.agent` 是两个独立 build，各自 `new BoundedMemorySaver()`，两份内存 dict 互不相通。
3. **LRU 实际是死代码**：[runtime.py](file:///workspace/agent_core/runtime.py#L42-L58) 重写的 `aput()` 只调 `super().aput()`，没调 `_touch()`；`put()` 未重写；`_lru` 这个 OrderedDict 从未被填充，`_evict_locked()` 永不触发。docstring 声称的淘汰逻辑实际未接线。
4. **HITL resume 重启后失效**：[entrypoints/web.py](file:///workspace/entrypoints/web.py#L639) 的 `/chat/resume` 用 `Command(resume=...)` + 原 thread_id，依赖 checkpointer 持有 pending interrupt；重启后 MemorySaver 丢了，resume 卡死。

### state 结构（决定 todos 是否需额外开发）
deepagents `create_deep_agent` 的 state 含 `messages` / `files` / `todos` 三个 channel，全部随 checkpoint 持久化：
- `todos` 由 `TodoListMiddleware` 维护，`write_todos` 工具整体替换 todos 列表。
- 前端 [chat.ts](file:///workspace/agent-frontend/src/stores/chat.ts#L21-L44) 从工具调用 `args.todos` 解析，注释"todos 字段是完整的任务列表"。
- 换 SqliteSaver 后 todos **自动落库，无需额外 schema、无需额外代码**。

### 各入口点实例化方式
| 入口 | 实例化 | 是否共享 |
|---|---|---|
| web [web.py](file:///workspace/entrypoints/web.py#L94-L127) | 懒加载单例 `build_agent(hitl=HITL_ENABLED)` | **独立** |
| cli [cli.py](file:///workspace/entrypoints/cli.py#L36) | 模块级 `build_agent(hitl=True)` | **独立** |
| wechat/wecom bridge | `from agent_core import agent` | 复用 `agent_core.agent` |

→ 换 SQLite 后**必须把 checkpointer 提升为全局单例**，否则多实例指向同一 DB 文件会引发 SQLite 单写者并发问题。

### 依赖现状
[requirement.txt](file:///workspace/requirement.txt) 未列 `langgraph`（随 deepagents 传递引入）、未列 `langgraph-checkpoint-sqlite`。全代码库无任何 DB/ORM/migration 痕迹。引入 SqliteSaver 是项目里**第一个**数据库用法。

### thread_id 映射（无需改动）
- web：sessionId 直接当 thread_id
- cli：`uuid.uuid4()` 每进程新建
- wechat：`sessions.json` 映射 user→`wechat:<uuid>`（[session.py](file:///workspace/channels/wechat/session.py)），需保留
- wecom：确定性 `wecom:{chat_id}`（[handlers.py](file:///workspace/channels/wecom/handlers.py#L13-L15)），无需存

---

## 改动方案

### 改动 1：依赖
[requirement.txt](file:///workspace/requirement.txt) 末尾新增一行：
```
langgraph-checkpoint-sqlite>=2.0
```
该包会自动带入 `aiosqlite`（`AsyncSqliteSaver` 依赖）。

### 改动 2：路径常量
[agent_core/config.py](file:///workspace/agent_core/config.py#L17-L20) 在路径常量区新增：
```python
# checkpointer 持久化目录与 DB 文件（task plan / messages / interrupts 落库位置）
STATE_DIR = WORKSPACE_ROOT / "state"
CHECKPOINT_DB_PATH = STATE_DIR / "checkpoints.sqlite"
```
并在 `ensure_runtime_dirs()` 里 `STATE_DIR.mkdir(parents=True, exist_ok=True)`，确保启动时目录存在。

**为何放 `workspace/state/`**：与现有 `output/` / `tmp/` / `uploads/` 同级，沿用 [config.py](file:///workspace/agent_core/config.py#L17-L20) 的常量风格。DB 文件随 workspace 一起持久（容器/沙箱挂卷时挂 workspace 即可带上）。

### 改动 3：换 checkpointer（核心）
[agent_core/runtime.py](file:///workspace/agent_core/runtime.py) 改动点：

**3a. 替换 import（L17）**
```python
# 删除：from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
```

**3b. 删除 BoundedMemorySaver 类与 MAX_THREADS（L25-58）**
整段 `MAX_THREADS`、`class BoundedMemorySaver` 删除。LRU 死代码不迁移到 SQLite 方案（SQLite 可存海量 thread，不需要内存淘汰；如未来需要清理，单独写基于 SQL 的 TTL 清理函数）。

**3c. 提升为模块级单例 checkpointer**
在 `build_agent` 之前新增：
```python
# 模块级单例 checkpointer：所有 build_agent() 共用，避免多实例指向同一 SQLite 文件
# 引发单写者并发问题。AsyncSqliteSaver 适合 web 的 astream / aget_state 异步路径。
_checkpointer: AsyncSqliteSaver | None = None


def get_checkpointer() -> AsyncSqliteSaver:
    """惰性创建模块级 AsyncSqliteSaver 单例。"""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = AsyncSqliteSaver.from_conn_string(str(CHECKPOINT_DB_PATH))
        # AsyncSqliteSaver 首次调用 setup() 建表
    return _checkpointer
```

**3d. build_agent() 用单例 checkpointer（L80）**
```python
# 原：checkpointer=BoundedMemorySaver(),
checkpointer=get_checkpointer(),
```

**3e. import 调整**
顶部加 `from agent_core.config import CHECKPOINT_DB_PATH`（与现有 `ensure_runtime_dirs` 同来源）。

### 改动 4：AsyncSqliteSaver 的初始化时序
`AsyncSqliteSaver` 是异步 saver，`from_conn_string` 返回的对象首次使用前需调 `await setup()` 建表。两种处理方式：

**方案 A（推荐，最小改动）**：在 `get_checkpointer()` 里同步建表。`AsyncSqliteSaver.from_conn_string` 实际会在首次 `aput/aget` 时自动初始化 schema（langgraph-checkpoint-sqlite 2.x 的行为），无需显式 `setup()`。验证时确认这一点即可。

**方案 B（兜底）**：如果首次使用前必须 `await setup()`，在 [entrypoints/web.py](file:///workspace/entrypoints/web.py#L99-L127) 的 `get_agent()` 懒加载里，build_agent 之前 `await get_checkpointer().setup()`。cli/channel 入口是同步路径，需要在 build_agent 里用 `asyncio.run` 一次性跑 setup（或改成同步 `SqliteSaver`）。

→ 实施时先按方案 A，跑通 web；如遇 schema 未建报错，再补 setup。**不引入 sync `SqliteSaver`**：web 走 `astream`/`aget_state`，async saver 避免同步阻塞事件循环；channel bridge 也已用 `astream_events`。

### 改动 5（可选，建议同步做）：前端启动时恢复 pending interrupt
当前 [chat.ts](file:///workspace/agent-frontend/src/stores/chat.ts) 的 `todosBySession` 只是流式事件镜像，重启前端后无法重新获取后端 todos / pending interrupt。换 SqliteSaver 后，建议补一个只读端点：

[entrypoints/web.py](file:///workspace/entrypoints/web.py) 新增：
```python
@app.get("/chat/state")
async def chat_state(sessionId: str):
    """读 thread 状态：是否有 pending interrupt、当前 todos。供前端启动时恢复 UI。"""
    agent_obj = await get_agent()
    config = {"configurable": {"thread_id": sessionId}}
    state = await agent_obj.aget_state(config)
    interrupts = []
    for task in state.tasks:
        for intr in task.interrupts:
            interrupts.extend(intr.value.get("action_requests", []))
    todos = state.values.get("todos", []) if state.values else []
    return {
        "hasInterrupt": bool(state.next),
        "interrupts": interrupts,
        "todos": todos,
        "messageCount": len(state.values.get("messages", [])) if state.values else 0,
    }
```
前端在 session 加载时调一次，发现 `hasInterrupt` 则恢复审批 UI，`todos` 则恢复待办列表。

**这一项标为可选**：核心目标（重启后对话续接）只靠改动 1-4 就达成。改动 5 是体验补强，可独立排期。

---

## 不做的事（明确边界）

- **不引入 PostgreSQL**：文档 §10 把 PG 列为 MVP3 目标，当前 MVP1 阶段 SQLite 足够，避免引入额外服务依赖。
- **不动 wechat 的 `sessions.json`**：它存的是 user→thread_id 映射，是 SqliteSaver 之上的一层，职责不同。
- **不清理历史 thread**：SQLite 文件增长在个人助手场景可接受；如需清理，后续单独加 TTL 函数（`DELETE FROM checkpoints WHERE ...`）。
- **不补对象存储 / 产物持久化**：agent 用 `execute` 写到 `workspace/output` 的真实磁盘文件不在 state 里，不能随 checkpoint 恢复，但这是另一层问题（容器卷持久化 / 对象存储），不在本次范围。
- **不删 `BoundedMemorySaver` 的 LRU 思路迁移**：那套 LRU 是死代码，迁移后整段删除即可，不在 SQLite 方案里重建淘汰逻辑。

---

## 假设与决策

1. **假设**：`langgraph-checkpoint-sqlite` 2.x 的 `AsyncSqliteSaver.from_conn_string` 首次使用时自动建表，无需显式 `await setup()`。如假设不成立，回退到方案 B（在入口点 build 前 `await setup()`）。
2. **决策**：用 `AsyncSqliteSaver` 而非同步 `SqliteSaver`。web 入口走 `astream`/`aget_state`，async saver 不阻塞事件循环；channel bridge 也已是异步路径。cli 是同步路径，但 `agent.stream()` 调用 async saver 时 langgraph 内部会处理 sync→async 桥接（MemorySaver 也是这样被 sync/async 混用的）。
3. **决策**：checkpointer 提升为模块级全局单例，`build_agent()` 引用它。web/cli/channel 三处 build 共用同一 DB 文件、同一连接。
4. **决策**：DB 路径放 `workspace/state/checkpoints.sqlite`，与 `output/tmp/uploads` 同级，随 workspace 卷一起持久化。
5. **假设**：thread_id 命名空间不冲突（web `s_*`、wechat `wechat:*`、wecom `wecom:*`、cli 随机 uuid），同一 SQLite 文件可安全存所有入口的 thread。

---

## 验证步骤

1. **依赖安装**：`pip install -r requirement.txt`，确认 `langgraph-checkpoint-sqlite` 与 `aiosqlite` 装上。
2. **启动 web**：`python run.py`，确认 `workspace/state/checkpoints.sqlite` 文件被创建，且含 `checkpoints` / `checkpoint_writes` / `checkpoint_blobs` 表（`sqlite3` CLI 查 `.tables`）。
3. **基本对话**：前端发一条消息，等回复完成。重启 `python run.py`。前端用**同一个 sessionId** 再发一条，确认 agent 记得上一轮内容（说明 thread 从 DB 恢复）。
4. **todos 恢复**：让 agent 跑一个会用 `write_todos` 的多步任务（如 daily-report skill），中途重启进程，前端同 sessionId 继续，确认 todos 仍在（state.todos 随 checkpoint 恢复）。
5. **HITL 跨重启 resume**：触发一个 execute 中断（前端显示审批 UI），**不点批准**，重启 `python run.py`。前端调 `/chat/resume` 提交 approve，确认 execute 能继续执行（pending interrupt 从 DB 恢复）。
6. **多入口共存**：cli 跑一轮，wecom 跑一轮，web 跑一轮，确认三者各自的 thread 在同一 DB 文件里互不干扰（查 `SELECT DISTINCT thread_id FROM checkpoints`）。
7. **回归**：跑一遍 md-to-pdf / word-docx skill，确认产物检测（[artifacts/detector.py](file:///workspace/artifacts/detector.py)）和 SSE artifact 事件正常。

---

## 关键文件索引

- [agent_core/runtime.py](file:///workspace/agent_core/runtime.py) —— checkpointer 工厂（核心改动）
- [agent_core/config.py](file:///workspace/agent_core/config.py) —— 路径常量（加 STATE_DIR / CHECKPOINT_DB_PATH）
- [requirement.txt](file:///workspace/requirement.txt) —— 依赖
- [entrypoints/web.py](file:///workspace/entrypoints/web.py) —— web 入口（自动获益，可选加 /chat/state）
- [entrypoints/cli.py](file:///workspace/entrypoints/cli.py) —— cli 入口（自动获益）
- [channels/wechat/bridge.py](file:///workspace/channels/wechat/bridge.py) + [session.py](file:///workspace/channels/wechat/session.py) —— 微信渠道（自动获益，sessions.json 保留）
- [channels/wecom/bridge.py](file:///workspace/channels/wecom/bridge.py) + [handlers.py](file:///workspace/channels/wecom/handlers.py) —— 企微渠道（自动获益）
- [README_ARCHITECTURE.md](file:///workspace/README_ARCHITECTURE.md#L164) —— L164 架构规划已明确"任务计划建议持久化到数据库"
