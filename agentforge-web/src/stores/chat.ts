/** 会话状态：消息列表 / 流式发送（打字机）/ 历史加载 / 失败重试 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { apiChatHistory, apiChatStream, isAbort } from '../api/chat'
import type { ChatMessage } from '../types/chat'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const agentId = ref<number | null>(null)
  const sending = ref(false)
  /** 最近一次用户消息（失败重试用） */
  const lastUserMessage = ref('')
  let abortController: AbortController | null = null

  function reset(agentIdValue: number): void {
    agentId.value = agentIdValue
    messages.value = []
    lastUserMessage.value = ''
    abortController?.abort()
    abortController = null
  }

  /** 加载历史（最近一页，20 条），组装为消息列表（正序） */
  async function loadHistory(agentIdValue: number): Promise<void> {
    const result = await apiChatHistory(agentIdValue, { page: 1, size: 20 })
    messages.value = [...result.list]
      .reverse()
      .flatMap((item) => [
        { role: 'user' as const, content: item.userMessage },
        { role: 'assistant' as const, content: item.assistantMessage, status: 'done' as const },
      ])
  }

  /**
   * 流式发送：追加用户消息 + 占位助手消息，逐块回填内容；
   * done 时回填来源；失败/中断标记为 error 并记录原因（可重试）。
   */
  async function send(content: string): Promise<void> {
    if (!agentId.value) throw new Error('当前未选择智能体')
    if (sending.value) return
    sending.value = true
    lastUserMessage.value = content
    messages.value.push({ role: 'user', content })
    const assistantMessage: ChatMessage = { role: 'assistant', content: '', status: 'streaming' }
    messages.value.push(assistantMessage)
    abortController?.abort()
    abortController = new AbortController()
    try {
      await apiChatStream(
        agentId.value,
        content,
        {
          onDelta: (delta) => {
            assistantMessage.content += delta
          },
          onDone: (result) => {
            assistantMessage.content = result.answer
            assistantMessage.sources = result.sources
            assistantMessage.status = 'done'
          },
          onError: (message) => {
            assistantMessage.status = 'error'
            assistantMessage.error = message
          },
        },
        abortController.signal,
      )
      // 流已结束但未收到 done/error：视为断连
      if (assistantMessage.status === 'streaming') {
        assistantMessage.status = 'error'
        assistantMessage.error = '回答中断，请重试'
      }
    } catch (e) {
      assistantMessage.status = 'error'
      assistantMessage.error = isAbort(e) ? '已停止回答' : '发送失败，请重试'
    } finally {
      sending.value = false
      abortController = null
    }
  }

  /** 停止当前流式回答（已输出的内容保留，标记为 error 可重试） */
  function stop(): void {
    abortController?.abort()
  }

  /** 重试最后一条失败消息：移除末尾失败对（用户消息 + error 助手消息）后重发 */
  function retry(): void {
    if (!lastUserMessage.value || sending.value) return
    const last = messages.value[messages.value.length - 1]
    if (last?.role !== 'assistant' || last.status !== 'error') return
    messages.value.splice(-2)
    void send(lastUserMessage.value)
  }

  return { messages, agentId, sending, reset, loadHistory, send, stop, retry }
})
