<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'

const auth = useAuthStore()
const t = useT()
const form = reactive({ email: '', username: '', display_name: '', password: '', password_confirm: '' })
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.register({ ...form })
    await navigateTo('/login?registered=1')
  } catch (e: any) {
    const detail = e?.data?.error?.detail
    error.value = detail
      ? Object.values(detail).flat().join(' ')
      : e?.data?.error?.message || 'Registration failed.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="grid min-h-full place-items-center p-4">
    <div class="card w-full max-w-md p-8">
      <h1 class="text-2xl font-bold">{{ t('auth.join') }}</h1>
      <p class="mt-1 text-sm text-slate-500">{{ t('auth.register') }}</p>

      <form class="mt-6 space-y-4" @submit.prevent="submit">
        <div>
          <label class="mb-1 block text-sm font-medium">{{ t('auth.email') }}</label>
          <input v-model="form.email" type="email" required class="input" placeholder="you@example.com" />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium">{{ t('auth.username') }}</label>
          <input v-model="form.username" required class="input" placeholder="username" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="mb-1 block text-sm font-medium">{{ t('auth.password') }}</label>
            <input v-model="form.password" type="password" required class="input" placeholder="••••••••" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium">{{ t('auth.confirm') }}</label>
            <input v-model="form.password_confirm" type="password" required class="input" placeholder="••••••••" />
          </div>
        </div>
        <p v-if="error" class="text-sm text-red-500">{{ error }}</p>
        <button type="submit" class="btn-primary w-full" :disabled="loading">
          {{ loading ? '…' : t('auth.register') }}
        </button>
      </form>

      <p class="mt-6 text-center text-sm text-slate-500">
        {{ t('auth.haveAccount') }}
        <NuxtLink to="/login" class="font-semibold text-brand-600 hover:underline">{{ t('auth.login') }}</NuxtLink>
      </p>
    </div>
  </div>
</template>
