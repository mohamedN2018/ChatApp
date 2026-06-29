# ChatApp Frontend (Nuxt 3)

A Nuxt 3 + TypeScript + TailwindCSS + Pinia client for the ChatApp API.

## What's implemented

* **Auth** — login / register / logout with JWT, automatic access-token refresh,
  and persisted sessions (`stores/auth.ts`, `composables/useApi.ts`).
* **Realtime chat** — conversation list, message thread, optimistic send, live
  delivery + typing, and **image/file attachments** (`pages/index.vue`).
* **Presence** — online/away/busy dots driven by the presence WebSocket.
* **WebRTC calls** — 1:1 audio/video with SDP/ICE over the call WebSocket, an
  incoming-call overlay, and mute/video/hangup controls (`composables/useCall.ts`,
  `components/CallOverlay.vue`).
* **Groups & channels** — create/join/discover, channels, realtime channel chat
  (`pages/groups.vue`).
* **Profile & settings** — edit profile, avatar upload, privacy + notification
  settings (`pages/profile.vue`).
* **Admin** — dashboard stats + chart, report moderation, feature flags, user
  management (`pages/admin.vue`).
* **Theming & i18n** — dark/light theme and English/Arabic with **RTL**, persisted
  (`stores/ui.ts`, `composables/useT.ts`).

## Develop

```bash
npm install
npm run dev      # http://localhost:3000  (expects the API at :8000)
```

Configuration is via runtime env: `NUXT_PUBLIC_API_BASE`, `NUXT_PUBLIC_WS_BASE`.

## Docker

Built and served by the root `docker-compose.yml` as the `frontend` service
(port 3000). `docker compose up --build` brings up the whole stack.

## Stack

Nuxt 3, Vue 3, TypeScript, Pinia, Vue Router, TailwindCSS, Heroicons.
