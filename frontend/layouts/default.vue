<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { useUiStore } from '~/stores/ui'
import { SunIcon, MoonIcon, ChatBubbleLeftRightIcon, ArrowRightOnRectangleIcon } from '@heroicons/vue/24/outline'

const auth = useAuthStore()
const ui = useUiStore()
const t = useT()
</script>

<template>
  <div class="flex h-full flex-col">
    <header class="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white/80 px-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
      <NuxtLink to="/" class="flex items-center gap-2 font-bold">
        <span class="grid h-8 w-8 place-items-center rounded-xl bg-brand-600 text-white">
          <ChatBubbleLeftRightIcon class="h-5 w-5" />
        </span>
        <span class="text-lg">{{ t('app.name') }}</span>
      </NuxtLink>

      <div class="flex items-center gap-1.5">
        <button class="btn-ghost px-2.5" :title="ui.locale === 'ar' ? 'English' : 'العربية'"
          @click="ui.setLocale(ui.locale === 'ar' ? 'en' : 'ar')">
          {{ ui.locale === 'ar' ? 'EN' : 'ع' }}
        </button>
        <button class="btn-ghost px-2.5" :title="ui.theme === 'dark' ? 'Light' : 'Dark'" @click="ui.toggleTheme()">
          <SunIcon v-if="ui.theme === 'dark'" class="h-5 w-5" />
          <MoonIcon v-else class="h-5 w-5" />
        </button>
        <template v-if="auth.isAuthenticated">
          <div class="mx-1 flex items-center gap-2">
            <div class="grid h-8 w-8 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700 dark:bg-brand-700/30 dark:text-brand-100">
              {{ (auth.user?.display_name || auth.user?.username || '?').charAt(0).toUpperCase() }}
            </div>
            <span class="hidden text-sm font-medium sm:block">@{{ auth.user?.username }}</span>
          </div>
          <button class="btn-ghost px-2.5" :title="t('common.logout')" @click="auth.logout()">
            <ArrowRightOnRectangleIcon class="h-5 w-5" />
          </button>
        </template>
      </div>
    </header>

    <main class="min-h-0 flex-1">
      <slot />
    </main>
  </div>
</template>
