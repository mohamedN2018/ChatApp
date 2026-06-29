<script setup lang="ts">
import { useAuthStore } from '~/stores/auth'
import { useUiStore } from '~/stores/ui'
import {
  SunIcon, MoonIcon, ChatBubbleLeftRightIcon, ArrowRightOnRectangleIcon,
  UserGroupIcon, UserCircleIcon, Cog6ToothIcon, UsersIcon,
} from '@heroicons/vue/24/outline'

const auth = useAuthStore()
const ui = useUiStore()
const t = useT()
const route = useRoute()

// The chat thread (and group view) hide the bottom tab bar on mobile so the
// message composer owns the bottom edge — set by those pages.
const hideTabbar = useState('hideTabbar', () => false)

const tabs = computed(() => {
  const base = [
    { to: '/', label: 'Chat', icon: ChatBubbleLeftRightIcon },
    { to: '/groups', label: 'Groups', icon: UserGroupIcon },
    { to: '/people', label: 'People', icon: UsersIcon },
    { to: '/profile', label: 'Profile', icon: UserCircleIcon },
  ]
  if (auth.user?.is_staff) base.push({ to: '/admin', label: 'Admin', icon: Cog6ToothIcon })
  return base
})
function isActive(to: string) {
  return to === '/' ? route.path === '/' : route.path.startsWith(to)
}
</script>

<template>
  <div class="flex h-full flex-col">
    <header class="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-slate-200 bg-white/80 px-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80 sm:px-4">
      <div class="flex items-center gap-4">
        <NuxtLink to="/" class="flex items-center gap-2 font-bold">
          <span class="grid h-8 w-8 place-items-center rounded-xl bg-brand-600 text-white">
            <ChatBubbleLeftRightIcon class="h-5 w-5" />
          </span>
          <span class="hidden text-lg sm:block">{{ t('app.name') }}</span>
        </NuxtLink>
        <nav v-if="auth.isAuthenticated" class="hidden items-center gap-1 text-sm font-medium md:flex">
          <NuxtLink v-for="tabItem in tabs" :key="tabItem.to" :to="tabItem.to"
            class="rounded-lg px-3 py-1.5 hover:bg-slate-200/60 dark:hover:bg-slate-800"
            :class="isActive(tabItem.to) ? 'text-brand-600' : ''">{{ tabItem.label }}</NuxtLink>
        </nav>
      </div>

      <div class="flex items-center gap-1">
        <button class="btn-ghost h-9 w-9 px-0" :title="ui.locale === 'ar' ? 'English' : 'العربية'"
          @click="ui.setLocale(ui.locale === 'ar' ? 'en' : 'ar')">
          <span class="text-sm font-semibold">{{ ui.locale === 'ar' ? 'EN' : 'ع' }}</span>
        </button>
        <button class="btn-ghost h-9 w-9 px-0" :title="ui.theme === 'dark' ? 'Light' : 'Dark'" @click="ui.toggleTheme()">
          <SunIcon v-if="ui.theme === 'dark'" class="h-5 w-5" />
          <MoonIcon v-else class="h-5 w-5" />
        </button>
        <template v-if="auth.isAuthenticated">
          <div class="ms-1 grid h-9 w-9 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700 dark:bg-brand-700/30 dark:text-brand-100">
            {{ (auth.user?.display_name || auth.user?.username || '?').charAt(0).toUpperCase() }}
          </div>
          <button class="btn-ghost h-9 w-9 px-0" :title="t('common.logout')" @click="auth.logout()">
            <ArrowRightOnRectangleIcon class="h-5 w-5" />
          </button>
        </template>
      </div>
    </header>

    <main class="min-h-0 flex-1">
      <slot />
    </main>

    <!-- Mobile bottom tab bar -->
    <nav v-if="auth.isAuthenticated && !hideTabbar"
      class="flex shrink-0 items-stretch border-t border-slate-200 bg-white/90 pb-safe backdrop-blur dark:border-slate-800 dark:bg-slate-900/90 md:hidden">
      <NuxtLink v-for="tabItem in tabs" :key="tabItem.to" :to="tabItem.to"
        class="flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-medium"
        :class="isActive(tabItem.to) ? 'text-brand-600' : 'text-slate-500'">
        <component :is="tabItem.icon" class="h-6 w-6" />
        {{ tabItem.label }}
      </NuxtLink>
    </nav>

    <ClientOnly>
      <CallOverlay v-if="auth.isAuthenticated" />
    </ClientOnly>
    <Toaster />
  </div>
</template>
