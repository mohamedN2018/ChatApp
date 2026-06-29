<script setup lang="ts">
import { ChatBubbleLeftIcon, UserPlusIcon, UserMinusIcon, NoSymbolIcon, CheckBadgeIcon } from '@heroicons/vue/24/solid'

definePageMeta({ middleware: 'auth' })
const { api } = useApi()
const route = useRoute()
const toast = useToast()
const mediaUrl = useMediaUrl()

const username = computed(() => route.params.username as string)
const profile = ref<any>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    profile.value = await api<any>(`/profiles/${username.value}/`)
  } catch (e: any) {
    error.value = e?.response?.status === 403 ? 'This profile is private.' : 'Profile not found.'
  } finally {
    loading.value = false
  }
}
const rel = computed(() => profile.value?.relationship)

async function act(fn: () => Promise<any>, msg: string) {
  try {
    await fn()
    if (msg) toast.success(msg)
    await load()
  } catch {
    toast.error('Action failed')
  }
}
const follow = () => act(() => api(`/social/users/${username.value}/follow/`, { method: 'POST' }), 'Following')
const unfollow = () => act(() => api(`/social/users/${username.value}/follow/`, { method: 'DELETE' }), 'Unfollowed')
const addFriend = () => act(() => api(`/social/users/${username.value}/friend-request/`, { method: 'POST' }), 'Friend request sent')
const removeFriend = () => act(() => api(`/social/users/${username.value}/friend/`, { method: 'DELETE' }), 'Removed')
const block = () => act(() => api(`/social/users/${username.value}/block/`, { method: 'POST' }), 'Blocked')
const unblock = () => act(() => api(`/social/users/${username.value}/block/`, { method: 'DELETE' }), 'Unblocked')
async function message() {
  await api('/chat/conversations/start/', { method: 'POST', body: { username: username.value } }).catch(() => {})
  await navigateTo('/')
}

onMounted(load)
</script>

<template>
  <div class="mx-auto h-full max-w-2xl overflow-y-auto pb-8">
    <Skeleton v-if="loading" :rows="4" />
    <div v-else-if="error" class="grid place-items-center p-16 text-center text-slate-400">{{ error }}</div>
    <div v-else-if="profile">
      <!-- cover -->
      <div class="relative h-36 bg-gradient-to-r from-brand-500 to-violet-500 sm:h-44">
        <img v-if="profile.cover" :src="mediaUrl(profile.cover)" class="h-full w-full object-cover" />
        <NuxtLink to="/people" class="absolute start-3 top-3 grid h-9 w-9 place-items-center rounded-full bg-black/30 text-white pt-safe">←</NuxtLink>
      </div>

      <div class="px-4 sm:px-6">
        <div class="-mt-10 flex items-end justify-between">
          <div class="rounded-full border-4 border-white dark:border-slate-950">
            <Avatar :src="profile.avatar" :name="profile.user.username" :size="80" />
          </div>
          <div class="mb-2 flex gap-2">
            <button class="btn-primary px-3 py-2 text-sm" @click="message"><ChatBubbleLeftIcon class="h-4 w-4" /> Message</button>
          </div>
        </div>

        <div class="mt-3">
          <h1 class="flex items-center gap-1 text-xl font-bold">
            {{ profile.user.display_name || profile.user.username }}
            <CheckBadgeIcon v-if="profile.user.is_verified" class="h-5 w-5 text-brand-500" />
          </h1>
          <p class="text-slate-500">@{{ profile.user.username }}</p>
          <p v-if="profile.bio" class="mt-2 text-sm">{{ profile.bio }}</p>
          <div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
            <span v-if="profile.country">📍 {{ profile.country }}</span>
            <a v-if="profile.website" :href="profile.website" target="_blank" class="text-brand-600 hover:underline">🔗 {{ profile.website }}</a>
          </div>
          <div class="mt-3 flex gap-4 text-sm">
            <span><b>{{ profile.following_count }}</b> <span class="text-slate-500">following</span></span>
            <span><b>{{ profile.followers_count }}</b> <span class="text-slate-500">followers</span></span>
          </div>
        </div>

        <!-- actions -->
        <div v-if="rel" class="mt-4 flex flex-wrap gap-2">
          <template v-if="rel.is_blocked">
            <button class="btn-ghost border border-slate-200 px-4 py-2 text-sm dark:border-slate-700" @click="unblock">Unblock</button>
          </template>
          <template v-else>
            <button v-if="rel.is_following" class="btn-ghost border border-slate-200 px-4 py-2 text-sm dark:border-slate-700" @click="unfollow"><UserMinusIcon class="h-4 w-4" /> Unfollow</button>
            <button v-else class="btn-primary px-4 py-2 text-sm" @click="follow"><UserPlusIcon class="h-4 w-4" /> Follow</button>
            <button v-if="rel.is_friend" class="btn-ghost border border-slate-200 px-4 py-2 text-sm dark:border-slate-700" @click="removeFriend">Remove friend</button>
            <button v-else class="btn-ghost border border-slate-200 px-4 py-2 text-sm dark:border-slate-700" @click="addFriend"><UserPlusIcon class="h-4 w-4" /> Add friend</button>
            <button class="btn-ghost px-3 py-2 text-sm text-red-500" @click="block"><NoSymbolIcon class="h-4 w-4" /> Block</button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>
