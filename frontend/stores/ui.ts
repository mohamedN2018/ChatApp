import { defineStore } from 'pinia'

type Theme = 'dark' | 'light'
type Locale = 'en' | 'ar'

// Theme (dark/light) + locale (en/ar) with RTL. Applied to <html> so Tailwind's
// `dark:` variants and `dir`-based layout react globally.
export const useUiStore = defineStore('ui', {
  state: () => ({ theme: 'dark' as Theme, locale: 'en' as Locale }),
  getters: {
    dir: (s): 'rtl' | 'ltr' => (s.locale === 'ar' ? 'rtl' : 'ltr'),
  },
  actions: {
    load() {
      if (!import.meta.client) return
      this.theme = (localStorage.getItem('theme') as Theme) || 'dark'
      this.locale = (localStorage.getItem('locale') as Locale) || 'en'
      this.apply()
    },
    apply() {
      if (!import.meta.client) return
      const html = document.documentElement
      html.classList.toggle('dark', this.theme === 'dark')
      html.setAttribute('dir', this.dir)
      html.setAttribute('lang', this.locale)
      localStorage.setItem('theme', this.theme)
      localStorage.setItem('locale', this.locale)
    },
    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark'
      this.apply()
    },
    setLocale(locale: Locale) {
      this.locale = locale
      this.apply()
    },
  },
})
