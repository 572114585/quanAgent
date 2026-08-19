/**
 * Chat store —— 拥有每个 session 的消息与中止器。
 * 走 src/api/chat.ts 的 sendChatMessage / resumeChat。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Message, MessageStatus, Attachment, ArtifactFile, TodoItem, TodoStatus, SubagentTask, ResumeGroup, WebReference, AgentMode } from '@/types/domain'
import { sendChatMessage, resumeChat, fetchHistory, cancelRun, fetchState } from '@/api/chat'

export type ChatMessage = Message

function uid(prefix = 'm') {
  return `${prefix}_${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36)}`
}

/**
 * 从 write_todos 工具调用的 args 中解析 todo 列表。
 * args 可能为 string(JSON) 或 object，todos 字段是完整的任务列表（每次调用整体替换）。
 * 解析失败返回 null（不更新现有 todo）。
 */
function parseTodosFromArgs(args: string | Record<string, any> | undefined): TodoItem[] | null {
  if (!args) return null
  let obj: any
  if (typeof args === 'string') {
    try {
      obj = JSON.parse(args)
    } catch {
      return null
    }
  } else {
    obj = args
  }
  const raw = obj?.todos
  if (!Array.isArray(raw)) return null
  const validStatuses: TodoStatus[] = ['pending', 'in_progress', 'completed']
  const todos: TodoItem[] = []
  for (const item of raw) {
    if (item && typeof item === 'object' && typeof item.content === 'string') {
      const status: TodoStatus = validStatuses.includes(item.status) ? item.status : 'pending'
      todos.push({ content: item.content, status })
    }
  }
  return todos
}

function parseWebRefsFromOutput(output: string | undefined): WebReference[] | null {
  if (!output) return null
  const match = output.match(/<!--WEB_REFS:(.+?)-->/s)
  if (!match) return null
  try {
    const arr = JSON.parse(match[1])
    if (!Array.isArray(arr)) return null
    const refs: WebReference[] = []
    for (const item of arr) {
      if (item && typeof item === 'object' && item.url) {
        refs.push({
          title: String(item.title ?? ''),
          url: String(item.url ?? ''),
          snippet: String(item.snippet ?? ''),
          provider: item.provider != null ? String(item.provider) : undefined,
        })
      }
    }
    return refs
  } catch {
    return null
  }
}

function mergeWebRefs(msg: ChatMessage, refs: WebReference[]) {
  if (!msg.webReferences) msg.webReferences = []
  for (const r of refs) {
    if (!msg.webReferences.find((x) => x.url === r.url)) {
      msg.webReferences.push(r)
    }
  }
}

interface SendOptions {
  attachments?: Attachment[]
}

export const useChatStore = defineStore('chat', () => {
  /** Keyed by sessionId. 消息正文不在前端本地持久化，由后端 SqliteSaver checkpoint 兜底，loadHistory() 拉取恢复。 */
  const messagesBySession = ref<Record<string, ChatMessage[]>>({})
  /** Abort controllers per session for in-flight streams. */
  const aborters = ref<Record<string, AbortController | null>>({})
  /** 当前活跃 runId / 最后收到的 eventId（按 session） */
  const runIdBySession = ref<Record<string, string | null>>({})
  const lastEventIdBySession = ref<Record<string, string | null>>({})
  /** Phase 3 placeholder: 上传中的文件。Phase 4/5 进一步持久化。 */
  const pendingAttachments = ref<Record<string, Attachment[]>>({})
  /** Agent 通过 write_todos 工具维护的待办列表（按 session 存储，整体替换语义）。 */
  const todosBySession = ref<Record<string, TodoItem[]>>({})
  /** 子智能体任务（task() 触发）按 session 存储；并行子 agent = 数组多元素。 */
  const subagentTasksBySession = ref<Record<string, SubagentTask[]>>({})
  /** Agent / Plan 模式（发给后端 mode 字段） */
  const agentMode = ref<AgentMode>('agent')

  function setAgentMode(mode: AgentMode) {
    agentMode.value = mode === 'plan' ? 'plan' : 'agent'
  }
  function list(sessionId: string): ChatMessage[] {
    return messagesBySession.value[sessionId] ?? []
  }

  function append(sessionId: string, msg: ChatMessage) {
    if (!messagesBySession.value[sessionId]) messagesBySession.value[sessionId] = []
    messagesBySession.value[sessionId].push(msg)
  }

  function setStatus(sessionId: string, id: string, status: MessageStatus, error?: string) {
    const arr = messagesBySession.value[sessionId]
    if (!arr) return
    const m = arr.find((x) => x.id === id)
    if (m) {
      m.status = status
      if (error !== undefined) m.error = error
    }
  }

  function appendDelta(sessionId: string, id: string, delta: string) {
    const arr = messagesBySession.value[sessionId]
    if (!arr) return
    const m = arr.find((x) => x.id === id)
    if (m) m.content += delta
  }

  function appendThinkingDelta(sessionId: string, id: string, delta: string) {
    const arr = messagesBySession.value[sessionId]
    if (!arr) return
    const m = arr.find((x) => x.id === id)
    if (m) {
      m.hasThought = true
      if (!m.thinkingContent) m.thinkingContent = ''
      m.thinkingContent += delta
    }
  }

  function addToolCall(sessionId: string, id: string, call: { callId?: string; name: string; args?: string | Record<string, any> }) {
    const arr = messagesBySession.value[sessionId]
    if (!arr) return
    const m = arr.find((x) => x.id === id)
    if (!m) return
    if (!m.toolCalls) m.toolCalls = []
    m.toolCalls.push({
      id: call.callId ?? uid('tc'),
      name: call.name,
      args: call.args,
      status: 'running'
    })
  }

  function updateToolResult(
    sessionId: string,
    id: string,
    payload: { callId?: string; name: string; output?: string; error?: string }
  ) {
    const arr = messagesBySession.value[sessionId]
    if (!arr) return
    const m = arr.find((x) => x.id === id)
    if (!m || !m.toolCalls) return
    // 优先按 callId 精确匹配，否则按 name 反向找最近一条 running
    let record = payload.callId
      ? m.toolCalls.find((tc) => tc.id === payload.callId)
      : undefined
    if (!record) {
      for (let i = m.toolCalls.length - 1; i >= 0; i--) {
        if (m.toolCalls[i].name === payload.name && m.toolCalls[i].status === 'running') {
          record = m.toolCalls[i]
          break
        }
      }
    }
    if (!record) {
      // 没找到对应 running 条目 → 新建一条 completed 记录
      m.toolCalls.push({
        id: payload.callId ?? uid('tc'),
        name: payload.name,
        output: payload.output,
        error: payload.error,
        status: payload.error ? 'failed' : 'completed'
      })
      return
    }
    record.output = payload.output
    record.error = payload.error
    record.status = payload.error ? 'failed' : 'completed'
  }

  function addArtifact(sessionId: string, id: string, artifact: ArtifactFile) {
    const arr = messagesBySession.value[sessionId]
    if (!arr) return
    const m = arr.find((x) => x.id === id)
    if (!m) return
    if (!m.artifacts) m.artifacts = []
    if (!m.artifacts.find((a) => a.path === artifact.path)) {
      m.artifacts.push(artifact)
    }
  }

  function clear(sessionId: string) {
    messagesBySession.value[sessionId] = []
  }

  function stop(sessionId: string) {
    const runId = runIdBySession.value[sessionId]
    void cancelRun(sessionId, runId)
    const c = aborters.value[sessionId]
    if (c) c.abort()
    aborters.value[sessionId] = null
    const arr = messagesBySession.value[sessionId]
    if (arr) {
      for (const m of arr) {
        if (m.status === 'streaming' || m.status === 'pending') {
          m.status = 'cancelled'
        }
      }
    }
  }

  /** 正在加载历史的 session 集合，避免并发重复请求。 */
  const loadingSet = ref<Set<string>>(new Set())

  /**
   * 从后端拉取历史消息恢复到 messagesBySession。
   * 后端 SqliteSaver checkpoint 是唯一数据源，前端不本地持久化消息正文。
   * 已加载 / 正在加载 / 已有内存数据（如正在流式）时跳过，避免覆盖。
   *
   * 失败时不写空数组：空数组 [] 是 truthy，会被上方 guard 当作"已加载"
   * 阻止重试。保持 undefined 让用户刷新/重进会话时能重新拉取。
   * ChatPanel 的 messages computed 用 `?? []` 兜底，undefined 不影响渲染。
   */
  async function loadHistory(sessionId: string) {
    if (messagesBySession.value[sessionId] || loadingSet.value.has(sessionId)) return
    loadingSet.value.add(sessionId)
    try {
      const data = await fetchHistory(sessionId)
      // 并发场景：加载期间若已被 send() 填充，则不覆盖
      if (!messagesBySession.value[sessionId]) {
        messagesBySession.value[sessionId] = data.messages
      }
      if (data.todos?.length && !todosBySession.value[sessionId]) {
        todosBySession.value[sessionId] = data.todos
      }
      // HITL 恢复：messages 已可能带 awaiting_approval；否则再拉 /chat/state
      let groups = data.interruptGroups
      if (data.hasInterrupt && (!groups || groups.length === 0)) {
        try {
          const state = await fetchState(sessionId)
          groups = state.interruptGroups
        } catch {
          /* ignore */
        }
      }
      if (data.hasInterrupt && groups && groups.length > 0) {
        const arr = messagesBySession.value[sessionId]
        if (arr) {
          for (let i = arr.length - 1; i >= 0; i--) {
            if (arr[i].role === 'assistant') {
              arr[i].status = 'awaiting_approval'
              arr[i].pendingInterruptGroups = groups
              break
            }
          }
        }
      }
    } catch (err) {
      console.error('[chat] loadHistory failed', err)
    } finally {
      loadingSet.value.delete(sessionId)
    }
  }

  /**
   * 发送一条消息：创建 user + assistant 占位、调 SSE 流、根据事件更新 assistant。
   * 内部回调直接操作 reactive 代理引用，避免每次 delta 都做线性查找。
   */
  async function send(sessionId: string, text: string, opts: SendOptions = {}) {
    const { useSessionsStore } = await import('./sessions')
    const sessions = useSessionsStore()
    const session = sessions.list.find((s) => s.id === sessionId)
    if (session && (session.title === '新对话' || !session.title)) {
      sessions.rename(sessionId, text.slice(0, 30) + (text.length > 30 ? '…' : ''))
    }

    const userMsg: ChatMessage = {
      id: uid('u'),
      sessionId,
      role: 'user',
      content: text,
      status: 'complete',
      attachments: opts.attachments,
      createdAt: Date.now()
    }
    const assistantMsg: ChatMessage = {
      id: uid('a'),
      sessionId,
      role: 'assistant',
      content: '',
      hasThought: true,
      status: 'streaming',
      createdAt: Date.now()
    }
    append(sessionId, userMsg)
    append(sessionId, assistantMsg)
    sessions.touch(sessionId)

    // 获取 reactive 代理引用，回调中直接操作，避免逐 token 线性查找
    const arr = messagesBySession.value[sessionId]
    const msg = arr[arr.length - 1]

    const controller = new AbortController()
    aborters.value[sessionId] = controller

    try {
      await sendChatMessage(
        {
          sessionId,
          message: text,
          mode: agentMode.value,
          attachments: opts.attachments?.map((a) => ({
            id: a.id,
            remoteUrl: a.remoteUrl ?? a.previewUrl ?? '',
            name: a.name,
            mime: a.mime,
            size: a.size ?? 0
          }))
        },
        controller.signal,
        {
          onStart: (_messageId, meta) => {
            msg.status = 'streaming'
            if (meta?.runId) runIdBySession.value[sessionId] = meta.runId
          },
          onEventMeta: ({ eventId, runId }) => {
            if (runId) runIdBySession.value[sessionId] = runId
            if (eventId) lastEventIdBySession.value[sessionId] = eventId
          },
          onDelta: (delta) => {
            msg.content += delta
          },
          onThinking: () => {
            msg.hasThought = true
          },
          onThinkingDelta: (delta) => {
            msg.hasThought = true
            if (!msg.thinkingContent) msg.thinkingContent = ''
            msg.thinkingContent += delta
          },
          onTool: (tool) => {
            // 旧协议兼容：写入 toolCalls 数组，不污染最终答案
            if (!msg.toolCalls) msg.toolCalls = []
            msg.toolCalls.push({
              id: uid('tc'),
              name: tool.name,
              args: tool.args,
              output: tool.preview,
              status: 'completed'
            })
          },
          onToolCall: (call) => {
            // write_todos 工具：解析 args.todos 更新 session 级待办列表，
            // 不进入 toolCalls 数组（升级为专门悬浮 UI，避免重复显示）
            if (call.name === 'write_todos') {
              const todos = parseTodosFromArgs(call.args)
              if (todos) todosBySession.value[sessionId] = todos
              return
            }
            // task() 工具调用：后端已改发 subagent_start/subagent_done，这里防御性跳过
            if (call.name === 'task') return
            // 子智能体内部工具调用（带 subagentId）→ 进入对应子 agent 卡片的 steps，
            // 不进 message.toolCalls（避免与思考区重复）
            if (call.subagentId) {
              addSubagentStep(sessionId, call.subagentId, {
                id: call.callId ?? uid('tc'),
                name: call.name,
                args: call.args
              })
              return
            }
            // 新协议：工具开始 → 进入 toolCalls 数组（独立于最终答案）
            if (!msg.toolCalls) msg.toolCalls = []
            msg.toolCalls.push({
              id: call.callId ?? uid('tc'),
              name: call.name,
              args: call.args,
              status: 'running'
            })
          },
          onToolResult: (payload) => {
            // 新协议：工具返回 → 补全对应条目
            // write_todos 已在 onToolCall 处理，跳过避免新建记录污染工具列表
            if (payload.name === 'write_todos') return
            if (payload.name === 'task') return
            // 子智能体内部工具返回 → 补全对应子 agent 卡片的 step
            if (payload.subagentId) {
              // 塞进 msg.kbReferences 供最终答案下方引用面板渲染
              
              if (payload.name === 'web_search' || payload.name === 'web_fetch') {
                const refs = parseWebRefsFromOutput(payload.output)
                if (refs && refs.length > 0) mergeWebRefs(msg, refs)
              }
              finishSubagentStep(sessionId, payload.subagentId, payload)
              return
            }
            if (!msg.toolCalls) return
            let record = payload.callId
              ? msg.toolCalls.find((tc) => tc.id === payload.callId)
              : undefined
            if (!record) {
              for (let i = msg.toolCalls.length - 1; i >= 0; i--) {
                if (msg.toolCalls[i].name === payload.name && msg.toolCalls[i].status === 'running') {
                  record = msg.toolCalls[i]
                  break
                }
              }
            }
            if (!record) {
              msg.toolCalls.push({
                id: payload.callId ?? uid('tc'),
                name: payload.name,
                output: payload.output,
                error: payload.error,
                status: payload.error ? 'failed' : 'completed'
              })
              return
            }
            record.output = payload.output
            record.error = payload.error
            record.status = payload.error ? 'failed' : 'completed'
          },
          onSubagentStart: (p) => {
            addSubagentTask(sessionId, p)
          },
          onSubagentDone: (p) => {
            finishSubagentTask(sessionId, p.subagentId)
          },
          onInterrupt: (groups) => {
            msg.pendingInterruptGroups = groups
            msg.status = 'awaiting_approval'
          },
          onError: (message) => {
            msg.status = 'error'
            msg.error = message
          },
          onUsage: (usage) => {
            msg.usage = usage
          },
          onArtifact: (artifact) => {
            if (!msg.artifacts) msg.artifacts = []
            if (!msg.artifacts.find((a) => a.path === artifact.path)) {
              msg.artifacts.push(artifact)
            }
          },
          onDone: () => {
            if (msg.status === 'streaming') msg.status = 'complete'
          }
        }
      )
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        if (msg.status === 'streaming') msg.status = 'cancelled'
      } else if (err?.name === 'ChatStreamError') {
        msg.status = 'error'
        msg.error = err.message
      } else {
        msg.status = 'error'
        msg.error = String(err?.message ?? err)
      }
    } finally {
      aborters.value[sessionId] = null
      if (msg.status !== 'awaiting_approval' && msg.status !== 'streaming') {
        runIdBySession.value[sessionId] = null
      }
      const msgs = messagesBySession.value[sessionId]
      if (msgs) {
        sessions.touch(sessionId, { messageCount: msgs.length })
      }
    }
  }

  /**
   * HITL 审批：批准/拒绝后继续流式输出。
   * 复用 lastApprovalMsg 的 reactive 代理引用，回调直接操作。
   */
  async function resume(sessionId: string, groups: ResumeGroup[]) {
    const { useSessionsStore } = await import('./sessions')
    const sessions = useSessionsStore()

    const arr = messagesBySession.value[sessionId]
    if (!arr) return
    let lastApprovalMsg: ChatMessage | undefined
    for (let i = arr.length - 1; i >= 0; i--) {
      if (arr[i].status === 'awaiting_approval') {
        lastApprovalMsg = arr[i]
        break
      }
    }
    if (!lastApprovalMsg) return
    const msg = lastApprovalMsg

    // 失败时恢复审批 UI，避免「已点批准但没执行」的错觉
    const savedPending = msg.pendingInterruptGroups
    msg.status = 'streaming'
    msg.pendingInterruptGroups = undefined
    msg.error = undefined
    const flatDecisions = groups.flatMap((g) => g.decisions ?? [])
    if (flatDecisions.length > 0) {
      msg.hitlNote = `✅ 用户决定：${flatDecisions
        .map((d) => (d.type === 'approve' ? '批准' : '拒绝'))
        .join('、')}`
    }
    sessions.touch(sessionId)

    const controller = new AbortController()
    aborters.value[sessionId] = controller

    try {
      await resumeChat(
        sessionId,
        groups,
        controller.signal,
        {
        onStart: (_messageId, meta) => {
          msg.status = 'streaming'
          if (meta?.runId) runIdBySession.value[sessionId] = meta.runId
        },
        onEventMeta: ({ eventId, runId }) => {
          if (runId) runIdBySession.value[sessionId] = runId
          if (eventId) lastEventIdBySession.value[sessionId] = eventId
        },
        onDelta: (delta) => {
          msg.content += delta
        },
        onThinkingDelta: (delta) => {
          msg.hasThought = true
          if (!msg.thinkingContent) msg.thinkingContent = ''
          msg.thinkingContent += delta
        },
        onTool: (tool) => {
          if (!msg.toolCalls) msg.toolCalls = []
          msg.toolCalls.push({
            id: uid('tc'),
            name: tool.name,
            args: tool.args,
            output: tool.preview,
            status: 'completed'
          })
        },
        onToolCall: (call) => {
          if (call.name === 'write_todos') {
            const todos = parseTodosFromArgs(call.args)
            if (todos) todosBySession.value[sessionId] = todos
            return
          }
          if (call.name === 'task') return
          if (call.subagentId) {
            addSubagentStep(sessionId, call.subagentId, {
              id: call.callId ?? uid('tc'),
              name: call.name,
              args: call.args
            })
            return
          }
          if (!msg.toolCalls) msg.toolCalls = []
          msg.toolCalls.push({
            id: call.callId ?? uid('tc'),
            name: call.name,
            args: call.args,
            status: 'running'
          })
        },
        onToolResult: (payload) => {
          if (payload.name === 'write_todos') return
          if (payload.name === 'task') return
          if (payload.subagentId) {
            
            if (payload.name === 'web_search' || payload.name === 'web_fetch') {
              const refs = parseWebRefsFromOutput(payload.output)
              if (refs && refs.length > 0) mergeWebRefs(msg, refs)
            }
            finishSubagentStep(sessionId, payload.subagentId, payload)
            return
          }
          if (!msg.toolCalls) return
          let record = payload.callId
            ? msg.toolCalls.find((tc) => tc.id === payload.callId)
            : undefined
          if (!record) {
            for (let i = msg.toolCalls.length - 1; i >= 0; i--) {
              if (msg.toolCalls[i].name === payload.name && msg.toolCalls[i].status === 'running') {
                record = msg.toolCalls[i]
                break
              }
            }
          }
          if (!record) {
            msg.toolCalls.push({
              id: payload.callId ?? uid('tc'),
              name: payload.name,
              output: payload.output,
              error: payload.error,
              status: payload.error ? 'failed' : 'completed'
            })
            return
          }
          record.output = payload.output
          record.error = payload.error
          record.status = payload.error ? 'failed' : 'completed'
        },
        onSubagentStart: (p) => {
          addSubagentTask(sessionId, p)
        },
        onSubagentDone: (p) => {
          finishSubagentTask(sessionId, p.subagentId)
        },
        onInterrupt: (groups) => {
          msg.pendingInterruptGroups = groups
          msg.status = 'awaiting_approval'
        },
        onError: (message) => {
          msg.status = 'error'
          msg.error = message
        },
        onUsage: (usage) => {
          msg.usage = usage
        },
        onArtifact: (artifact) => {
          if (!msg.artifacts) msg.artifacts = []
          if (!msg.artifacts.find((a) => a.path === artifact.path)) {
            msg.artifacts.push(artifact)
          }
        },
        onDone: () => {
          if (msg.status === 'streaming') msg.status = 'complete'
        }
      },
        { mode: agentMode.value }
      )
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        if (msg.status === 'streaming') msg.status = 'cancelled'
      } else {
        msg.status = 'error'
        msg.error = String(err?.message ?? err)
        // resume 失败：恢复待审批 UI，或从 /chat/state 拉取
        try {
          const state = await fetchState(sessionId)
          if (state.interruptGroups && state.interruptGroups.length > 0) {
            msg.pendingInterruptGroups = state.interruptGroups
            msg.status = 'awaiting_approval'
            msg.hitlNote = undefined
          } else if (savedPending && savedPending.length > 0) {
            msg.pendingInterruptGroups = savedPending
            msg.status = 'awaiting_approval'
            msg.hitlNote = undefined
          }
        } catch {
          if (savedPending && savedPending.length > 0) {
            msg.pendingInterruptGroups = savedPending
            msg.status = 'awaiting_approval'
            msg.hitlNote = undefined
          }
        }
      }
    } finally {
      aborters.value[sessionId] = null
      if (msg.status !== 'awaiting_approval' && msg.status !== 'streaming') {
        runIdBySession.value[sessionId] = null
      }
      const msgs = messagesBySession.value[sessionId]
      if (msgs) {
        sessions.touch(sessionId, { messageCount: msgs.length })
      }
    }
  }

  /**
   * 重新生成最后一条 assistant 回复。
   */
  async function regenerate(sessionId: string) {
    const arr = messagesBySession.value[sessionId]
    if (!arr) return
    let lastUserIdx = -1
    for (let i = arr.length - 1; i >= 0; i--) {
      if (arr[i].role === 'user') {
        lastUserIdx = i
        break
      }
    }
    if (lastUserIdx < 0) return
    const kept = arr.slice(0, lastUserIdx + 1)
    messagesBySession.value[sessionId] = kept
    const last = kept[lastUserIdx]
    await send(sessionId, last.content, { attachments: last.attachments })
  }

  /** 把附件挂到「下一条发送」上（Phase 5 完整集成，Phase 3 简化为发时即传）。 */
  function addPendingAttachment(sessionId: string, a: Attachment) {
    if (!pendingAttachments.value[sessionId]) pendingAttachments.value[sessionId] = []
    pendingAttachments.value[sessionId].push(a)
  }
  function takePendingAttachments(sessionId: string): Attachment[] {
    const out = pendingAttachments.value[sessionId] ?? []
    pendingAttachments.value[sessionId] = []
    return out
  }

  /** 清空指定 session 的待办列表（如切换/清空会话时） */
  function clearTodos(sessionId: string) {
    delete todosBySession.value[sessionId]
  }

  /** 清空指定 session 的子智能体任务列表 */
  function clearSubagents(sessionId: string) {
    delete subagentTasksBySession.value[sessionId]
  }

  /** 子智能体启动：新增一张 running 卡片 */
  function addSubagentTask(sessionId: string, p: { subagentId: string; subagentType: string; description: string }) {
    if (!subagentTasksBySession.value[sessionId]) subagentTasksBySession.value[sessionId] = []
    if (!subagentTasksBySession.value[sessionId].find((s) => s.id === p.subagentId)) {
      subagentTasksBySession.value[sessionId].push({
        id: p.subagentId,
        subagentType: p.subagentType,
        description: p.description,
        status: 'running',
        steps: []
      })
    }
  }

  /** 子智能体结束：把对应卡片置为已完成 */
  function finishSubagentTask(sessionId: string, subagentId: string) {
    const arr = subagentTasksBySession.value[sessionId]
    if (!arr) return
    const task = arr.find((s) => s.id === subagentId)
    if (task) task.status = 'completed'
  }

  /** 子智能体内部工具调用开始：追加一条 running 步骤 */
  function addSubagentStep(
    sessionId: string,
    subagentId: string,
    step: { id: string; name: string; args?: string | Record<string, any> }
  ) {
    const arr = subagentTasksBySession.value[sessionId]
    if (!arr) return
    const task = arr.find((s) => s.id === subagentId)
    if (!task) return
    if (!task.steps.find((st) => st.id === step.id)) {
      task.steps.push({ id: step.id, name: step.name, args: step.args, status: 'running' })
    }
  }

  /** 子智能体内部工具返回：补全对应步骤的 output/status */
  function finishSubagentStep(
    sessionId: string,
    subagentId: string,
    payload: { callId?: string; name: string; output?: string; error?: string }
  ) {
    const arr = subagentTasksBySession.value[sessionId]
    if (!arr) return
    const task = arr.find((s) => s.id === subagentId)
    if (!task) return
    let step = payload.callId ? task.steps.find((st) => st.id === payload.callId) : undefined
    if (!step) {
      for (let i = task.steps.length - 1; i >= 0; i--) {
        if (task.steps[i].name === payload.name && task.steps[i].status === 'running') {
          step = task.steps[i]
          break
        }
      }
    }
    if (!step) {
      task.steps.push({
        id: payload.callId ?? uid('tc'),
        name: payload.name,
        output: payload.output,
        error: payload.error,
        status: payload.error ? 'failed' : 'completed'
      })
      return
    }
    step.output = payload.output
    step.error = payload.error
    step.status = payload.error ? 'failed' : 'completed'
  }

  return {
    messagesBySession,
    pendingAttachments,
    todosBySession,
    subagentTasksBySession,
    agentMode,
    setAgentMode,
    list,
    append,
    setStatus,
    appendDelta,
    appendThinkingDelta,
    addArtifact,
    addToolCall,
    updateToolResult,
    clear,
    clearTodos,
    clearSubagents,
    stop,
    loadHistory,
    send,
    resume,
    regenerate,
    addPendingAttachment,
    takePendingAttachments
  }
})
