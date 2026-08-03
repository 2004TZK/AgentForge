/** 认证接口：注册 / 登录 / 当前用户 */
import { http } from '../utils/request'
import type { LoginResult, UserInfo } from '../types/auth'

export function apiRegister(data: { username: string; password: string; email?: string }): Promise<UserInfo> {
  return http.post<UserInfo>('/auth/register', data)
}

export function apiLogin(data: { username: string; password: string }): Promise<LoginResult> {
  return http.post<LoginResult>('/auth/login', data)
}

export function apiGetMe(): Promise<UserInfo> {
  return http.get<UserInfo>('/auth/me')
}
