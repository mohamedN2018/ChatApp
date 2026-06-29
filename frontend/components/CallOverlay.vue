<script setup lang="ts">
import {
  PhoneXMarkIcon, MicrophoneIcon, VideoCameraIcon, VideoCameraSlashIcon, PhoneIcon,
  ComputerDesktopIcon,
} from '@heroicons/vue/24/solid'

const call = useCall()
const sound = useSound()
const localVideo = ref<HTMLVideoElement | null>(null)
const remoteVideo = ref<HTMLVideoElement | null>(null)

// Connect the call socket so incoming calls arrive even when idle.
onMounted(() => call.listen())

// Ring while a call is incoming; stop once answered/declined/ended.
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
</script>

<template>
  <!-- Incoming call prompt -->
  <div v-if="call.status.value === 'incoming'" class="fixed inset-x-0 top-4 z-50 mx-auto w-full max-w-sm px-4">
    <div class="card flex items-center gap-3 p-4 shadow-xl">
      <div class="grid h-12 w-12 place-items-center rounded-full bg-brand-100 font-bold text-brand-700 dark:bg-brand-700/30 dark:text-brand-100">
        {{ (call.incoming.value?.initiator?.username || '?').charAt(0).toUpperCase() }}
      </div>
      <div class="flex-1">
        <p class="font-semibold">@{{ call.incoming.value?.initiator?.username }}</p>
        <p class="text-sm text-slate-500">Incoming {{ call.type.value }} call…</p>
      </div>
      <button class="grid h-11 w-11 place-items-center rounded-full bg-red-500 text-white" @click="call.reject()">
        <PhoneXMarkIcon class="h-5 w-5" />
      </button>
      <button class="grid h-11 w-11 place-items-center rounded-full bg-emerald-500 text-white" @click="call.accept()">
        <PhoneIcon class="h-5 w-5" />
      </button>
    </div>
  </div>

  <!-- Active call -->
  <div v-else-if="call.status.value !== 'idle'" class="fixed inset-0 z-50 flex flex-col bg-slate-950 text-white">
    <div class="relative flex-1">
      <video ref="remoteVideo" autoplay playsinline class="h-full w-full bg-slate-900 object-cover" />
      <div v-if="call.status.value !== 'ongoing'" class="absolute inset-0 grid place-items-center">
        <div class="text-center">
          <div class="mx-auto mb-3 h-20 w-20 animate-pulse rounded-full bg-brand-600/40" />
          <p class="text-lg font-medium capitalize">{{ call.status.value }}…</p>
        </div>
      </div>
      <video ref="localVideo" autoplay playsinline muted
        class="absolute bottom-4 end-4 h-36 w-28 rounded-xl border border-white/20 bg-slate-800 object-cover shadow-lg" />
    </div>

    <div class="flex items-center justify-center gap-4 p-6">
      <button class="grid h-12 w-12 place-items-center rounded-full"
        :class="call.muted.value ? 'bg-white text-slate-900' : 'bg-white/15'" @click="call.toggleMute()">
        <MicrophoneIcon class="h-6 w-6" />
      </button>
      <button v-if="call.type.value === 'video'" class="grid h-12 w-12 place-items-center rounded-full"
        :class="call.videoOff.value ? 'bg-white text-slate-900' : 'bg-white/15'" @click="call.toggleVideo()" title="Camera">
        <VideoCameraSlashIcon v-if="call.videoOff.value" class="h-6 w-6" />
        <VideoCameraIcon v-else class="h-6 w-6" />
      </button>
      <button class="grid h-12 w-12 place-items-center rounded-full"
        :class="call.isScreenSharing.value ? 'bg-brand-500' : 'bg-white/15'" @click="call.toggleScreenShare()" title="Share screen">
        <ComputerDesktopIcon class="h-6 w-6" />
      </button>
      <button class="grid h-14 w-14 place-items-center rounded-full bg-red-500" @click="call.hangup()" title="End call">
        <PhoneXMarkIcon class="h-7 w-7" />
      </button>
    </div>
  </div>
</template>
