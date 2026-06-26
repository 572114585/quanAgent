/**
 * Reusable domain types for chat / sessions / messages.
 * Concrete fields will be tightened once the backend OpenAPI is finalized.
 */

export type Role = 'user' | 'assistant' | 'system'

export type MessageStatus =
  | 'pending'
  | 'streaming'
  | 'complete'
  | 'error'
  | 'cancelled'
  | 'awaiting_approval'

export interface Attachment {
  id: string
  name: string
  mime: string
  size: number
  /** For images: a data: or blob: URL for inline preview. */
  previewUrl?: string
  /** Backend-assigned URL once uploaded. */
  remoteUrl?: string
}

export interface ToolCallRequest {
  name: string
  args?: string | Record<string, any>
  description?: string
}

/** 思考过程中产生的工具调用记录（与最终答案 content 解耦） */
export interface ToolCallRecord {
  /** 唯一 id，前端生成 */
  id: string
  /** 工具名 */
  name: string
  /** 原始入参（字符串 JSON 或对象） */
  args?: string | Record<string, any>
  /** 工具返回结果（已完成时填充） */
  output?: string
  /** 执行状态 */
  status: 'pending' | 'running' | 'completed' | 'failed'
  /** 失败原因 */
  error?: string
}

export interface Message {
  id: string
  sessionId: string
  role: Role
  /** 最终回答正文 —— 思考过程的 token 不应进入这里 */
  content: string
  /** 思考 / 规划 / 内心独白（thinking_delta 累计） */
  thinkingContent?: string
  hasThought?: boolean
  /** 思考过程中产生的工具调用列表（独立渲染到思考区） */
  toolCalls?: ToolCallRecord[]
  /** HITL 批准/拒绝的视觉反馈（如 "✅ 用户决定：批准"）—— 渲染在思考区，不进最终答案 */
  hitlNote?: string
  status: MessageStatus
  attachments?: Attachment[]
  artifacts?: ArtifactFile[]
  createdAt: number
  error?: string
  pendingToolCalls?: ToolCallRequest[]
  usage?: { prompt: number; completion: number }
}

export interface Session {
  id: string
  title: string
  preview?: string
  createdAt: number
  updatedAt: number
  messageCount: number
}

export interface ChatRequest {
  sessionId: string
  message: string
  attachments?: Array<{ id: string; remoteUrl: string; name: string; mime: string; size: number }>
}

export interface ArtifactFile {
  name: string
  path: string
  url: string
  mime: string
  size: number
}

export type StreamEvent =
  | { type: 'start'; messageId: string }
  /** 最终答案的 token 增量 —— 进入 message.content */
  | { type: 'delta'; delta: string }
  /** 思考过程开始标记（用于展开思考区） */
  | { type: 'thinking' }
  /** 思考 / 规划 token 增量 —— 进入 message.thinkingContent */
  | { type: 'thinking_delta'; delta: string }
  /** 工具开始调用 —— 新增：与最终答案解耦，进入 message.toolCalls */
  | { type: 'tool_call'; callId: string; name: string; args?: string | Record<string, any> }
  /** 工具执行完成 —— 新增：补全对应 callId 的 output / status */
  | { type: 'tool_result'; callId: string; name: string; output?: string; error?: string }
  /** 旧协议兼容：tool 结果预览（旧后端会发这个，前端降级追加到 thinking 区） */
  | { type: 'tool'; name: string; args?: string; preview?: string }
  | { type: 'interrupt'; toolCalls: ToolCallRequest[] }
  | { type: 'usage'; promptTokens: number; completionTokens: number }
  | { type: 'artifact'; name: string; path: string; url: string; mime: string; size: number }
  | { type: 'done'; messageId: string }
  | { type: 'error'; message: string }
  | { type: 'ping'; ts: number }
