<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { PaperAirplaneIcon, PlusIcon, MagnifyingGlassIcon } from '@heroicons/vue/24/solid'

definePageMeta({ middleware: 'auth' })

const { api } = useApi()
const auth = useAuthStore()
const ui = useUiStore()
const t = useT()

const conversations = ref<any[]>([])
const activeId = ref<string | null>(null)
const messages = ref<any[]>([])
const draft = ref('')
const newChatUser = ref('')
const search = ref('')
const presence = reactive<Record<string, string>>({})
const typing = reactive<Record<string, number>>({})
const threadEl = ref<HTMLElement | null>(null)

const chatSocket = useSocket('/ws/chat/')
const presenceSocket = useSocket('/ws/presence/')

const activeConv = computed(() => conversations.value.find((c) => c.id === activeId.value))
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return conversations.value
  return conversations.value.filter((c) => otherUser(c)?.username?.toLowerCase().includes(q))
})
const someoneTyping = computed(() => Object.keys(typing).length > 0)

function otherUser(conv: any) {
  return conv?.participants?.find((p: any) => p.id !== auth.user?.id) || conv?.participants?.[0]
}
function presenceColor(status?: string) {
  return { online: 'bg-emerald-500', away: 'bg-amber-400', busy: 'bg-red-500' }[status || ''] || 'bg-slate-400'
}
function isMine(m: any) {
  return m.sender?.id === auth.user?.id
}
function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
function scrollToBottom() {
  const el = threadEl.value
  if (el) el.scrollTop = el.scrollHeight
}

async function loadConversations() {
  const data = await api<any>('/chat/conversations/')
  conversations.value = data.results || data
  const ids = [
    ...new Set(
      conversations.value
        .flatMap((c: any) => c.participants.map((p: any) => p.id))
        .filter((id: string) => id !== auth.user?.id),
    ),
  ]
  if (ids.length) presenceSocket.send({ action: 'subscribe', user_ids: ids })
}

async function openConversation(id: string) {
  activeId.value = id
  const data = await api<any>(`/chat/conversations/${id}/messages/`)
  messages.value = (data.results || []).slice().reverse()
  await nextTick()
  scrollToBottom()
  api(`/chat/conversations/${id}/read/`, { method: 'POST' }).catch(() => {})
  if (activeConv.value) activeConv.value.unread_count = 0
}

async function startChat() {
  const username = newChatUser.value.trim()
  if (!username) return
  try {
    const conv = await api<any>('/chat/conversations/start/', {
      method: 'POST',
      body: { username },
    })
    newChatUser.value = ''
    if (!conversations.value.find((c) => c.id === conv.id)) conversations.value.unshift(conv)
    await openConversation(conv.id)
  } catch {
    /* unknown user / blocked */
  }
}

async function send() {
  const text = draft.value.trim()
  if (!text || !activeId.value) return
  draft.value = ''
  try {
    await api(`/chat/conversations/${activeId.value}/messages/`, { method: 'POST', body: { text } })
  } catch {
    draft.value = text
  }
}

let typingTimer: any
function onInput() {
  if (!activeId.value) return
  chatSocket.send({ action: 'typing', conversation_id: activeId.value, state: 'start' })
  clearTimeout(typingTimer)
  typingTimer = setTimeout(
    () => chatSocket.send({ action: 'typing', conversation_id: activeId.value, state: 'stop' }),
    1800,
  )
}

onMounted(async () => {
  chatSocket.connect()
  presenceSocket.connect()

  chatSocket.on((evt: any) => {
    if (evt.event === 'message.new') {
      const m = evt.message
      delete typing[m.sender?.id]
      if (m.conversation === activeId.value) {
        messages.value.push(m)
        nextTick().then(scrollToBottom)
      }
      const conv = conversations.value.find((c) => c.id === m.conversation)
      if (conv) {
        conv.last_message = m
        if (m.conversation !== activeId.value && !isMine(m))
          conv.unread_count = (conv.unread_count || 0) + 1
        conversations.value = [conv, ...conversations.value.filter((c) => c.id !== conv.id)]
      } else {
        loadConversations()
      }
    } else if (
      evt.event === 'typing' &&
      evt.conversation_id === activeId.value &&
      evt.user_id !== auth.user?.id
    ) {
      if (evt.state === 'start') typing[evt.user_id] = Date.now()
      else delete typing[evt.user_id]
    }
  })

  presenceSocket.on((evt: any) => {
    if (evt.type === 'presence.snapshot') evt.users.forEach((u: any) => (presence[u.user_id] = u.status))
    else if (evt.type === 'presence.update') presence[evt.user_id] = evt.status
  })

  await loadConversations()
})

onUnmounted(() => {
  chatSocket.close()
  presenceSocket.close()
})
</script>

<template>
  <div class="mx-auto flex h-full max-w-6xl">
    <!-- Sidebar: conversations -->
    <aside class="flex w-full max-w-xs shrink-0 flex-col border-e border-slate-200 dark:border-slate-800"
      :class="activeId ? 'hidden md:flex' : 'flex'">
      <div class="space-y-3 p-3">
        <div class="relative">
          <MagnifyingGlassIcon class="pointer-events-none absolute inset-y-0 start-3 my-auto h-4 w-4 text-slate-400" />
          <input v-model="search" class="input ps-9" :placeholder="t('common.search')" />
        </div>
        <form class="flex gap-2" @submit.prevent="startChat">
          <input v-model="newChatUser" class="input" :placeholder="t('chat.startBy')" />
          <button class="btn-primary px-3" :title="t('chat.newChat')"><PlusIcon class="h-5 w-5" /></button>
        </form>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        <button v-for="c in filtered" :key="c.id"
          class="flex w-full items-center gap-3 rounded-xl p-2.5 text-start transition hover:bg-slate-100 dark:hover:bg-slate-800"
          :class="c.id === activeId ? 'bg-slate-100 dark:bg-slate-800' : ''"
          @click="openConversation(c.id)">
          <div class="relative">
            <div class="grid h-10 w-10 place-items-center rounded-full bg-brand-100 font-semibold text-brand-700 dark:bg-brand-700/30 dark:text-brand-100">
              {{ (otherUser(c)?.display_name || otherUser(c)?.username || '?').charAt(0).toUpperCase() }}
            </div>
            <span class="absolute -bottom-0.5 -end-0.5 h-3 w-3 rounded-full border-2 border-white dark:border-slate-900"
              :class="presenceColor(presence[otherUser(c)?.id])" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between gap-2">
              <span class="truncate font-semibold">@{{ otherUser(c)?.username }}</span>
              <span v-if="c.unread_count" class="grid h-5 min-w-5 place-items-center rounded-full bg-brand-600 px-1.5 text-xs font-bold text-white">
                {{ c.unread_count }}
              </span>
            </div>
            <p class="truncate text-sm text-slate-500">{{ c.last_message?.text || '—' }}</p>
          </div>
        </button>
        <p v-if="!filtered.length" class="p-6 text-center text-sm text-slate-400">{{ t('chat.conversations') }}…</p>
      </div>
    </aside>

    <!-- Thread -->
    <section class="flex min-w-0 flex-1 flex-col" :class="activeId ? 'flex' : 'hidden md:flex'">
      <template v-if="activeConv">
        <header class="flex h-14 items-center gap-3 border-b border-slate-200 px-4 dark:border-slate-800">
          <button class="btn-ghost px-2 md:hidden" @click="activeId = null">←</button>
          <div class="grid h-9 w-9 place-items-center rounded-full bg-brand-100 font-semibold text-brand-700 dark:bg-brand-700/30 dark:text-brand-100">
            {{ (otherUser(activeConv)?.username || '?').charAt(0).toUpperCase() }}
          </div>
          <div>
            <p class="font-semibold leading-tight">@{{ otherUser(activeConv)?.username }}</p>
            <p class="text-xs text-slate-500">
              {{ presence[otherUser(activeConv)?.id] === 'online' ? t('common.online') : t('common.offline') }}
            </p>
          </div>
        </header>

        <div ref="threadEl" class="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
          <div v-for="m in messages" :key="m.id" class="flex" :class="isMine(m) ? 'justify-end' : 'justify-start'">
            <div class="max-w-[75%] rounded-2xl px-3.5 py-2 text-sm shadow-sm"
              :class="isMine(m)
                ? 'bg-brand-600 text-white rounded-ee-md'
                : 'bg-white text-slate-800 dark:bg-slate-800 dark:text-slate-100 rounded-es-md'">
              <p class="whitespace-pre-wrap break-words">
                <span v-if="m.deleted_for_everyone" class="italic opacity-60">deleted</span>
                <span v-else>{{ m.text }}</span>
              </p>
              <p class="mt-0.5 text-[10px] opacity-60">{{ fmtTime(m.created_at) }}</p>
            </div>
          </div>
          <p v-if="someoneTyping" class="text-xs text-slate-400">{{ t('chat.typing') }}</p>
        </div>

        <form class="flex items-center gap-2 border-t border-slate-200 p-3 dark:border-slate-800" @submit.prevent="send">
          <input v-model="draft" class="input" :placeholder="t('chat.placeholder')" @input="onInput" />
          <button class="btn-primary px-3" :disabled="!draft.trim()">
            <PaperAirplaneIcon class="h-5 w-5" :class="ui.dir === 'rtl' ? 'rotate-180' : ''" />
          </button>
        </form>
      </template>

      <div v-else class="grid flex-1 place-items-center text-slate-400">
        <div class="text-center">
          <div class="mx-auto mb-3 grid h-16 w-16 place-items-center rounded-2xl bg-slate-100 dark:bg-slate-800">💬</div>
          <p>{{ t('chat.empty') }}</p>
        </div>
      </div>
    </section>
  </div>
</template>
