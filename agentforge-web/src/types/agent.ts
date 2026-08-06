/** 智能体相关类型 */

/** 工具配置项 Schema（M3：后端透传 AI 服务 /tools/meta，前端按此渲染配置表单） */
export interface ToolMeta {
  name: string
  description: string
  /** LLM 工具调用参数 {参数名: {type, description, required?}} */
  parameters: Record<string, { type: string; description?: string; required?: boolean }>
  /** 智能体级配置参数 {参数名: {type, description}}（存 tool_config） */
  config: Record<string, { type: string; description?: string }>
}

export interface AgentTool {
  toolName: string
  /** M5：工具来源 builtin=内置 / custom=我的自定义工具 */
  toolSource?: 'builtin' | 'custom'
  /** M5：自定义工具定义 ID（toolSource=custom 时） */
  toolDefinitionId?: number | null
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
  /** M3：运行模式 chat / workflow */
  mode: string
  /** M3：绑定的工作流 ID（mode=workflow 时生效） */
  workflowId: number | null
  /** M4：可见性 PUBLIC 公开 / PRIVATE 私有（仅创建者可见） */
  visibility: string
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
  tools: {
    toolName: string
    toolSource?: 'builtin' | 'custom'
    toolDefinitionId?: number | null
    toolConfig: Record<string, unknown>
    enabled: boolean
  }[]
  mode?: string
  workflowId?: number | null
  visibility?: string
}
