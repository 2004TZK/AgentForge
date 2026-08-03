/** 模型 Provider 类型（M4 多模型配置） */

export interface Provider {
  id: number
  name: string
  /** ollama（本地原生）/ openai（OpenAI 兼容） */
  providerType: string
  baseUrl: string
  /** API Key（本地模型为空） */
  apiKey: string | null
  /** 可用模型列表 */
  models: string[]
  enabled: boolean
  /** 0 = 系统内置（不可改删） */
  creatorId: number
  createdTime: string
}

export interface ProviderPayload {
  name: string
  providerType: string
  baseUrl: string
  apiKey?: string
  models: string[]
  enabled: boolean
}
