<script setup lang="ts">
const emit = defineEmits<{ select: [emoji: string] }>()

const cats = [
  {
    name: 'Smileys',
    icon: '😀',
    list: '😀 😃 😄 😁 😆 😅 😂 🤣 🙂 🙃 😉 😊 😇 🥰 😍 🤩 😘 😗 😚 😙 😋 😛 😜 🤪 😝 🤑 🤗 🤭 🤫 🤔 🤐 😐 😑 😶 😏 😒 🙄 😬 🤥 😌 😔 😪 🤤 😴 😷 🤒 🤕 🤧 🥵 🥶 🥴 😵 🤯 🤠 🥳 😎 🤓 🧐 😕 😟 🙁 😮 😯 😲 😳 🥺 😦 😧 😨 😰 😥 😢 😭 😱 😖 😣 😞 😓 😩 😫 🥱 😤 😡 😠 🤬 😈 👿 💀 💩 🤡',
  },
  {
    name: 'Gestures',
    icon: '👍',
    list: '👍 👎 👌 ✌️ 🤞 🤟 🤘 🤙 👈 👉 👆 👇 ☝️ ✋ 🤚 🖐️ 🖖 👋 🤝 🙏 ✍️ 💪 👏 🙌 👐 🤲 🤜 🤛 ✊ 👊',
  },
  {
    name: 'Hearts',
    icon: '❤️',
    list: '❤️ 🧡 💛 💚 💙 💜 🤎 🖤 🤍 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝 💟 💯 ✨ 🔥 🎉 🎊 🌟 ⭐',
  },
  {
    name: 'Animals',
    icon: '🐶',
    list: '🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🐔 🐧 🐦 🐤 🦄 🐴 🦋 🐢 🐍 🐙 🦀 🐠 🐬 🐳 🐝 🐞',
  },
  {
    name: 'Food',
    icon: '🍔',
    list: '🍏 🍎 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🥑 🌽 🥕 🍔 🍟 🍕 🌭 🥪 🌮 🌯 🍜 🍝 🍣 🍱 🍙 🍩 🍪 🎂 🍰 🍫 🍬 🍭 🍦 ☕ 🍵 🍺 🍷 🥤',
  },
  {
    name: 'Activities',
    icon: '⚽',
    list: '⚽ 🏀 🏈 ⚾ 🎾 🏐 🏉 🎱 🏓 🏸 🥅 🏒 🥊 🥋 🎯 ⛳ 🎮 🎲 🎸 🎹 🎺 🎻 🥁 🎤 🎧 🎬 🏆 🥇 🥈 🥉 🚗 ✈️ 🚀 🌍 🏖️ 🗺️',
  },
  {
    name: 'Symbols',
    icon: '✅',
    list: '✅ ❌ ❓ ❗ ⚠️ 💤 💬 💭 🔔 🔕 ⚡ 💥 💫 ☀️ 🌙 ☁️ 🌈 ❄️ 💧 🔴 🟠 🟡 🟢 🔵 🟣 ⚫ ⚪ ✔️ ➕ ➖ 🔗 🔒 🔑',
  },
].map((c) => ({ ...c, emojis: c.list.split(' ') }))

const active = ref(0)
</script>

<template>
  <div class="w-[300px] max-w-[88vw] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-800">
    <div class="flex border-b border-slate-100 dark:border-slate-700">
      <button v-for="(c, i) in cats" :key="i" type="button" class="flex-1 py-2 text-lg"
        :class="active === i ? 'bg-slate-100 dark:bg-slate-700' : ''" @click="active = i">{{ c.icon }}</button>
    </div>
    <div class="grid max-h-56 grid-cols-8 gap-0.5 overflow-y-auto p-2">
      <button v-for="(e, i) in cats[active].emojis" :key="i" type="button"
        class="rounded-lg p-1 text-xl transition hover:scale-110 hover:bg-slate-100 dark:hover:bg-slate-700"
        @click="emit('select', e)">{{ e }}</button>
    </div>
  </div>
</template>
