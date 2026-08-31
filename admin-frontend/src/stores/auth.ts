/** 登录态 store。 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getToken, clearToken } from '@/utils/request'
import * as authApi from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const loggedIn = ref(!!getToken())
  const adminName = ref(localStorage.getItem('sw_admin_name') || '')
  const isAdmin = computed(() => loggedIn.value)

  async function login(username: string, password: string) {
    const data = await authApi.login(username, password)
    loggedIn.value = true
    adminName.value = data.admin.nickname
    localStorage.setItem('sw_admin_name', data.admin.nickname)
    return data
  }

  function logout() {
    clearToken()
    loggedIn.value = false
    adminName.value = ''
    localStorage.removeItem('sw_admin_name')
  }

  return { loggedIn, adminName, isAdmin, login, logout }
})
