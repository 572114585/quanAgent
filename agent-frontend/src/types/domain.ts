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
  /** 与后端 pending 动作一致的摘要，approve 时必须回传 */
  actionHash?: string
  /** 为何需要审批（来自 execute_policy） */
  riskNote?: string
  riskReason?: string
}

/** ask_user_question 单题 */
export interface AskUserQuestionItem {
  id: string
  prompt: string
  options?: string[] | null
  allowMultiple?: boolean
  allowFreeText?: boolean
}

/** 用户对单题的回答 */
export interface AskUserAnswer {
  questionId: string
  selected: string[]
  text: string
}

export type InterruptKind = 'tool_approval' | 'ask_user_question'

/** HITL 中断分组：一个 interrupt_id 下可能含多个并发工具调用，或一份问卷 */
export interface InterruptGroup {
  interruptId: string
  kind?: InterruptKind
  toolCalls?: ToolCallRequest[]
  title?: string
  questions?: AskUserQuestionItem[]
  /** 组级 hash（通常等于首个 toolCall 的 actionHash） */
  actionHash?: string
}

/** 单个工具调用的批准/拒绝决定 */
export type ResumeDecision = { type: 'approve' | 'reject' }

/** 恢复请求里按 interrupt_id 分组的决定 */
export interface ResumeGroup {
  interruptId: string
  kind?: InterruptKind
  decisions?: ResumeDecision[]
  answers?: AskUserAnswer[]
  /** 批准时必填，与 pending 动作绑定 */
  actionHash?: string
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

export interface WebReference {
  title: string
  url: string
  snippet: string
  provider?: string
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
  pendingInterruptGroups?: InterruptGroup[]
  usage?: { prompt: number; completion: number }
  webReferences?: WebReference[]
  /** 前端记录的本次 agent 执行开始时间与最终耗时。历史消息可能没有这些字段。 */
  executionStartedAt?: number
  executionDurationMs?: number
}

export interface Session {
  id: string
  title: string
  preview?: string
  createdAt: number
  updatedAt: number
  messageCount: number
}

/** agent=可执行；plan=只规划不写/不 shell */
export type AgentMode = 'agent' | 'plan'

export interface ChatRequest {
  sessionId: string
  message: string
  attachments?: Array<{ id: string; remoteUrl: string; name: string; mime: string; size: number }>
  /** 可选；空则后端用 AGENT_MODE 默认值 */
  mode?: AgentMode
}

export interface ArtifactFile {
  name: string
  path: string
  url: string
  mime: string
  size: number
}

/** Agent 通过 write_todos 工具维护的待办项（与 deepagents TodoListMiddleware 对齐） */
export type TodoStatus = 'pending' | 'in_progress' | 'completed'

export interface TodoItem {
  content: string
  status: TodoStatus
}

/** 子智能体执行过程中的嵌套步骤（其内部工具调用，如 web_search / write_file） */
export interface SubagentStep {
  /** 唯一 id（callId） */
  id: string
  /** 工具名 */
  name: string
  /** 原始入参（字符串 JSON 或对象） */
  args?: string | Record<string, any>
  /** 工具返回结果（已完成时填充） */
  output?: string
  /** 失败原因 */
  error?: string
  /** 执行状态 */
  status: 'running' | 'completed' | 'failed'
}

/** 子智能体任务（由主 agent 的 task() 工具触发） */
export interface SubagentTask {
  /** subagentId，后端用 langgraph base namespace 'tools:<tid>' */
  id: string
  subagentType: string
  /** 任务描述（task() 入参的 description） */
  description: string
  /** 整体状态：运行中 / 已完成 */
  status: 'running' | 'completed'
  /** 前端记录的子智能体执行时间。 */
  startedAt?: number
  durationMs?: number
  /** 内部工具调用步骤 */
  steps: SubagentStep[]
}

/** schemaVersion 3：公共字段 runId/eventId；未知字段应忽略以保持兼容 */
type StreamEventBase = {
  runId?: string
  eventId?: string
  schemaVersion?: number
}

export type StreamEvent = StreamEventBase & (
  | { type: 'start'; messageId: string }
  /** 最终答案的 token 增量 —— 进入 message.content */
  | { type: 'delta'; delta: string }
  /** 思考过程开始标记（用于展开思考区） */
  | { type: 'thinking' }
  /** 思考 / 规划 token 增量 —— 进入 message.thinkingContent */
  | { type: 'thinking_delta'; delta: string }
  /** 工具开始调用 —— 新增：与最终答案解耦，进入 message.toolCalls（subagentId 非空=子智能体内部步骤） */
  | { type: 'tool_call'; callId: string; name: string; args?: string | Record<string, any>; subagentId?: string }
  /** 工具执行完成 —— 新增：补全对应 callId 的 output / status（subagentId 非空=子智能体内部步骤） */
  | { type: 'tool_result'; callId: string; name: string; output?: string; error?: string; subagentId?: string; denied?: boolean }
  | { type: 'done'; messageId: string }
  /** 子智能体 task() 启动 —— 进入任务进度区的"子智能体"分区 */
  | { type: 'subagent_start'; subagentId: string; subagentType: string; description: string }
  /** 子智能体 task() 结束 —— 把对应卡片置为已完成 */
  | { type: 'subagent_done'; subagentId: string }
  /** 旧协议兼容：tool 结果预览（旧后端会发这个，前端降级追加到 thinking 区） */
  | { type: 'tool'; name: string; args?: string; preview?: string }
  | { type: 'interrupt'; groups: InterruptGroup[] }
  | { type: 'usage'; promptTokens: number; completionTokens: number }
  | { type: 'artifact'; name: string; path: string; url: string; mime: string; size: number }
  | { type: 'error'; message: string; activeRunId?: string }
  | { type: 'ping'; ts: number }
)
