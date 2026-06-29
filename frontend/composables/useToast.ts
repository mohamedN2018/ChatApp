// Global toast notifications. Shared via useState so any component can push and
// the <Toaster> in the layout renders them.
interface Toast {
  id: number
  type: 'success' | 'error' | 'info'
  message: string
}

let counter = 0

export function useToast() {
  const toasts = useState<Toast[]>('toasts', () => [])

  function push(type: Toast['type'], message: string, timeout = 3200) {
    const id = ++counter
    toasts.value = [...toasts.value, { id, type, message }]
    setTimeout(() => dismiss(id), timeout)
  }
  function dismiss(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }
  return {
    toasts,
    dismiss,
    success: (m: string) => push('success', m),
    error: (m: string) => push('error', m),
    info: (m: string) => push('info', m),
  }
}
