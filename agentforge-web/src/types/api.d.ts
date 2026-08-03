/**
 * 统一接口类型：与后端 Result<T> / PageResult<T> 对齐（设计 7.2 节）。
 */

/** 统一响应体 */
export interface Result<T = unknown> {
  code: number
  message: string
  data: T
}

/** 统一分页响应 */
export interface PageResult<T> {
  list: T[]
  total: number
  page: number
  size: number
}

/** 分页查询参数 */
export interface PageQuery {
  page?: number
  size?: number
}
