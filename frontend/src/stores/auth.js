import { defineStore } from 'pinia'
import client from '@/api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('token') || null,
  }),
  getters: {
    isAuthenticated: (s) => {
      if (!s.token) return false
      // reject tokens whose exp has already passed (best-effort, server still authoritative)
      try {
        const { exp } = JSON.parse(atob(s.token.split('.')[1]))
        return !exp || exp * 1000 > Date.now()
      } catch {
        return false
      }
    },
    role: (s) => s.user?.role || null,
    isAdmin: (s) => s.user?.role === 'admin',
    isManager: (s) => ['admin', 'manager'].includes(s.user?.role),
    // member-or-above may create/move/edit tasks; viewer is read-only
    canEdit: (s) => ['admin', 'manager', 'member'].includes(s.user?.role),
  },
  actions: {
    async login(username, password) {
      const form = new URLSearchParams()
      form.append('username', username)
      form.append('password', password)
      const { data } = await client.post('/api/auth/login', form)
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))
    },
    logout() {
      this.token = null
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
    // refresh the cached user (e.g. after an admin changes roles) via /api/auth/me
    async refresh() {
      try {
        const { data } = await client.get('/api/auth/me')
        this.user = data
        localStorage.setItem('user', JSON.stringify(data))
      } catch {
        /* token invalid/expired — interceptor handles the redirect */
      }
    },
  },
})
