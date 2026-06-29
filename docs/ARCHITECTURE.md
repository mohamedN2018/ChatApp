# Architecture & Engineering Decisions

This document records the *why* behind the structural choices. It is updated as
each phase lands. Phase 0 establishes the foundation everything else builds on.

## Principles

1. **Vertical slices, not horizontal layers.** Each phase ships a complete,
   working feature (models → API → tests → docs), verified before the next
   begins. No half-wired stubs.
2. **One image, many environments.** Configuration is 12-factor: the same
   Docker image runs in dev/CI/prod and only environment variables change.
3. **Scale-ready from row zero.** UUID keys, soft delete, connection pooling,
   cursor pagination for hot feeds, and Redis-backed caching/presence are built
   into the base, not retrofitted.

## Backend layout

```
backend/
├── config/          Django project (not an app): settings, urls, asgi/wsgi, celery
│   └── settings/    base.py + development.py / production.py / test.py
└── apps/            Django apps, each a bounded context
    ├── common/      cross-cutting primitives (no business domain)
    └── accounts/    identity & the custom User model
```

* **`config` vs `apps`** — project wiring is separated from domain apps so apps
  stay portable and independently testable.
* **Settings split** — `base.py` holds everything shared; environment modules
  override. `test.py` swaps Postgres→SQLite, Redis→in-memory, and Celery→eager
  so the unit suite runs anywhere with zero external services.

## Data model foundation (`apps/common/models.py`)

| Mixin | Adds | Rationale |
|---|---|---|
| `UUIDModel` | UUIDv4 primary key | Non-enumerable, URL/API-safe, collision-free across shards/replicas. |
| `TimeStampedModel` | `created_at`, `updated_at` | Universal audit timestamps; `created_at` indexed for time-ordered queries. |
| `SoftDeleteModel` | `is_deleted`, `deleted_at` + managers | "Deleting" a message/user must preserve referential integrity and history. The default manager hides soft-deleted rows; `all_objects` exposes them for admin/restore. |
| `BaseModel` | all of the above | The default base for domain tables. |

A periodic Celery Beat job will hard-purge rows soft-deleted beyond a retention
window (added with the chat phase, where volume justifies it).

## Identity (`apps/accounts`)

* **Custom `User` from day one.** `AUTH_USER_MODEL = accounts.User` is set before
  the first migration because changing it later is a destructive, error-prone
  migration. The model is intentionally **narrow** (identity + account state):
  rich profile data lands in a separate `Profile` table so auth's hot path
  touches few columns.
* **Email is the login identifier** (`USERNAME_FIELD = "email"`); `username` is
  the public `@handle`, independently unique and regex-validated.
* **Argon2** is the primary password hasher (memory-hard, OWASP-recommended),
  with PBKDF2/bcrypt kept for verifying legacy hashes.

## Authentication (Phase 1)

The auth slice is structured as a **service layer** (`apps/accounts/services.py`):
views/serializers validate and shape I/O, while `AuthService` owns every rule, so
the logic is unit-testable without HTTP and reused identically across endpoints.

Key mechanisms:

* **One-time tokens** (`OneTimeToken`) for email verification and password reset
  store only a SHA-256 *hash* of the token — the raw value is emailed and never
  persisted, so a DB leak yields no usable tokens. Tokens are single-use,
  expiring, and issuing a new one invalidates prior ones of the same purpose.
* **Session-bound JWTs.** Each login creates a `UserSession`; its id rides in the
  `sid` claim of both access and refresh tokens. This decouples "is this login
  valid?" from token expiry and powers the active-devices UI.
* **Immediate revocation.** Logout / "sign out this device" / password change flip
  the session, enforced two ways: access tokens are rejected at once via a Redis
  flag checked in `SessionAwareJWTAuthentication`; refresh is rejected because the
  refresh serializer checks the backing session is still active. No per-user
  token-blacklist scans needed. A password *reset* signs out every device; a
  *change* keeps the current one.
* **Security log.** `SecurityEvent` is an append-only audit trail (login,
  login-failed, logout, password change/reset, session revoked…) surfaced as the
  user's login history and to admins for suspicious-activity review.
* **Async email** via Celery (verification, reset, login alert) so SMTP never
  blocks a request. **Per-endpoint throttling** (scoped rates on login, register,
  verify, reset) defends against brute force. Privacy-preserving responses on
  resend-verification and reset-request never reveal whether an email is
  registered.

## Realtime (ASGI + Channels)

* A single **ASGI** application (`config/asgi.py`) multiplexes HTTP (Django/DRF)
  and WebSocket (Channels) so both share the auth stack, ORM, and settings.
* **WebSocket auth** (`apps/realtime/middleware.py`): a JWT access token is passed
  as `?token=…` (browsers can't set WS headers); the same session-revocation check
  used for HTTP applies, so a revoked session can't open a socket.
* **`channels-redis`** backs the channel layer, enabling horizontal scaling:
  multiple ASGI workers coordinate fan-out through Redis pub/sub.

## Profiles, social graph & presence (Phase 2)

* **Side tables, not a fat user row.** `Profile`, `PrivacySettings`, and
  `NotificationSettings` are 1:1 with `User`, auto-provisioned by a `post_save`
  signal, keeping the auth hot-path table narrow.
* **Dual social model.** Asymmetric `Follow` (followers/following) *and* symmetric
  friendship (`FriendRequest` → `Friendship`, stored canonically as an ordered
  pair). Sending a request to someone who already requested you auto-accepts.
* **Block is a hard cascade** (`SocialService.block`): severs follows and
  friendship both ways and cancels pending requests. **Mute** is soft (suppresses
  notifications silently). Privacy gates (`everyone`/`friends`/`nobody`) govern who
  can follow, friend, and view a profile.
* **Realtime presence** (`apps/realtime`): a user is online while holding ≥1 live
  WebSocket. Connections are tracked in a Redis SET per user with a heartbeat TTL,
  so a crashed client expires instead of pinning online. The `PresenceConsumer`
  lets clients `subscribe` to specific users (fan-out via `presence.u.{id}` groups)
  and `set_status` (online/away/busy/invisible). `resolve_visible_status` combines
  connectivity + chosen mode + privacy; a REST endpoint exposes the same for
  initial render. Image uploads (avatar/cover) are validated and re-encoded to
  WebP via Pillow (`apps/common/images.py`), with a decompression-bomb guard.

## Realtime chat (Phase 3)

* **One service, two transports.** `ChatService` is the single code path for
  send/edit/delete/react/read. A message sent over REST *or* over the WebSocket
  persists and then broadcasts identically — so a REST `POST` is delivered to
  connected clients in realtime (verified live: REST send → Redis channel layer →
  recipient's socket).
* **Personal-group fan-out.** Each socket joins only `chat.user.{id}`; every
  conversation event is sent to each participant's personal group. One
  subscription per client, and newly created conversations reach participants
  without re-subscribing. (N sends per event — fine at 1:1/small-group; revisited
  for large groups.)
* **Conversations & participants.** A direct conversation is unique per pair via a
  canonical `direct_key`. Per-user state (`ConversationParticipant`) carries read/
  delivery cursors (→ unread counts & receipts), pin/archive/mute, and a
  `cleared_at` "clear history for me" marker.
* **Message semantics.** Reply (self-FK), edit (flagged), **delete-for-everyone**
  (tombstone row preserved) vs **delete-for-me** (`hidden_for` M2M), reactions
  (toggle, aggregated), and `client_id` echo for optimistic-UI dedupe. History is
  **cursor-paginated** (stable under concurrent inserts) for infinite scroll.
* **Channel-layer payloads** are normalised through DRF's JSON encoder so UUIDs/
  datetimes survive both the in-memory (tests) and Redis/msgpack (prod) layers.

## Media & files (Phase 4)

* **Object storage by default.** User media lives in MinIO/S3 via django-storages,
  toggled by `USE_S3` (on in the dev compose + production; the test suite uses
  in-memory storage). MinIO needs path-style addressing.
* **Two upload paths, one model.** Direct multipart upload for small files; a
  **chunked/resumable** session (`init → chunk → complete`, with a status endpoint
  for resume) for large ones, assembled server-side. Both yield a `MediaFile`.
* **Async processing** (Celery, off the request path): `status` advances
  PENDING → PROCESSING → READY/FAILED. Images get dimensions + a WebP thumbnail
  (Pillow); video gets dimensions, duration, and a poster frame (FFmpeg); audio
  gets duration; voice notes additionally get a downsampled waveform. FFmpeg is in
  the container image and the code degrades gracefully where it's absent. Verified
  live: an uploaded image and its generated thumbnail both land in the MinIO bucket.
* **Access control.** A `MediaFile` is readable by its owner, or by any participant
  of a conversation where it's attached (`MessageAttachment`). URLs are
  time-limited presigned links.

## Groups & channels (Phase 5)

* **Channels reuse the chat layer.** A `Channel` is backed 1:1 by a
  `Conversation`; group membership is mirrored into each public channel's
  `ConversationParticipant` rows by `GroupService`. So messages, reactions,
  receipts, attachments, and the WebSocket fan-out all work for channels with no
  special-casing (verified live: a channel post reached a member's socket).
* **Role hierarchy** owner > admin > moderator > member > guest, compared by rank
  for every privileged action (create/delete channels, kick, change role, manage
  invites). The owner is protected (can't be kicked/demoted; must transfer or
  delete). Group/channel creation, joins, and removals keep channel participation
  in sync so access and realtime delivery stay correct.
* **Invites** carry an opaque code, optional expiry, and max-uses; joining is
  atomic and increments usage. Public groups also support direct join + discovery
  search. DM list endpoints are filtered to `direct` conversations so channels
  don't leak into the inbox.

## Voice & video calls (Phase 6)

* **Signaling, not media.** The server is the signaling + state plane: it tracks
  who's in a call and relays WebRTC SDP/ICE between peers over `ws/calls/`. Media
  flows peer-to-peer (mesh) and never reaches the server.
* **Per-socket + per-room fan-out.** Each socket joins `call.user.{id}` (incoming
  calls + targeted signaling) and, while in a call, `call.room.{id}` (peer join/
  leave/state). `signal` is relayed to a specific peer's personal group; `state`
  (mute/video/raise-hand) broadcasts to the room.
* **Lifecycle in `CallService`:** initiate (RINGING) → join (ONGOING, sets
  `started_at`) / reject → leave/end. A call auto-terminates when the last
  participant leaves (ENDED if it connected, else MISSED); a 1:1 reject ends it.
  Verified live: initiate → accept → end with duration recorded.
* **ICE** servers come from `GET /calls/ice-servers/` (public STUN by default;
  a TURN server is added via `WEBRTC_TURN_URL`). Mesh suits 1:1 and small groups;
  large group calls would introduce an SFU — out of scope here, noted for prod.

## Administration, moderation & hardening (Phase 7)

* **Admin panel API** (`/api/v1/admin/`, `IsAdminUser`): dashboard analytics
  (counts + 14-day signup/message charts via DB aggregation), report moderation,
  feature-flag CRUD, announcements, user management, and an admin audit log
  (every privileged mutation is recorded with actor + IP).
* **Abuse reporting** is open to any authenticated user; admins triage via the
  moderation queue. **Feature flags** and **announcements** have user-facing read
  endpoints so the client can react at runtime.
* **Maintenance mode** is a singleton `SystemConfig` (cached) enforced by
  middleware: normal traffic gets 503 while health checks, the admin API, login,
  and docs stay reachable — so an admin can always switch it back off (verified
  in tests).
* **i18n** — English/Arabic. `UserLanguageMiddleware` honours an `X-Language`
  header (over Django's Accept-Language negotiation) so the client can force a
  language and drive RTL, without a cookie round-trip. `GET /i18n/languages/`
  lists the supported set. Translation catalogs are added via Django's
  make/compile-messages; the negotiation layer is in place.

## Redis: three roles, three logical DBs

| DB | Role |
|---|---|
| `…/0` | Django cache (`RedisCache`) |
| `…/1` | Channels layer |
| `…/2`, `…/3` | Celery broker / result backend |

Isolating them keeps a flood in one subsystem (e.g. cache churn) from evicting
another's keys, and makes per-role metrics and flushing possible.

## Async work (Celery + Beat)

Celery handles anything that must not block a request or a WebSocket frame:
email delivery, media transcoding (FFmpeg), thumbnailing (Pillow), push
notifications, retention purges. **Celery Beat** with the database scheduler
(`django_celery_beat`) runs periodic jobs and lets schedules be edited at
runtime via the admin.

## API surface

* **Versioned** under `/api/v1/` (URL-path versioning) so breaking changes can
  ship as `/api/v2/` without disrupting clients.
* **drf-spectacular** generates OpenAPI 3; Swagger UI at `/api/docs/`, ReDoc at
  `/api/redoc/`.
* **Uniform error envelope** (`apps/common/exceptions.py`) — every error, from
  validation to 500, returns `{ "error": { type, message, detail, status_code } }`
  so the frontend has one contract.
* **Throttling** via DRF scoped rates; **pagination** is page-number by default
  and **cursor-based** for high-volume message feeds.

## Serving & ops

* **Dev:** `runserver` under Daphne (ASGI, hot reload, WebSocket-capable).
* **Prod:** Gunicorn with Uvicorn workers behind Nginx. Nginx terminates TLS,
  serves collected static, and upgrades `/ws/` connections.
* **Health probes:** `/health/` (liveness, never touches dependencies) and
  `/health/ready/` (readiness — checks DB, cache, channel layer; returns 503 when
  degraded so load balancers drain the instance).
* **Startup ordering:** `wait_for_services` blocks until Postgres and Redis accept
  connections before migrations/boot, avoiding crash-loops during `compose up`.

## Security baseline (deepened in Phase 7)

Argon2 hashing, JWT with rotating + blacklisted refresh tokens, HSTS/secure
cookies/SSL redirect in production, CORS allow-list, content-type nosniff,
`X-Frame-Options: DENY`, per-scope rate limiting, and non-root container user.
