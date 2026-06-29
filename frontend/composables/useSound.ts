// Lightweight tones via the Web Audio API (no audio assets needed): a short
// notification chime for new messages and a looping ringtone for incoming calls.
let ctx: AudioContext | null = null
let ringTimer: any = null

function audioCtx(): AudioContext | null {
  if (!import.meta.client) return null
  if (!ctx) {
    const Ctor = window.AudioContext || (window as any).webkitAudioContext
    if (!Ctor) return null
    ctx = new Ctor()
  }
  if (ctx.state === 'suspended') ctx.resume().catch(() => {})
  return ctx
}

function tone(freq: number, duration = 0.15, vol = 0.07) {
  const ac = audioCtx()
  if (!ac) return
  try {
    const osc = ac.createOscillator()
    const gain = ac.createGain()
    osc.type = 'sine'
    osc.frequency.value = freq
    gain.gain.value = vol
    osc.connect(gain)
    gain.connect(ac.destination)
    const now = ac.currentTime
    osc.start(now)
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration)
    osc.stop(now + duration)
  } catch {
    /* autoplay may be blocked until a user gesture */
  }
}

export function useSound() {
  function notify() {
    tone(880, 0.12)
    setTimeout(() => tone(1180, 0.12), 130)
  }
  function ringStart() {
    if (ringTimer) return
    const ring = () => {
      tone(480, 0.4, 0.09)
      setTimeout(() => tone(620, 0.4, 0.09), 450)
    }
    ring()
    ringTimer = setInterval(ring, 2200)
  }
  function ringStop() {
    clearInterval(ringTimer)
    ringTimer = null
  }
  return { notify, ringStart, ringStop }
}
