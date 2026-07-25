/**
 * SSE 客户端封装 —— 基于原生 fetch + ReadableStream 解析 text/event-stream。
 * 同时兼容浏览器 fetch 和 Tauri WebView 内的 fetch。
 * 支持 AbortSignal、60s 空闲超时、`data: [DONE]` 终止符。
 */
import type { ChatRequest, StreamEvent, ResumeGroup } from '@/types/domain'

const IDLE_TIMEOUT_MS = 60_000

/** 运行时可被设置面板覆盖的 baseURL，优先级高于 import.meta.env。 */
let runtimeBaseUrl = ''

/** 暴露给 store / 设置面板的 setter，仅本进程生效，不写盘。 */
export function setRuntimeBaseUrl(url: string) {
  runtimeBaseUrl = (url || '').trim()
}

/** 把 baseURL 与 path 拼接，避免双斜杠 / 漏斜杠。 */
function joinUrl(base: string, path: string): string {
  if (!base) return path
  const a = base.replace(/\/+$/, '')
  const b = path.replace(/^\/+/, '')
  return `${a}/${b}`
}

/** 解析当前生效的 baseURL。 */
function resolveBaseURL(): string {
  return (
    runtimeBaseUrl ||
    (import.meta.env.VITE_API_BASE_URL as string | undefined) ||
    ''
  )
}

/** Bearer Token：VITE_AGENT_API_TOKEN；未配置时不附加 Authorization。 */
export function resolveApiToken(): string {
  return ((import.meta.env.VITE_AGENT_API_TOKEN as string | undefined) || '').trim()
}

/** 供 SSE / REST 共用的鉴权头。 */
export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { ...(extra || {}) }
  const token = resolveApiToken()
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

/** 解析 SSE 一帧，支持多行 data 合并与 id: 字段；遇到空行返回 null。 */
function parseSseFrame(frame: string): (StreamEvent & { _sseId?: string }) | null {
  if (!frame) return null
  const normalized = frame.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const dataLines: string[] = []
  let sseId = ''
  for (const raw of normalized.split('\n')) {
    const line = raw
    if (!line) continue
    if (line.startsWith(':')) continue
    const idMatch = /^id:\s?(.*)$/.exec(line)
    if (idMatch) {
      sseId = idMatch[1]
      continue
    }
    const m = /^data:\s?(.*)$/.exec(line)
    if (m) dataLines.push(m[1])
  }
  if (dataLines.length === 0) return null
  const payload = dataLines.join('\n')
  if (payload === '[DONE]') {
    return { type: 'done', messageId: '', eventId: sseId || undefined, _sseId: sseId || undefined }
  }
  try {
    const parsed = JSON.parse(payload) as StreamEvent
    if (sseId && !parsed.eventId) {
      ;(parsed as StreamEvent & { eventId?: string }).eventId = sseId
    }
    return { ...parsed, _sseId: sseId || undefined }
  } catch {
    return { type: 'error', message: `无法解析 SSE 帧: ${payload.slice(0, 120)}` }
  }
}

/** 读取器：把流式文本按 SSE 帧（空行分隔）切出来。支持 \n\n / \r\n\r\n / \r\r 分隔符。 */
async function* iterSseFrames(
  body: ReadableStream<Uint8Array>,
  signal: AbortSignal
): AsyncGenerator<string> {
  const reader = body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let timedOut = false

  const FRAME_SEP_RE = /\r\n\r\n|\n\n|\r\r/g

  try {
    while (true) {
      if (signal.aborted) return
      const readPromise = reader.read()
      let timer: ReturnType<typeof setTimeout> | null = null
      const timeoutPromise = new Promise<{ done: true; value: undefined }>((resolve) => {
        timer = setTimeout(() => {
          timedOut = true
          resolve({ done: true, value: undefined })
        }, IDLE_TIMEOUT_MS)
      })
      readPromise.finally(() => {
        if (timer) clearTimeout(timer)
      })
      const result = await Promise.race([readPromise, timeoutPromise])
      if (timedOut) {
        throw new Error('连接中断，请重试')
      }
      const value = result.value
      const done = result.done
      buffer += decoder.decode(value || new Uint8Array(), { stream: true })

      let sepIdx = -1
      let sepLen = 0
      FRAME_SEP_RE.lastIndex = 0
      const m = FRAME_SEP_RE.exec(buffer)
      if (m) {
        sepIdx = m.index
        sepLen = m[0].length
      }
      while (sepIdx >= 0) {
        const frame = buffer.slice(0, sepIdx)
        buffer = buffer.slice(sepIdx + sepLen)
        if (frame.trim()) yield frame
        FRAME_SEP_RE.lastIndex = 0
        const next = FRAME_SEP_RE.exec(buffer)
        if (next) {
          sepIdx = next.index
          sepLen = next[0].length
        } else {
          sepIdx = -1
        }
      }

      if (done) {
        if (buffer.trim()) yield buffer
        return
      }
    }
  } finally {
    try {
      reader.releaseLock()
    } catch {
      /* ignore */
    }
  }
}

export interface ChatStreamOptions {
  signal: AbortSignal
  /** 当服务端推送 usage 事件时回调（仅做透传统计）。 */
  onUsage?: (u: { prompt: number; completion: number }) => void
  /** 每个事件携带 eventId 时回调，供断线补流游标。 */
  onEventId?: (eventId: string, runId?: string) => void
}

/**
 * 通用流式 POST：把请求体 JSON 化后 POST 到 {baseURL}{path}，按 SSE 解析。
 * 内部使用，被 chatStream / resumeStream 复用。
 */
async function* postStream(
  path: string,
  body: any,
  signal: AbortSignal,
  onUsage?: (u: { prompt: number; completion: number }) => void,
  onEventId?: (eventId: string, runId?: string) => void
): AsyncGenerator<StreamEvent> {
  if (signal.aborted) return

  const baseURL = resolveBaseURL()
  const url = joinUrl(baseURL, path)

  const resp = await fetch(url, {
    method: 'POST',
    headers: authHeaders({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream, application/json;q=0.9, */*;q=0.5'
    }),
    body: JSON.stringify(body),
    signal
  }).catch((err: unknown) => {
    if ((err as { name?: string })?.name === 'AbortError') throw err
    throw new Error(`网络错误: ${(err as Error)?.message ?? String(err)}`)
  })

  if (!resp.ok) {
    let msg = `HTTP ${resp.status}`
    try {
      const ct = resp.headers.get('content-type') || ''
      if (ct.includes('application/json')) {
        const data = (await resp.json()) as { message?: string; error?: string; detail?: string }
        msg = data.message || data.error || data.detail || msg
      } else {
        const text = await resp.text()
        if (text) msg = text.slice(0, 200)
      }
    } catch {
      /* ignore */
    }
    yield { type: 'error', message: msg }
    yield { type: 'done', messageId: '' }
    return
  }

  const contentType = resp.headers.get('content-type') || ''
  if (!contentType.includes('text/event-stream')) {
    try {
      const data = (await resp.json()) as { content?: string; message?: string }
      if (typeof data.content === 'string') yield { type: 'delta', delta: data.content }
      else if (data.message) yield { type: 'error', message: data.message }
    } catch (err) {
      yield { type: 'error', message: `解析响应失败: ${(err as Error).message}` }
    }
    yield { type: 'done', messageId: '' }
    return
  }

  if (!resp.body) {
    yield { type: 'error', message: '响应体为空' }
    yield { type: 'done', messageId: '' }
    return
  }

  let sawDone = false
  const seenEventIds = new Set<string>()
  try {
    for await (const frame of iterSseFrames(resp.body, signal)) {
      const evt = parseSseFrame(frame)
      if (!evt) continue
      const eventId = evt.eventId || evt._sseId
      if (eventId) {
        if (seenEventIds.has(eventId)) continue
        seenEventIds.add(eventId)
        onEventId?.(eventId, evt.runId)
      }
      const { _sseId: _drop, ...clean } = evt as StreamEvent & { _sseId?: string }
      if (clean.type === 'usage') {
        onUsage?.({
          prompt: clean.promptTokens,
          completion: clean.completionTokens
        })
        continue
      }
      if (clean.type === 'done') {
        sawDone = true
        yield clean
        return
      }
      if (clean.type === 'error') {
        yield clean
        yield { type: 'done', messageId: '' }
        return
      }
      yield clean
    }
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') return
    yield { type: 'error', message: (err as Error)?.message ?? '连接中断，请重试' }
  }

  if (!sawDone) yield { type: 'done', messageId: '' }
}

/**
 * 流式调用 chat 接口，异步产出 StreamEvent。
 * 复用 postStream 通用逻辑，避免重复代码。
 */
export async function* chatStream(
  req: ChatRequest,
  opts: ChatStreamOptions
): AsyncGenerator<StreamEvent> {
  yield* postStream('/chat', req, opts.signal, opts.onUsage, opts.onEventId)
}

/** 获取当前生效的 baseURL（供 uploadFile 等使用）。 */
export function getRuntimeBaseUrl(): string {
  return resolveBaseURL()
}

/** HITL resume 专用流。body.decisions 按 interrupt_id 分组，与后端 ResumeRequest 对齐。 */
export async function* resumeStream(
  body: { sessionId: string; decisions: ResumeGroup[]; mode?: string },
  opts: ChatStreamOptions
): AsyncGenerator<StreamEvent> {
  yield* postStream('/chat/resume', body, opts.signal, opts.onUsage, opts.onEventId)
}
