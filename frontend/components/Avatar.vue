<script setup lang="ts">
const props = withDefaults(
  defineProps<{ src?: string | null; name?: string; size?: number; status?: string | null }>(),
  { size: 40 },
)
const mediaUrl = useMediaUrl()

const initial = computed(() => (props.name || '?').charAt(0).toUpperCase())
const palette = ['bg-brand-500', 'bg-emerald-500', 'bg-amber-500', 'bg-rose-500', 'bg-sky-500', 'bg-violet-500', 'bg-teal-500']
const color = computed(() => palette[(props.name?.charCodeAt(0) || 0) % palette.length])
const dot = computed(
  () => ({ online: 'bg-emerald-500', away: 'bg-amber-400', busy: 'bg-red-500' })[props.status || ''] || 'bg-slate-400',
)
</script>

<template>
  <div class="relative shrink-0" :style="{ width: size + 'px', height: size + 'px' }">
    <img v-if="src" :src="mediaUrl(src)" class="h-full w-full rounded-full object-cover" :alt="name" />
    <div v-else class="grid h-full w-full place-items-center rounded-full font-semibold text-white" :class="color"
      :style="{ fontSize: size * 0.4 + 'px' }">
      {{ initial }}
    </div>
    <span v-if="status" class="absolute -bottom-0.5 -end-0.5 rounded-full border-2 border-white dark:border-slate-900"
      :class="dot" :style="{ width: Math.max(8, size * 0.28) + 'px', height: Math.max(8, size * 0.28) + 'px' }" />
  </div>
</template>
