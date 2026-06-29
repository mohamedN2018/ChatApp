# ChatApp — Real-Time Messaging Platform

A production-grade, self-hostable messaging platform (Discord/Telegram/Slack-class)
built on Django 5, Django Channels, PostgreSQL, Redis, Celery, and a Nuxt 3 frontend.
Everything runs on free and open-source software.

> **Status — All 8 phases complete.** The full backend + WebSocket API (Phases
> 0–7) and a Nuxt 3 frontend (Phase 8) are built, verified, and Dockerized. Run
> `docker compose up --build` and open http://localhost:3000. See the
> [Roadmap](#roadmap).

---

## Architecture at a glance

```
                       ┌──────────────┐
                       │   Nuxt 3 UI  │  (Phase 8)
                       └──────┬───────┘
                              │ HTTPS / WSS
                       ┌──────▼───────┐
                       │    Nginx     │  reverse proxy, TLS, static, WS upgrade
                       └──────┬───────┘
            ┌─────────────────┼──────────────────┐
            │                 │                  │
     ┌──────▼──────┐   ┌──────▼──────┐    ┌──────▼──────┐
     │  Gunicorn   │   │   Celery    │    │ Celery Beat │
     │  + Uvicorn  │   │   workers   │    │  scheduler  │
     │ (ASGI app)  │   └──────┬──────┘    └──────┬──────┘
     │ DRF + WS    │          │                  │
     └──┬───┬───┬──┘          │                  │
        │   │   │             │                  │
 ┌──────▼┐ ┌▼──────┐ ┌────────▼─────┐    ┌────────▼─────┐
 │Postgres│ │ Redis │ │    MinIO     │    │   Postgres   │
 │  (DB)  │ │cache/ │ │ (S3 media)   │    │ (beat sched) │
 └────────┘ │broker/│ └──────────────┘    └──────────────┘
            │channel│
            └───────┘
```

* **ASGI everywhere** — a single application serves both REST (DRF) and
  WebSockets (Channels) so realtime and request/response share auth and models.
* **Redis** is used for three isolated concerns on separate logical DBs: cache,
  the Channels layer, and the Celery broker/result backend.
* **MinIO** provides S3-compatible object storage for user media.
* **UUID primary keys + soft delete** on every domain table (see
  `backend/apps/common/models.py`) for safe horizontal scaling and audit trails.

Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2, Django REST Framework, Django Channels (ASGI) |
| Realtime | WebSockets via Channels, `channels-redis` |
| Async jobs | Celery + Celery Beat (Redis broker) |
| Database | PostgreSQL 16 |
| Cache / broker / channel layer | Redis 7 |
| Object storage | MinIO (S3-compatible), django-storages |
| Media processing | FFmpeg, Pillow |
| Auth | SimpleJWT (access + rotating refresh), Argon2 hashing |
| API docs | drf-spectacular (OpenAPI 3 / Swagger / ReDoc) |
| Serving | Gunicorn + Uvicorn workers, Nginx |
| Frontend *(Phase 8)* | Nuxt 3, Vue 3, TypeScript, Pinia, TailwindCSS |
| Infra | Docker + Docker Compose |

---

## Quick start (Docker — recommended)

Prerequisites: Docker + Docker Compose.

```bash
cp .env.example .env          # adjust secrets as needed
docker compose up --build     # starts postgres, redis, minio, web, worker, beat
```

Then:

| URL | What |
|---|---|
| http://localhost:3000/ | **Frontend** (Nuxt) — sign up, sign in, chat in realtime |
| http://localhost:8000/health/ | Liveness probe |
| http://localhost:8000/health/ready/ | Readiness (DB + Redis + channel layer) |
| http://localhost:8000/api/docs/ | Swagger UI |
| http://localhost:8000/api/redoc/ | ReDoc |
| http://localhost:8000/admin/ | Django admin |
| http://localhost:9001/ | MinIO console (`minioadmin` / `minioadmin`) |

Create an admin user:

```bash
docker compose exec web python manage.py createsuperuser
```

## Local development (without Docker)

Requires Python 3.11+ and a reachable Postgres + Redis (or use the Docker
services for just those). The test suite needs neither — it runs on SQLite.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on *nix)
pip install -r requirements/development.txt

pytest                          # run the test suite (SQLite, in-memory)
ruff check .                    # lint
python manage.py runserver      # ASGI dev server (HTTP + WebSocket)
```

`DJANGO_SETTINGS_MODULE` defaults to `config.settings.development`. Tests use
`config.settings.test` (configured in `pyproject.toml`).

---

## Project structure

```
ChatApp/
├── backend/
│   ├── config/                 # Django project: settings split, urls, asgi, wsgi, celery
│   │   └── settings/           #   base / development / production / test
│   ├── apps/
│   │   ├── common/             # base models, managers, pagination, exceptions, health, wait_for_services
│   │   └── accounts/           # custom User model (UUID PK, email login)
│   ├── requirements/           # base / development / production
│   ├── Dockerfile              # multi-stage (builder + slim runtime, non-root)
│   └── pyproject.toml          # pytest / ruff / mypy config
├── docker/
│   ├── entrypoint.sh           # waits for services, then execs the role command
│   └── nginx/                  # reverse-proxy config (prod)
├── docker-compose.yml          # dev stack
├── docker-compose.prod.yml     # prod stack (gunicorn + nginx + collectstatic)
├── .env.example
├── Makefile
└── docs/
```

---

## Roadmap

The build proceeds one complete, verified slice at a time.

- [x] **Phase 0 — Foundation:** monorepo, Docker Compose (Postgres/Redis/MinIO),
  Django+ASGI skeleton, settings split, base models (UUID/soft-delete/audit),
  custom User model, health checks, OpenAPI/Swagger, test + lint setup.
- [x] **Phase 1 — Authentication:** email register/verify (single-use hashed
  tokens), JWT + rotating refresh, session-bound login with **immediate
  revocation**, logout, password reset/change, device/session management,
  security log, async email (Celery), per-endpoint rate limiting.
- [x] **Phase 2 — Profiles & Social & Presence:** profile (avatar/cover via Pillow,
  bio/links/custom status), privacy + notification settings, follow/unfollow,
  friend requests (with mutual auto-accept), block (cascading), mute, and
  **realtime presence** over a JWT-authenticated WebSocket (Redis-backed
  online/away/busy/invisible + last-seen, with a REST fallback).
- [x] **Phase 3 — Realtime chat (1:1):** conversations (direct), messages with
  reply/edit/delete (for-me & for-everyone tombstone), reactions, read/delivery
  receipts, unread counts, pin/archive/mute, cursor-paginated history (infinite
  scroll), and a JWT WebSocket `ChatConsumer` (send/typing/read/react/edit/delete)
  — REST and WS share one service so a REST send is delivered in realtime.
- [x] **Phase 4 — Media & files:** MinIO/S3 object storage, direct + chunked/
  resumable uploads, async processing (Pillow image thumbnails + dimensions;
  FFmpeg video poster/duration; audio duration; voice-note waveforms),
  access-controlled retrieval, and chat message attachments.
- [x] **Phase 5 — Groups & channels:** communities with role hierarchy (owner/
  admin/moderator/member/guest), public/private groups, invite links (expiry +
  max-uses), text/voice/video/announcement channels backed by conversations
  (so channels reuse the chat realtime pipeline), avatar/banner, member
  management, ownership transfer, and public discovery.
- [x] **Phase 6 — Voice & video calls:** WebRTC signaling over a JWT WebSocket
  (`ws/calls/`) relaying SDP/ICE peer-to-peer (mesh), full call lifecycle
  (ring → accept/reject → ongoing → end, with missed/cancelled), call history,
  per-peer mute/video/raise-hand state, and ICE-server config (STUN; TURN via
  env). *(Large group calls would add an SFU — noted for production.)*
- [x] **Phase 7 — Admin, i18n, hardening:** admin dashboard analytics (users/
  messages/calls/storage + daily charts), abuse reporting + moderation, runtime
  feature flags, announcements, user management, admin audit log, singleton system
  config with a **maintenance-mode** middleware (kill-switch), and i18n
  (English/Arabic) language negotiation via `X-Language` / Accept-Language.
- [x] **Phase 8 — Frontend:** Nuxt 3 + TypeScript + TailwindCSS + Pinia app —
  auth (JWT + refresh), realtime chat (conversation list, thread, live delivery,
  typing) and presence over WebSockets, dark/light theme, and English/Arabic with
  **RTL** — Dockerized as the `frontend` service. The remaining screens (calls,
  groups, admin) follow the same composable/store patterns.

---

## License

To be determined.
