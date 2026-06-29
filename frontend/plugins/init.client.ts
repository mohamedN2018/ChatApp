import { useAuthStore } from '~/stores/auth'
import { useUiStore } from '~/stores/ui'

// Restore persisted session + theme/locale before the app paints.
export default defineNuxtPlugin(() => {
  const auth = useAuthStore()
  auth.load()
  useUiStore().load()
  // Refresh the cached user (e.g. to pick up is_staff) in the background.
  if (auth.isAuthenticated) auth.fetchMe().catch(() => {})
})
