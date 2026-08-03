/** Agent 接口：分页 / 详情 / 创建 / 更新 / 删除 / 工具元数据 */
import { http } from '../utils/request'
import type { PageQuery, PageResult } from '../types/api'
import type { AgentDetail, AgentItem, AgentPayload, ToolMeta } from '../types/agent'

export function apiAgentPage(params: PageQuery & { name?: string }): Promise<PageResult<AgentItem>> {
  return http.get<PageResult<AgentItem>>('/agent/page', params as Record<string, unknown>)
}

export function apiAgentDetail(id: number): Promise<AgentDetail> {
  return http.get<AgentDetail>(`/agent/${id}`)
}

export function apiCreateAgent(data: AgentPayload): Promise<AgentDetail> {
  return http.post<AgentDetail>('/agent', data)
}

export function apiUpdateAgent(id: number, data: AgentPayload): Promise<AgentDetail> {
  return http.put<AgentDetail>(`/agent/${id}`, data)
}

export function apiDeleteAgent(id: number): Promise<void> {
  return http.del<void>(`/agent/${id}`)
}

/** 工具元数据列表（M3：前端按 Schema 渲染工具配置表单） */
export function apiToolsMeta(): Promise<ToolMeta[]> {
  return http.get<ToolMeta[]>('/tools/meta')
}
