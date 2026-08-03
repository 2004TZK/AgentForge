/** 认证状态：token / userInfo / 登录 / 登出 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiGetMe, apiLogin, apiRegister } from '../api/auth'
import type { UserInfo } from '../types/auth'
import { clearToken, getToken, getUser, setToken, setUser } from '../utils/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<UserInfo | null>(getUser() as UserInfo | null)

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string): Promise<void> {
    const result = await apiLogin({ username, password })
    token.value = result.token
    user.value = result.user
    setToken(result.token)
    setUser(result.user)
  }

  async function register(username: string, password: string, email?: string): Promise<void> {
    await apiRegister({ username, password, email })
  }

  /** 拉取最新用户信息（刷新页面后恢复会话） */
  async function fetchMe(): Promise<void> {
    if (!token.value) return
    try {
      user.value = await apiGetMe()
      if (user.value) setUser(user.value)
    } catch {
      logout()
    }
  }

  function logout(): void {
    token.value = null
    user.value = null
    clearToken()
  }

  return { token, user, isLoggedIn, login, register, fetchMe, logout }
})
