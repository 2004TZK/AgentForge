/** 对话接口：发送消息（同步/SSE 流式）/ 历史查询 */
import { http } from '../utils/request'
import { getToken } from '../utils/auth'
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

/** SSE 事件（与后端 /chat/stream 对齐） */
export interface ChatStreamEvent {
  type: 'delta' | 'done' | 'error'
  content?: string
  answer?: string
  sources?: string[]
  toolCalls?: string[]
  code?: number
  message?: string
}

export interface ChatStreamHandlers {
  onDelta: (content: string) => void
  onDone: (result: ChatResult) => void
  onError: (message: string) => void
}

/**
 * SSE 流式发送：fetch + ReadableStream 逐块解析（axios 无法流式读取响应）。
 * 事件协议：delta 增量 / done 汇总（含完整答案）/ error 失败。
 * 流中断（未收到 done/error 即结束）时以 onError('回答中断') 回调；
 * 主动取消（signal abort）时抛出 AbortError，由调用方决定消息状态。
 */
export async function apiChatStream(
  agentId: number,
  message: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const base = import.meta.env.VITE_API_BASE || '/api'
  const token = getToken()
  let res: Response
  try {
    res = await fetch(`${base}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ agentId, message }),
      signal,
    })
  } catch (e) {
    if (isAbort(e)) throw e
    handlers.onError('网络错误，无法连接服务器')
    return
  }

  // 非 2xx（401 登录过期 / 参数错误等）：后端返回统一 Result JSON
  if (!res.ok || !res.body) {
    let errMsg = `请求失败（HTTP ${res.status}）`
    try {
      const data = await res.json()
      if (data?.message) errMsg = data.message
    } catch {
      /* 非 JSON 错误体，使用默认提示 */
    }
    handlers.onError(errMsg)
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let settled = false

  const dispatch = (event: ChatStreamEvent): void => {
    settled = true
    switch (event.type) {
      case 'delta':
        if (event.content) handlers.onDelta(event.content)
        break
      case 'done':
        handlers.onDone({
          answer: event.answer || '',
          sources: event.sources || [],
          toolCalls: event.toolCalls || [],
        })
        break
      case 'error':
        handlers.onError(event.message || '回答失败')
        break
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE 事件以空行分隔；逐块解析 data 行（注释/空行忽略）
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        const dataLine = block.split('\n').find((l) => l.startsWith('data:'))
        if (!dataLine) continue
        const raw = dataLine.slice('data:'.length).trim()
        if (!raw) continue
        try {
          dispatch(JSON.parse(raw) as ChatStreamEvent)
        } catch {
          /* 忽略无法解析的事件 */
        }
      }
    }
    // 流正常结束但未收到终端事件：视为连接中断
    if (!settled) handlers.onError('回答中断，请重试')
  } catch (e) {
    if (isAbort(e)) throw e
    handlers.onError('回答中断，请重试')
  }
}

export function isAbort(e: unknown): boolean {
  return e instanceof DOMException && e.name === 'AbortError'
}
