// Desktop notifications for new messages (with a graceful no-op when unsupported
// or denied). Only shows when the tab isn't focused on the relevant chat.
export function useNotifications() {
  function request() {
    if (import.meta.client && 'Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {})
    }
  }
  function show(title: string, body: string) {
    if (!import.meta.client || !('Notification' in window)) return
    if (Notification.permission !== 'granted') return
    try {
      const n = new Notification(title, { body, icon: '/favicon.ico', tag: 'chatapp' })
      n.onclick = () => {
        window.focus()
        n.close()
      }
    } catch {
      /* ignore */
    }
  }
  return { request, show }
}
