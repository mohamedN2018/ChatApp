<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import {
  PaperAirplaneIcon, PlusIcon, MagnifyingGlassIcon, PaperClipIcon, XMarkIcon, DocumentIcon,
  PhoneIcon, VideoCameraIcon, MicrophoneIcon, StopIcon, FaceSmileIcon, ArrowUturnLeftIcon,
} from '@heroicons/vue/24/solid'

definePageMeta({ middleware: 'auth' })

const { api } = useApi()
const auth = useAuthStore()
const ui = useUiStore()
const t = useT()
const mediaUrl = useMediaUrl()
const call = useCall()
const sound = useSound()
const notifications = useNotifications()

const REACTIONS = ['👍', '❤️', '😂', '😮', '😢', '🙏']

const conversations = ref<any[]>([])
const activeId = ref<string | null>(null)
const messages = ref<any[]>([])
const draft = ref('')
const newChatUser = ref('')
const search = ref('')
const presence = reactive<Record<string, string>>({})
const typing = reactive<Record<string, number>>({})
const threadEl = ref<HTMLElement | null>(null)

const pending = ref<any[]>([])
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const replyingTo = ref<any>(null)
const pickerFor = ref<string | null>(null)

// Voice recording
const recording = ref(false)
const recordSecs = ref(0)
let recorder: MediaRecorder | null = null
let recordChunks: Blob[] = []
let recordTimer: any = null
let recordStream: MediaStream | null = null

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
function fmtDur(s?: number) {
  if (!s) return ''
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}
function scrollToBottom() {
  const el = threadEl.value
  if (el) el.scrollTop = el.scrollHeight
}
function myReacted(r: any) {
  return r.user_ids?.includes(auth.user?.id)
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
  replyingTo.value = null
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
    const conv = await api<any>('/chat/conversations/start/', { method: 'POST', body: { username } })
    newChatUser.value = ''
    if (!conversations.value.find((c) => c.id === conv.id)) conversations.value.unshift(conv)
    await openConversation(conv.id)
  } catch {
    /* unknown user / blocked */
  }
}

function pickFiles() {
  fileInput.value?.click()
}
async function onFiles(e: Event) {
  const files = Array.from((e.target as HTMLInputElement).files || [])
  if (!files.length) return
  uploading.value = true
  try {
    for (const file of files) {
      const fd = new FormData()
      fd.append('file', file)
      pending.value.push(await api<any>('/media/upload/', { method: 'POST', body: fd }))
    }
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}
function removePending(id: string) {
  pending.value = pending.value.filter((m) => m.id !== id)
}

async function send() {
  const text = draft.value.trim()
  const attachment_ids = pending.value.map((m) => m.id)
  if ((!text && !attachment_ids.length) || !activeId.value) return
  draft.value = ''
  const sentAtt = pending.value
  const reply = replyingTo.value
  pending.value = []
  replyingTo.value = null
  try {
    await api(`/chat/conversations/${activeId.value}/messages/`, {
      method: 'POST',
      body: { text, attachment_ids, reply_to: reply?.id },
    })
  } catch {
    draft.value = text
    pending.value = sentAtt
    replyingTo.value = reply
  }
}

async function react(message: any, emoji: string) {
  pickerFor.value = null
  try {
    const updated = await api<any>(`/chat/messages/${message.id}/react/`, {
      method: 'POST',
      body: { emoji },
    })
    const idx = messages.value.findIndex((m) => m.id === message.id)
    if (idx !== -1) messages.value[idx].reactions = updated.reactions
  } catch {
    /* ignore */
  }
}
function setReply(message: any) {
  replyingTo.value = message
}

// --- voice notes ---
async function toggleRecord() {
  if (recording.value) return stopRecord(true)
  try {
    recordStream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch {
    return
  }
  recordChunks = []
  recorder = new MediaRecorder(recordStream)
  recorder.ondataavailable = (e) => e.data.size && recordChunks.push(e.data)
  recorder.onstop = onRecordStop
  recorder.start()
  recording.value = true
  recordSecs.value = 0
  recordTimer = setInterval(() => (recordSecs.value += 1), 1000)
}
function stopRecord(sendIt: boolean) {
  clearInterval(recordTimer)
  recording.value = false
  ;(recorder as any)._send = sendIt
  recorder?.stop()
}
async function onRecordStop() {
  recordStream?.getTracks().forEach((t) => t.stop())
  const shouldSend = (recorder as any)?._send
  recorder = null
  if (!shouldSend || !recordChunks.length || !activeId.value) return
  const blob = new Blob(recordChunks, { type: 'audio/webm' })
  const fd = new FormData()
  fd.append('file', new File([blob], 'voice.webm', { type: 'audio/webm' }))
  fd.append('kind', 'voice')
  const media = await api<any>('/media/upload/', { method: 'POST', body: fd })
  await api(`/chat/conversations/${activeId.value}/messages/`, {
    method: 'POST',
    body: { attachment_ids: [media.id] },
  })
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

function startCall(video: boolean) {
  if (activeId.value) call.start(activeId.value, video)
}
function openMedia(url: string) {
  if (import.meta.client) window.open(url, '_blank')
}

function notifyMessage(m: any) {
  const conv = conversations.value.find((c) => c.id === m.conversation)
  const name = m.sender?.display_name || m.sender?.username || 'New message'
  const body = m.text || (m.attachments?.length ? '📎 Attachment' : '')
  const focusedHere = import.meta.client && document.hasFocus() && m.conversation === activeId.value
  if (!focusedHere) {
    sound.notify()
    notifications.show(name, body)
  }
}

onMounted(async () => {
  notifications.request()
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
      if (!isMine(m)) notifyMessage(m)
      const conv = conversations.value.find((c) => c.id === m.conversation)
      if (conv) {
        conv.last_message = m
        if (m.conversation !== activeId.value && !isMine(m))
          conv.unread_count = (conv.unread_count || 0) + 1
        conversations.value = [conv, ...conversations.value.filter((c) => c.id !== conv.id)]
      } else {
        loadConversations()
      }
    } else if (evt.event === 'reaction.update') {
      const m = messages.value.find((x) => x.id === evt.message_id)
      if (m) m.reactions = evt.reactions
    } else if (evt.event === 'message.update') {
      const idx = messages.value.findIndex((x) => x.id === evt.message.id)
      if (idx !== -1) messages.value[idx] = evt.message
    } else if (evt.event === 'message.delete') {
      const m = messages.value.find((x) => x.id === evt.message_id)
      if (m) {
        m.deleted_for_everyone = true
        m.text = ''
        m.attachments = []
      }
    } else if (evt.event === 'typing' && evt.conversation_id === activeId.value && evt.user_id !== auth.user?.id) {
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
  clearInterval(recordTimer)
})
</script>

<template>
  <div class="mx-auto flex h-full max-w-6xl">
    <!-- Sidebar -->
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
          :class="c.id === activeId ? 'bg-slate-100 dark:bg-slate-800' : ''" @click="openConversation(c.id)">
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
              <span v-if="c.unread_count" class="grid h-5 min-w-5 place-items-center rounded-full bg-brand-600 px-1.5 text-xs font-bold text-white">{{ c.unread_count }}</span>
            </div>
            <p class="truncate text-sm text-slate-500">{{ c.last_message?.text || (c.last_message ? '📎' : '—') }}</p>
          </div>
        </button>
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
          <div class="flex-1">
            <p class="font-semibold leading-tight">@{{ otherUser(activeConv)?.username }}</p>
            <p class="text-xs text-slate-500">
              {{ presence[otherUser(activeConv)?.id] === 'online' ? t('common.online') : t('common.offline') }}
            </p>
          </div>
          <button class="btn-ghost px-2" title="Voice call" @click="startCall(false)"><PhoneIcon class="h-5 w-5" /></button>
          <button class="btn-ghost px-2" title="Video call" @click="startCall(true)"><VideoCameraIcon class="h-5 w-5" /></button>
        </header>

        <div ref="threadEl" class="min-h-0 flex-1 space-y-1 overflow-y-auto p-4">
          <div v-for="m in messages" :key="m.id" class="group flex" :class="isMine(m) ? 'justify-end' : 'justify-start'">
            <!-- hover actions (left of own messages / right of others) -->
            <div class="flex items-center gap-1 opacity-0 transition group-hover:opacity-100" :class="isMine(m) ? 'order-1 me-1' : 'order-2 ms-1'">
              <div class="relative">
                <button class="rounded-full p-1 text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700" @click="pickerFor = pickerFor === m.id ? null : m.id">
                  <FaceSmileIcon class="h-4 w-4" />
                </button>
                <div v-if="pickerFor === m.id" class="absolute bottom-full z-10 mb-1 flex gap-1 rounded-full bg-white p-1 shadow-lg dark:bg-slate-800"
                  :class="isMine(m) ? 'end-0' : 'start-0'">
                  <button v-for="e in REACTIONS" :key="e" class="rounded-full px-1 text-lg hover:scale-125" @click="react(m, e)">{{ e }}</button>
                </div>
              </div>
              <button class="rounded-full p-1 text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700" title="Reply" @click="setReply(m)">
                <ArrowUturnLeftIcon class="h-4 w-4" />
              </button>
            </div>

            <div class="order-1 max-w-[78%]">
              <div class="rounded-2xl px-3.5 py-2 text-sm shadow-sm"
                :class="isMine(m) ? 'bg-brand-600 text-white rounded-ee-md' : 'bg-white text-slate-800 dark:bg-slate-800 dark:text-slate-100 rounded-es-md'">
                <!-- reply preview -->
                <div v-if="m.reply_to" class="mb-1 border-s-2 border-current/40 ps-2 text-xs opacity-80">
                  <span class="font-semibold">@{{ m.reply_to.sender?.username }}</span>
                  <span class="ms-1">{{ m.reply_to.text || '📎' }}</span>
                </div>
                <!-- attachments -->
                <div v-if="m.attachments?.length" class="mb-1 space-y-1.5">
                  <template v-for="a in m.attachments" :key="a.id">
                    <img v-if="a.kind === 'image'" :src="mediaUrl(a.thumbnail_url || a.url)" class="max-h-52 max-w-full cursor-pointer rounded-lg" @click="openMedia(mediaUrl(a.url))" />
                    <video v-else-if="a.kind === 'video'" :src="mediaUrl(a.url)" controls class="max-h-64 max-w-full rounded-lg" />
                    <div v-else-if="a.kind === 'voice' || a.kind === 'audio'" class="min-w-[200px]">
                      <audio :src="mediaUrl(a.url)" controls class="h-9 w-full" />
                      <div v-if="a.waveform?.length" class="mt-1 flex h-6 items-end gap-px">
                        <span v-for="(p, i) in a.waveform" :key="i" class="flex-1 rounded-sm bg-current/40" :style="{ height: `${Math.max(8, p * 100)}%` }" />
                      </div>
                    </div>
                    <a v-else :href="mediaUrl(a.url)" target="_blank" class="flex items-center gap-2 rounded-lg bg-black/10 px-2.5 py-1.5 text-xs hover:underline dark:bg-white/10">
                      <DocumentIcon class="h-4 w-4 shrink-0" /><span class="truncate">{{ a.original_filename }}</span>
                    </a>
                  </template>
                </div>
                <p v-if="m.text || m.deleted_for_everyone" class="whitespace-pre-wrap break-words">
                  <span v-if="m.deleted_for_everyone" class="italic opacity-60">deleted</span>
                  <span v-else>{{ m.text }}</span>
                </p>
                <p class="mt-0.5 text-[10px] opacity-60">{{ fmtTime(m.created_at) }}</p>
              </div>
              <!-- reactions -->
              <div v-if="m.reactions?.length" class="mt-0.5 flex flex-wrap gap-1" :class="isMine(m) ? 'justify-end' : ''">
                <button v-for="r in m.reactions" :key="r.emoji" @click="react(m, r.emoji)"
                  class="rounded-full border px-1.5 py-0.5 text-xs"
                  :class="myReacted(r) ? 'border-brand-500 bg-brand-50 dark:bg-brand-700/30' : 'border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800'">
                  {{ r.emoji }} {{ r.count }}
                </button>
              </div>
            </div>
          </div>
          <p v-if="someoneTyping" class="text-xs text-slate-400">{{ t('chat.typing') }}</p>
        </div>

        <!-- Composer -->
        <div class="border-t border-slate-200 dark:border-slate-800">
          <div v-if="replyingTo" class="flex items-center gap-2 px-3 pt-2 text-xs">
            <ArrowUturnLeftIcon class="h-4 w-4 text-brand-500" />
            <span class="flex-1 truncate">Replying to @{{ replyingTo.sender?.username }}: {{ replyingTo.text || '📎' }}</span>
            <button @click="replyingTo = null"><XMarkIcon class="h-4 w-4" /></button>
          </div>
          <div v-if="pending.length || uploading" class="flex flex-wrap gap-2 px-3 pt-2">
            <div v-for="m in pending" :key="m.id" class="relative">
              <img v-if="m.kind === 'image'" :src="mediaUrl(m.thumbnail_url || m.url)" class="h-14 w-14 rounded-lg object-cover" />
              <div v-else class="grid h-14 w-14 place-items-center rounded-lg bg-slate-200 dark:bg-slate-700"><DocumentIcon class="h-5 w-5" /></div>
              <button class="absolute -end-1.5 -top-1.5 grid h-5 w-5 place-items-center rounded-full bg-slate-700 text-white" @click="removePending(m.id)"><XMarkIcon class="h-3 w-3" /></button>
            </div>
            <div v-if="uploading" class="grid h-14 w-14 place-items-center rounded-lg bg-slate-100 text-xs text-slate-400 dark:bg-slate-800">…</div>
          </div>

          <form v-if="!recording" class="flex items-center gap-2 p-3" @submit.prevent="send">
            <input ref="fileInput" type="file" multiple class="hidden" @change="onFiles" />
            <button type="button" class="btn-ghost px-2" title="Attach" @click="pickFiles"><PaperClipIcon class="h-5 w-5" /></button>
            <button type="button" class="btn-ghost px-2" title="Voice note" @click="toggleRecord"><MicrophoneIcon class="h-5 w-5" /></button>
            <input v-model="draft" class="input" :placeholder="t('chat.placeholder')" @input="onInput" />
            <button class="btn-primary px-3" :disabled="!draft.trim() && !pending.length">
              <PaperAirplaneIcon class="h-5 w-5" :class="ui.dir === 'rtl' ? 'rotate-180' : ''" />
            </button>
          </form>
          <div v-else class="flex items-center gap-3 p-3">
            <span class="flex items-center gap-2 text-sm text-red-500"><span class="h-2.5 w-2.5 animate-pulse rounded-full bg-red-500" /> {{ fmtDur(recordSecs) }}</span>
            <span class="flex-1 text-sm text-slate-500">Recording voice note…</span>
            <button class="btn-ghost px-3" @click="stopRecord(false)">Cancel</button>
            <button class="btn-primary px-3" title="Send" @click="stopRecord(true)"><StopIcon class="h-5 w-5" /></button>
          </div>
        </div>
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
