// Nuxt 3 configuration.
// Runtime config exposes the API + WebSocket base URLs so the same build runs in
// any environment (only env vars change). Tailwind handles styling; Pinia state.
export default defineNuxtConfig({
  compatibilityDate: '2025-01-01',
  devtools: { enabled: false },
  modules: ['@nuxtjs/tailwindcss', '@pinia/nuxt'],
  // Use our stylesheet (with @tailwind directives) as the Tailwind entry so the
  // module doesn't also inject a second base layer.
  tailwindcss: { cssPath: '~/assets/css/main.css' },
  app: {
    pageTransition: { name: 'page', mode: 'out-in' },
    head: {
      title: 'ChatApp',
      htmlAttrs: { lang: 'en' },
      meta: [
        { charset: 'utf-8' },
        {
          name: 'viewport',
          content: 'width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover',
        },
        { name: 'theme-color', content: '#4f46e5' },
        { name: 'mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
      ],
    },
  },
  runtimeConfig: {
    public: {
      // Browser-reachable backend (override via NUXT_PUBLIC_API_BASE / _WS_BASE).
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:8000/api/v1',
      wsBase: process.env.NUXT_PUBLIC_WS_BASE || 'ws://localhost:8000',
    },
  },
  typescript: { shim: false },
})
