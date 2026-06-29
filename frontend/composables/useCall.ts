import { useAuthStore } from '~/stores/auth'

// 1:1 WebRTC call: REST drives the call lifecycle; the call WebSocket relays SDP/
// ICE. Media is peer-to-peer (mesh). A single client-side singleton holds the
// state so the call overlay (in the layout) and the chat page share one call.
function createCall() {
  const { api } = useApi()
  const auth = useAuthStore()

  const status = ref<'idle' | 'ringing' | 'incoming' | 'connecting' | 'ongoing'>('idle')
  const callId = ref('')
  const type = ref<'audio' | 'video'>('audio')
  const incoming = ref<any>(null)
  const peer = ref<any>(null)
  const duration = ref(0)
  const localStream = ref<MediaStream | null>(null)
  const remoteStream = ref<MediaStream | null>(null)
  const muted = ref(false)
  const videoOff = ref(false)
  const isScreenSharing = ref(false)

  let pc: RTCPeerConnection | null = null
  let screenStream: MediaStream | null = null
  let remoteUserId = ''
  let durationTimer: any = null
  let currentCameraId = ''

  function markOngoing() {
    status.value = 'ongoing'
    if (!durationTimer) durationTimer = setInterval(() => (duration.value += 1), 1000)
  }
  let iceServers: RTCIceServer[] = [{ urls: ['stun:stun.l.google.com:19302'] }]
  const socket = useSocket('/ws/calls/')

  socket.on(onEvent)

  async function loadIce() {
    try {
      const r = await api<any>('/calls/ice-servers/')
      if (r?.iceServers?.length) iceServers = r.iceServers
    } catch {
      /* keep STUN default */
    }
  }

  async function getMedia() {
    localStream.value = await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: type.value === 'video',
    })
    currentCameraId = localStream.value.getVideoTracks()[0]?.getSettings().deviceId || ''
  }

  async function switchCamera() {
    if (type.value !== 'video' || !pc) return
    const devices = await navigator.mediaDevices.enumerateDevices()
    const cams = devices.filter((d) => d.kind === 'videoinput')
    if (cams.length < 2) return
    const idx = cams.findIndex((c) => c.deviceId === currentCameraId)
    const next = cams[(idx + 1) % cams.length]
    const fresh = await navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: next.deviceId } } })
    const track = fresh.getVideoTracks()[0]
    currentCameraId = next.deviceId
    if (!isScreenSharing.value) {
      pc.getSenders().find((s) => s.track?.kind === 'video')?.replaceTrack(track)
    }
    // Swap the track in the local preview stream.
    const old = localStream.value?.getVideoTracks()[0]
    if (old && localStream.value) {
      localStream.value.removeTrack(old)
      old.stop()
      localStream.value.addTrack(track)
      localStream.value = new MediaStream(localStream.value.getTracks())
    }
  }

  function newPc() {
    pc = new RTCPeerConnection({ iceServers })
    pc.onicecandidate = (e) => {
      if (e.candidate) sendSignal({ candidate: e.candidate })
    }
    pc.ontrack = (e) => {
      remoteStream.value = e.streams[0]
      markOngoing()
    }
    localStream.value?.getTracks().forEach((tr) => pc!.addTrack(tr, localStream.value!))
  }

  function sendSignal(data: any) {
    socket.send({ action: 'signal', call_id: callId.value, to_user_id: remoteUserId, data })
  }

  async function onEvent(evt: any) {
    switch (evt.event) {
      case 'call.incoming':
        if (status.value === 'idle') {
          incoming.value = evt.call
          peer.value = evt.call.initiator
          callId.value = evt.call.id
          type.value = evt.call.type
          status.value = 'incoming'
        }
        break
      case 'peer.joined':
        // The other side connected — initiator makes the offer.
        if (evt.user_id !== auth.user?.id && (status.value === 'ringing' || status.value === 'connecting')) {
          remoteUserId = evt.user_id
          if (!pc) newPc()
          status.value = 'connecting'
          const offer = await pc!.createOffer()
          await pc!.setLocalDescription(offer)
          sendSignal(offer)
        }
        break
      case 'call.signal': {
        const d = evt.data
        if (d?.type === 'offer') {
          remoteUserId = evt.from_user_id
          if (!pc) newPc()
          await pc!.setRemoteDescription(d)
          const answer = await pc!.createAnswer()
          await pc!.setLocalDescription(answer)
          sendSignal(answer)
        } else if (d?.type === 'answer') {
          await pc?.setRemoteDescription(d)
        } else if (d?.candidate) {
          try {
            await pc?.addIceCandidate(d.candidate)
          } catch {
            /* ignore late/duplicate candidates */
          }
        }
        break
      }
      case 'call.rejected':
      case 'call.ended':
        cleanup()
        break
    }
  }

  async function start(conversationId: string, video: boolean, peerInfo: any = null) {
    if (status.value !== 'idle') return
    peer.value = peerInfo
    type.value = video ? 'video' : 'audio'
    await loadIce()
    socket.connect()
    await getMedia()
    const call = await api<any>('/calls/initiate/', {
      method: 'POST',
      body: { conversation_id: conversationId, type: type.value },
    })
    callId.value = call.id
    status.value = 'ringing'
    socket.send({ action: 'join', call_id: call.id }) // join the room to receive peer.joined
  }

  async function accept() {
    if (!incoming.value) return
    await loadIce()
    socket.connect()
    await getMedia()
    await api(`/calls/${callId.value}/accept/`, { method: 'POST' }).catch(() => {})
    socket.send({ action: 'join', call_id: callId.value })
    status.value = 'connecting'
    incoming.value = null
  }

  async function hangup() {
    if (callId.value) {
      socket.send({ action: 'leave', call_id: callId.value })
      await api(`/calls/${callId.value}/end/`, { method: 'POST', body: { end: 'true' } }).catch(() => {})
    }
    cleanup()
  }

  function reject() {
    if (callId.value) api(`/calls/${callId.value}/reject/`, { method: 'POST' }).catch(() => {})
    cleanup()
  }

  function cleanup() {
    pc?.close()
    pc = null
    localStream.value?.getTracks().forEach((t) => t.stop())
    screenStream?.getTracks().forEach((t) => t.stop())
    screenStream = null
    localStream.value = null
    remoteStream.value = null
    remoteUserId = ''
    currentCameraId = ''
    callId.value = ''
    incoming.value = null
    peer.value = null
    clearInterval(durationTimer)
    durationTimer = null
    duration.value = 0
    muted.value = false
    videoOff.value = false
    isScreenSharing.value = false
    status.value = 'idle'
  }

  function toggleMute() {
    muted.value = !muted.value
    localStream.value?.getAudioTracks().forEach((t) => (t.enabled = !muted.value))
    socket.send({ action: 'state', call_id: callId.value, is_muted: muted.value })
  }
  function toggleVideo() {
    videoOff.value = !videoOff.value
    localStream.value?.getVideoTracks().forEach((t) => (t.enabled = !videoOff.value))
    socket.send({ action: 'state', call_id: callId.value, is_video_on: !videoOff.value })
  }

  async function renegotiate() {
    if (!pc) return
    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    sendSignal(offer)
  }

  async function toggleScreenShare() {
    if (isScreenSharing.value) return stopScreen()
    try {
      screenStream = await (navigator.mediaDevices as any).getDisplayMedia({ video: true })
    } catch {
      return
    }
    const track = screenStream!.getVideoTracks()[0]
    track.onended = () => stopScreen()
    const sender = pc?.getSenders().find((s) => s.track?.kind === 'video')
    if (sender) {
      await sender.replaceTrack(track)
    } else if (pc) {
      pc.addTrack(track, screenStream!)
      await renegotiate()
    }
    isScreenSharing.value = true
  }

  function stopScreen() {
    if (!isScreenSharing.value) return
    const cam = localStream.value?.getVideoTracks()[0] || null
    pc?.getSenders().find((s) => s.track?.kind === 'video')?.replaceTrack(cam)
    screenStream?.getTracks().forEach((t) => t.stop())
    screenStream = null
    isScreenSharing.value = false
  }

  function listen() {
    socket.connect()
  }

  return {
    status, type, incoming, peer, duration, localStream, remoteStream, muted, videoOff,
    isScreenSharing,
    start, accept, reject, hangup, toggleMute, toggleVideo, toggleScreenShare, switchCamera, listen,
  }
}

let _instance: ReturnType<typeof createCall> | null = null

export function useCall() {
  if (!_instance) _instance = createCall()
  return _instance
}
