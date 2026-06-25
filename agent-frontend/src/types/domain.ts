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

export interface Message {
  id: string
  sessionId: string
  role: Role
  content: string
  thinkingContent?: string
  hasThought?: boolean
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
  | { type: 'delta'; delta: string }
  | { type: 'thinking' }
  | { type: 'thinking_delta'; delta: string }
  | { type: 'tool'; name: string; args?: string; preview?: string }
  | { type: 'interrupt'; toolCalls: ToolCallRequest[] }
  | { type: 'usage'; promptTokens: number; completionTokens: number }
  | { type: 'artifact'; name: string; path: string; url: string; mime: string; size: number }
  | { type: 'done'; messageId: string }
  | { type: 'error'; message: string }
  | { type: 'ping'; ts: number }
