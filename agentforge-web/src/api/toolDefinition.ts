/** 自定义工具定义接口：CRUD / 复制 / 测试 */
import { http } from '../utils/request'
import type { PageQuery, PageResult } from '../types/api'
import type {
  ToolDefinition,
  ToolDefinitionPayload,
  ToolTestPayload,
  ToolTestResult,
} from '../types/toolDefinition'

export function apiToolDefinitionPage(
  params: PageQuery & { keyword?: string },
): Promise<PageResult<ToolDefinition>> {
  return http.get<PageResult<ToolDefinition>>('/tool-definitions/page', params as Record<string, unknown>)
}

export function apiToolDefinitionDetail(id: number): Promise<ToolDefinition> {
  return http.get<ToolDefinition>(`/tool-definitions/${id}`)
}

export function apiCreateToolDefinition(data: ToolDefinitionPayload): Promise<ToolDefinition> {
  return http.post<ToolDefinition>('/tool-definitions', data)
}

export function apiUpdateToolDefinition(id: number, data: ToolDefinitionPayload): Promise<ToolDefinition> {
  return http.put<ToolDefinition>(`/tool-definitions/${id}`, data)
}

export function apiDeleteToolDefinition(id: number): Promise<void> {
  return http.del<void>(`/tool-definitions/${id}`)
}

export function apiCopyToolDefinition(id: number): Promise<ToolDefinition> {
  return http.post<ToolDefinition>(`/tool-definitions/${id}/copy`)
}

/** 测试工具定义（HTTP 直发 / 代码进沙箱真实执行） */
export function apiTestToolDefinition(data: ToolTestPayload): Promise<ToolTestResult> {
  return http.post<ToolTestResult>('/tool-definitions/test', data)
}
