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
* The WebSocket `URLRouter` is empty in Phase 0; chat/presence/call consumers and
  a JWT WebSocket auth middleware are added in their phases.
* **`channels-redis`** backs the channel layer, enabling horizontal scaling:
  multiple ASGI workers coordinate fan-out through Redis pub/sub.

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
