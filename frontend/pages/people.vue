<script setup lang="ts">
import { MagnifyingGlassIcon, UserPlusIcon, ChatBubbleLeftIcon, CheckIcon, XMarkIcon, NoSymbolIcon } from '@heroicons/vue/24/solid'

definePageMeta({ middleware: 'auth' })
const { api } = useApi()
const toast = useToast()

const tab = ref<'find' | 'friends' | 'requests' | 'following'>('find')
const q = ref('')
const results = ref<any[]>([])
const searching = ref(false)
const friends = ref<any[]>([])
const incoming = ref<any[]>([])
const outgoing = ref<any[]>([])
const following = ref<any[]>([])
const followers = ref<any[]>([])

let searchTimer: any
function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(doSearch, 300)
}
async function doSearch() {
  const term = q.value.trim()
  if (term.length < 2) {
    results.value = []
    return
  }
  searching.value = true
  try {
    const data = await api<any>(`/profiles/search/?q=${encodeURIComponent(term)}`)
    results.value = data.results || data
  } finally {
    searching.value = false
  }
}

async function loadFriends() {
  friends.value = (await api<any>('/social/me/friends/')).results || []
}
async function loadRequests() {
  incoming.value = (await api<any>('/social/me/friend-requests/incoming/')).results || []
  outgoing.value = (await api<any>('/social/me/friend-requests/outgoing/')).results || []
}
async function loadFollowing() {
  following.value = (await api<any>('/social/me/following/')).results || []
  followers.value = (await api<any>('/social/me/followers/')).results || []
}

async function addFriend(u: any) {
  try {
    await api(`/social/users/${u.username}/friend-request/`, { method: 'POST' })
    toast.success(`Friend request sent to @${u.username}`)
  } catch {
    toast.error('Could not send request')
  }
}
async function follow(u: any) {
  try {
    await api(`/social/users/${u.username}/follow/`, { method: 'POST' })
    toast.success(`Following @${u.username}`)
  } catch {
    toast.error('Could not follow')
  }
}
async function block(u: any) {
  try {
    await api(`/social/users/${u.username}/block/`, { method: 'POST' })
    toast.info(`Blocked @${u.username}`)
  } catch {
    toast.error('Could not block')
  }
}
async function accept(r: any) {
  await api(`/social/friend-requests/${r.id}/accept/`, { method: 'POST' })
  toast.success(`You and @${r.from_user.username} are now friends`)
  loadRequests()
  loadFriends()
}
async function reject(r: any) {
  await api(`/social/friend-requests/${r.id}/reject/`, { method: 'POST' })
  loadRequests()
}
async function cancel(r: any) {
  await api(`/social/friend-requests/${r.id}/cancel/`, { method: 'POST' })
  loadRequests()
}
async function removeFriend(u: any) {
  await api(`/social/users/${u.username}/friend/`, { method: 'DELETE' })
  loadFriends()
}
async function message(u: any) {
  try {
    await api('/chat/conversations/start/', { method: 'POST', body: { username: u.username } })
    await navigateTo('/')
  } catch {
    toast.error('Could not open chat')
  }
}

watch(tab, (newTab) => {
  if (newTab === 'friends') loadFriends()
  else if (newTab === 'requests') loadRequests()
  else if (newTab === 'following') loadFollowing()
})
</script>

<template>
  <div class="mx-auto h-full max-w-2xl space-y-4 overflow-y-auto p-4 pb-8 sm:p-6">
    <h1 class="text-2xl font-bold">People</h1>

    <div class="flex gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1 text-sm dark:bg-slate-800">
      <button v-for="x in ['find','friends','requests','following']" :key="x"
        class="flex-1 whitespace-nowrap rounded-lg px-3 py-1.5 capitalize" :class="tab === x ? 'bg-white shadow dark:bg-slate-700' : ''"
        @click="tab = x as any">{{ x }}</button>
    </div>

    <!-- Find -->
    <div v-if="tab === 'find'" class="space-y-2">
      <div class="relative">
        <MagnifyingGlassIcon class="pointer-events-none absolute inset-y-0 start-3 my-auto h-4 w-4 text-slate-400" />
        <input v-model="q" class="input ps-9" placeholder="Search by username or name…" @input="onSearch" />
      </div>
      <p v-if="searching" class="p-4 text-center text-sm text-slate-400">Searching…</p>
      <div v-for="u in results" :key="u.id" class="card flex items-center gap-3 p-3">
        <NuxtLink :to="`/u/${u.username}`"><Avatar :src="u.avatar" :name="u.username" /></NuxtLink>
        <NuxtLink :to="`/u/${u.username}`" class="min-w-0 flex-1">
          <p class="truncate font-semibold">{{ u.display_name || u.username }}</p>
          <p class="truncate text-sm text-slate-500">@{{ u.username }}</p>
        </NuxtLink>
        <button class="btn-ghost h-9 w-9 px-0" title="Add friend" @click="addFriend(u)"><UserPlusIcon class="h-5 w-5" /></button>
        <button class="btn-ghost h-9 w-9 px-0" title="Message" @click="message(u)"><ChatBubbleLeftIcon class="h-5 w-5" /></button>
        <button class="btn-ghost h-9 w-9 px-0 text-red-500" title="Block" @click="block(u)"><NoSymbolIcon class="h-5 w-5" /></button>
      </div>
      <p v-if="q.length >= 2 && !searching && !results.length" class="p-6 text-center text-slate-400">No users found</p>
    </div>

    <!-- Friends -->
    <div v-else-if="tab === 'friends'" class="space-y-2">
      <div v-for="u in friends" :key="u.id" class="card flex items-center gap-3 p-3">
        <NuxtLink :to="`/u/${u.username}`"><Avatar :src="u.avatar" :name="u.username" /></NuxtLink>
        <div class="min-w-0 flex-1"><p class="truncate font-semibold">@{{ u.username }}</p></div>
        <button class="btn-primary px-3 py-1.5 text-sm" @click="message(u)">Message</button>
        <button class="btn-ghost px-2 text-sm text-red-500" @click="removeFriend(u)">Remove</button>
      </div>
      <p v-if="!friends.length" class="p-6 text-center text-slate-400">No friends yet — find people to connect.</p>
    </div>

    <!-- Requests -->
    <div v-else-if="tab === 'requests'" class="space-y-4">
      <div>
        <h2 class="mb-2 text-sm font-semibold text-slate-500">Incoming</h2>
        <div v-for="r in incoming" :key="r.id" class="card mb-2 flex items-center gap-3 p-3">
          <Avatar :src="r.from_user.avatar" :name="r.from_user.username" />
          <p class="min-w-0 flex-1 truncate font-semibold">@{{ r.from_user.username }}</p>
          <button class="grid h-9 w-9 place-items-center rounded-full bg-emerald-500 text-white" @click="accept(r)"><CheckIcon class="h-5 w-5" /></button>
          <button class="grid h-9 w-9 place-items-center rounded-full bg-slate-200 dark:bg-slate-700" @click="reject(r)"><XMarkIcon class="h-5 w-5" /></button>
        </div>
        <p v-if="!incoming.length" class="text-sm text-slate-400">No incoming requests</p>
      </div>
      <div>
        <h2 class="mb-2 text-sm font-semibold text-slate-500">Sent</h2>
        <div v-for="r in outgoing" :key="r.id" class="card mb-2 flex items-center gap-3 p-3">
          <Avatar :src="r.to_user.avatar" :name="r.to_user.username" />
          <p class="min-w-0 flex-1 truncate font-semibold">@{{ r.to_user.username }}</p>
          <button class="btn-ghost px-2 text-sm" @click="cancel(r)">Cancel</button>
        </div>
        <p v-if="!outgoing.length" class="text-sm text-slate-400">No sent requests</p>
      </div>
    </div>

    <!-- Following -->
    <div v-else class="space-y-4">
      <div>
        <h2 class="mb-2 text-sm font-semibold text-slate-500">Following ({{ following.length }})</h2>
        <div v-for="u in following" :key="u.id" class="card mb-2 flex items-center gap-3 p-3">
          <Avatar :src="u.avatar" :name="u.username" />
          <p class="min-w-0 flex-1 truncate font-semibold">@{{ u.username }}</p>
          <NuxtLink :to="`/u/${u.username}`" class="btn-ghost px-2 text-sm">View</NuxtLink>
        </div>
        <p v-if="!following.length" class="text-sm text-slate-400">Not following anyone</p>
      </div>
      <div>
        <h2 class="mb-2 text-sm font-semibold text-slate-500">Followers ({{ followers.length }})</h2>
        <div v-for="u in followers" :key="u.id" class="card mb-2 flex items-center gap-3 p-3">
          <Avatar :src="u.avatar" :name="u.username" />
          <p class="min-w-0 flex-1 truncate font-semibold">@{{ u.username }}</p>
        </div>
        <p v-if="!followers.length" class="text-sm text-slate-400">No followers yet</p>
      </div>
    </div>
  </div>
</template>
