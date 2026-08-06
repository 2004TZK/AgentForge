/** 对话接口：发送消息（同步/SSE 流式）/ 历史查询 / 会话管理 */
import { http } from '../utils/request'
import { getToken } from '../utils/auth'
import type { PageQuery, PageResult } from '../types/api'
import type { ChatResult, ConversationItem, SessionItem, SourceItem } from '../types/chat'

export function apiSendMessage(
  agentId: number,
  sessionId: number,
  message: string,
): Promise<ChatResult> {
  return http.post<ChatResult>('/chat', { agentId, sessionId, message })
}

export function apiChatHistory(
  agentId: number,
  sessionId: number,
  params: PageQuery,
): Promise<PageResult<ConversationItem>> {
  return http.get<PageResult<ConversationItem>>('/chat/history', {
    agentId,
    sessionId,
    ...params,
  })
}

/** 会话列表（按最后活跃倒序） */
export function apiSessionList(agentId: number): Promise<SessionItem[]> {
  return http.get<SessionItem[]>('/chat/session/list', { agentId })
}

/** 新建会话 */
export function apiSessionCreate(agentId: number, name?: string): Promise<SessionItem> {
  return http.post<SessionItem>('/chat/session', { agentId, name })
}

/** 删除会话 */
export function apiSessionDelete(id: number): Promise<void> {
  return http.del<void>(`/chat/session/${id}`)
}

/** 工具执行事件（M3：tool 轮执行结果，实时展示工具活动） */
export interface ToolEvent {
  name: string
  arguments: Record<string, unknown>
  result: string
}

/** SSE 事件（与后端 /chat/stream 对齐；M3 新增 tool 类型） */
export interface ChatStreamEvent {
  type: 'delta' | 'done' | 'error' | 'tool'
  content?: string
  answer?: string
  sources?: SourceItem[]
  toolCalls?: string[]
  code?: number
  message?: string
  /** tool 事件的附加字段 */
  name?: string
  arguments?: Record<string, unknown>
  result?: string
}

export interface ChatStreamHandlers {
  onDelta: (content: string) => void
  onDone: (result: ChatResult) => void
  onError: (message: string) => void
  /** M3：工具执行完成（tool 事件） */
  onTool?: (event: ToolEvent) => void
}

/**
 * SSE 流式发送：fetch + ReadableStream 逐块解析（axios 无法流式读取响应）。
 * 事件协议：delta 增量 / done 汇总（含完整答案）/ error 失败。
 * 流中断（未收到 done/error 即结束）时以 onError('回答中断') 回调；
 * 主动取消（signal abort）时抛出 AbortError，由调用方决定消息状态。
 */
export async function apiChatStream(
  agentId: number,
  sessionId: number,
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
      body: JSON.stringify({ agentId, sessionId, message }),
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
    switch (event.type) {
      case 'delta':
        if (event.content) handlers.onDelta(event.content)
        break
      case 'done':
        settled = true
        handlers.onDone({
          answer: event.answer || '',
          sources: event.sources || [],
          toolCalls: event.toolCalls || [],
        })
        break
      case 'error':
        settled = true
        handlers.onError(event.message || '回答失败')
        break
      case 'tool':
        if (handlers.onTool) {
          handlers.onTool({
            name: event.name || '',
            arguments: event.arguments || {},
            result: event.result || '',
          })
        }
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
    // 流结束后处理残余 buffer：最后一个 SSE 帧可能没有结尾空行（帧尾被截断）
    if (buffer.trim()) {
      const dataLine = buffer.split('\n').find((l) => l.startsWith('data:'))
      if (dataLine) {
        const raw = dataLine.slice('data:'.length).trim()
        if (raw) {
          try {
            dispatch(JSON.parse(raw) as ChatStreamEvent)
          } catch {
            /* 忽略无法解析的残余帧 */
          }
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
