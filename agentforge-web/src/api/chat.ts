/** 对话接口：发送消息 / 历史查询 */
import { http } from '../utils/request'
import type { PageQuery, PageResult } from '../types/api'
import type { ChatResult, ConversationItem } from '../types/chat'

export function apiSendMessage(agentId: number, message: string): Promise<ChatResult> {
  return http.post<ChatResult>('/chat', { agentId, message })
}

export function apiChatHistory(
  agentId: number,
  params: PageQuery,
): Promise<PageResult<ConversationItem>> {
  return http.get<PageResult<ConversationItem>>('/chat/history', {
    agentId,
    ...params,
  })
}
