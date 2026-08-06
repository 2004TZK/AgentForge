/** 用户自定义工具类型（工具定义开发文档 v3.0 §5.1） */

/** HTTP 请求定义 */
export interface HttpConfig {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS'
  url: string
  headers?: Record<string, string>
  bodyTemplate?: Record<string, unknown> | string
  query?: Record<string, string>
  auth?: {
    type: 'api_key' | 'bearer' | 'basic'
    headerName?: string
    value?: unknown
  }
  timeoutSeconds?: number
}

/** 代码定义 */
export interface ScriptConfig {
  language: 'python' | 'javascript'
  source: string
  entrypoint?: string
}

/** 工具定义（列表/详情） */
export interface ToolDefinition {
  id: number
  creatorId: number
  name: string
  displayName: string
  description: string | null
  toolType: 'http' | 'script'
  /** OpenAI function parameters：{type: 'object', properties, required?} */
  parameters: Record<string, unknown>
  /** 密钥字段已脱敏为 ******** */
  httpConfig: HttpConfig | null
  scriptConfig: ScriptConfig | null
  visibility: 'PRIVATE' | 'PUBLIC'
  createdTime: string
  updatedTime: string
}

/** 创建/更新入参 */
export interface ToolDefinitionPayload {
  name: string
  displayName: string
  description?: string
  toolType: 'http' | 'script'
  parameters: Record<string, unknown>
  httpConfig?: HttpConfig | null
  scriptConfig?: ScriptConfig | null
  visibility: 'PRIVATE' | 'PUBLIC'
}

/** 测试入参 */
export interface ToolTestPayload {
  toolType: 'http' | 'script'
  httpConfig?: HttpConfig | null
  scriptConfig?: ScriptConfig | null
  parameters?: Record<string, unknown>
  args: Record<string, unknown>
}

/** 测试出参 */
export interface ToolTestResult {
  ok: boolean
  result: unknown
  stdout: string
  error: string
  durationMs: number
}

/** 参数 Schema 行（行式编辑器用） */
export interface ParamRow {
  key: string
  type: string
  description: string
  required: boolean
}
