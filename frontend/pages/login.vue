<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

const auth = useAuthStore()
const t = useT()
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const route = useRoute()

onMounted(() => {
  if (auth.isAuthenticated) navigateTo('/')
})

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    await navigateTo('/')
  } catch (e: any) {
    error.value = e?.data?.error?.message || 'Invalid email or password.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="grid min-h-full place-items-center p-4">
    <div class="card w-full max-w-md p-8">
      <h1 class="text-2xl font-bold">{{ t('auth.welcome') }}</h1>
      <p class="mt-1 text-sm text-slate-500">{{ t('auth.login') }} · {{ t('app.name') }}</p>

      <p v-if="route.query.registered" class="mt-4 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
        {{ t('auth.registered') }}
      </p>

      <form class="mt-6 space-y-4" @submit.prevent="submit">
        <div>
          <label class="mb-1 block text-sm font-medium">{{ t('auth.email') }}</label>
          <input v-model="email" type="email" required class="input" placeholder="you@example.com" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium">{{ t('auth.password') }}</label>
          <input v-model="password" type="password" required class="input" placeholder="••••••••" />
        </div>
        <p v-if="error" class="text-sm text-red-500">{{ error }}</p>
        <button type="submit" class="btn-primary w-full" :disabled="loading">
          {{ loading ? '…' : t('auth.login') }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-slate-500">
        {{ t('auth.noAccount') }}
        <NuxtLink to="/register" class="font-semibold text-brand-600 hover:underline">{{ t('auth.register') }}</NuxtLink>
      </p>
    </div>
  </div>
</template>
