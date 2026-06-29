<script setup lang="ts">
withDefaults(defineProps<{ rows?: number; avatar?: boolean }>(), { rows: 6, avatar: true })
</script>

<template>
  <div class="space-y-3 p-3">
    <div v-for="i in rows" :key="i" class="flex items-center gap-3">
      <div v-if="avatar" class="h-10 w-10 shrink-0 animate-pulse rounded-full bg-slate-200 dark:bg-slate-800" />
      <div class="flex-1 space-y-2">
        <div class="h-3 w-1/3 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
        <div class="h-3 w-2/3 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
      </div>
    </div>
  </div>
</template>
