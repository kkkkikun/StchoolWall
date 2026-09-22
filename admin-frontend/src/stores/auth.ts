/** 登录态 store。 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getToken, setToken, clearToken } from '@/utils/request'
import * as authApi from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const loggedIn = ref(!!getToken())
  const adminName = ref(localStorage.getItem('sw_admin_name') || '')
  const adminUsername = ref(localStorage.getItem('sw_admin_username') || '')
  const adminId = ref(localStorage.getItem('sw_admin_id') || '')
  const isAdmin = computed(() => loggedIn.value)

  async function login(username: string, password: string) {
    const data = await authApi.login(username, password)
    setToken(data.access_token) // 不落 token 守卫会弹回登录页
    loggedIn.value = true
    adminName.value = data.admin.nickname
    adminUsername.value = data.admin.username
    adminId.value = data.admin.id
    localStorage.setItem('sw_admin_name', data.admin.nickname)
    localStorage.setItem('sw_admin_username', data.admin.username)
    localStorage.setItem('sw_admin_id', data.admin.id)
    return data
  }

  function logout() {
    clearToken()
    loggedIn.value = false
    adminName.value = ''
    adminUsername.value = ''
    adminId.value = ''
    localStorage.removeItem('sw_admin_name')
    localStorage.removeItem('sw_admin_username')
    localStorage.removeItem('sw_admin_id')
  }

  return { loggedIn, adminName, adminUsername, adminId, isAdmin, login, logout }
})
