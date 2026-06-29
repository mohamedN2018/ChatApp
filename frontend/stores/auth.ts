import { defineStore } from 'pinia'

export interface User {
  id: string
  username: string
  email: string
  display_name: string
  is_email_verified: boolean
  is_verified: boolean
  is_staff?: boolean
}

interface RegisterPayload {
  email: string
  username: string
  password: string
  password_confirm: string
  display_name?: string
}

// Tokens persist in localStorage so a refresh keeps the session; the API client
// (composables/useApi) attaches the access token and transparently refreshes it.
export const useAuthStore = defineStore('auth', {
  state: () => ({ access: '', refresh: '', user: null as User | null }),
  getters: {
    isAuthenticated: (s) => !!s.access,
  },
  actions: {
    base(): string {
      return useRuntimeConfig().public.apiBase
    },
    load() {
      if (!import.meta.client) return
      this.access = localStorage.getItem('access') || ''
      this.refresh = localStorage.getItem('refresh') || ''
      const u = localStorage.getItem('user')
      this.user = u ? JSON.parse(u) : null
    },
    persist() {
      if (!import.meta.client) return
      localStorage.setItem('access', this.access)
      localStorage.setItem('refresh', this.refresh)
      localStorage.setItem('user', JSON.stringify(this.user))
    },
    async login(email: string, password: string) {
      const data = await $fetch<{ access: string; refresh: string; user: User }>(
        `${this.base()}/accounts/login/`,
        { method: 'POST', body: { email, password } },
      )
      this.access = data.access
      this.refresh = data.refresh
      this.user = data.user
      this.persist()
    },
    async register(payload: RegisterPayload) {
      return await $fetch(`${this.base()}/accounts/register/`, { method: 'POST', body: payload })
    },
    async fetchMe() {
      this.user = await $fetch<User>(`${this.base()}/accounts/me/`, {
        headers: { Authorization: `Bearer ${this.access}` },
      })
      this.persist()
    },
    async refreshTokens() {
      if (!this.refresh) throw new Error('no refresh token')
      const data = await $fetch<{ access: string; refresh?: string }>(
        `${this.base()}/accounts/token/refresh/`,
        { method: 'POST', body: { refresh: this.refresh } },
      )
      this.access = data.access
      if (data.refresh) this.refresh = data.refresh
      this.persist()
    },
    async logout() {
      try {
        await $fetch(`${this.base()}/accounts/logout/`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${this.access}` },
          body: { refresh: this.refresh },
        })
      } catch {
        // best-effort; clear locally regardless
      }
      this.access = ''
      this.refresh = ''
      this.user = null
      if (import.meta.client) {
        localStorage.removeItem('access')
        localStorage.removeItem('refresh')
        localStorage.removeItem('user')
      }
      await navigateTo('/login')
    },
  },
})
