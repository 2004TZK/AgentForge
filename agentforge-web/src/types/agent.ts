/** 智能体相关类型 */
export interface AgentTool {
  toolName: string
  toolConfig: Record<string, unknown>
  enabled: boolean
}

/** 列表项 */
export interface AgentItem {
  id: number
  name: string
  description: string | null
  modelName: string
  temperature: number
  creatorId: number
  createdTime: string
}

/** 详情（编辑回显） */
export interface AgentDetail extends AgentItem {
  systemPrompt: string
  tools: AgentTool[]
}

/** 创建/更新入参 */
export interface AgentPayload {
  name: string
  description?: string
  systemPrompt: string
  modelName: string
  temperature: number
  tools: { toolName: string; toolConfig: Record<string, unknown>; enabled: boolean }[]
}
