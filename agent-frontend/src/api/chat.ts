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
import type { ChatRequest, StreamEvent, ToolCallRequest } from '@/types/domain'
import { chatStream, resumeStream, getRuntimeBaseUrl } from './sse'

export interface StreamHandlers {
  onStart?: (messageId: string) => void
  onDelta: (delta: string) => void
  onThinking?: () => void
  onThinkingDelta?: (delta: string) => void
  onTool?: (tool: { name: string; args?: string; preview?: string }) => void
  /** 新协议：工具开始调用（独立于最终答案，进入 message.toolCalls） */
  onToolCall?: (call: { callId: string; name: string; args?: string | Record<string, any> }) => void
  /** 新协议：工具执行完成（补全 message.toolCalls 中对应条目） */
  onToolResult?: (payload: { callId: string; name: string; output?: string; error?: string }) => void
  onInterrupt?: (toolCalls: ToolCallRequest[]) => void
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
        handlers.onToolCall?.({ callId: evt.callId, name: evt.name, args: evt.args })
        break
      case 'tool_result':
        handlers.onToolResult?.({
          callId: evt.callId,
          name: evt.name,
          output: evt.output,
          error: evt.error
        })
        break
      case 'interrupt':
        handlers.onInterrupt?.(evt.toolCalls)
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
 */
export async function resumeChat(
  sessionId: string,
  decisions: Array<{ type: 'approve' | 'reject' }>,
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
