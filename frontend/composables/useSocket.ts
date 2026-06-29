import { useAuthStore } from '~/stores/auth'

type Handler = (data: any) => void

// Reusable JWT-authenticated WebSocket client with auto-reconnect. The backend
// reads the token from the query string (browsers can't set WS headers).
export function useSocket(path: string) {
  const auth = useAuthStore()
  const wsBase = useRuntimeConfig().public.wsBase
  let socket: WebSocket | null = null
  let reconnectTimer: any = null
  let manualClose = false
  const handlers = new Set<Handler>()

  function connect() {
    if (!import.meta.client || !auth.access) return
    manualClose = false
    socket = new WebSocket(`${wsBase}${path}?token=${encodeURIComponent(auth.access)}`)
    socket.onmessage = (e) => {
      let data: any
      try {
        data = JSON.parse(e.data)
      } catch {
        return
      }
      handlers.forEach((h) => h(data))
    }
    socket.onclose = () => {
      if (!manualClose) reconnectTimer = setTimeout(connect, 1500)
    }
  }

  function send(obj: Record<string, any>) {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(obj))
  }

  function on(handler: Handler) {
    handlers.add(handler)
    return () => handlers.delete(handler)
  }

  function close() {
    manualClose = true
    clearTimeout(reconnectTimer)
    socket?.close()
    socket = null
  }

  return { connect, send, on, close }
}
