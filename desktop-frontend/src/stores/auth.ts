import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as authApi from '@/api/auth'
import {
  getAccessToken,
  restoreSession,
  setAccessToken,
  setCsrfToken,
  setRefreshToken,
} from '@/utils/http'
import type { SessionData, SessionUser } from '@/api/types'

/**
 * 会话状态。
 *
 * 访问令牌只放内存（http.ts 的模块变量），刷新令牌在纯 HTTP 环境下
 * 由 localStorage 持有、在 HTTPS 环境下由服务端 HttpOnly cookie 持有。
 */
export const useAuthStore = defineStore('auth', () => {
  const user = ref<SessionUser | null>(null)
  const role = ref('')

  const loggedIn = computed(() => !!user.value && !!getAccessToken())

  /** 写接口要求 student 或 admin 角色，新注册账号是 guest，需要先做学生证认证。 */
  const canPublish = computed(() => role.value === 'student' || role.value === 'admin')

  function applySession(session: SessionData): void {
    setAccessToken(session.access_token)
    if (session.refresh_token) setRefreshToken(session.refresh_token)
    if (session.csrf_token) setCsrfToken(session.csrf_token)
    user.value = session.user_info
    role.value = session.role
  }

  function clear(): void {
    setAccessToken(null)
    setRefreshToken(null)
    setCsrfToken(null)
    user.value = null
    role.value = ''
  }

  async function login(username: string, password: string): Promise<void> {
    applySession(await authApi.webLogin(username, password))
  }

  async function register(username: string, password: string): Promise<void> {
    applySession(await authApi.register(username, password))
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } finally {
      clear()
    }
  }

  /** 页面刷新后恢复会话：走刷新通道，成功则回填用户信息。 */
  async function restore(): Promise<boolean> {
    const session = await restoreSession()
    if (!session?.user_info) return false
    user.value = session.user_info
    role.value = session.role ?? ''
    return true
  }

  /**
   * 接管后端下发的新会话。
   *
   * 跨端配对绑定原账号后，登录身份会并入原账号并换发新会话，
   * 这里用新会话替换本地令牌，页面状态无需重新登录。
   */
  function adopt(session: SessionData): void {
    applySession(session)
  }

  return { user, role, loggedIn, canPublish, login, register, logout, restore, adopt, clear }
})
