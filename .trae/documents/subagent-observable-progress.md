# 子智能体执行可观测性 · 前端任务进度展示

## Summary

让主 agent 通过 `task()` 调用子 agent（research-agent）时，前端"任务进度"悬浮面板（`FloatingTodoList.vue`）能实时显示子 agent 的任务描述及其内部工具调用（web_search / write_file）作为嵌套步骤，并支持同时展示多个并行子 agent 卡片（防御式 UI，当前后端串行调用也能正常工作；未来后端并行时无需改前端）。

核心改造：后端开启 langgraph 子图流式（`subgraphs=True`）并把子 agent 内部活动识别出来，通过新增/扩展的 SSE 事件传给前端；前端在现有任务清单面板内新增"子智能体"分区，按 `subagentId` 聚合步骤。

## Current State Analysis

### 后端（`/workspace/entrypoints/web.py`）
- `_stream_agent`（行 289-500）用 `agent.astream(input_payload, config=config, stream_mode="messages")`（行 327-331），**未开 `subgraphs=True`**。
- langgraph 在 `subgraphs=False`（默认）下，子图（子 agent）内部消息被 `StreamMessagesHandler` 过滤（`langgraph/pregel/_messages.py:145`），**完全不回流父 stream**。
- 结果：主 agent 调 `task()` 时，前端只看到一条 `tool_call(name="task")` + `tool_result(name="task")`（合成的最终摘要），子 agent 内部的 web_search/write_file 不可见。
- 当前 `_meta` 被忽略（行 342 `async for msg_chunk, _meta in stream_iter:` 只用 `msg_chunk`）。

### 子 agent 机制（deepagents 0.6.12 + langgraph 1.2.7，已实测）
- `task` 工具（`deepagents/middleware/subagents.py:725`）入参 `TaskToolSchema` 仅两字段：`description`（兼 prompt）、`subagent_type`。
- 子 agent 是编译好的子图，由 `task` 工具内 `subagent.invoke/ainvoke` 阻塞执行（`subagents.py:693/721`）。
- 开 `subgraphs=True` 后，`astream(stream_mode="messages")` 产出形状从 `(chunk, _meta)` 变为 `(namespace_tuple, (chunk, _meta))`；父图自身 chunk 的 `namespace=()`，子 agent 内部 chunk 的 `namespace=('tools:<tid>',)` 且 `_meta["langgraph_checkpoint_ns"]` 形如 `tools:<tid>|agent:<sub_tid>`。
- 父图 "tools" 节点处理 `task()` 工具返回的 ToolMessage，其 `_meta["langgraph_checkpoint_ns"]='tools:<tid>'`（无 `|`），与该次 task() spawn 的子 agent 共享同一个 `<tid>` → 据此把"子 agent 内部活动"关联到"父级 task() 调用"。
- 并行 task()：每个 tool_call 是独立 Send、独立 tid，可区分（当前后端只有 1 个 research-agent 且串行，但前端按 tid 聚合天然支持并行）。

### 前端
- 任务进度 UI：`/workspace/agent-frontend/src/components/chat/FloatingTodoList.vue`，由 `ChatPanel.vue:182` 挂载，props `:todos="todos"`。
- 状态：`/workspace/agent-frontend/src/stores/chat.ts` 行 58 `todosBySession`，由 `write_todos` 工具调用驱动（行 261-265 / 401-405 拦截，不进 `message.toolCalls`）。
- SSE 事件类型：`/workspace/agent-frontend/src/types/domain.ts` 行 102-121 `StreamEvent` 联合。
- 事件分发：`/workspace/agent-frontend/src/api/chat.ts` 行 37-94 `consumeStream` 的 switch。
- 当前 `task()` 调用落到 `MessageBubble.vue` 思考区的 toolCalls 列表（行 324-363），与 read_file/execute 等并列，无子 agent 专属视觉。

## Proposed Changes

### 决策（基于用户确认）
- 展示粒度：**任务描述 + 内嵌步骤**（子 agent 描述 + 其内部 web_search/write_file 作为嵌套步骤）。不流式展示子 agent 内部思考文字。
- 并行：**仅前端支持并行展示**，后端不改 task() 调用方式（保持串行）；前端按 `subagentId` 聚合，天然支持多卡片。
- UI 位置：**融入现有 `FloatingTodoList`**，在 todos 列表下方加"子智能体"分区，子 agent 卡片含嵌套步骤。

### 1. 后端：`/workspace/entrypoints/web.py`（`_stream_agent`，行 289-500）

**1.1 开启子图流式**
- 行 329-331：`astream(..., stream_mode="messages")` → 增加 `subgraphs=True`。
- 行 336-338：同步 fallback 的 `agent_obj.stream(...)` 同样加 `subgraphs=True`。
- 行 342：迭代解构改为 `async for namespace, (msg_chunk, _meta) in stream_iter:`（subgraphs=True 单 stream_mode 形状为 `(namespace_tuple, (chunk, meta))`；实现时先打印一次 `type(item)` 确认形状，必要时用 `item[0], item[1]` 兜底）。

**1.2 新增子 agent 跟踪状态**（在行 311 `pending_tool_calls` 附近）
```python
# subagent 跟踪：key = base namespace 'tools:<tid>'，即 subagentId
active_subagents: dict[str, dict] = {}
# 待认领的 task() 工具调用（按累积顺序），用于在子 agent 首个 chunk 到达时取 description/subagent_type
pending_task_calls: list[dict] = []  # 每项 = {"id": call_id, "args": "...", "claimed": False}
```

**1.3 在累积 tool_call_chunks 时（行 466-475 附近）识别 task() 调用**
- 当某条累积完成的 pending tool call 的 `name == "task"` 时，把它追加到 `pending_task_calls`（带 `claimed=False`）。
- 判定"累积完成"的简易时机：在 ToolMessage 处理前，pending_tool_calls 里 name=="task" 且未入 pending_task_calls 的视为待认领候选（实现时可维护一个 `task_indices_seen` 集合避免重复）。

**1.4 子 agent chunk 识别与事件发射**（在 `async for` 循环内，处理 msg_chunk 之前）
- 计算 `is_subagent = isinstance(namespace, tuple) and len(namespace) > 0`。
- 若 `is_subagent`：
  - `subagent_id = namespace[0]`（即 `'tools:<tid>'`）。
  - 首次见到该 `subagent_id`：
    - 从 `pending_task_calls` 找第一个 `claimed=False` 的项 → `claimed=True`，解析其 `args`（JSON）取 `description` / `subagent_type`。
    - 找不到（防御）：用 `description="子智能体任务"`、`subagent_type="subagent"`。
    - 记录 `active_subagents[subagent_id] = {"call_id": pending["id"], "subagent_type": ..., "description": ..., "started_emitted": True}`。
    - `yield _sse({"type": "subagent_start", "subagentId": subagent_id, "subagentType": subagent_type, "description": description})`。
  - 仅处理该 chunk 中的 **ToolMessage**（子 agent 内部工具调用 = 嵌套步骤）：
    - 复用现有 ToolMessage 处理逻辑（行 391-452 的 pending 匹配、callId 生成），但发射的 `tool_call`/`tool_result` 事件**额外带 `"subagentId": subagent_id`** 字段。
    - **跳过子 agent 的 AIMessageChunk**（不流式其 thinking/content，符合"任务+内嵌步骤"粒度）。
  - `continue`（不进入下方父图分支逻辑）。

**1.5 父图 task() ToolMessage 收尾**（修改行 391-452 的 ToolMessage 处理）
- 取 `_meta.get("langgraph_checkpoint_ns", "")` 作为潜在 `subagent_id`。
- 若 `subagent_id in active_subagents`：说明这条 ToolMessage 是 `task()` 工具返回（子 agent 结束）。
  - `yield _sse({"type": "subagent_done", "subagentId": subagent_id})`。
  - **不发射** `tool_call`/`tool_result`（避免 task() 重复出现在思考区）。
  - `del active_subagents[subagent_id]`。
  - `pending_tool_calls.clear()` 后 `continue`。
- 若 `subagent_id` 不在 `active_subagents` 但 pending 中 name=="task"（子 agent 未产内部 chunk 的边界情况）：补发 `subagent_start`（从 pending args 取 description）+ `subagent_done`，同样跳过 tool_call/tool_result。
- 其他普通工具（get_current_time 等）：走原有逻辑，发射 `tool_call`/`tool_result`（不带 subagentId）。

**1.6 事件格式补充**（行 18-29 文件头注释同步更新）
- 新增事件：`subagent_start` / `subagent_done`。
- `tool_call` / `tool_result` 增加可选字段 `subagentId`。

### 2. 前端类型：`/workspace/agent-frontend/src/types/domain.ts`

在行 100 后新增：
```ts
/** 子智能体执行的嵌套步骤（其内部工具调用） */
export interface SubagentStep {
  id: string
  name: string
  args?: string | Record<string, any>
  output?: string
  status: 'running' | 'completed' | 'failed'
}

/** 子智能体任务（由 task() 工具触发） */
export interface SubagentTask {
  /** subagentId，后端用 base namespace 'tools:<tid>' */
  id: string
  subagentType: string
  description: string
  status: 'running' | 'completed'
  steps: SubagentStep[]
}
```

扩展 `StreamEvent`（行 102-121）：
- 给 `tool_call` / `tool_result` 加 `subagentId?: string`。
- 新增两个变体：
```ts
| { type: 'subagent_start'; subagentId: string; subagentType: string; description: string }
| { type: 'subagent_done'; subagentId: string }
```

### 3. 前端 API 分发：`/workspace/agent-frontend/src/api/chat.ts`

- `StreamHandlers`（行 16-31）新增：
  - `onSubagentStart?: (p: { subagentId: string; subagentType: string; description: string }) => void`
  - `onSubagentDone?: (p: { subagentId: string }) => void`
  - `onToolCall` / `onToolResult` 回调签名增加可选 `subagentId?: string`。
- `consumeStream` switch（行 37-94）：
  - `tool_call` 分支：透传 `subagentId`。
  - `tool_result` 分支：透传 `subagentId`。
  - 新增 `case 'subagent_start'` / `case 'subagent_done'` 分支。

### 4. 前端状态：`/workspace/agent-frontend/src/stores/chat.ts`

- import 增加 `SubagentTask, SubagentStep`。
- 行 58 附近新增：`const subagentTasksBySession = ref<Record<string, SubagentTask[]>>({})`。
- `send()` 与 `resume()` 的回调块各新增：
  - `onSubagentStart`：向 `subagentTasksBySession[sessionId]` push 新 `SubagentTask`（status='running', steps=[]）。
  - `onSubagentDone`：把对应 id 的 status 置 'completed'。
  - `onToolCall`：若 `call.subagentId` 存在 → 找到对应 SubagentTask，push 一条 `SubagentStep`（status='running'），**不进 `msg.toolCalls`**；若 `call.name === 'task'`（防御）直接 return。
  - `onToolResult`：若 `payload.subagentId` 存在 → 在对应 SubagentTask.steps 里按 callId 找记录补全 output/status；若 `payload.name === 'task'`（防御）直接 return。
- 新增 `clearSubagents(sessionId)`（与 `clearTodos` 对称，行 512-514 附近）。
- return 块（行 516-536）导出 `subagentTasksBySession` 与 `clearSubagents`。

### 5. 前端 UI：`/workspace/agent-frontend/src/components/chat/FloatingTodoList.vue`

- import 增加 `SubagentTask`，新增 prop `subagents?: SubagentTask[]`。
- 顶部容器 `v-if`（行 83）改为 `v-if="totalCount > 0 || subagentCount > 0"`。
- 新增计算：`subagentCount`、`runningSubagents`、`currentSubagent`。
- 展开态列表（行 122-162）的 `<ol>` 后追加"子智能体"分区：
  - 一条分隔线 + 小标题"子智能体"（带 `Bot` 图标，lucide-vue-next 已有）。
  - 每个子 agent 一张卡片：头部 `Bot` 图标 + `subagentType` + `description` 截断 + 状态徽章（running=`Loader2` spin / completed=`CheckCircle2`）；下方缩进 `<ul>` 列出 `steps`（每步：小图标 + 工具名 mono + 状态点）。
  - 并行子 agent = 多张卡片纵向堆叠。
- 折叠态摘要（行 97-105）：若 `currentSubagent` 存在且无 `currentTask`，显示"子智能体：{subagentType} · {description 截断}"。
- 进度徽章（行 111-115）：保持 todos 的 `N/M`；子智能体单独在其分区头部显示 `完成数/总数`，不混入 todos 计数（避免语义混淆）。
- 全部完成自动折叠的 watch（行 31-38）：条件改为 `todos 全完成 && subagents 全完成`。

### 6. 前端挂载：`/workspace/agent-frontend/src/components/chat/ChatPanel.vue`

- 行 43 附近新增 `const subagents = computed(() => chat.subagentTasksBySession[props.session.id] ?? [])`。
- 行 182 `<FloatingTodoList :todos="todos" :default-expanded="hasRoom" />` 增加 `:subagents="subagents"`。

### 7. Mock SSE 服务器：`/workspace/agent-frontend/scripts/mock-sse-server.mjs`

- 增加一段 mock 序列：`subagent_start` → 几条带 `subagentId` 的 `tool_call`/`tool_result`（模拟 web_search/write_file）→ `subagent_done`，且演示两条并行 `subagent_start`（不同 subagentId），用于前端联调多卡片渲染。
- mock 的 `tool_call`/`tool_result` 帧增加 `subagentId` 字段示例。

## Assumptions & Decisions

1. **子 agent 内部思考文字不展示**（用户选"任务+内嵌步骤"，非"任务+实时思考"）；后端在子 agent chunk 中只处理 ToolMessage，跳过 AIMessageChunk。
2. **task() 工具调用不在思考区重复显示**：后端对 task() 的 ToolMessage 不发 `tool_call`/`tool_result`，改发 `subagent_start`/`subagent_done`；前端 onToolCall/onToolResult 对 `name==='task'` 防御性 return。
3. **subagentId 用 langgraph 的 base namespace 字符串** `'tools:<tid>'`（opaque，前端只做相等匹配）。
4. **并行前端天然支持**：按 subagentId 聚合，多卡片堆叠；后端不改 task() 调用语义。
5. **待认领 task() 的匹配**：子 agent 首个 chunk 到达时取 `pending_task_calls` 中第一个未认领项；串行场景下唯一，并行场景下按到达顺序认领（描述与 tid 的精确映射依赖 langgraph 顺序，边界情况下仍能展示，仅 description 可能错配——可接受，因当前后端串行）。
6. **不改后端 agent 装配**（`runtime.py` / `prompts.py` 不动），只改 SSE 流式层与前端。
7. **类型安全**：所有新增 TS 字段可选，旧后端/旧 mock 不发新事件也不会报错。

## Verification

1. **后端形状确认**（实现时第一步）：
   ```bash
   python -c "
   import asyncio
   from agent_core.runtime import build_agent
   a = build_agent(hitl=False)
   async def main():
       async for item in a.astream({'messages':[{'role':'user','content':'搜一下 langgraph 子图流式'}]}, config={'configurable':{'thread_id':'t1'}}, stream_mode='messages', subgraphs=True):
           print(type(item), repr(item)[:0], getattr(item,'__len__',lambda:None)())
           break
   asyncio.run(main())
   ```
   确认 `item` 是 `(namespace_tuple, (chunk, meta))` 形状，再定解构方式。

2. **后端 SSE 联调**：启动 `python -m entrypoints.web`，前端发一条会触发 research-agent 的消息（如"帮我搜一下 X 并写成 md"），用 `curl -N` 或浏览器 DevTools Network 看 SSE 帧，确认顺序为：`start` → `tool_call(name=task)`（不发，被抑制）→ `subagent_start` → 若干 `tool_call`/`tool_result`（带 subagentId）→ `subagent_done` → `delta`（最终答案）→ `done`。

3. **前端 mock 联调**：`node scripts/mock-sse-server.mjs` + `npm run dev`，确认 FloatingTodoList 出现"子智能体"分区、嵌套步骤、并行多卡片、状态图标与配色正确、全部完成自动折叠。

4. **前端类型检查**：`cd agent-frontend && npm run type-check`（或 `vue-tsc --noEmit`）通过。

5. **回归**：发一条不触发子 agent 的普通消息（如"现在几点"），确认 FloatingTodoList 行为不变、思考区 toolCalls 正常显示、无空"子智能体"分区。

6. **并行展示验证**（mock 演示）：mock 同时发两条 `subagent_start`（不同 subagentId），确认前端两张卡片并存且步骤各自归属正确。
