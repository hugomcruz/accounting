import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'

interface User {
  id: number
  username: string
  email: string
  full_name: string
  role: string
  is_active: boolean
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('auth_token'))
  const user = ref<User | null>(
    localStorage.getItem('auth_user')
      ? JSON.parse(localStorage.getItem('auth_user')!)
      : null
  )

  const isAuthenticated = computed(() => !!token.value)

  const role = computed(() => user.value?.role?.toLowerCase() ?? '')
  const isAdmin = computed(() => role.value === 'admin')
  const isAccountant = computed(() => role.value === 'accounting')
  const isUser = computed(() => role.value === 'user')
  const isStaff = computed(() => ['admin', 'accounting', 'finance'].includes(role.value))

  async function login(username: string, password: string) {
    const response = await api.post('/auth/login', { username, password })
    const data = response.data
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('auth_token', data.access_token)
    localStorage.setItem('auth_user', JSON.stringify(data.user))
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
  }

  return { token, user, isAuthenticated, role, isAdmin, isAccountant, isUser, isStaff, login, logout }
})
