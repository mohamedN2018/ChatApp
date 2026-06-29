<script setup lang="ts">
import {
  PhoneXMarkIcon, MicrophoneIcon, VideoCameraIcon, VideoCameraSlashIcon, PhoneIcon,
  ComputerDesktopIcon, ArrowPathIcon,
} from '@heroicons/vue/24/solid'

const call = useCall()
const sound = useSound()
const localVideo = ref<HTMLVideoElement | null>(null)
const remoteVideo = ref<HTMLVideoElement | null>(null)

onMounted(() => call.listen())

watch(call.status, (s) => {
  if (s === 'incoming') sound.ringStart()
  else sound.ringStop()
})
watch(call.localStream, (s) => {
  if (localVideo.value) localVideo.value.srcObject = s
})
watch(call.remoteStream, (s) => {
  if (remoteVideo.value) remoteVideo.value.srcObject = s
})

const peerName = computed(() => {
  const p: any = call.peer.value
  return p ? '@' + (p.username || p.display_name) : 'Call'
})
const peerInitial = computed(() => {
  const p: any = call.peer.value
  return (p?.display_name || p?.username || '?').charAt(0).toUpperCase()
})
function fmtDur(s: number) {
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}
const subtitle = computed(() => {
  if (call.status.value === 'ongoing') return fmtDur(call.duration.value)
  if (call.status.value === 'ringing') return 'Ringing…'
  if (call.status.value === 'connecting') return 'Connecting…'
  return ''
})
</script>

<template>
  <!-- Incoming call prompt -->
  <div v-if="call.status.value === 'incoming'" class="fixed inset-x-0 top-0 z-50 px-3 pt-safe">
    <div class="card mx-auto mt-3 flex w-full max-w-sm items-center gap-3 p-4 shadow-2xl">
      <div class="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-brand-100 font-bold text-brand-700 dark:bg-brand-700/30 dark:text-brand-100">
        {{ peerInitial }}
      </div>
      <div class="min-w-0 flex-1">
        <p class="truncate font-semibold">{{ peerName }}</p>
        <p class="text-sm text-slate-500">Incoming {{ call.type.value }} call…</p>
      </div>
      <button class="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-red-500 text-white active:scale-95" @click="call.reject()">
        <PhoneXMarkIcon class="h-6 w-6" />
      </button>
      <button class="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-emerald-500 text-white active:scale-95" @click="call.accept()">
        <PhoneIcon class="h-6 w-6" />
      </button>
    </div>
  </div>

  <!-- Active call -->
  <div v-else-if="call.status.value !== 'idle'" class="fixed inset-0 z-50 flex flex-col bg-slate-950 text-white">
    <!-- top bar -->
    <div class="absolute inset-x-0 top-0 z-10 flex items-center gap-3 bg-gradient-to-b from-black/60 to-transparent px-4 pb-6 pt-safe">
      <div class="grid h-9 w-9 place-items-center rounded-full bg-white/15 text-sm font-bold">{{ peerInitial }}</div>
      <div>
        <p class="font-semibold leading-tight">{{ peerName }}</p>
        <p class="text-xs text-white/70">{{ subtitle }}</p>
      </div>
      <span v-if="call.isScreenSharing.value" class="ms-auto rounded-full bg-brand-500 px-2 py-0.5 text-xs font-medium">Sharing screen</span>
    </div>

    <div class="relative flex-1">
      <video ref="remoteVideo" autoplay playsinline class="h-full w-full bg-slate-900 object-cover" />
      <!-- avatar fallback while connecting / audio call -->
      <div v-if="call.status.value !== 'ongoing' || call.type.value === 'audio'" class="absolute inset-0 grid place-items-center">
        <div class="text-center">
          <div class="mx-auto mb-4 grid h-28 w-28 place-items-center rounded-full bg-brand-600/30 text-4xl font-bold">{{ peerInitial }}</div>
          <p class="text-lg font-medium">{{ peerName }}</p>
          <p class="text-white/60">{{ subtitle }}</p>
        </div>
      </div>
      <video ref="localVideo" autoplay playsinline muted
        class="absolute bottom-4 end-4 h-32 w-24 rounded-2xl border border-white/20 bg-slate-800 object-cover shadow-lg sm:h-40 sm:w-28" />
    </div>

    <!-- controls -->
    <div class="flex items-center justify-center gap-3 px-4 pb-safe pt-4 sm:gap-4 sm:pb-6">
      <button class="grid h-14 w-14 place-items-center rounded-full active:scale-95"
        :class="call.muted.value ? 'bg-white text-slate-900' : 'bg-white/15'" @click="call.toggleMute()" title="Mute">
        <MicrophoneIcon class="h-6 w-6" />
      </button>
      <button v-if="call.type.value === 'video'" class="grid h-14 w-14 place-items-center rounded-full active:scale-95"
        :class="call.videoOff.value ? 'bg-white text-slate-900' : 'bg-white/15'" @click="call.toggleVideo()" title="Camera">
        <VideoCameraSlashIcon v-if="call.videoOff.value" class="h-6 w-6" />
        <VideoCameraIcon v-else class="h-6 w-6" />
      </button>
      <button v-if="call.type.value === 'video'" class="grid h-14 w-14 place-items-center rounded-full bg-white/15 active:scale-95" @click="call.switchCamera()" title="Switch camera">
        <ArrowPathIcon class="h-6 w-6" />
      </button>
      <button class="grid h-14 w-14 place-items-center rounded-full active:scale-95"
        :class="call.isScreenSharing.value ? 'bg-brand-500' : 'bg-white/15'" @click="call.toggleScreenShare()" title="Share screen">
        <ComputerDesktopIcon class="h-6 w-6" />
      </button>
      <button class="grid h-16 w-16 place-items-center rounded-full bg-red-500 active:scale-95" @click="call.hangup()" title="End call">
        <PhoneXMarkIcon class="h-7 w-7" />
      </button>
    </div>
  </div>
</template>
