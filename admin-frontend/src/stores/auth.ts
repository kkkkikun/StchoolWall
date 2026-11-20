import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getToken, setToken, clearToken } from '@/utils/request'
import * as authApi from '@/api/auth'
import type { AdminRole, LoginResult } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const loggedIn = ref(!!getToken())
  const adminName = ref(localStorage.getItem('sw_admin_name') || '')
  const adminUsername = ref(localStorage.getItem('sw_admin_username') || '')
  const adminId = ref(localStorage.getItem('sw_admin_id') || '')
  const adminRole = ref<AdminRole | ''>(localStorage.getItem('sw_admin_role') as AdminRole || '')
  const isAdmin = computed(() => loggedIn.value)
  const isOwner = computed(() => loggedIn.value && adminRole.value === 'owner')

  function applySession(data: LoginResult) {
    setToken(data.access_token)
    loggedIn.value = true
    adminName.value = data.admin.nickname
    adminUsername.value = data.admin.username
    adminId.value = data.admin.id
    adminRole.value = data.admin.role
    localStorage.setItem('sw_admin_name', data.admin.nickname)
    localStorage.setItem('sw_admin_username', data.admin.username)
    localStorage.setItem('sw_admin_id', data.admin.id)
    localStorage.setItem('sw_admin_role', data.admin.role)
  }

  async function login(username: string, password: string, loginKind: AdminRole, totpCode?: string) {
    const data = await authApi.login(username, password, loginKind, totpCode)
    if (!('mfa_setup_required' in data)) applySession(data)
    return data
  }

  async function completeMfaSetup(setupToken: string, totpCode: string) {
    const data = await authApi.verifyMfaSetup(setupToken, totpCode)
    applySession(data)
    return data
  }

  async function logout() {
    if (getToken()) {
      try { await authApi.logout() } catch { /* local session is cleared even if the server is unreachable */ }
    }
    clearToken()
    loggedIn.value = false
    adminName.value = ''
    adminUsername.value = ''
    adminId.value = ''
    adminRole.value = ''
    localStorage.removeItem('sw_admin_name')
    localStorage.removeItem('sw_admin_username')
    localStorage.removeItem('sw_admin_id')
    localStorage.removeItem('sw_admin_role')
  }

  async function fetchMe() {
    if (!getToken()) return
    try {
      const me = await authApi.me()
      loggedIn.value = true
      adminName.value = me.display_name
      adminUsername.value = me.username
      adminId.value = me.id
      adminRole.value = me.role
      localStorage.setItem('sw_admin_name', me.display_name)
      localStorage.setItem('sw_admin_username', me.username)
      localStorage.setItem('sw_admin_id', me.id)
      localStorage.setItem('sw_admin_role', me.role)
    } catch {
      await logout()
    }
  }

  return {
    loggedIn, adminName, adminUsername, adminId, adminRole, isAdmin, isOwner,
    login, completeMfaSetup, logout, fetchMe,
  }
})
