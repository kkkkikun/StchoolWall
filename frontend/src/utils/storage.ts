/**
 * 本地存储工具
 * 用于管理 Token、用户信息等
 */

const KEYS = {
  ACCESS_TOKEN: 'access_token',
  REFRESH_TOKEN: 'refresh_token',
  USER_INFO: 'user_info',
  POST_DRAFT: 'post_draft', // 发帖草稿
}

/**
 * Token 管理
 */
export const tokenStorage = {
  getToken(): string {
    return uni.getStorageSync(KEYS.ACCESS_TOKEN) || ''
  },

  setToken(token: string): void {
    uni.setStorageSync(KEYS.ACCESS_TOKEN, token)
  },

  removeToken(): void {
    uni.removeStorageSync(KEYS.ACCESS_TOKEN)
  },

  isLoggedIn(): boolean {
    return !!this.getToken()
  },
}

/**
 * 用户信息管理
 */
interface UserInfo {
  id: string
  nickname: string
  role: 'guest' | 'student' | 'admin'
  is_verified: boolean
  avatar_url?: string
  [key: string]: any
}

export const userStorage = {
  getUserInfo(): UserInfo | null {
    const info = uni.getStorageSync(KEYS.USER_INFO)
    return info ? JSON.parse(info) : null
  },

  setUserInfo(info: UserInfo): void {
    uni.setStorageSync(KEYS.USER_INFO, JSON.stringify(info))
  },

  removeUserInfo(): void {
    uni.removeStorageSync(KEYS.USER_INFO)
  },

  updateUserInfo(partial: Partial<UserInfo>): void {
    const info = this.getUserInfo()
    if (info) {
      this.setUserInfo({ ...info, ...partial })
    }
  },

  clear(): void {
    this.removeUserInfo()
    tokenStorage.removeToken()
  },
}

/**
 * 发帖草稿管理
 */
interface PostDraft {
  content: string
  images: string[]
  post_type: string
  price?: number
  tag_ids: number[]
}

export const draftStorage = {
  getDraft(): PostDraft | null {
    const draft = uni.getStorageSync(KEYS.POST_DRAFT)
    return draft ? JSON.parse(draft) : null
  },

  setDraft(draft: PostDraft): void {
    uni.setStorageSync(KEYS.POST_DRAFT, JSON.stringify(draft))
  },

  clearDraft(): void {
    uni.removeStorageSync(KEYS.POST_DRAFT)
  },
}
