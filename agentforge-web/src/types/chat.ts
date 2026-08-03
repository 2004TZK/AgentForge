/** 对话相关类型 */
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  /** 引用来源（助手消息） */
  sources?: string[]
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
