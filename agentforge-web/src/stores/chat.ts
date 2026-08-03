/** 会话状态：当前消息列表 / 发送 / 历史加载 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiChatHistory, apiSendMessage } from '../api/chat'
import type { ChatMessage } from '../types/chat'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const agentId = ref<number | null>(null)
  const sending = ref(false)

  function reset(agentIdValue: number): void {
    agentId.value = agentIdValue
    messages.value = []
  }

  /** 加载历史（最近一页，20 条），组装为消息列表（正序） */
  async function loadHistory(agentIdValue: number): Promise<void> {
    const result = await apiChatHistory(agentIdValue, { page: 1, size: 20 })
    messages.value = [...result.list]
      .reverse()
      .flatMap((item) => [
        { role: 'user' as const, content: item.userMessage },
        { role: 'assistant' as const, content: item.assistantMessage },
      ])
  }

  async function send(content: string): Promise<ChatMessage> {
    if (!agentId.value || sending.value) throw new Error('当前未选择智能体')
    sending.value = true
    const userMessage: ChatMessage = { role: 'user', content }
    messages.value.push(userMessage)
    try {
      const result = await apiSendMessage(agentId.value, content)
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: result.answer,
        sources: result.sources,
      }
      messages.value.push(assistantMessage)
      return assistantMessage
    } finally {
      sending.value = false
    }
  }

  return { messages, agentId, sending, reset, loadHistory, send }
})
