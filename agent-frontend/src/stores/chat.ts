/**
 * Chat store —— 拥有每个 session 的消息与中止器。
 * 走 src/api/chat.ts 的 sendChatMessage / resumeChat。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Message, MessageStatus, Attachment, ArtifactFile } from '@/types/domain'
import { sendChatMessage, resumeChat } from '@/api/chat'

export type ChatMessage = Message

function uid(prefix = 'm') {
  return `${prefix}_${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36)}`
}

interface SendOptions {
  attachments?: Attachment[]
}

export const useChatStore = defineStore('chat', () => {
  /** Keyed by sessionId. Phase 4 will swap to persistent storage. */
  const messagesBySession = ref<Record<string, ChatMessage[]>>({})
  /** Abort controllers per session for in-flight streams. */
  const aborters = ref<Record<string, AbortController | null>>({})
  /** Phase 3 placeholder: 上传中的文件。Phase 4/5 进一步持久化。 */
  const pendingAttachments = ref<Record<string, Attachment[]>>({})

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
          onStart: () => {
            msg.status = 'streaming'
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
          onInterrupt: (toolCalls) => {
            msg.pendingToolCalls = toolCalls
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
  async function resume(sessionId: string, decisions: Array<{ type: 'approve' | 'reject' }>) {
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
    // arr 是 reactive 数组，arr[i] 返回的是代理对象，可直接操作
    const msg = lastApprovalMsg

    msg.status = 'streaming'
    msg.pendingToolCalls = undefined
    if (decisions.length > 0) {
      msg.hitlNote = `✅ 用户决定：${decisions
        .map((d) => (d.type === 'approve' ? '批准' : '拒绝'))
        .join('、')}`
    }
    sessions.touch(sessionId)

    const controller = new AbortController()
    aborters.value[sessionId] = controller

    try {
      await resumeChat(sessionId, decisions, controller.signal, {
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
          if (!msg.toolCalls) msg.toolCalls = []
          msg.toolCalls.push({
            id: call.callId ?? uid('tc'),
            name: call.name,
            args: call.args,
            status: 'running'
          })
        },
        onToolResult: (payload) => {
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
        onInterrupt: (toolCalls) => {
          msg.pendingToolCalls = toolCalls
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
      })
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        if (msg.status === 'streaming') msg.status = 'cancelled'
      } else {
        msg.status = 'error'
        msg.error = String(err?.message ?? err)
      }
    } finally {
      aborters.value[sessionId] = null
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

  return {
    messagesBySession,
    pendingAttachments,
    list,
    append,
    setStatus,
    appendDelta,
    appendThinkingDelta,
    addArtifact,
    addToolCall,
    updateToolResult,
    clear,
    stop,
    send,
    resume,
    regenerate,
    addPendingAttachment,
    takePendingAttachments
  }
})
