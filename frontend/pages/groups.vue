<script setup lang="ts">
import { PlusIcon, PaperAirplaneIcon, HashtagIcon, UsersIcon } from '@heroicons/vue/24/solid'

definePageMeta({ middleware: 'auth' })
const { api } = useApi()
const auth = useAuthStore()

const groups = ref<any[]>([])
const discover = ref<any[]>([])
const active = ref<any>(null)
const activeChannel = ref<any>(null)
const messages = ref<any[]>([])
const draft = ref('')
const newGroup = ref('')
const inviteCode = ref('')
const newChannel = ref('')
const tab = ref<'mine' | 'discover'>('mine')

const chatSocket = useSocket('/ws/chat/')

async function loadGroups() {
  groups.value = await api<any[]>('/groups/')
}
async function loadDiscover() {
  const d = await api<any>('/groups/discover/')
  discover.value = d.results || d
}
async function openGroup(slug: string) {
  active.value = await api<any>(`/groups/${slug}/`)
  activeChannel.value = active.value.channels?.[0] || null
  if (activeChannel.value) openChannel(activeChannel.value)
}
async function createGroup() {
  if (!newGroup.value.trim()) return
  const g = await api<any>('/groups/', { method: 'POST', body: { name: newGroup.value.trim(), is_public: true } })
  newGroup.value = ''
  await loadGroups()
  openGroup(g.slug)
}
async function join() {
  if (!inviteCode.value.trim()) return
  const g = await api<any>('/groups/join/', { method: 'POST', body: { code: inviteCode.value.trim() } })
  inviteCode.value = ''
  await loadGroups()
  openGroup(g.slug)
}
async function joinPublic(slug: string) {
  await api(`/groups/${slug}/join/`, { method: 'POST' })
  await loadGroups()
  openGroup(slug)
}
async function addChannel() {
  if (!newChannel.value.trim() || !active.value) return
  await api(`/groups/${active.value.slug}/channels/`, {
    method: 'POST',
    body: { name: newChannel.value.trim(), type: 'text' },
  })
  newChannel.value = ''
  openGroup(active.value.slug)
}
async function openChannel(ch: any) {
  activeChannel.value = ch
  const data = await api<any>(`/chat/conversations/${ch.conversation_id}/messages/`)
  messages.value = (data.results || []).slice().reverse()
}
async function send() {
  const text = draft.value.trim()
  if (!text || !activeChannel.value) return
  draft.value = ''
  await api(`/chat/conversations/${activeChannel.value.conversation_id}/messages/`, {
    method: 'POST',
    body: { text },
  }).catch(() => (draft.value = text))
}

onMounted(async () => {
  chatSocket.connect()
  chatSocket.on((evt: any) => {
    if (evt.event === 'message.new' && evt.message.conversation === activeChannel.value?.conversation_id) {
      messages.value.push(evt.message)
    }
  })
  await loadGroups()
})
onUnmounted(() => chatSocket.close())
</script>

<template>
  <div class="mx-auto flex h-full max-w-6xl">
    <aside class="flex w-72 shrink-0 flex-col border-e border-slate-200 dark:border-slate-800">
      <div class="space-y-2 p-3">
        <div class="flex gap-1 rounded-xl bg-slate-100 p-1 text-sm dark:bg-slate-800">
          <button class="flex-1 rounded-lg py-1.5" :class="tab === 'mine' ? 'bg-white shadow dark:bg-slate-700' : ''" @click="tab = 'mine'">My groups</button>
          <button class="flex-1 rounded-lg py-1.5" :class="tab === 'discover' ? 'bg-white shadow dark:bg-slate-700' : ''" @click="tab = 'discover'; loadDiscover()">Discover</button>
        </div>
        <form v-if="tab === 'mine'" class="flex gap-2" @submit.prevent="createGroup">
          <input v-model="newGroup" class="input" placeholder="New group name" />
          <button class="btn-primary px-3"><PlusIcon class="h-5 w-5" /></button>
        </form>
        <form v-if="tab === 'mine'" class="flex gap-2" @submit.prevent="join">
          <input v-model="inviteCode" class="input" placeholder="Invite code" />
          <button class="btn-ghost px-3">Join</button>
        </form>
      </div>
      <div class="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        <template v-if="tab === 'mine'">
          <button v-for="g in groups" :key="g.id"
            class="flex w-full items-center gap-3 rounded-xl p-2.5 text-start hover:bg-slate-100 dark:hover:bg-slate-800"
            :class="active?.id === g.id ? 'bg-slate-100 dark:bg-slate-800' : ''" @click="openGroup(g.slug)">
            <div class="grid h-9 w-9 place-items-center rounded-xl bg-brand-600 font-bold text-white">{{ g.name.charAt(0).toUpperCase() }}</div>
            <div class="min-w-0 flex-1">
              <p class="truncate font-semibold">{{ g.name }}</p>
              <p class="text-xs text-slate-500">{{ g.member_count }} members · {{ g.my_role }}</p>
            </div>
          </button>
        </template>
        <template v-else>
          <div v-for="g in discover" :key="g.id" class="flex items-center gap-3 rounded-xl p-2.5">
            <div class="grid h-9 w-9 place-items-center rounded-xl bg-slate-400 font-bold text-white">{{ g.name.charAt(0).toUpperCase() }}</div>
            <div class="min-w-0 flex-1">
              <p class="truncate font-semibold">{{ g.name }}</p>
              <p class="text-xs text-slate-500">{{ g.member_count }} members</p>
            </div>
            <button class="btn-ghost px-2 text-xs" @click="joinPublic(g.slug)">{{ g.my_role ? 'Open' : 'Join' }}</button>
          </div>
        </template>
      </div>
    </aside>

    <section class="flex min-w-0 flex-1 flex-col">
      <template v-if="active">
        <header class="flex h-14 items-center gap-3 border-b border-slate-200 px-4 dark:border-slate-800">
          <p class="font-bold">{{ active.name }}</p>
          <span class="flex items-center gap-1 text-xs text-slate-500"><UsersIcon class="h-4 w-4" />{{ active.member_count }}</span>
        </header>
        <div class="flex min-h-0 flex-1">
          <!-- Channels -->
          <div class="w-48 shrink-0 space-y-1 overflow-y-auto border-e border-slate-200 p-2 dark:border-slate-800">
            <button v-for="ch in active.channels" :key="ch.id"
              class="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
              :class="activeChannel?.id === ch.id ? 'bg-slate-100 font-semibold dark:bg-slate-800' : ''" @click="openChannel(ch)">
              <HashtagIcon class="h-4 w-4 text-slate-400" />{{ ch.name }}
            </button>
            <form class="flex gap-1 pt-1" @submit.prevent="addChannel">
              <input v-model="newChannel" class="input px-2 py-1 text-xs" placeholder="new-channel" />
              <button class="btn-ghost px-2 py-1"><PlusIcon class="h-4 w-4" /></button>
            </form>
          </div>
          <!-- Channel chat -->
          <div class="flex min-w-0 flex-1 flex-col">
            <div class="min-h-0 flex-1 space-y-2 overflow-y-auto p-4">
              <div v-for="m in messages" :key="m.id" class="text-sm">
                <span class="font-semibold text-brand-600">@{{ m.sender?.username }}</span>
                <span class="ms-2 text-slate-700 dark:text-slate-200">{{ m.text }}</span>
              </div>
            </div>
            <form v-if="activeChannel" class="flex gap-2 border-t border-slate-200 p-3 dark:border-slate-800" @submit.prevent="send">
              <input v-model="draft" class="input" :placeholder="`Message #${activeChannel.name}`" />
              <button class="btn-primary px-3"><PaperAirplaneIcon class="h-5 w-5" /></button>
            </form>
          </div>
        </div>
      </template>
      <div v-else class="grid flex-1 place-items-center text-slate-400">Select or create a group</div>
    </section>
  </div>
</template>
