/** 用户相关类型 */
export interface UserInfo {
  id: number
  username: string
  email: string | null
  avatar: string | null
  createdTime: string
}

export interface LoginResult {
  token: string
  expiresIn: number
  user: UserInfo
}
