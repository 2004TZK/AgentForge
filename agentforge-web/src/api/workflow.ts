/** 工作流接口：定义 CRUD / 触发运行 / 运行记录 */
import { http } from '../utils/request'
import type { PageQuery, PageResult } from '../types/api'
import type { Workflow, WorkflowPayload, WorkflowRun } from '../types/workflow'

export function apiWorkflowPage(params: PageQuery): Promise<PageResult<Workflow>> {
  return http.get<PageResult<Workflow>>('/workflows', params as Record<string, unknown>)
}

export function apiWorkflowDetail(id: number): Promise<Workflow> {
  return http.get<Workflow>(`/workflows/${id}`)
}

export function apiCreateWorkflow(data: WorkflowPayload): Promise<Workflow> {
  return http.post<Workflow>('/workflows', data)
}

export function apiUpdateWorkflow(id: number, data: WorkflowPayload): Promise<Workflow> {
  return http.put<Workflow>(`/workflows/${id}`, data)
}

export function apiDeleteWorkflow(id: number): Promise<void> {
  return http.del<void>(`/workflows/${id}`)
}

/** 触发运行（input 为模板变量，如 {"message": "..."}） */
export function apiRunWorkflow(id: number, input: Record<string, unknown>): Promise<WorkflowRun> {
  return http.post<WorkflowRun>(`/workflows/${id}/run`, { input })
}

export function apiWorkflowRuns(
  id: number,
  params: PageQuery,
): Promise<PageResult<WorkflowRun>> {
  return http.get<PageResult<WorkflowRun>>(`/workflows/${id}/runs`, params as Record<string, unknown>)
}

export function apiWorkflowRunDetail(runId: number): Promise<WorkflowRun> {
  return http.get<WorkflowRun>(`/workflows/runs/${runId}`)
}
