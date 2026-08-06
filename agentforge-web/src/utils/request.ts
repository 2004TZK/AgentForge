/**
 * axios 实例：baseURL=/api，请求注入 Bearer JWT，响应统一处理 Result<T>。
 * - code=0 走正常流程（返回 data）
 * - code!=0 弹出错误提示并 reject
 * - HTTP 401 清除 token 并跳转登录
 */
import axios, { AxiosError } from 'axios'
import type { Result } from '../types/api'
import { clearToken, getToken } from './auth'
import { notifyError } from './notify'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  // 工作流同步运行可能耗时 1-3 分钟（AI 服务读取超时已放宽到 10 分钟），
  // 全局超时与后端 AGENTFORGE_AI_READ_TIMEOUT_MS=600000 对齐
  timeout: 600000,
})

// 请求拦截：注入 JWT
request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一处理 Result 与 401
request.interceptors.response.use(
  (response) => {
    const result = response.data as Result
    if (result.code === 0) {
      return result.data
    }
    notifyError(result.message || '请求失败')
    return Promise.reject(new Error(result.message || '请求失败'))
  },
  (error: AxiosError<Result>) => {
    if (error.response?.status === 401) {
      clearToken()
      if (location.pathname !== '/login') {
        notifyError('登录已过期，请重新登录')
        location.href = '/login'
      }
    } else {
      notifyError(error.response?.data?.message || error.message || '网络错误')
    }
    return Promise.reject(error)
  },
)

/** 类型化的请求封装：get/post/put/del，返回 Result.data */
export const http = {
  get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    return request.get(url, { params }) as Promise<T>
  },
  post<T>(url: string, data?: unknown): Promise<T> {
    return request.post(url, data) as Promise<T>
  },
  put<T>(url: string, data?: unknown): Promise<T> {
    return request.put(url, data) as Promise<T>
  },
  del<T>(url: string): Promise<T> {
    return request.delete(url) as Promise<T>
  },
}

export default request
