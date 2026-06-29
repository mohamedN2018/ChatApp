import { useAuthStore } from '~/stores/auth'

// Guard protected pages: bounce unauthenticated users to /login.
export default defineNuxtRouteMiddleware(() => {
  const auth = useAuthStore()
  if (import.meta.client && !auth.isAuthenticated) {
    return navigateTo('/login')
  }
})
