import { clientType, csrfCookie, refreshAdapter } from './platform-auth'
import { createWebSessionSync } from './web-session-sync'

let accessToken = ''
let csrfToken = ''
let sessionId = ''
let currentSession: SessionData | null = null
let webSync: ReturnType<typeof createWebSessionSync> | null = null
const KEYS = { ACCESS_TOKEN: 'access_token', USER_INFO: 'user_info', POST_DRAFT: 'post_draft' }

export interface StoredUserInfo {
  id: string
  nickname: string
  role: 'guest' | 'student' | 'admin'
  is_verified: boolean
  avatar_url?: string
  [key: string]: unknown
}

export interface SessionData {
  access_token: string
  refresh_token?: string
  csrf_token?: string
  session_id?: string
  expires_in?: number
  role: StoredUserInfo['role']
  user_info: { id: string; nickname: string; is_verified: boolean }
}

export const tokenStorage = {
  getToken(): string {
    if (clientType() === 'weixin') return uni.getStorageSync(KEYS.ACCESS_TOKEN) || ''
    // Web and Android never persist access tokens.
    uni.removeStorageSync(KEYS.ACCESS_TOKEN)
    if (clientType() === 'web') uni.removeStorageSync('refresh_token')
    return accessToken
  },
  setToken(token: string): void {
    accessToken = token
    if (clientType() === 'weixin') uni.setStorageSync(KEYS.ACCESS_TOKEN, token)
    else uni.removeStorageSync(KEYS.ACCESS_TOKEN)
  },
  getRefreshToken(): string { return refreshAdapter.get() },
  getCsrfToken(): string { return clientType() === 'web' ? csrfCookie() || csrfToken : csrfToken },
  getSessionId(): string { return sessionId },
  setSession(data: SessionData, broadcast = true): void {
    if (clientType() !== 'web') {
      if (!data.refresh_token) throw new Error('服务端未返回安全会话，请重新登录')
      refreshAdapter.set(data.refresh_token)
    } else {
      // Clear tokens left by the legacy browser client.
      uni.removeStorageSync('refresh_token')
    }
    this.setToken(data.access_token)
    csrfToken = data.csrf_token || ''
    sessionId = data.session_id || ''
    currentSession = data
    userStorage.setUserInfo({ ...data.user_info, role: data.role })
    if (broadcast && clientType() === 'web') getWebSessionSync()?.publish(data)
  },
  removeToken(): void {
    accessToken = ''
    csrfToken = ''
    sessionId = ''
    currentSession = null
    uni.removeStorageSync(KEYS.ACCESS_TOKEN)
    refreshAdapter.clear()
  },
  isLoggedIn(): boolean {
    try {
      return !!this.getToken() || (clientType() === 'web'
        ? !!csrfCookie() && !!userStorage.getUserInfo()
        : !!refreshAdapter.get())
    } catch { return false }
  },
}

export const userStorage = {
  getUserInfo(): StoredUserInfo | null {
    const info = uni.getStorageSync(KEYS.USER_INFO)
    try { return info ? (typeof info === 'string' ? JSON.parse(info) : info) : null }
    catch { return null }
  },
  setUserInfo(info: StoredUserInfo): void {
    uni.setStorageSync(KEYS.USER_INFO, JSON.stringify(info))
  },
  removeUserInfo(): void { uni.removeStorageSync(KEYS.USER_INFO) },
  updateUserInfo(partial: Partial<StoredUserInfo>): void {
    const info = this.getUserInfo()
    if (info) this.setUserInfo({ ...info, ...partial })
  },
  clear(broadcast = true): void {
    this.removeUserInfo()
    tokenStorage.removeToken()
    if (broadcast && clientType() === 'web') getWebSessionSync()?.logout()
  },
}

function getWebSessionSync() {
  if (!webSync && clientType() === 'web' && typeof BroadcastChannel !== 'undefined') {
    webSync = createWebSessionSync(new BroadcastChannel('schoolwall-session-v1'), {
      current: () => currentSession, csrf: csrfCookie,
      apply: (data) => tokenStorage.setSession(data, false), clear: () => userStorage.clear(false),
    })
  }
  return webSync
}
export async function syncWebSession(): Promise<void> {
  const locks = typeof navigator !== 'undefined' ? navigator.locks : undefined
  const sync = getWebSessionSync()
  if (!locks || !sync) throw new Error('浏览器不支持安全会话同步，请使用最新版 Chrome、Edge 或其他支持 Web Locks 的浏览器并重新登录')
  await sync.request()
}
// Listen before the first API request so another tab can share its current in-memory access token.
if (clientType() === 'web') getWebSessionSync()

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
    try { return draft ? JSON.parse(draft) : null } catch { return null }
  },
  setDraft(draft: PostDraft): void { uni.setStorageSync(KEYS.POST_DRAFT, JSON.stringify(draft)) },
  clearDraft(): void { uni.removeStorageSync(KEYS.POST_DRAFT) },
}
