/** 对话相关类型 */

/** 助手消息状态：streaming 打字机中 / done 完成 / error 失败 */
export type ChatMessageStatus = 'streaming' | 'done' | 'error'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  /** 引用来源（助手消息） */
  sources?: string[]
  /** 助手消息流式/失败状态（用户消息与历史消息无该字段） */
  status?: ChatMessageStatus
  /** 失败原因（status=error 时展示） */
  error?: string
}

/** 历史记录条目 */
export interface ConversationItem {
  id: number
  agentId: number
  userMessage: string
  assistantMessage: string
  createdTime: string
}

/** 发送消息返回 */
export interface ChatResult {
  answer: string
  sources: string[]
  toolCalls: string[]
}

/** 文档 */
export interface DocumentItem {
  id: number
  agentId: number
  fileName: string
  fileType: string
  status: 'PENDING' | 'PROCESSING' | 'READY' | 'FAILED'
  createdTime: string
}
