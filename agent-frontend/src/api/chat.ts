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
 *
 * 兼容入口：如果后端走 OpenAI 兼容协议（chunk.choices[0].delta.content），
 * 可在 chatStream 内增加分支解析；Phase 3 默认走自定义 StreamEvent。
 */
import type { ChatRequest, StreamEvent, ToolCallRequest } from '@/types/domain'
import { chatStream } from './sse'

export interface StreamHandlers {
  onStart?: (messageId: string) => void
  onDelta: (delta: string) => void
  onThinking?: () => void
  onThinkingDelta?: (delta: string) => void
  onTool?: (tool: { name: string; args?: string; preview?: string }) => void
  onInterrupt?: (toolCalls: ToolCallRequest[]) => void
  onUsage?: (usage: { prompt: number; completion: number }) => void
  onArtifact?: (artifact: { name: string; path: string; url: string; mime: string; size: number }) => void
  onError?: (message: string) => void
  onDone?: () => void
}

/**
 * 消费 SSE 流直至结束或被 abort。
 *  - delta：逐片调用 onDelta
 *  - tool：调用 onTool 显示工具调用摘要
 *  - interrupt：调用 onInterrupt 触发 HITL 审批 UI
 *  - done：调用 onDone 后正常返回
 *  - error：调用 onError 后抛 ChatStreamError，由 store 标 status=error
 */
export async function sendChatMessage(
  req: ChatRequest,
  signal: AbortSignal,
  handlers: StreamHandlers
): Promise<void> {
  let sawError: string | null = null
  for await (const evt of chatStream(req, { signal, onUsage: handlers.onUsage })) {
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
 * HITL 批准/拒绝后继续流式输出。
 * 复用 sendChatMessage 之外的 /chat/resume 端点。
 */
export async function resumeChat(
  sessionId: string,
  decisions: Array<{ type: 'approve' | 'reject' }>,
  signal: AbortSignal,
  handlers: StreamHandlers
): Promise<void> {
  const { resumeStream } = await import('./sse')
  let sawError: string | null = null
  for await (const evt of resumeStream({ sessionId, decisions }, { signal, onUsage: handlers.onUsage })) {
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
      case 'interrupt':
        handlers.onInterrupt?.(evt.toolCalls)
        break
      case 'usage':
        handlers.onUsage?.({ prompt: evt.promptTokens, completion: evt.completionTokens })
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

/** 上传单个文件，返回后端分配的 URL。 */
export async function uploadFile(file: File): Promise<{
  url: string
  name: string
  mime: string
  size: number
}> {
  const { getRuntimeBaseUrl } = await import('./sse')
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
