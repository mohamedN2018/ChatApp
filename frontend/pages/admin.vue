<script setup lang="ts">
definePageMeta({ middleware: 'auth' })
const { api } = useApi()

const tab = ref<'overview' | 'reports' | 'flags' | 'users'>('overview')
const stats = ref<any>(null)
const reports = ref<any[]>([])
const flags = ref<any[]>([])
const users = ref<any[]>([])
const userSearch = ref('')
const denied = ref(false)

async function loadOverview() {
  try {
    stats.value = await api<any>('/admin/dashboard/')
  } catch {
    denied.value = true
  }
}
async function loadReports() {
  reports.value = (await api<any>('/admin/reports/')).results || []
}
async function resolveReport(id: string, status: string) {
  await api(`/admin/reports/${id}/`, { method: 'PATCH', body: { status } })
  loadReports()
}
async function loadFlags() {
  flags.value = await api<any[]>('/admin/feature-flags/')
}
async function toggleFlag(f: any) {
  await api(`/admin/feature-flags/${f.key}/`, { method: 'PATCH', body: { is_enabled: !f.is_enabled } })
  loadFlags()
}
async function loadUsers() {
  const q = userSearch.value ? `?search=${encodeURIComponent(userSearch.value)}` : ''
  users.value = (await api<any>(`/admin/users/${q}`)).results || []
}
async function toggleUser(u: any, field: string) {
  const updated = await api<any>(`/admin/users/${u.id}/`, { method: 'PATCH', body: { [field]: !u[field] } })
  Object.assign(u, updated)
}

const maxSignup = computed(() => Math.max(1, ...(stats.value?.charts?.signups || []).map((p: any) => p.count)))
function fmtBytes(n: number) {
  if (!n) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(n) / Math.log(1024))
  return `${(n / 1024 ** i).toFixed(1)} ${u[i]}`
}

watch(tab, (t) => {
  if (t === 'reports') loadReports()
  else if (t === 'flags') loadFlags()
  else if (t === 'users') loadUsers()
})
onMounted(loadOverview)
</script>

<template>
  <div class="mx-auto max-w-5xl p-4 sm:p-6">
    <h1 class="mb-4 text-2xl font-bold">Admin</h1>
    <p v-if="denied" class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-500/10">
      You need staff privileges to view the admin panel.
    </p>

    <template v-else>
      <div class="mb-5 flex gap-1 overflow-x-auto rounded-xl bg-slate-100 p-1 text-sm dark:bg-slate-800">
        <button v-for="x in ['overview','reports','flags','users']" :key="x"
          class="rounded-lg px-4 py-1.5 capitalize" :class="tab === x ? 'bg-white shadow dark:bg-slate-700' : ''"
          @click="tab = x as any">{{ x }}</button>
      </div>

      <!-- Overview -->
      <div v-if="tab === 'overview' && stats" class="space-y-5">
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div class="card p-4"><p class="text-2xl font-bold">{{ stats.users.total }}</p><p class="text-xs text-slate-500">Users ({{ stats.users.new_7d }} new)</p></div>
          <div class="card p-4"><p class="text-2xl font-bold">{{ stats.messages.total }}</p><p class="text-xs text-slate-500">Messages</p></div>
          <div class="card p-4"><p class="text-2xl font-bold">{{ stats.calls.total }}</p><p class="text-xs text-slate-500">Calls ({{ stats.calls.ongoing }} live)</p></div>
          <div class="card p-4"><p class="text-2xl font-bold">{{ stats.groups.total }}</p><p class="text-xs text-slate-500">Groups</p></div>
          <div class="card p-4"><p class="text-2xl font-bold">{{ stats.media.count }}</p><p class="text-xs text-slate-500">{{ fmtBytes(stats.media.storage_bytes) }} stored</p></div>
          <div class="card p-4"><p class="text-2xl font-bold">{{ stats.reports.pending }}</p><p class="text-xs text-slate-500">Pending reports</p></div>
        </div>
        <div class="card p-5">
          <h2 class="mb-3 text-sm font-semibold">Signups (14 days)</h2>
          <div class="flex h-32 items-end gap-1">
            <div v-for="(p, i) in stats.charts.signups" :key="i" class="flex-1 rounded-t bg-brand-500"
              :style="{ height: `${(p.count / maxSignup) * 100}%` }" :title="`${p.date}: ${p.count}`" />
            <p v-if="!stats.charts.signups.length" class="text-sm text-slate-400">No data yet</p>
          </div>
        </div>
      </div>

      <!-- Reports -->
      <div v-else-if="tab === 'reports'" class="space-y-2">
        <div v-for="r in reports" :key="r.id" class="card flex items-center gap-3 p-3 text-sm">
          <span class="rounded-md bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-800">{{ r.target_type }}</span>
          <span class="font-medium">{{ r.reason }}</span>
          <span class="text-slate-500">by @{{ r.reporter?.username }}</span>
          <span class="ms-auto rounded-md px-2 py-0.5 text-xs" :class="r.status === 'pending' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'">{{ r.status }}</span>
          <button class="btn-ghost px-2 text-xs" @click="resolveReport(r.id, 'resolved')">Resolve</button>
          <button class="btn-ghost px-2 text-xs" @click="resolveReport(r.id, 'dismissed')">Dismiss</button>
        </div>
        <p v-if="!reports.length" class="p-6 text-center text-slate-400">No reports</p>
      </div>

      <!-- Flags -->
      <div v-else-if="tab === 'flags'" class="space-y-2">
        <div v-for="f in flags" :key="f.id" class="card flex items-center justify-between p-3 text-sm">
          <div><p class="font-medium">{{ f.key }}</p><p class="text-xs text-slate-500">{{ f.description }}</p></div>
          <button class="rounded-full px-3 py-1 text-xs font-semibold" :class="f.is_enabled ? 'bg-emerald-500 text-white' : 'bg-slate-300 dark:bg-slate-700'" @click="toggleFlag(f)">
            {{ f.is_enabled ? 'ON' : 'OFF' }}
          </button>
        </div>
        <p v-if="!flags.length" class="p-6 text-center text-slate-400">No feature flags</p>
      </div>

      <!-- Users -->
      <div v-else-if="tab === 'users'" class="space-y-2">
        <form class="mb-2 flex gap-2" @submit.prevent="loadUsers">
          <input v-model="userSearch" class="input" placeholder="Search users…" />
          <button class="btn-ghost px-3">Search</button>
        </form>
        <div v-for="u in users" :key="u.id" class="card flex items-center gap-3 p-3 text-sm">
          <span class="font-medium">@{{ u.username }}</span>
          <span class="text-slate-500">{{ u.email }}</span>
          <div class="ms-auto flex gap-2">
            <button class="rounded-md px-2 py-1 text-xs" :class="u.is_verified ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 dark:bg-slate-800'" @click="toggleUser(u, 'is_verified')">Verified</button>
            <button class="rounded-md px-2 py-1 text-xs" :class="u.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'" @click="toggleUser(u, 'is_active')">{{ u.is_active ? 'Active' : 'Suspended' }}</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
