/** 工作流（M3 Workflow v1）相关类型 */

/** 流程节点（线性链） */
export interface WorkflowNode {
  nodeKey: string
  /** llm / tool */
  nodeType: 'llm' | 'tool'
  /** 节点参数（tool 名与 payload / llm 提示词模板；支持 {var} 模板） */
  params: Record<string, unknown>
  /** 下一节点键（null=流程结束） */
  nextNode: string | null
}

export interface Workflow {
  id: number
  name: string
  description: string | null
  creatorId: number
  status: string
  createdTime: string
  nodes: WorkflowNode[]
}

/** 节点级执行日志 */
export interface WorkflowNodeLog {
  node: string
  type: string
  status: 'SUCCESS' | 'FAILED'
  output: string
  error: string | null
  durationMs: number
}

/** 运行记录 */
export interface WorkflowRun {
  id: number
  workflowId: number
  agentId: number | null
  status: 'RUNNING' | 'SUCCESS' | 'FAILED'
  input: Record<string, unknown>
  output: string
  nodeLogs: WorkflowNodeLog[]
  error: string
  startedTime: string
  finishedTime: string
}

/** 创建/更新入参 */
export interface WorkflowPayload {
  name: string
  description?: string
  nodes: WorkflowNode[]
}
