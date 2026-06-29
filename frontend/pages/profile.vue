<script setup lang="ts">
definePageMeta({ middleware: 'auth' })
const { api } = useApi()
const mediaUrl = useMediaUrl()

const profile = ref<any>(null)
const privacy = ref<any>(null)
const notifications = ref<any>(null)
const saved = ref('')
const avatarInput = ref<HTMLInputElement | null>(null)

const statuses = ['online', 'away', 'busy', 'invisible']

async function load() {
  profile.value = await api<any>('/profiles/me/')
  privacy.value = await api<any>('/profiles/me/privacy/')
  notifications.value = await api<any>('/profiles/me/notifications/')
}
function flash(msg: string) {
  saved.value = msg
  setTimeout(() => (saved.value = ''), 1800)
}
async function saveProfile() {
  await api('/profiles/me/', {
    method: 'PATCH',
    body: {
      bio: profile.value.bio,
      country: profile.value.country,
      website: profile.value.website,
      status: profile.value.status,
      custom_status_text: profile.value.custom_status_text,
    },
  })
  flash('Profile saved')
}
async function savePrivacy() {
  await api('/profiles/me/privacy/', { method: 'PATCH', body: privacy.value })
  flash('Privacy saved')
}
async function saveNotifications() {
  await api('/profiles/me/notifications/', { method: 'PATCH', body: notifications.value })
  flash('Notifications saved')
}
async function onAvatar(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const fd = new FormData()
  fd.append('image', file)
  profile.value = await api<any>('/profiles/me/avatar/', { method: 'POST', body: fd })
  flash('Avatar updated')
}

onMounted(load)
</script>

<template>
  <div v-if="profile" class="mx-auto max-w-2xl space-y-6 p-4 sm:p-6">
    <h1 class="text-2xl font-bold">Profile & settings</h1>
    <p v-if="saved" class="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">{{ saved }}</p>

    <!-- Profile -->
    <div class="card space-y-4 p-5">
      <div class="flex items-center gap-4">
        <div class="grid h-16 w-16 place-items-center overflow-hidden rounded-full bg-brand-100 text-xl font-bold text-brand-700 dark:bg-brand-700/30 dark:text-brand-100">
          <img v-if="profile.avatar" :src="mediaUrl(profile.avatar)" class="h-full w-full object-cover" />
          <span v-else>{{ profile.user.username.charAt(0).toUpperCase() }}</span>
        </div>
        <div>
          <p class="font-semibold">@{{ profile.user.username }}</p>
          <button class="text-sm text-brand-600 hover:underline" @click="avatarInput?.click()">Change avatar</button>
          <input ref="avatarInput" type="file" accept="image/*" class="hidden" @change="onAvatar" />
        </div>
      </div>
      <div>
        <label class="mb-1 block text-sm font-medium">Bio</label>
        <textarea v-model="profile.bio" rows="2" class="input" />
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="mb-1 block text-sm font-medium">Country</label>
          <input v-model="profile.country" maxlength="2" class="input" placeholder="EG" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium">Website</label>
          <input v-model="profile.website" class="input" placeholder="https://" />
        </div>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="mb-1 block text-sm font-medium">Status</label>
          <select v-model="profile.status" class="input">
            <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium">Custom status</label>
          <input v-model="profile.custom_status_text" class="input" placeholder="What's happening?" />
        </div>
      </div>
      <button class="btn-primary" @click="saveProfile">Save profile</button>
    </div>

    <!-- Privacy -->
    <div class="card space-y-3 p-5">
      <h2 class="font-semibold">Privacy</h2>
      <div v-for="key in ['profile_visibility','last_seen_visibility','online_status_visibility','who_can_friend_request']" :key="key"
        class="flex items-center justify-between gap-3 text-sm">
        <span class="capitalize">{{ key.replaceAll('_', ' ') }}</span>
        <select v-model="privacy[key]" class="input w-44">
          <option value="everyone">Everyone</option>
          <option value="friends">Friends</option>
          <option value="nobody">Nobody</option>
        </select>
      </div>
      <button class="btn-primary" @click="savePrivacy">Save privacy</button>
    </div>

    <!-- Notifications -->
    <div class="card space-y-3 p-5">
      <h2 class="font-semibold">Notifications</h2>
      <label v-for="key in ['email_messages','push_messages','push_friend_requests','push_calls','sound_enabled']" :key="key"
        class="flex items-center justify-between text-sm">
        <span class="capitalize">{{ key.replaceAll('_', ' ') }}</span>
        <input v-model="notifications[key]" type="checkbox" class="h-5 w-5 rounded accent-brand-600" />
      </label>
      <button class="btn-primary" @click="saveNotifications">Save notifications</button>
    </div>
  </div>
</template>
