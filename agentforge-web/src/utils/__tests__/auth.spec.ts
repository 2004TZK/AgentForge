/** 认证工具冒烟测试（M4 前端冒烟）：token/用户信息本地存取 + 损坏数据处理 */
import { describe, expect, it, beforeEach } from 'vitest'
import { clearToken, getToken, getUser, setToken, setUser } from '../auth'

describe('auth utils', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('token 存取与清除', () => {
    expect(getToken()).toBeNull()
    setToken('abc.def.ghi')
    expect(getToken()).toBe('abc.def.ghi')
    clearToken()
    expect(getToken()).toBeNull()
  })

  it('用户信息存取（JSON 序列化）', () => {
    const user = { id: 1, username: 'alice', email: null, avatar: null }
    setUser(user)
    expect(getUser()).toEqual(user)
  })

  it('clearToken 同时清除用户信息', () => {
    setToken('t')
    setUser({ id: 1, username: 'alice', email: null, avatar: null })
    clearToken()
    expect(getUser()).toBeNull()
  })

  it('损坏的用户 JSON 返回 null 而非抛错', () => {
    localStorage.setItem('agentforge_user', '{broken')
    expect(getUser()).toBeNull()
  })
})
