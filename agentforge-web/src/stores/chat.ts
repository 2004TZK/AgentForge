/** 会话状态：消息列表 / 会话列表（M2 多会话）/ 流式发送 / 历史加载 / 失败重试 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  apiChatHistory,
  apiChatStream,
  apiSessionCreate,
  apiSessionDelete,
  apiSessionList,
  isAbort,
} from '../api/chat'
import type { ChatMessage, SessionItem, StarChartData } from '../types/chat'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const agentId = ref<number | null>(null)
  const sessions = ref<SessionItem[]>([])
  const currentSessionId = ref<number | null>(null)
  const sending = ref(false)
  /** 最近一次用户消息（失败重试用） */
  const lastUserMessage = ref('')
  let abortController: AbortController | null = null

  function reset(agentIdValue: number): void {
    agentId.value = agentIdValue
    messages.value = []
    sessions.value = []
    currentSessionId.value = null
    lastUserMessage.value = ''
    abortController?.abort()
    abortController = null
  }

  /** 加载会话列表；无会话时自动创建一个（保证发送前必有会话） */
  async function ensureSessions(): Promise<void> {
    if (!agentId.value) return
    sessions.value = await apiSessionList(agentId.value)
    if (!sessions.value.length) {
      const session = await apiSessionCreate(agentId.value)
      sessions.value = [session]
    }
    if (!currentSessionId.value || !sessions.value.some((s) => s.id === currentSessionId.value)) {
      currentSessionId.value = sessions.value[0].id
    }
  }

  /** 新建会话并切换 */
  async function createSession(): Promise<void> {
    if (!agentId.value) return
    const session = await apiSessionCreate(agentId.value)
    sessions.value.unshift(session)
    currentSessionId.value = session.id
    messages.value = []
  }

  /** 删除会话（确认后切换回第一个会话） */
  async function deleteSession(sessionId: number): Promise<void> {
    await apiSessionDelete(sessionId)
    sessions.value = sessions.value.filter((s) => s.id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = sessions.value[0]?.id ?? null
      messages.value = []
      if (currentSessionId.value) await loadHistory(agentId.value!, currentSessionId.value)
    }
  }

  /** 加载历史（最近一页，20 条），组装为消息列表（正序） */
  async function loadHistory(agentIdValue: number, sessionId: number): Promise<void> {
    const result = await apiChatHistory(agentIdValue, sessionId, { page: 1, size: 20 })
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
    if (!currentSessionId.value) throw new Error('当前无会话，请先新建会话')
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
        currentSessionId.value,
        content,
        {
          onDelta: (delta) => {
            assistantMessage.content += delta
          },
          onTool: (event) => {
            // M3：工具执行事件实时累积（如 'calculator({...}) → 4'）
            if (!assistantMessage.toolCalls) assistantMessage.toolCalls = []
            assistantMessage.toolCalls.push(
              `${event.name}(${JSON.stringify(event.arguments)}) → ${event.result.slice(0, 120)}`,
            )
            // M2.5/V2：star_chart/transit_chart/progression_chart 返回 JSON 时解析为
            // 结构化数据渲染排盘卡片（transit/progression 顶层字段与本命盘一致，另含扩展区块）
            if (
              ['star_chart', 'transit_chart', 'progression_chart'].includes(event.name)
              && event.result.startsWith('{')
            ) {
              try {
                assistantMessage.chart = JSON.parse(event.result) as StarChartData
              } catch {
                // 解析失败仅保留文本工具记录，不阻塞对话
              }
            }
          },
          onDone: (result) => {
            assistantMessage.content = result.answer
            assistantMessage.sources = result.sources
            assistantMessage.toolCalls = result.toolCalls
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

  return {
    messages,
    agentId,
    sessions,
    currentSessionId,
    sending,
    reset,
    ensureSessions,
    createSession,
    deleteSession,
    loadHistory,
    send,
    stop,
    retry,
  }
})
