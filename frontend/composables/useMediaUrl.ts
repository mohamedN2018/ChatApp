// Resolve backend-relative media paths (e.g. /api/v1/media/{id}/download/?token=…)
// against the API origin so they work in <img>/<a>.
export function useMediaUrl() {
  const apiBase = useRuntimeConfig().public.apiBase
  const origin = apiBase.replace(/\/api\/v1\/?$/, '')
  return (path?: string | null) => (path ? `${origin}${path}` : '')
}
