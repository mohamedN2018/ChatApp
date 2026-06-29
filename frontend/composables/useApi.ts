import { useAuthStore } from '~/stores/auth'

// Thin authenticated API wrapper: attaches the JWT access token and, on a 401,
// transparently refreshes once and retries. Returns parsed JSON.
export function useApi() {
  const auth = useAuthStore()
  const base = useRuntimeConfig().public.apiBase

  async function api<T = unknown>(path: string, opts: Record<string, any> = {}): Promise<T> {
    const headers: Record<string, string> = { ...(opts.headers || {}) }
    if (auth.access) headers.Authorization = `Bearer ${auth.access}`
    try {
      return await $fetch<T>(`${base}${path}`, { ...opts, headers })
    } catch (e: any) {
      if (e?.response?.status === 401 && auth.refresh) {
        await auth.refreshTokens()
        return await $fetch<T>(`${base}${path}`, {
          ...opts,
          headers: { ...headers, Authorization: `Bearer ${auth.access}` },
        })
      }
      throw e
    }
  }

  return { api }
}
