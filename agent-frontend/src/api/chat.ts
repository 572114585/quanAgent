/**
 * Chat API 端点模块。
 *
 * 实际部署时把 VITE_API_BASE_URL 改为你的 Agent 后端地址（设置面板里也可以改）。
 * 协议：POST {baseURL}/chat，请求体 ChatRequest，响应 text/event-stream 帧内容
 * 遵循 StreamEvent 格式：
 *   { type: 'start' | 'delta' | 'tool' | 'interrupt' | 'done' | 'error' | 'usage', ... }
 *
 * 配套端点：
 *   POST {baseURL}/chat/resume  HITL 中断后提交决定
 *   POST {baseURL}/upload       FormData 单文件上传，返回 { url, name, mime, size }
 */
import type { ChatRequest, StreamEvent, InterruptGroup, ResumeGroup, Message, TodoItem, Session } from '@/types/domain'
import { chatStream, resumeStream, getRuntimeBaseUrl } from './sse'

export interface StreamHandlers {
  onStart?: (messageId: string) => void
  onDelta: (delta: string) => void
  onThinking?: () => void
  onThinkingDelta?: (delta: string) => void
  onTool?: (tool: { name: string; args?: string; preview?: string }) => void
  /** 新协议：工具开始调用（独立于最终答案，进入 message.toolCalls；subagentId 非空=子智能体内部步骤） */
  onToolCall?: (call: { callId: string; name: string; args?: string | Record<string, any>; subagentId?: string }) => void
  /** 新协议：工具执行完成（补全 message.toolCalls 中对应条目；subagentId 非空=子智能体内部步骤） */
  onToolResult?: (payload: { callId: string; name: string; output?: string; error?: string; subagentId?: string }) => void
  /** 子智能体 task() 启动 —— 进入任务进度区的"子智能体"分区 */
  onSubagentStart?: (p: { subagentId: string; subagentType: string; description: string }) => void
  /** 子智能体 task() 结束 —— 把对应卡片置为已完成 */
  onSubagentDone?: (p: { subagentId: string }) => void
  onInterrupt?: (groups: InterruptGroup[]) => void
  onUsage?: (usage: { prompt: number; completion: number }) => void
  onArtifact?: (artifact: { name: string; path: string; url: string; mime: string; size: number }) => void
  onError?: (message: string) => void
  onDone?: () => void
}

/**
 * 消费 SSE 流直至结束或被 abort，统一分发事件到 handlers。
 * 提取自 sendChatMessage / resumeChat 的公共逻辑，消除重复 switch。
 */
async function consumeStream(
  stream: AsyncGenerator<StreamEvent>,
  handlers: StreamHandlers
): Promise<void> {
  let sawError: string | null = null
  for await (const evt of stream) {
    switch (evt.type) {
      case 'start':
        handlers.onStart?.(evt.messageId)
        break
      case 'delta':
        handlers.onDelta(evt.delta)
        break
      case 'thinking':
        handlers.onThinking?.()
        break
      case 'thinking_delta':
        handlers.onThinkingDelta?.(evt.delta)
        break
      case 'tool':
        handlers.onTool?.({ name: evt.name, args: evt.args, preview: evt.preview })
        break
      case 'tool_call':
        handlers.onToolCall?.({ callId: evt.callId, name: evt.name, args: evt.args, subagentId: evt.subagentId })
        break
      case 'tool_result':
        handlers.onToolResult?.({
          callId: evt.callId,
          name: evt.name,
          output: evt.output,
          error: evt.error,
          subagentId: evt.subagentId
        })
        break
      case 'subagent_start':
        handlers.onSubagentStart?.({
          subagentId: evt.subagentId,
          subagentType: evt.subagentType,
          description: evt.description
        })
        break
      case 'subagent_done':
        handlers.onSubagentDone?.({ subagentId: evt.subagentId })
        break
      case 'interrupt':
        handlers.onInterrupt?.(evt.groups)
        break
      case 'usage':
        handlers.onUsage?.({
          prompt: evt.promptTokens,
          completion: evt.completionTokens
        })
        break
      case 'artifact':
        handlers.onArtifact?.({ name: evt.name, path: evt.path, url: evt.url, mime: evt.mime, size: evt.size })
        break
      case 'ping':
        break
      case 'error':
        sawError = evt.message
        handlers.onError?.(evt.message)
        break
      case 'done':
        handlers.onDone?.()
        break
    }
  }
  if (sawError) throw new ChatStreamError(sawError)
}

/**
 * 发送消息并通过 SSE 流式接收响应。
 */
export async function sendChatMessage(
  req: ChatRequest,
  signal: AbortSignal,
  handlers: StreamHandlers
): Promise<void> {
  await consumeStream(
    chatStream(req, { signal, onUsage: handlers.onUsage }),
    handlers
  )
}

/**
 * HITL 批准/拒绝后继续流式输出。
 * decisions 按 interrupt_id 分组，与后端 ResumeRequest 一一对应。
 */
export async function resumeChat(
  sessionId: string,
  decisions: ResumeGroup[],
  signal: AbortSignal,
  handlers: StreamHandlers
): Promise<void> {
  await consumeStream(
    resumeStream({ sessionId, decisions }, { signal, onUsage: handlers.onUsage }),
    handlers
  )
}

/** 上传单个文件，返回后端分配的 URL。 */
export async function uploadFile(file: File): Promise<{
  url: string
  name: string
  mime: string
  size: number
}> {
  const base = getRuntimeBaseUrl()
  const url = base ? `${base.replace(/\/+$/, '')}/upload` : '/upload'
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(url, { method: 'POST', body: fd })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      if (data?.detail) detail += `: ${data.detail}`
    } catch {
      /* ignore */
    }
    throw new ChatStreamError(detail)
  }
  return (await res.json()) as { url: string; name: string; mime: string; size: number }
}

/** GET /chat/messages 的返回结构：历史消息 + todos + 是否有 pending interrupt。 */
export interface HistoryResponse {
  sessionId: string
  messages: Message[]
  todos: TodoItem[]
  hasInterrupt: boolean
}

/**
 * 拉取某 session 的完整历史消息（后端 SqliteSaver checkpoint 为唯一数据源）。
 * 供前端打开会话时恢复 messagesBySession，避免刷新/重启后消息丢失。
 */
export async function fetchHistory(sessionId: string): Promise<HistoryResponse> {
  const base = getRuntimeBaseUrl()
  const url = base
    ? `${base.replace(/\/+$/, '')}/chat/messages?sessionId=${encodeURIComponent(sessionId)}`
    : `/chat/messages?sessionId=${encodeURIComponent(sessionId)}`
  const res = await fetch(url)
  if (!res.ok) {
    let detail = `HTTP ${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      if (data?.message) detail += `: ${data.message}`
    } catch {
      /* ignore */
    }
    throw new ChatStreamError(detail)
  }
  return (await res.json()) as HistoryResponse
}

/** GET /chat/sessions 的返回结构：所有持久化会话列表 */
export interface SessionsListResponse {
  sessions: Session[]
}

/**
 * 从后端拉取所有持久化的会话线程列表。
 * 前端刷新后用此接口恢复会话列表，解决本地存储清空后历史会话丢失的问题。
 */
export async function fetchSessions(): Promise<Session[]> {
  const base = getRuntimeBaseUrl()
  const url = base ? `${base.replace(/\/+$/, '')}/chat/sessions` : '/chat/sessions'
  try {
    const res = await fetch(url)
    if (!res.ok) return []
    const data = (await res.json()) as SessionsListResponse
    return Array.isArray(data?.sessions) ? data.sessions : []
  } catch {
    return []
  }
}

/** 暴露给 store 的命名导出，供旧引用 / 未来扩展用。 */
export const abortStream = (c: AbortController | null) => {
  if (c) c.abort()
}

export class ChatStreamError extends Error {
  status?: number
  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ChatStreamError'
    this.status = status
  }
}

// 重新导出 StreamEvent 方便上层使用
export type { StreamEvent }
