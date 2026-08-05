/** 对话相关类型 */

/** 助手消息状态：streaming 打字机中 / done 完成 / error 失败 */
export type ChatMessageStatus = 'streaming' | 'done' | 'error'

/** 知识库引用来源（M2 起含片段，可点击查看） */
export interface SourceItem {
  file: string
  snippet: string
  score: number
}

/** 星盘点位（行星/四轴）：星座 + 度数 + 黄道经度 */
export interface ChartPoint {
  sign: string
  signIndex: number
  degree: number
  longitude: number
}

/** 行星数据（M2.5 排盘卡片）：落座 × 落宫 × 逆行 */
export interface PlanetData extends ChartPoint {
  house: number
  retrograde: boolean
}

/** 宫位数据 */
export interface HouseData {
  cusp: number
  sign: string
  planets: string[]
}

/** 相位（M2.5 排盘卡片） */
export interface AspectData {
  p1: string
  p2: string
  type: string
  typeEn: string
  orb: number
}

/** 格局（由 star_chart 工具判定，LLM 只解读） */
export interface PatternData {
  type: string
  scope?: string
  house?: number
  sign?: string
  planets: string[]
  apex?: string
}

/** star_chart 工具出参（与 agentforge-ai/app/tools/star_chart.py OUTPUT_SCHEMA_DOC 对应） */
export interface StarChartData {
  meta: {
    zodiac: string
    houseSystem: string
    houseSystemFallback?: boolean
    timezone: string
    ephemeris: string
    ayanamsa: string | null
    birthDateTime?: string
    utDateTime?: string
  }
  ascendant: ChartPoint
  midheaven: ChartPoint
  descendant: ChartPoint
  imum_coeli: ChartPoint
  planets: Record<string, PlanetData>
  houses: Record<string, HouseData>
  aspects: AspectData[]
  patterns: PatternData[]
  birthText?: string | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  /** 引用来源（助手消息） */
  sources?: SourceItem[]
  /** 工具调用记录（M3：如 'calculator({"expression":"2+2"}) → 4'，助手消息） */
  toolCalls?: string[]
  /** 星盘排盘数据（M2.5：star_chart 工具成功后实时填充，渲染排盘卡片） */
  chart?: StarChartData
  /** 助手消息流式/失败状态（用户消息与历史消息无该字段） */
  status?: ChatMessageStatus
  /** 失败原因（status=error 时展示） */
  error?: string
}

/** 历史记录条目 */
export interface ConversationItem {
  id: number
  agentId: number
  userMessage: string
  assistantMessage: string
  createdTime: string
}

/** 发送消息返回 */
export interface ChatResult {
  answer: string
  sources: SourceItem[]
  toolCalls: string[]
}

/** 会话（M2 多会话） */
export interface SessionItem {
  id: number
  agentId: number
  name: string
  createdTime: string
  updatedTime: string
}

/** 文档 */
export interface DocumentItem {
  id: number
  agentId: number
  fileName: string
  fileType: string
  status: 'PENDING' | 'PROCESSING' | 'READY' | 'FAILED'
  createdTime: string
}
