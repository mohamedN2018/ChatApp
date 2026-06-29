<script setup lang="ts">
import { CheckCircleIcon, ExclamationCircleIcon, InformationCircleIcon, XMarkIcon } from '@heroicons/vue/24/solid'

const { toasts, dismiss } = useToast()
const icon = { success: CheckCircleIcon, error: ExclamationCircleIcon, info: InformationCircleIcon }
const tint = {
  success: 'text-emerald-500',
  error: 'text-red-500',
  info: 'text-brand-500',
}
</script>

<template>
  <div class="pointer-events-none fixed inset-x-0 top-0 z-[60] flex flex-col items-center gap-2 px-3 pt-safe">
    <TransitionGroup name="toast">
      <div v-for="toUiToast in toasts" :key="toUiToast.id"
        class="pointer-events-auto mt-2 flex w-full max-w-sm items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm shadow-lg dark:border-slate-700 dark:bg-slate-800">
        <component :is="icon[toUiToast.type]" class="h-5 w-5 shrink-0" :class="tint[toUiToast.type]" />
        <span class="flex-1">{{ toUiToast.message }}</span>
        <button class="text-slate-400 hover:text-slate-600" @click="dismiss(toUiToast.id)"><XMarkIcon class="h-4 w-4" /></button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}
</style>
