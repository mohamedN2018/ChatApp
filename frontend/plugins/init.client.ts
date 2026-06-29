import { useAuthStore } from '~/stores/auth'
import { useUiStore } from '~/stores/ui'

// Restore persisted session + theme/locale before the app paints.
export default defineNuxtPlugin(() => {
  useAuthStore().load()
  useUiStore().load()
})
