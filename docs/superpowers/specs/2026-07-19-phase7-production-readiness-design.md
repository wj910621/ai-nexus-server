# Phase 7: Production Readiness Design Spec

**Date:** 2026-07-19
**Phase:** 7 (Production Readiness & Performance Optimization)
**Predecessor:** Phase 6 (Commercialization — 338 tests passing)
**Deployment target:** Cloud-hosted commercial SaaS (primary) + Electron desktop app (commercial product, not just developer tool).
**Goal:** Make ComicStudio AI commercially deployable as BOTH cloud SaaS AND downloadable desktop app, with both reaching/beating ComfyUI/即梦 on user-perceived latency via:
  - **Cloud**: caching + WebSocket + CDN + provider failover + HTTP/2 + SSE
  - **Desktop**: local AI inference (ONNX Runtime for CPU + diffusers/xFormers for GPU) so users without internet OR with GPUs get ComfyUI-class speed
Full observability, database/API productionization, CI/CD automation, commercial ops essentials (CDN, alerting, backup, SLA monitoring).

---

## 1. Goals & Non-Goals

### 1.1 Goals

1. **Performance (user-perceived latency)**: Match or exceed ComfyUI/即梦 on user-perceived latency on BOTH cloud and desktop:
   - **Cloud cache hit p99**: <50ms (beats ComfyUI local GPU)
   - **Cloud cache miss p99**: ≤5s (matches 即梦)
   - **Desktop local GPU p99** (NVIDIA GPU users): ≤3s (matches ComfyUI local GPU)
   - **Desktop local CPU p99** (no GPU users): ≤15s (slower than ComfyUI local GPU but works offline)
   - **Desktop remote API fallback p99**: ≤5s (when local inference unavailable)
   - **WebSocket progress push latency**: <100ms (matches ComfyUI/即梦 real-time feedback)
   - **WebP vs PNG size reduction**: ≥30% (mobile/bandwidth optimization)
   - **Time-to-first-feedback** (click → first progress frame): ≤2s
2. **Observability**: Achieve production-grade monitoring (metrics + structured logs + traces + error tracking)
3. **Database maturity**: Replace `create_all` with Alembic migrations, fix N+1 queries, add missing indexes
4. **API productionization**: Versioning, compression, short-lived JWT + refresh, ETag support, SSE streaming
5. **CI/CD**: One-command release pipeline via GitHub Actions + multi-stage Docker builds + desktop installers with bundled local AI runtime
6. **Compatibility**: Zero regression on 338 existing tests; both cloud SaaS and desktop app remain commercial-grade
7. **Commercial ops**: CDN for static/AI asset distribution, alerting on SLO breaches, automated DB + file backup, SLA monitoring dashboard
8. **Target test count**: ≥504 passing (338 baseline + 166 new across 16 tasks)

### 1.2 Non-Goals (Explicitly Out of Scope)

- Kubernetes manifests (Docker Compose with Nginx reverse proxy is sufficient for v1; K8s deferred to Phase 8 scale-out)
- Multi-tenant database isolation
- GraphQL API (REST remains)
- Horizontal autoscaling logic (delegated to orchestrator / docker-compose `scale`)
- Migration of frontend to Next.js (current React+Vite stays)
- Multi-region deployment (single-region with CDN edge caching is sufficient for v1)
- Vector-similarity prompt cache (semantic "similar prompt" reuse) — Phase 7 uses exact hash only; Phase 8 may add embedding-based similarity
- Model fine-tuning / LoRA training UI (users can load existing LoRA files but cannot train in-app; deferred to Phase 8)
- AMD ROCm / Intel OpenVINO support (Phase 7 supports NVIDIA CUDA + CPU only; AMD/Intel deferred to Phase 8)

---

## 2. Architecture Overview

### 2.1 Layered View

```
┌─────────────────────────────────────────────────────────────┐
│  Users (Browser/Electron) → CDN Edge (Cloudflare/七牛)         │
│  - Static assets (JS/CSS/images) cached at edge              │
│  - AI-generated images/videos served via CDN                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ (origin pull)
┌─────────────────────────────────────────────────────────────┐
│ Nginx Reverse Proxy (TLS termination, rate limit, gzip)      │
│ - /static/* → CDN-cached                                      │
│ - /uploads/* → CDN-cached (AI assets)                         │
│ - /api/* → FastAPI backend                                    │
│ - /ws → WebSocket upgrade to FastAPI                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Backend (api/v1 + api legacy + /ws)                  │
│ ┌──────────┬──────────┬──────────┬──────────┬──────────┐    │
│ │ Metrics  │ RequestID│ Gzip     │ CORS     │ Sentry   │    │
│ │ Middlew. │ Middlew. │ Middlew. │ Middlew. │ SDK      │    │
│ └──────────┴──────────┴──────────┴──────────┴──────────┘    │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ API Routers (auth/users/projects/ai/billing/tasks/...) │    │
│ │ + cache decorator + concurrency semaphore             │    │
│ │ + SSE streaming for /ai/chat                          │    │
│ └──────────────────────────────────────────────────────┘    │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ WebSocketManager (/ws) — task/image/video channels    │    │
│ └──────────────────────────────────────────────────────┘    │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ Services (BillingService/AdminService/TaskService...) │    │
│ │ + ResultCacheService + RequestDeduplicator            │    │
│ └──────────────────────────────────────────────────────┘    │
│ ┌─────────────┬──────────────┬─────────────────────────┐    │
│ │ CacheSvc    │ TaskRunner   │ EngineManager           │    │
│ │ (Redis)     │ (asyncio+DB) │ (5 engines + semaphore) │    │
│ │             │              │ + shared httpx client   │    │
│ │             │              │ + HTTP/2 + limits       │    │
│ └─────────────┴──────────────┴─────────────────────────┘    │
│ ┌──────────────────────────────────────────────────────┐    │
│ │ ImageOptimizer (WebP + thumbnails)                    │    │
│ └──────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
        │                   │                    │
        ▼                   ▼                    ▼
   PostgreSQL          Redis (REQUIRED       External AI APIs
   + Alembic            in production)       (Pollinations/DeepSeek/...)
   + pg_dump backup     + result cache       (HTTP/2 + keep-alive)
   + read replica       + dedup futures      + provider failover
   (Phase 8)            + rate limiter
                        + AOF persistence
```

### 2.2 Key Design Principles

1. **Dual first-class deployment targets**: Cloud SaaS and Electron desktop app are BOTH commercial products. Neither is a "fallback" for the other. Each is optimized for its deployment context (cloud = scale + caching + CDN; desktop = local inference + offline).
2. **Local-first desktop inference**: Desktop app must achieve ComfyUI-class speed via local AI inference (ONNX Runtime for CPU + diffusers/xFormers for NVIDIA GPU). Remote API is a FALLBACK when local inference is unavailable, not the default.
3. **Cloud-first scale**: Cloud SaaS uses Redis (required), PostgreSQL, CDN, and provider failover to achieve commercial SLO at scale.
4. **Zero-cost default for ops**: All infrastructure uses free tiers / open-source (Cloudflare R2 free tier, GitHub Actions free minutes, HuggingFace free model downloads, ONNX Runtime / diffusers open-source). Only pay for VPS + domain + DB hosting.
5. **Provider failover**: External AI APIs (Pollinations, DeepSeek) are wrapped with retry + circuit breaker + secondary provider; one provider going down does not take the service offline. Desktop falls back to local inference when remote API is unreachable.
6. **Additive only**: No breaking changes to existing API paths, schemas, or DB models; new features are layered on top
7. **TDD**: Each Task follows RED-GREEN-REFACTOR; every new module has ≥80% test coverage
8. **SLO-driven**: All performance optimizations target measurable SLOs (p99 latency, uptime, cache hit rate); monitored via Prometheus + alerting on breach (cloud) or local logs (desktop)

---

## 3. Task Breakdown

### Task 1: Cache Layer (CacheService + Decorator)

**Responsibility**: Provide a unified caching abstraction with `lru_cache` memory backend (desktop/default) and Redis backend (cloud, when `redis_url` is configured and reachable).

**Files:**
- Create: `app/core/cache.py` — `CacheService` class + `cached()` decorator
- Modify: `app/core/config.py` — add `cache_enabled`, `cache_ttl_default`, `cache_redis_url`
- Modify: `app/main.py` — initialize cache on startup
- Create: `tests/test_cache.py` — 12 tests

**API:**
```python
class CacheService:
    async def get(self, key: str) -> Any | None
    async def set(self, key: str, value: Any, ttl: int = 300) -> None
    async def delete(self, key: str) -> None
    async def invalidate_pattern(self, pattern: str) -> int
    async def clear_all(self) -> int

def cached(ttl: int = 300, key_builder: Callable | None = None):
    """Decorator for caching async function results."""
```

**Behavior:**
- Desktop mode OR no Redis URL → use `cachetools.TTLCache` (in-process memory)
- Cloud mode + Redis URL → use `redis.asyncio` client
- All cache keys prefixed with `cs:` to avoid collisions
- `cached()` decorator serializes args via `hashlib.md5(repr(args).encode())`
- Cache hits logged at DEBUG level with key + TTL

**Usage examples (where to apply):**
- `BillingService.get_balance` — cache 30s (balance changes invalidate)
- `SubscriptionService.get_plan_info` — cache 3600s (static plans)
- `AdminService.get_stats` — cache 60s
- `engine_manager.get_all_info` — cache 10s

### Task 2: Async Task Engine (TaskService + DB State Machine)

**Responsibility**: Run long-running operations (video compose, render, batch image generation) in background asyncio tasks with DB-tracked state machine for progress polling and cancellation.

**Files:**
- Create: `app/models/task.py` — `BackgroundTask` model (id, user_id, type, status, progress, result, error, created_at, started_at, completed_at)
- Modify: `app/models/__init__.py` — export `BackgroundTask`
- Create: `app/schemas/task.py` — `TaskResponse`, `TaskListResponse`, `TaskProgressResponse`
- Create: `app/services/task_service.py` — `TaskService` with `submit()`, `get_status()`, `cancel()`, `list_user_tasks()`
- Create: `app/api/tasks.py` — 4 endpoints: `POST /tasks`, `GET /tasks/{id}`, `GET /tasks`, `DELETE /tasks/{id}`
- Modify: `app/api/router.py` — register tasks router
- Modify: `app/api/ai.py` — `video_compose` endpoint now submits background task and returns task_id with 202 Accepted; for synchronous callers, a `?sync=true` query param preserves old behavior (block until done, returns 200 with result)
- Create: `tests/test_task_service.py` — 12 tests

**State Machine:**
```
pending → running → succeeded
                 → failed
                 → cancelled (by user)
```

**Concurrency control:**
- Max concurrent tasks: 4 (configurable via `CS_MAX_CONCURRENT_TASKS`)
- Use `asyncio.Semaphore` to limit
- Tasks persisted to DB **before** execution starts (crash recovery)
- On startup: resume `pending`/`running` tasks (mark as `failed` with reason "interrupted by restart")

**Task type registry:**
```python
TASK_HANDLERS = {
    "video_compose": handle_video_compose,
    "render_video": handle_render_video,
    "batch_text2img": handle_batch_text2img,
}
```

### Task 3: AI Engine Concurrency Control

**Responsibility**: Limit concurrent calls to external AI APIs (Pollinations/DeepSeek/edge-tts) to avoid rate-limit bans, with per-engine semaphore.

**Files:**
- Create: `app/engines/concurrency.py` — `EngineConcurrencyManager` with per-engine `asyncio.Semaphore`
- Modify: `app/engines/manager.py` — integrate semaphore into engine calls
- Modify: `app/api/ai.py` — wrap generation endpoints with `acquire_slot()` context manager
- Create: `tests/test_engine_concurrency.py` — 8 tests

**Configuration:**
- `CS_ENGINE_MAX_CONCURRENT_IMAGE`: 5 (Pollinations rate limit ~100/min, 5 concurrent is safe)
- `CS_ENGINE_MAX_CONCURRENT_LLM`: 10 (DeepSeek rate limit ~60/min)
- `CS_ENGINE_MAX_CONCURRENT_TTS`: 8 (edge-tts has no hard limit, but bandwidth)
- `CS_ENGINE_MAX_CONCURRENT_VIDEO`: 2 (FFmpeg CPU-bound)
- `CS_ENGINE_MAX_CONCURRENT_CHARACTER`: 3

**Behavior:**
- Each engine type has its own semaphore
- When slot unavailable, request waits (up to 30s, then HTTP 503 "AI 引擎繁忙")
- Metrics exposed: `engine_concurrent_requests{type=...}`, `engine_wait_seconds{type=...}`

### Task 4: Observability — Metrics, Logs, Traces, Sentry

**Responsibility**: Production-grade observability stack.

**Files:**
- Create: `app/core/middleware/request_id.py` — `RequestIDMiddleware` (X-Request-ID header)
- Create: `app/core/middleware/access_log.py` — structured JSON access log middleware
- Modify: `app/main.py` — register middlewares, init Sentry, init Prometheus
- Create: `app/core/logging_config.py` — loguru JSON sink + log levels by env
- Modify: `app/core/config.py` — add `sentry_dsn`, `log_format` (text/json), `metrics_enabled`
- Create: `tests/test_observability.py` — 10 tests

**Components:**

1. **Request ID Middleware**: Inject `X-Request-ID` header (UUID4), propagate to loguru context, attach to response
2. **Access Log Middleware**: JSON-structured log per request: `{request_id, method, path, status, duration_ms, user_id, ip}`
3. **Prometheus Metrics** (via `prometheus-fastapi-instrumentator`):
   - `http_requests_total{method, path, status}` (auto)
   - `http_request_duration_seconds{method, path}` (auto histogram)
   - `engine_concurrent_requests{type}` (custom gauge from Task 3)
   - `credits_consumed_total{operation}` (custom counter from Task 8 of Phase 6)
   - `cache_hits_total{key_prefix}` / `cache_misses_total{key_prefix}` (custom from Task 1)
   - Exposed at `/metrics` (admin-only)
4. **Sentry SDK**: `sentry_sdk.init(dsn=settings.sentry_dsn)` in lifespan; no-op when DSN empty. Captures all unhandled exceptions + 5xx responses.
5. **Loguru JSON sink**: When `log_format=json`, serialize all logs as `{"time":..., "level":..., "message":..., "request_id":..., "extra":...}`. Compatible with ELK/Loki.

### Task 5: Health Check Layering + Graceful Shutdown

**Responsibility**: Kubernetes-friendly health probes + graceful shutdown on SIGTERM.

**Files:**
- Modify: `app/main.py` — split `/health` into `/health` (liveness) and `/ready` (readiness), add shutdown handler
- Create: `app/core/health.py` — `HealthChecker` with checks for: database, redis (optional), engines, disk space
- Create: `tests/test_health.py` — 8 tests (extend existing)

**Endpoints:**
- `GET /health` — liveness: always 200 if process is alive (no dependency checks)
- `GET /ready` — readiness: 200 if all critical deps OK (DB reachable, engines initialized), 503 otherwise
- `GET /metrics` — Prometheus metrics (admin-only, behind `get_current_admin`)

**Graceful shutdown:**
- On SIGTERM: stop accepting new requests, wait up to 30s for in-flight tasks, then close DB engine
- Active background tasks (from Task 2) marked as `interrupted` in DB for recovery on next boot

### Task 6: Alembic Migrations + Index Optimization + N+1 Fix

**Responsibility**: Replace `create_all` with proper migrations, add missing indexes, fix N+1 queries in services.

**Files:**
- Create: `backend/alembic/versions/001_initial_schema.py` — initial migration covering all 11 existing models
- Create: `backend/alembic/versions/002_add_indexes.py` — add missing indexes (see below)
- Modify: `app/services/base_service.py` — `list()` method now supports `eager_load` param
- Modify: `app/services/admin_service.py` — `list_users` uses eager loading to avoid N+1 on preferences
- Modify: `app/core/database.py` — add `run_migrations_on_startup()` helper
- Modify: `app/main.py` — call `run_migrations_on_startup()` in dev/desktop mode (production uses CLI)
- Create: `tests/test_migrations.py` — 6 tests

**Missing indexes (to add in 002):**
- `audit_logs.actor_id` (already indexed)
- `audit_logs.action` (already indexed)
- `audit_logs.created_at` (NEW — for time-range queries)
- `credit_transactions.user_id` (NEW — for list_transactions)
- `credit_transactions.created_at` (NEW — for time-range queries)
- `subscriptions.user_id` (NEW)
- `subscriptions.status` (NEW)
- `background_tasks.user_id` (NEW — from Task 2)
- `background_tasks.status` (NEW)
- `projects.user_id` (verify existing; add if missing)
- `users.email` UNIQUE (verify existing)
- `users.role` (NEW — for admin queries)

**N+1 fixes:**
- `AdminService.list_users` — currently selects User, then lazy-loads `preferences` JSON; fix to eager load via `selectinload(User.preferences)` (if relationship exists) or single-query with `User.preferences` column
- `BillingService.list_transactions` — already single query, no N+1
- `AuditService.list_all` — single query, no N+1

### Task 7: API Versioning + Gzip + JWT Refresh + ETag

**Responsibility**: Production harden the API surface.

**Files:**
- Modify: `app/api/router.py` — create `api_v1_router` (alias of existing `api_router`), mount both at `/api` and `/api/v1`
- Modify: `app/main.py` — add `GZipMiddleware(min_size=1024)`
- Modify: `app/core/security.py` — `create_access_token` expire 30min (was 1440min), `create_refresh_token` 7d (existing), add `rotate_refresh_token()`
- Modify: `app/api/auth.py` — `/refresh` endpoint now issues new access + new refresh (rotation), old refresh invalidated
- Modify: `app/core/deps.py` — `get_current_user` checks token type (access vs refresh)
- Create: `app/core/middleware/etag.py` — `ETagMiddleware` for GET responses (compute MD5 of body, handle `If-None-Match`)
- Modify: `app/core/config.py` — `jwt_access_token_expire_minutes: int = 30` (was 1440)
- Create: `tests/test_api_production.py` — 10 tests

**Behavior:**
- Both `/api/users/me` and `/api/v1/users/me` resolve to same handler (backward compat)
- Gzip compresses responses >1KB
- JWT access tokens now 30min; clients must use refresh token to get new access
- Refresh token rotation: each `/auth/refresh` issues new refresh, old one blacklisted in `revoked_tokens` table (NEW)
- ETag on GET responses: client sends `If-None-Match`, server returns 304 if unchanged

**New model:**
- `app/models/auth.py` — `RevokedToken(jti, user_id, expires_at)` for refresh token blacklist

### Task 8: CI/CD + Docker Optimization + Production Config

**Responsibility**: Automated build/test/release pipeline.

**Files:**
- Create: `.github/workflows/ci.yml` — on push/PR: lint + test backend + test desktop + build
- Create: `.github/workflows/release.yml` — on tag v*: build Docker images + Electron installers + publish
- Modify: `docker/Dockerfile.backend` — multi-stage build (builder + runtime), final image <150MB
- Modify: `docker/Dockerfile.frontend` — multi-stage with nginx, final image <50MB
- Modify: `docker/docker-compose.yml` — add Redis service, healthchecks, volumes for uploads
- Create: `.env.production.example` — production env template with all vars documented
- Create: `docs/deployment/production-deploy.md` — step-by-step deploy guide
- Create: `scripts/release.ps1` + `scripts/release.sh` — local release helper
- Create: `tests/test_docker_build.py` — 4 tests (validate Dockerfile syntax)

**CI Pipeline stages:**
1. **Lint**: ruff (Python) + eslint (TS)
2. **Test backend**: pytest with coverage threshold (≥70%)
3. **Test desktop**: vitest
4. **Build backend Docker**: multi-stage, push to GHCR on main
5. **Build desktop installers**: electron-builder for win/mac/linux (on tag)
6. **Integration test**: docker-compose up, hit /health, smoke test

**Docker multi-stage:**
```dockerfile
# Stage 1: builder
FROM python:3.14-slim AS builder
# install deps to /install
# Stage 2: runtime
FROM python:3.14-slim AS runtime
COPY --from=builder /install /usr/local/lib/python3.14/site-packages
COPY app /app
USER nobody
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Task 9: AI Result Cache + Request Deduplication

**Responsibility**: Cache AI generation results (image/tts/video) by content hash + deduplicate in-flight identical requests. This is the single highest-impact optimization — turns repeat/similar requests from 3-30s into <50ms.

**Files:**
- Create: `app/services/result_cache_service.py` — `ResultCacheService(BaseService[ResultCacheEntry])` extending Task 1's CacheService
- Create: `app/models/result_cache.py` — `ResultCacheEntry` model (id, cache_key, engine_type, prompt_hash, params_hash, storage_path, content_type, size_bytes, hits, created_at, last_accessed_at, expires_at)
- Create: `app/core/request_dedup.py` — `RequestDeduplicator` with in-flight `asyncio.Future` map
- Modify: `app/engines/image/pollinations.py` — check cache before API call, store on success
- Modify: `app/engines/tts/edge_tts.py` — check cache before API call
- Modify: `app/engines/video/ffmpeg.py` — check cache before compose (cache only deterministic inputs)
- Modify: `app/api/ai.py` — add `X-Cache: HIT|MISS|DEDUP` response header
- Create: `tests/test_result_cache.py` — 12 tests

**Cache key computation:**
```python
def compute_cache_key(engine_type: str, params: dict) -> str:
    """SHA256 of normalized params — deterministic ordering, ignores timestamps."""
    normalized = json.dumps(
        {"engine": engine_type, **params},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

**Behavior:**
- Cache key includes: `engine_type + prompt + negative_prompt + seed + width + height + model + num_inference_steps` (image); `engine_type + text + voice + rate` (tts); `engine_type + frames_hash + fps + codec` (video)
- TTL: image=24h, tts=7d, video=30d (configurable per engine)
- Storage: file on disk + metadata row in `result_cache_entries` table (indexed by `cache_key` UNIQUE, `engine_type`, `expires_at`)
- In-flight dedup: same `cache_key` concurrent requests share a single `asyncio.Future`; first caller does the work, others await the same future
- LRU eviction: when table size > `result_cache_max_entries` (default 10000), delete oldest `last_accessed_at` rows + their files
- Cache hits increment `hits` column and update `last_accessed_at`
- Response header `X-Cache: HIT` (cache hit), `MISS` (cache miss, fresh), `DEDUP` (in-flight dedup hit)
- Desktop mode: same behavior, in-process only (no Redis needed)
- Prometheus metrics: `result_cache_hits_total{engine_type}`, `result_cache_misses_total{engine_type}`, `result_cache_dedup_hits_total{engine_type}`, `result_cache_size_bytes`

**Usage examples:**
- User generates "anime girl, blue hair, 1024x1024" → cache miss → 3s → stored
- User regenerates same prompt → cache HIT → 50ms ✅ beats ComfyUI local
- 10 users simultaneously request same popular prompt → 1 external call + 9 dedup hits
- Workflow with cached nodes skips API calls entirely

### Task 10: WebSocket Streaming + Progress Push

**Responsibility**: Replace HTTP polling with real-time WebSocket progress push for long-running operations (video compose, batch image gen, character consistency). Eliminates polling overhead and matches ComfyUI/即梦 real-time feedback.

**Files:**
- Create: `app/api/websocket.py` — `@router.websocket("/ws")` endpoint with JWT auth
- Create: `app/core/ws_manager.py` — `WebSocketManager` singleton (connection registry, channel pub/sub, heartbeat)
- Create: `app/schemas/ws.py` — WS message protocol (`WSMessage`, `WSRequest`, `WSResponse`)
- Modify: `app/services/task_service.py` — `TaskService` emits progress events to `WebSocketManager` on status change + periodic progress updates
- Modify: `app/engines/video/ffmpeg.py` — parse FFmpeg `-progress pipe:2` output, emit `video_render.progress` events
- Modify: `app/engines/image/pollinations.py` — emit `image_gen.started` / `image_gen.completed` events
- Modify: `app/main.py` — register WS router, init `WebSocketManager` in lifespan
- Modify: `app/api/router.py` — include `ws_router`
- Create: `tests/test_websocket.py` — 10 tests

**WS protocol:**
```python
# Client → Server: subscribe
{"type": "subscribe", "channel": "task.{task_id}"}
# Server → Client: progress
{"type": "progress", "channel": "task.{task_id}", "data": {"progress": 0.45, "stage": "rendering"}, "timestamp": 1784437525}
# Server → Client: completed
{"type": "completed", "channel": "task.{task_id}", "data": {"status": "succeeded", "result_url": "..."}, "timestamp": ...}
# Server → Client: heartbeat
{"type": "ping"}  → client must respond {"type": "pong"} within 10s
```

**Channels:**
- `task.{task_id}` — generic task progress (from TaskService)
- `image_gen.{request_id}` — single image generation progress
- `video_render.{task_id}` — FFmpeg frame-by-frame progress (frame=X, fps=Y, speed=Nx)
- `user.{user_id}` — user-scoped notifications (credit deductions, plan changes)

**Behavior:**
- Auth: `ws://host/ws?token=JWT` — verify JWT in `websocket_connect`, close with code 4001 if invalid
- One connection per user (new connection replaces old with `4003 Duplicate Connection` close)
- Heartbeat: server sends `ping` every 30s; client must `pong` within 10s or connection closed
- Backpressure: if send queue > 100 messages, drop oldest non-critical, send `{"type": "warn", "code": "backpressure"}`
- Desktop mode: WS works on localhost (Electron connects to local backend)
- Prometheus: `websocket_connections_active`, `websocket_messages_sent_total{type}`, `websocket_messages_received_total{type}`

**FFmpeg progress parsing:**
```python
# FFmpeg -progress pipe:2 output (key=value lines)
frame=120
fps=30.5
speed=2.1x
bitrate=1500kbits/s
total_size=12500000
out_time_ms=4000000
progress=continue  # or progress=end

# Parsed and emitted as:
{"type": "progress", "channel": "video_render.{task_id}",
 "data": {"frame": 120, "fps": 30.5, "speed": 2.1, "progress": 0.45}, ...}
```

### Task 11: HTTP/2 + Connection Pool + Image Format Optimization

**Responsibility**: Upgrade all external HTTP clients to HTTP/2 with explicit connection pools (eliminates FFmpeg per-frame client creation anti-pattern), auto-convert PNG→WebP, generate thumbnails. Cuts network overhead and mobile bandwidth.

**Files:**
- Create: `app/core/http_client.py` — `HttpClientFactory` singleton, shared `httpx.AsyncClient` per base_url with HTTP/2 + Limits
- Modify: `app/engines/image/pollinations.py` — use factory client, remove per-instance `httpx.AsyncClient`
- Modify: `app/engines/llm/deepseek.py` — use factory client
- Modify: `app/engines/video/ffmpeg.py` — use factory client for frame downloads (shared), `asyncio.gather` with `Semaphore(8)` for parallel frame downloads
- Create: `app/services/image_optimizer.py` — `ImageOptimizer` (WebP conversion + thumbnail generation)
- Modify: `app/core/storage.py` — `FileStorage.save()` accepts `optimize=True` param to trigger WebP conversion
- Modify: `app/api/ai.py` — image endpoints return `{url, thumbnail_url, original_url, format}`
- Modify: `app/schemas/ai.py` — `Text2ImageResponse` includes `thumbnail_url`, `original_url`, `format`
- Create: `tests/test_http_client.py` — 6 tests
- Create: `tests/test_image_optimizer.py` — 6 tests

**HTTP/2 client configuration:**
```python
# app/core/http_client.py
class HttpClientFactory:
    """Singleton factory — one shared AsyncClient per base_url with HTTP/2."""
    def __init__(self):
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=50,
            keepalive_expiry=30.0,
        )

    def get_client(self, base_url: str = "") -> httpx.AsyncClient:
        if base_url not in self._clients:
            self._clients[base_url] = httpx.AsyncClient(
                base_url=base_url,
                http2=True,  # HTTP/2 multiplexing
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=self._limits,
                headers={"User-Agent": "ComicStudio/1.0"},
            )
        return self._clients[base_url]

    async def close_all(self):
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()

http_client_factory = HttpClientFactory()
```

**FFmpeg parallel frame download fix:**
```python
# Before (anti-pattern): N frames = N new clients, serial download
for i, frame in enumerate(frames):
    async with httpx.AsyncClient() as client:  # ❌ new client per frame
        resp = await client.get(frame.url)
        await _save_frame(resp.content, i)

# After: shared client + parallel with concurrency limit
sem = asyncio.Semaphore(8)
client = http_client_factory.get_client()

async def download_one(i: int, frame: Frame) -> None:
    async with sem:
        resp = await client.get(frame.url)
        resp.raise_for_status()
        await _save_frame(resp.content, i)

await asyncio.gather(*[download_one(i, f) for i, f in enumerate(frames)])  # ✅
```

**Image optimizer behavior:**
- PNG → WebP conversion: quality=85, method=4 (balanced speed/size)
- Thumbnail: 300x300 max, WebP quality=75
- Original PNG preserved (configurable: `image_keep_original=True`)
- Storage layout: `uploads/images/20260719/{uuid}.webp` + `{uuid}_thumb.webp` + `{uuid}.png` (if keep_original)
- Pure Python via Pillow (already a transitive dep via Electron build); zero new heavy deps
- Desktop mode: same behavior (WebP supported everywhere)
- Response shape:
  ```json
  {
    "url": "/uploads/images/20260719/abc.webp",
    "thumbnail_url": "/uploads/images/20260719/abc_thumb.webp",
    "original_url": "/uploads/images/20260719/abc.png",
    "format": "webp",
    "width": 1024,
    "height": 1024,
    "size_bytes": 234567
  }
  ```

**Performance targets:**
- HTTP/2 multiplexing: 30-50% reduction in connection overhead for burst requests
- FFmpeg frame download: 4-8x speedup for 30-frame videos (parallel vs serial)
- WebP vs PNG: 30-50% size reduction for typical AI-generated images
- Thumbnail: enables instant preview UI without full-image download

### Task 12: DeepSeek SSE Stream Pass-through

**Responsibility**: Expose DeepSeek's native SSE streaming through `/api/ai/chat` for typewriter UX (eliminates 3-10s wait for full response — first token in <500ms).

**Files:**
- Modify: `app/engines/llm/deepseek.py` — add `chat_stream()` async generator method (DeepSeek SDK already supports `stream=True`)
- Modify: `app/api/ai.py` — `/api/ai/chat` accepts `stream=true` query param, returns `text/event-stream` when set
- Modify: `app/schemas/ai.py` — add `stream: bool = False` to `ChatRequest`
- Create: `tests/test_sse_stream.py` — 6 tests

**SSE protocol:**
```
POST /api/ai/chat?stream=true
Authorization: Bearer <jwt>
Content-Type: application/json

{"message": "写一个短篇漫画剧本", "context": [...]}
```

Response (200, `text/event-stream`):
```
data: {"delta": "好的", "finish_reason": null}

data: {"delta": "，我", "finish_reason": null}

data: {"delta": "来写", "finish_reason": null}

...

data: {"delta": "", "finish_reason": "stop", "usage": {"prompt_tokens": 50, "completion_tokens": 120}}

data: [DONE]

```

**Behavior:**
- `stream=false` (default): preserves existing behavior (blocking call, returns full `ChatResponse`)
- `stream=true`: returns SSE stream; each `data:` line is a JSON delta
- Client uses `EventSource` or `fetch` with `ReadableStream` to consume
- On error mid-stream: `data: {"error": "rate_limited", "message": "..."}\n\n` then close
- Credit deduction happens upfront (existing behavior); refund on stream error if no tokens received
- Desktop mode: same behavior (DeepSeek is remote either way)
- Prometheus: `sse_streams_total`, `sse_stream_errors_total`

**Client example (frontend):**
```typescript
const resp = await fetch('/api/v1/ai/chat?stream=true', {
  method: 'POST',
  headers: {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'},
  body: JSON.stringify({message: '写剧本', context: []}),
});
const reader = resp.body!.getReader();
const decoder = new TextDecoder();
let buffer = '';
while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, {stream: true});
  const lines = buffer.split('\n\n');
  buffer = lines.pop() || '';
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      if (data.delta) appendToUI(data.delta);
      if (data.finish_reason === 'stop') break;
    }
  }
}
```

### Task 13: CDN Integration + Provider Failover

**Responsibility**: Commercial-grade asset distribution (CDN edge caching for AI-generated images/videos + static assets) and external AI provider failover (so a single provider outage does not take the service offline).

**Files:**
- Create: `app/core/cdn.py` — `CDNManager` abstraction (S3-compatible / Cloudflare R2 / 七牛云 Kodo)
- Create: `app/core/storage_cdn.py` — `CDNFileStorage` subclass of `FileStorage` that uploads to CDN after local save
- Modify: `app/core/storage.py` — `FileStorage.save()` accepts `push_to_cdn=True` param
- Modify: `app/core/config.py` — add `cdn_provider` (none/r2/qiniu/s3), `cdn_*` credentials, `cdn_base_url`
- Create: `app/engines/provider_failover.py` — `ProviderFailover` wrapper with retry + circuit breaker + secondary provider
- Modify: `app/engines/image/pollinations.py` — wrap with failover; secondary = local placeholder image generation (text-to-image with PIL, degraded mode)
- Modify: `app/engines/llm/deepseek.py` — wrap with failover; secondary = Pollinations text API (free)
- Create: `tests/test_cdn.py` — 6 tests
- Create: `tests/test_provider_failover.py` — 6 tests

**CDN providers (zero-cost):**
- **Cloudflare R2** (recommended): 10GB free + 1M reads/month + 10M writes/month free tier; S3-compatible API
- **七牛云 Kodo** (China alternative): 10GB free + 1GB/day egress free for individual developers
- **Self-hosted MinIO**: 0 cost but no edge caching (only suitable for backup, not CDN)
- `cdn_provider=none`: skip CDN, serve from local disk (desktop/dev only)

**CDN upload behavior:**
```python
# CDNManager.upload(local_path, key) — async, non-blocking
# Returns CDN URL (e.g., https://cdn.comicstudio.ai/images/abc.webp)
# Local copy retained for fallback if CDN upload fails
```

**Storage layout with CDN:**
- Local disk: `uploads/images/20260719/abc.webp` (fallback)
- CDN: `https://cdn.comicstudio.ai/images/20260719/abc.webp` (primary, served to users)
- Response: `url` field points to CDN URL when `cdn_provider != none`

**Provider failover behavior:**
```python
class ProviderFailover:
    """Wraps a primary provider with retry + circuit breaker + secondary fallback."""

    def __init__(self, primary, secondary=None, max_retries=3,
                 circuit_breaker_threshold=5, circuit_breaker_reset_seconds=60):
        ...

    async def call(self, operation: str, *args, **kwargs):
        # 1. Check circuit breaker (open → skip primary)
        # 2. Retry primary up to max_retries (exponential backoff)
        # 3. If all retries fail OR circuit open → call secondary
        # 4. If no secondary → raise ProviderUnavailableError
        # 5. On N consecutive failures → open circuit breaker
```

**Failover matrix:**
| Engine | Primary | Secondary | Degraded mode |
|---|---|---|---|
| image | Pollinations.ai | (none — no free alternative) | PIL placeholder with prompt text overlay |
| llm | DeepSeek | Pollinations text API (free) | Local rule-based response (canned) |
| tts | edge-tts | (none) | Error to user |
| video | FFmpeg local | (none) | Error to user |
| character | soft_provider (LLM+seed) | (none) | Use base image without consistency |

**Circuit breaker metrics (Prometheus):**
- `provider_circuit_state{provider, state=open|closed|half_open}`
- `provider_calls_total{provider, result=success|failure|fallback}`
- `provider_retry_total{provider}`

### Task 14: Backup, Alerting, SLA Monitoring

**Responsibility**: Commercial ops essentials — automated DB + file backup, Prometheus alerting rules + Alertmanager integration, SLA/SLO dashboard, runbook for incident response.

**Files:**
- Create: `scripts/backup.sh` + `scripts/backup.ps1` — pg_dump + uploads tarball + Redis BGSAVE
- Create: `scripts/restore.sh` + `scripts/restore.ps1` — restore from backup
- Create: `deploy/cron/backup.cron` — daily 3am backup crontab entry
- Create: `deploy/prometheus/alerts.yml` — Prometheus alerting rules (15 rules)
- Create: `deploy/prometheus/prometheus.yml` — Prometheus scrape config
- Create: `deploy/alertmanager/config.yml` — Alertmanager routing (email + webhook to Feishu/DingTalk)
- Create: `deploy/grafana/dashboards/` — 3 dashboards (API health, AI engines, Business metrics)
- Create: `app/api/admin_ops.py` — admin endpoints for backup trigger, restore status, SLA report
- Modify: `app/api/admin.py` — register admin_ops router
- Modify: `app/core/middleware/access_log.py` — also emit SLO metrics (request within SLO = 1, breach = 0)
- Create: `docs/runbook/incident-response.md` — incident response playbook
- Create: `tests/test_backup.py` — 4 tests (validate backup script syntax, file structure)
- Create: `tests/test_alerting.py` — 4 tests (validate alert rules syntax, threshold logic)

**Backup strategy:**
- **Frequency**: Daily full backup at 3:00 AM server time; Redis BGSAVE every 6h
- **Retention**: 30 days rolling (30 daily backups), 12 weekly (Sunday) for 12 weeks, 12 monthly for 1 year
- **Storage**: Local `/backups/` + upload to CDN R2 bucket `comicstudio-backups` (cross-region)
- **Components**:
  - PostgreSQL: `pg_dump --format=custom --compress=9`
  - Uploads: `tar -czf uploads-YYYYMMDD.tar.gz uploads/`
  - Redis: `BGSAVE` then copy `dump.rdb`
  - Config: `.env.production` (without secrets, secrets via vault)
- **Restore drill**: monthly cron job restores to staging DB, runs smoke tests, alerts if fails

**Prometheus alert rules (15 rules):**
```yaml
groups:
- name: comicstudio-critical
  rules:
  # Service down
  - alert: BackendDown
    expr: up{job="comicstudio-backend"} == 0
    for: 1m
    labels: {severity: critical}
    annotations: {summary: "Backend {{ $labels.instance }} down"}

  # High error rate
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
    for: 5m
    labels: {severity: critical}
    annotations: {summary: "5xx error rate > 5% for 5min"}

  # SLO breach: p99 latency > 5s on AI endpoints
  - alert: HighAILatency
    expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{path=~"/api/v1/ai/.*"}[5m])) > 5
    for: 10m
    labels: {severity: warning}
    annotations: {summary: "AI endpoint p99 > 5s for 10min"}

  # Cache hit rate drop
  - alert: LowCacheHitRate
    expr: rate(result_cache_hits_total[15m]) / (rate(result_cache_hits_total[15m]) + rate(result_cache_misses_total[15m])) < 0.20
    for: 30m
    labels: {severity: warning}
    annotations: {summary: "Result cache hit rate < 20% for 30min"}

  # Database connection pool exhaustion
  - alert: DBPoolExhaustion
    expr: pg_stat_activity_count / pg_settings_max_connections > 0.8
    for: 5m
    labels: {severity: critical}

  # Redis memory high
  - alert: RedisMemoryHigh
    expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.85
    for: 10m
    labels: {severity: warning}

  # Disk space low
  - alert: DiskSpaceLow
    expr: (1 - node_filesystem_avail_bytes / node_filesystem_size_bytes) > 0.85
    for: 5m
    labels: {severity: warning}

  # ... 8 more rules (engine circuit breaker open, websocket connection saturation,
  #     credit deduction failures, payment webhook failures, SSL cert expiry < 14d,
  #     backup job failure, task queue backlog, SSE stream error spike)
```

**Alertmanager routing:**
```yaml
route:
  receiver: default
  group_by: [alertname, severity]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
receivers:
- name: default
  webhook_configs:
  - url: https://open.feishu.cn/open-apis/bot/v2/hook/{token}  # Feishu bot
    send_resolved: true
- name: critical
  webhook_configs:
  - url: https://oapi.dingtalk.com/robot/send?access_token={token}  # DingTalk
  email_configs:
  - to: ops@comicstudio.ai
```

**Grafana dashboards (3):**
1. **API Health**: QPS, p50/p90/p99 latency, error rate, SLO compliance %, active users
2. **AI Engines**: per-engine QPS, cache hit rate, concurrent requests, circuit breaker state, provider fallback rate
3. **Business**: credit consumption rate, subscription conversions, payment success rate, MRR proxy

**SLA endpoints (admin-only):**
- `GET /api/v1/admin/ops/sla` — returns SLO compliance for last 24h/7d/30d
- `POST /api/v1/admin/ops/backup` — trigger immediate backup
- `GET /api/v1/admin/ops/backups` — list available backups
- `POST /api/v1/admin/ops/restore` — trigger restore from specified backup (with confirmation token)

**SLA targets (commercial):**
| Metric | Target | Alert threshold |
|---|---|---|
| API uptime (monthly) | 99.5% | <99.5% triggers compensation |
| AI endpoint p99 latency (cloud) | ≤5s | >5s for 10min → warning |
| Desktop local GPU p99 latency | ≤3s | N/A (local) |
| Desktop local CPU p99 latency | ≤15s | N/A (local) |
| Cache hit rate (peak hours) | ≥30% | <20% for 30min → warning |
| Backup success rate | 100% | Any failure → critical |
| Payment webhook latency | ≤2s | >5s for 5min → warning |

### Task 15: Desktop Local AI Inference Engine

**Responsibility**: Bundle local AI inference into the desktop app so users get ComfyUI-class speed without internet. Supports NVIDIA GPU (fastest, via diffusers + xFormers + Flash Attention) and CPU fallback (via ONNX Runtime with quantized models). Three-tier fallback: local GPU → local CPU → remote API.

**Files:**
- Create: `backend/app/engines/image/local_diffusers.py` — `LocalDiffusersProvider` (NVIDIA GPU path, SDXL Turbo / SDXL Lightning / SD 1.5)
- Create: `backend/app/engines/image/local_onnx.py` — `LocalOnnxProvider` (CPU path, quantized SD 1.5 / SDXL Turbo ONNX)
- Create: `backend/app/engines/llm/local_llm.py` — `LocalLLMProvider` (CPU: qwen2.5-1.5B-Instruct Q4 via llama.cpp Python bindings; GPU: same model Q8 or larger)
- Create: `backend/app/engines/tts/local_tts.py` — `LocalTTSProvider` (Piper TTS, offline, CPU-friendly)
- Create: `backend/app/engines/local_runtime.py` — `LocalRuntimeDetector`: detects GPU, manages model loading/unloading, provides shared VRAM/RAM pool
- Create: `backend/app/engines/model_manager.py` — `ModelManager`: HuggingFace download, model registry, LoRA loading, model switching at runtime
- Modify: `backend/app/engines/manager.py` — `EngineManager` auto-selects local vs remote based on `LocalRuntimeDetector` + user preference
- Modify: `backend/app/engines/image/pollinations.py` — becomes FALLBACK when local unavailable
- Modify: `backend/app/api/ai.py` — `/api/ai/text2img` accepts `engine=auto|local|remote` param (default `auto`)
- Create: `backend/app/api/models.py` — endpoints: `GET /api/models`, `POST /api/models/download`, `DELETE /api/models/{id}`, `POST /api/models/{id}/activate`
- Modify: `backend/app/api/router.py` — register models router
- Modify: `backend/app/core/config.py` — add `local_inference_enabled`, `local_inference_device` (auto/cpu/cuda), `local_model_dir`, `local_default_image_model`, `local_default_llm_model`, `local_default_tts_voice`
- Create: `backend/app/schemas/model.py` — `ModelInfo`, `ModelListResponse`, `ModelDownloadRequest`, `ModelActivateRequest`
- Create: `backend/tests/test_local_diffusers.py` — 6 tests (skip if no GPU)
- Create: `backend/tests/test_local_onnx.py` — 6 tests (skip if onnxruntime not installed)
- Create: `backend/tests/test_local_llm.py` — 4 tests
- Create: `backend/tests/test_local_runtime_detector.py` — 4 tests

**LocalRuntimeDetector behavior:**
```python
class LocalRuntimeDetector:
    """Detects available local compute and selects optimal provider."""

    @staticmethod
    def detect_device() -> str:
        """Returns 'cuda', 'cpu', or 'mps' (future Mac support)."""
        # 1. Try torch.cuda.is_available() → 'cuda'
        # 2. Try torch.backends.mps.is_available() → 'mps' (Phase 8)
        # 3. Else → 'cpu'

    @staticmethod
    def get_gpu_info() -> dict | None:
        """Returns {name, vram_total_bytes, vram_free_bytes, cuda_version} or None."""

    @staticmethod
    def get_recommended_provider(engine_type: str) -> str:
        """Returns 'local_gpu', 'local_cpu', or 'remote' based on hardware + user config."""
        # image: if GPU VRAM >= 6GB → 'local_gpu'; elif RAM >= 16GB → 'local_cpu'; else 'remote'
        # llm: if GPU VRAM >= 4GB → 'local_gpu' (qwen2.5-7b Q4); elif RAM >= 8GB → 'local_cpu' (qwen2.5-1.5b Q4); else 'remote'
        # tts: always 'local_cpu' (Piper is fast on CPU)
```

**LocalDiffusersProvider (NVIDIA GPU path):**
```python
class LocalDiffusersProvider(BaseImageEngine):
    """Local image generation via diffusers + xFormers + Flash Attention.

    Models: SDXL Turbo (4 steps, ~2s on RTX 3060), SDXL Lightning (8 steps, ~3s),
            SD 1.5 (20 steps, ~5s, lowest VRAM)
    Optimization: xFormers memory-efficient attention, FP16, sliced VAE decode,
                  sequential CPU offload (for low-VRAM GPUs)
    """
    async def text2img(self, prompt, negative_prompt, width, height, steps, cfg_scale, seed):
        # 1. Load pipeline (cached in memory after first call)
        # 2. Apply xFormers + FP16
        # 3. generator = torch.Generator().manual_seed(seed)
        # 4. image = pipeline(prompt, negative_prompt, width, height, steps,
        #                     cfg_scale, generator=generator).images[0]
        # 5. Emit WebSocket progress events per step
        # 6. Return PIL Image
```

**LocalOnnxProvider (CPU path):**
```python
class LocalOnnxProvider(BaseImageEngine):
    """CPU image generation via ONNX Runtime with quantized models.

    Models: SD 1.5 ONNX INT8 (~2GB, ~15s/image on i7-12700K)
    Optimization: ONNX Runtime with CPU EP, INT8 quantization, thread pinning
    """
    async def text2img(self, prompt, ...):
        # 1. Load ONNX UNet + VAE + CLIP text encoder (cached)
        # 2. Run inference with onnxruntime.InferenceSession
        # 3. Return PIL Image
```

**ModelManager behavior:**
- Default models (downloaded on first launch if user opts in):
  - Image: `stabilityai/sdxl-turbo` (~6GB, GPU) / `runwayml/stable-diffusion-v1-5` ONNX INT8 (~2GB, CPU)
  - LLM: `Qwen/Qwen2.5-1.5B-Instruct` GGUF Q4 (~1GB, CPU) / `Qwen/Qwen2.5-7B-Instruct` GGUF Q4 (~4GB, GPU)
  - TTS: `rhasspy/piper-voices` zh_CN-huayan-medium (~60MB)
- HuggingFace download with progress (uses `huggingface_hub.snapshot_download`)
- Model registry stored in SQLite (`local_models` table: id, name, type, path, size_bytes, quantization, active, downloaded_at)
- User can browse HuggingFace models via API and add to download queue
- LoRA support: scan `~/.comicstudio/loras/`, apply to image pipeline via `pipeline.load_lora_weights()`
- Model switching: hot-swap active model without restart (unloads previous, loads new)

**Desktop API endpoints:**
- `GET /api/models` — list available models (downloaded + downloadable)
- `POST /api/models/download` — start download (returns task_id, progress via WebSocket)
- `DELETE /api/models/{id}` — delete model from disk
- `POST /api/models/{id}/activate` — set as active model for engine type
- `GET /api/runtime/info` — returns device info, VRAM, RAM, recommended provider

**Three-tier fallback logic:**
```python
async def generate_image(prompt, ...):
    provider = LocalRuntimeDetector.get_recommended_provider("image")

    if provider == "local_gpu" and local_diffusers.is_available():
        try:
            return await local_diffusers.text2img(prompt, ...)
        except Exception as e:
            logger.warning(f"Local GPU failed, falling back to CPU: {e}")

    if provider in ("local_gpu", "local_cpu") and local_onnx.is_available():
        try:
            return await local_onnx.text2img(prompt, ...)
        except Exception as e:
            logger.warning(f"Local CPU failed, falling back to remote: {e}")

    # Final fallback: remote API (existing Pollinations provider)
    return await pollinations.text2img(prompt, ...)
```

**Cloud deployment behavior:**
- `local_inference_enabled=False` by default in cloud (servers typically have no GPU or GPU is expensive)
- Cloud uses remote API (Pollinations/DeepSeek) + result cache (Task 9) + CDN (Task 13)
- All local inference code is import-guarded; cloud installs without torch/onnxruntime

**Desktop deployment behavior:**
- `local_inference_enabled=True` by default
- First launch: ask user to download default models (skip → use remote API only)
- GPU detected → use diffusers path (~2-3s per image)
- No GPU → use ONNX path (~15s per image)
- Remote API used only when: local fails, OR user explicitly sets `engine=remote`, OR model not downloaded

**New dependencies (desktop only):**
```
# desktop-requirements.txt (separate from cloud requirements.txt)
torch==2.4.0          # GPU inference (auto-detects CUDA)
torchvision==0.19.0
diffusers==0.30.0     # HuggingFace diffusers
transformers==4.44.0  # CLIP, Qwen
xformers==0.0.27      # Memory-efficient attention (GPU only)
accelerate==0.34.0    # Device management
onnxruntime==1.19.0   # CPU inference (no torch dependency)
huggingface_hub==0.25.0  # Model download
llama_cpp_python==0.3.0  # Local LLM (Qwen GGUF)
piper-tts==1.2.0      # Offline TTS
```

**Desktop installer size impact:**
- Without models: +1.5GB (PyTorch + diffusers + onnxruntime)
- With default models: +10GB (SDXL Turbo 6GB + Qwen 1GB + Piper 60MB + ONNX SD 2GB)
- Strategy: installer bundles runtime only; models downloaded on first launch (user choice)
- Electron-builder `extraResources` includes Python runtime + libs; models in user data dir

**Performance targets (desktop):**
| Hardware | Image (1024x1024) | LLM (100 tokens) | TTS (1 sentence) |
|---|---|---|---|
| RTX 3060 12GB | ~2s (SDXL Turbo 4-step) | ~1s (Qwen 7B Q4) | ~200ms |
| RTX 4060 8GB | ~1.5s (SDXL Turbo) | ~0.5s (Qwen 7B Q4) | ~150ms |
| i7-12700K CPU | ~15s (SD 1.5 ONNX INT8) | ~5s (Qwen 1.5B Q4) | ~300ms |
| M2 (future) | ~4s (MPS, Phase 8) | ~2s | ~250ms |

### Task 16: Desktop Installer with Bundled AI Runtime

**Responsibility**: Build desktop installers that bundle Python + local AI runtime + Electron app into a single commercial-grade installer. Handles first-launch model download UX, GPU detection, and disk space management.

**Files:**
- Modify: `desktop/package.json` — add `dist:win-gpu`, `dist:win-cpu`, `dist:linux-gpu`, `dist:linux-cpu` scripts (4 installer variants)
- Modify: `desktop/electron-builder.yml` — add per-variant config (GPU bundle includes torch+CUDA, CPU bundle includes onnxruntime only)
- Create: `desktop/scripts/build-python-runtime.ts` — uses PyInstaller to bundle Python + AI libs into single folder
- Create: `desktop/scripts/extract-torch-cuda.ps1` + `.sh` — extracts CUDA runtime DLLs for GPU installer variant
- Modify: `desktop/src/main/backend-process.ts` — detect GPU on launch, set `CS_LOCAL_INFERENCE_DEVICE=cuda|cpu` env var for backend
- Create: `desktop/src/renderer/src/pages/FirstLaunchSetup.tsx` — first-launch wizard: detect GPU, recommend model package, download progress, sample test
- Create: `desktop/src/main/gpu-detector.ts` — native module to query GPU info via `wmic` (Win) / `lspci` (Linux)
- Modify: `desktop/src/preload/api.ts` — expose `gpuDetector.getInfo()`, `modelManager.download()`, `modelManager.activate()` to renderer
- Create: `desktop/src/renderer/src/pages/ModelManager.tsx` — UI to browse/download/activate/delete models
- Modify: `desktop/src/renderer/src/pages/Settings.tsx` — add "AI Engine" section: local vs remote preference, GPU selection, VRAM limit
- Create: `desktop/tests/test-gpu-detector.test.ts` — 4 tests
- Create: `desktop/tests/test-first-launch-setup.test.tsx` — 4 tests
- Create: `backend/tests/test_model_manager.py` — 4 tests

**Four installer variants:**
```yaml
# electron-builder.yml variants
win-gpu:
  name: "ComicStudio AI (GPU 版)"
  artifactName: "ComicStudio-Setup-${version}-gpu.exe"
  extraResources:
    - from: ../backend/dist/local-gpu  # PyInstaller bundle (torch+CUDA)
      to: backend
  # Size: ~2.5GB installer (downloads models on first launch)
  # Targets: NVIDIA GPU users (RTX 20-series and newer)

win-cpu:
  name: "ComicStudio AI (CPU 版)"
  artifactName: "ComicStudio-Setup-${version}-cpu.exe"
  extraResources:
    - from: ../backend/dist/local-cpu  # PyInstaller bundle (onnxruntime only)
      to: backend
  # Size: ~600MB installer
  # Targets: users without GPU; also works on any PC

linux-gpu / linux-cpu:
  # Same as Win variants but .AppImage / .deb
```

**First-launch wizard UX:**
```
┌─────────────────────────────────────────┐
│  Welcome to ComicStudio AI              │
│                                          │
│  Detected hardware:                      │
│  ✓ NVIDIA RTX 3060 (12GB VRAM)          │
│  ✓ 32GB RAM                             │
│  ✓ 500GB free disk space                │
│                                          │
│  Recommended setup:                      │
│  • SDXL Turbo (6GB) - fast image gen    │
│  • Qwen2.5-7B (4GB) - smart chat        │
│  • Piper TTS (60MB) - offline voice     │
│  Total: ~10GB download                  │
│                                          │
│  [Download & Install]  [Customize]      │
│  [Skip - use cloud only]                │
└─────────────────────────────────────────┘
```

**Build pipeline (CI/CD):**
- GitHub Actions matrix: `[win, linux] × [gpu, cpu]` = 4 build jobs
- GPU variant: bundles `torch==2.4.0+cu121` (~2GB) + CUDA runtime DLLs
- CPU variant: bundles `onnxruntime==1.19.0` (~200MB)
- Each variant tested on GitHub Actions runner with smoke test
- Released as separate GitHub Releases assets (user picks variant on download page)

**PyInstaller spec for local AI runtime:**
```python
# backend/local-gpu.spec
a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    hiddenimports=[
        'torch', 'torchvision', 'diffusers', 'transformers',
        'xformers', 'accelerate', 'huggingface_hub',
        'llama_cpp', 'piper_tts',
        # CUDA backends
        'torch.cuda', 'torch.backends.cudnn',
    ],
    excludes=['onnxruntime'],  # GPU variant doesn't need ONNX
    # ... hooks for native libs
)
# Bundle CUDA runtime DLLs alongside
exe = EXE(..., name='comicstudio-backend-gpu')
```

**Disk space management:**
- Detect free disk space before download
- Warn if < 15GB free (default models + buffer)
- Allow user to choose custom model storage location (e.g., external SSD)
- Models stored in `%APPDATA%/ComicStudio/models/` (Windows) or `~/.comicstudio/models/` (Linux)

---

## 4. Data Flow Examples

### 4.0 Cache-Hit Fast Path (p99 < 50ms)

```
1. Client POST /api/v1/ai/text2img {prompt: "anime girl", seed: 42, size: 1024x1024}
2. Rate limiter checks plan limit
3. check_and_deduct_credits(user, "text2img") → -10 credits
4. ai.text2img endpoint:
   a. compute_cache_key("image", {prompt, seed, size, model}) → sha256 hash
   b. ResultCacheService.get(cache_key) → HIT!
   c. Return cached URL with X-Cache: HIT header
   d. Refund credits (cache hit is free, configurable)
5. Total latency: <50ms (no external API call, no disk write)
```

### 4.1 Cached + Async Video Compose (with CDN + WS)

```
1. Client POST /api/v1/ai/video/compose
2. Nginx: TLS termination, rate limit, forward to backend
3. Rate limiter (Redis) checks plan limit (free=30/min)
4. check_and_deduct_credits(user, "video_compose") → -50 credits
5. ResultCacheService.get(cache_key) → MISS
6. ai.video_compose endpoint:
   a. Acquire engine semaphore (max 2 concurrent)
   b. Submit to TaskService.submit("video_compose", payload)
   c. Task persisted to DB with status="pending"
   d. Return 202 Accepted with task_id + ws_channel="task.{task_id}"
7. Client opens WS /ws?token=JWT, subscribes to task.{task_id}
8. Background coroutine:
   a. Status="running", progress=0 → WS push
   b. FFmpeg compose with -progress pipe:2 → periodic WS pushes (frame, fps, speed)
   c. On success: ImageOptimizer converts frames → WebP; CDNManager uploads final video
   d. Status="succeeded" + CDN result URL → WS push; ResultCacheService stores
   e. On failure: status="failed" + error → WS push; credits refunded
9. Client receives WS "completed" event with CDN URL, plays video from edge
```

### 4.2 Provider Failover Path

```
1. Client POST /api/v1/ai/text2img {prompt: "..."}
2. ResultCacheService.get(cache_key) → MISS
3. EngineConcurrencyManager.acquire_slot("image") → got slot
4. ProviderFailover.call("text2img", ...):
   a. Primary (Pollinations): retry 1 → 503; retry 2 → 503; retry 3 → timeout
   b. Circuit breaker opens (5 consecutive failures)
   c. Secondary: PIL placeholder generation (degraded mode)
   d. Returns placeholder image with prompt text overlay
   e. Response includes X-Provider: fallback header
5. Frontend shows degraded image with "AI 服务繁忙,显示降级结果" notice
6. After 60s, circuit breaker → half-open → next request tries primary again
7. Prometheus: provider_circuit_state{provider=pollinations, state=open}
8. Alertmanager: ProviderCircuitOpen alert → Feishu webhook notification
```

### 4.3 Request with Full Observability

```
1. Client request arrives
2. RequestIDMiddleware: generate X-Request-ID (or use client's)
3. AccessLogMiddleware: log start time
4. CORS / Gzip / Sentry middlewares process
5. Route handler executes (with cache + semaphore decorators)
6. Response generated
7. Prometheus instrumentator records: http_requests_total, http_request_duration_seconds
8. AccessLogMiddleware: log JSON {request_id, method, path, status, duration_ms, user_id, ip}
9. Response sent with X-Request-ID header
```

---

## 5. Error Handling Strategy

### 5.1 Graceful Degradation Matrix

| Subsystem | Failure mode | Fallback |
|-----------|--------------|----------|
| CacheService (Redis down) | Catch `ConnectionError`, log warning, fall back to in-memory `TTLCache` | 100% function, reduced hit rate |
| TaskService (DB write fail) | Return 500, refund credits, log error | Client retries |
| EngineConcurrency (semaphore full) | Wait 30s, then HTTP 503 + credit refund | Client backs off |
| Prometheus (instrumentator fail) | Log warning, continue serving | Metrics gap |
| Sentry (DSN unset/init fail) | No-op, log debug | Errors only in logs |
| Alembic (migration fail on startup) | Log error, fall back to `create_all` | App still boots |
| Gzip (compression error) | Fall back to uncompressed | Slightly more bandwidth |
| ETag (hash fail) | Skip ETag header | Normal response |
| CDN (R2 upload fail) | Serve from local disk; retry CDN upload in background | Increased origin bandwidth |
| Provider failover (primary down) | Circuit breaker → secondary provider or degraded mode | Service remains available |
| Backup job (pg_dump fail) | Retry 3x, alert on final failure; previous backup retained | No data loss (prev backup exists) |
| Alertmanager (notification fail) | Log + retry; Sentry capture as backup channel | Alerts may be delayed |
| WebSocket (client disconnect) | Clean up connection in finally; mark task as orphaned | Task continues; client reconnects |
| Result cache (disk full) | LRU eviction triggered; if still full, skip caching for new entries | Cache disabled, requests go to provider |

### 5.2 Error Response Format

All errors continue using existing `ApiResponse.error()` format:
```json
{
  "code": -1,
  "message": "积分不足",
  "data": null,
  "timestamp": 1784437525
}
```

Plus `X-Request-ID` header for traceability.

---

## 6. Testing Strategy

### 6.1 Test Categories

| Category | Tools | Target |
|----------|-------|--------|
| Unit tests | pytest + pytest-asyncio | Each new service/middleware |
| Integration tests | pytest + httpx AsyncClient | API endpoints with real DB |
| Migration tests | pytest + Alembic | Upgrade/downgrade path |
| Cache tests | pytest + fakeredis | Metadata cache + result cache (both backends) |
| Concurrency tests | pytest + asyncio.Semaphore mock | Semaphore limits |
| Observability tests | pytest + TestClient | Middleware output |
| WebSocket tests | pytest + httpx WebSocket / websockets lib | Connection lifecycle, channel pub/sub, heartbeat |
| SSE stream tests | pytest + httpx stream client | Stream chunks, error handling, refund on early abort |
| HTTP/2 tests | pytest + httpx mock | Client factory reuse, limits enforcement |
| Image optimization tests | pytest + Pillow | WebP conversion, thumbnail size, format preservation |
| CDN tests | pytest + moto (S3 mock) / fakeredis | R2/七牛 upload, URL generation, fallback on failure |
| Provider failover tests | pytest + mock providers | Retry, circuit breaker open/close, secondary fallback |
| Backup tests | pytest + script validation | Backup script structure, restore drill |
| Alerting tests | pytest + Prometheus rule unittest | Alert rule syntax, threshold evaluation |
| Local AI inference tests | pytest + skip-if-no-GPU/CPU | LocalDiffusersProvider, LocalOnnxProvider, LocalLLMProvider, LocalRuntimeDetector |
| Model manager tests | pytest + huggingface_hub mock | Model download, registry, activation, LoRA loading |
| Desktop installer tests | vitest + electron-builder mock | First-launch wizard, GPU detector, model manager UI |
| Docker tests | pytest + docker build | Image builds successfully |
| Regression tests | Full suite | 338 existing + 166 new = 504+ |

### 6.2 Test Count Targets

| Task | New Tests | Cumulative |
|------|-----------|------------|
| 1 (Cache - metadata) | 12 | 350 |
| 2 (Async Tasks) | 12 | 362 |
| 3 (Concurrency) | 8 | 370 |
| 4 (Observability) | 10 | 380 |
| 5 (Health) | 8 | 388 |
| 6 (Migrations + N+1) | 6 | 394 |
| 7 (API Production) | 10 | 404 |
| 8 (CI/CD + Docker) | 4 | 408 |
| 9 (Result Cache + Dedup) | 12 | 420 |
| 10 (WebSocket Streaming) | 10 | 430 |
| 11 (HTTP/2 + Image Opt) | 12 | 442 |
| 12 (SSE Stream) | 6 | 448 |
| 13 (CDN + Provider Failover) | 12 | 460 |
| 14 (Backup + Alerting + SLA) | 8 | 468 |
| 15 (Local AI Inference Engine) | 20 | 488 |
| 16 (Desktop Installer + Runtime) | 12 | 500 |
| Buffer (integration/regression) | 4 | 504 |
| **Total** | **166** | **504** |

### 6.3 Coverage Target

- Backend: ≥70% (currently ~75%, maintain or improve)
- Desktop: ≥80% (currently ~85%, maintain)
- New modules: ≥80%

---

## 7. Compatibility Guarantees

### 7.1 Phase 1-6 Backward Compatibility

| Aspect | Guarantee |
|--------|-----------|
| API paths | All `/api/*` paths continue to work; `/api/v1/*` is alias |
| DB schema | All existing tables/columns preserved; Alembic `001_initial_schema.py` creates identical schema to current `create_all` |
| Config | All existing env vars keep same defaults; new vars have safe defaults |
| Desktop mode | `CS_DESKTOP_MODE=1` continues to work with no-op fallbacks for cache/task/concurrency/metrics/Sentry |
| Tests | All 338 existing tests pass unchanged (except minor fixture additions for new User fields if needed) |

### 7.2 Migration Path

1. **Phase 7 release**: New env vars added (all with defaults), existing deployments work without changes
2. **First restart with Alembic**: `001_initial_schema.py` runs, creates `alembic_version` table, no schema changes (matches current `create_all`)
3. **Optional `002_add_indexes.py`**: Adds performance indexes, no data changes
4. **JWT change**: Existing 24h tokens continue to work until expiry; new tokens are 30min; clients should implement refresh logic (frontend change)

### 7.3 Desktop Mode Specifics (First-Class Commercial Product)

Desktop app (CS_DESKTOP_MODE=1) is a **first-class commercial product** alongside the cloud SaaS. It is NOT a developer convenience — users download it as a commercial product. All performance optimizations apply to BOTH deployment targets. Where cloud uses Redis/PostgreSQL/CDN, desktop uses in-process/SQLite/local-disk equivalents with the SAME performance characteristics (within hardware constraints).

| Task | Desktop behavior (commercial product) |
|------|------------------------------------------|
| 1 (Cache - metadata) | In-memory `TTLCache` (same perf as Redis for single-user) |
| 2 (Async Tasks) | asyncio tasks in-process + SQLite persistence (same as cloud) |
| 3 (Concurrency) | Semaphores apply (prevents CPU/GPU overload, more important than cloud) |
| 4 (Observability) | No Sentry (privacy), text logs to user data dir, Prometheus on localhost for diagnostics |
| 5 (Health) | `/health` and `/ready` work; Redis check skipped; GPU/VRAM check included |
| 6 (Migrations) | `run_migrations_on_startup()` runs Alembic on local SQLite |
| 7 (API Production) | Gzip + ETag + JWT + refresh all work identically |
| 8 (CI/CD) | 4 desktop installer variants: win-gpu, win-cpu, linux-gpu, linux-cpu |
| 9 (Result Cache + Dedup) | Local file cache + SQLite metadata; same cache hit p99 <50ms target |
| 10 (WebSocket) | WS on localhost (Electron → local backend), <5ms latency (no network) |
| 11 (HTTP/2 + Image Opt) | HTTP/2 only when calling remote API (fallback); WebP always on |
| 12 (SSE Stream) | Works identically (local LLM can stream even faster than remote) |
| 13 (CDN + Failover) | `cdn_provider=none` (no CDN needed locally); provider failover = local→remote |
| 14 (Backup + Alerting) | Local backup to user-chosen location (no offsite); alerts via desktop notifications |
| 15 (Local AI Inference) | **CORE FEATURE**: GPU via diffusers (~2-3s), CPU via ONNX (~15s); three-tier fallback |
| 16 (Desktop Installer) | 4 installer variants, first-launch wizard, model manager UI |

**Critical**: Desktop local inference SLO targets are HARD requirements (not best-effort):
- Desktop local GPU p99 ≤ 3s for text2img (matches ComfyUI)
- Desktop local CPU p99 ≤ 15s for text2img (works offline)
- Desktop cache hit p99 ≤ 50ms (same as cloud)
- WebSocket progress push ≤ 5ms (localhost, no network latency)

---

## 8. Configuration Additions

### 8.1 New Settings (all with defaults)

```python
# Metadata cache (Task 1)
cache_enabled: bool = True
cache_ttl_default: int = 300  # 5 min
cache_redis_url: str = ""  # Empty = use redis_url; "memory" = force in-memory

# Async tasks (Task 2)
max_concurrent_tasks: int = 4
task_timeout_seconds: int = 1800  # 30 min

# Engine concurrency (Task 3)
engine_max_concurrent_image: int = 5
engine_max_concurrent_llm: int = 10
engine_max_concurrent_tts: int = 8
engine_max_concurrent_video: int = 2
engine_max_concurrent_character: int = 3
engine_acquire_timeout_seconds: int = 30

# Observability (Task 4)
sentry_dsn: str = ""  # Empty = disabled
log_format: str = "text"  # text | json
metrics_enabled: bool = True
metrics_path: str = "/metrics"

# JWT (Task 7, CHANGED default)
jwt_access_token_expire_minutes: int = 30  # was 1440

# Migration (Task 6)
run_migrations_on_startup: bool = True  # dev/desktop only; prod uses CLI

# Result cache (Task 9)
result_cache_enabled: bool = True
result_cache_max_entries: int = 10000  # LRU eviction threshold
result_cache_ttl_image_seconds: int = 86400  # 24h
result_cache_ttl_tts_seconds: int = 604800  # 7d
result_cache_ttl_video_seconds: int = 2592000  # 30d
result_cache_refund_on_hit: bool = True  # Refund credits on cache hit
result_cache_dedup_enabled: bool = True

# WebSocket (Task 10)
websocket_enabled: bool = True
websocket_heartbeat_interval_seconds: int = 30
websocket_heartbeat_timeout_seconds: int = 10
websocket_max_connections: int = 1000
websocket_backpressure_limit: int = 100

# HTTP/2 + image optimization (Task 11)
http_client_http2_enabled: bool = True
http_client_max_keepalive: int = 20
http_client_max_connections: int = 50
http_client_keepalive_expiry: float = 30.0
image_format: str = "webp"  # webp | png | both
image_webp_quality: int = 85
image_thumbnail_size: int = 300
image_thumbnail_quality: int = 75
image_keep_original: bool = True  # Keep PNG when generating WebP
ffmpeg_parallel_frame_downloads: int = 8

# SSE stream (Task 12)
sse_stream_enabled: bool = True

# CDN (Task 13)
cdn_provider: str = "none"  # none | r2 | qiniu | s3 | minio
cdn_base_url: str = ""  # e.g., https://cdn.comicstudio.ai
cdn_r2_account_id: str = ""
cdn_r2_access_key: str = ""
cdn_r2_secret_key: str = ""
cdn_r2_bucket: str = "comicstudio-assets"
cdn_qiniu_access_key: str = ""
cdn_qiniu_secret_key: str = ""
cdn_qiniu_bucket: str = ""
cdn_qiniu_domain: str = ""  # e.g., https://cdn.comicstudio.ai
cdn_s3_endpoint: str = ""  # for MinIO or other S3-compatible
cdn_s3_access_key: str = ""
cdn_s3_secret_key: str = ""
cdn_s3_bucket: str = ""
cdn_s3_region: str = "us-east-1"

# Provider failover (Task 13)
provider_failover_enabled: bool = True
provider_max_retries: int = 3
provider_circuit_breaker_threshold: int = 5
provider_circuit_breaker_reset_seconds: int = 60
provider_retry_backoff_seconds: float = 1.0  # exponential base

# Backup (Task 14)
backup_enabled: bool = True  # Production only
backup_local_dir: str = "/backups"
backup_cdn_bucket: str = "comicstudio-backups"  # R2 bucket for offsite backups
backup_retention_daily: int = 30
backup_retention_weekly: int = 12
backup_retention_monthly: int = 12
backup_encryption_key: str = ""  # AES-256 key for encrypting backups at rest

# Alerting (Task 14)
alertmanager_enabled: bool = True
alertmanager_webhook_feishu: str = ""  # Feishu bot webhook URL
alertmanager_webhook_dingtalk: str = ""  # DingTalk bot webhook URL
alertmanager_email_to: str = "ops@comicstudio.ai"
slo_target_uptime_monthly: float = 0.995  # 99.5%
slo_target_p99_latency_seconds: float = 5.0
slo_target_cache_hit_rate: float = 0.30

# Local AI inference (Task 15, desktop only)
local_inference_enabled: bool = False  # Auto-set True in desktop mode
local_inference_device: str = "auto"  # auto | cpu | cuda
local_model_dir: str = ""  # Empty = use OS default (~/.comicstudio/models or %APPDATA%/ComicStudio/models)
local_default_image_model: str = "stabilityai/sdxl-turbo"
local_default_image_model_cpu: str = "runwayml/stable-diffusion-v1-5"  # ONNX INT8
local_default_llm_model: str = "Qwen/Qwen2.5-7B-Instruct-GGUF"  # GPU
local_default_llm_model_cpu: str = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"  # CPU
local_default_tts_voice: str = "zh_CN-huayan-medium"
local_vram_limit_gb: int = 0  # 0 = auto-detect; positive = manual cap
local_enable_lora: bool = True
local_lora_dir: str = ""  # Empty = use OS default
local_inference_timeout_seconds: int = 60  # Kill local inference if exceeds
```

### 8.2 New Dependencies

**Cloud requirements.txt additions:**
```
cachetools==5.5.0          # In-memory TTL cache (Task 1)
prometheus-fastapi-instrumentator==7.0.0  # Metrics (Task 4)
sentry-sdk[fastapi]==2.10.0  # Error tracking (Task 4)
alembic==1.13.3            # Migrations (Task 6)
websockets==13.1           # WebSocket server (Task 10)
Pillow==11.0.0             # Image optimization (Task 11)
boto3==1.35.0              # CDN upload (Task 13) — S3-compatible API for R2/七牛/MinIO
qiniu==7.14.0              # CDN upload China alt (Task 13) — only if cdn_provider=qiniu
cryptography==43.0.0       # Backup encryption (Task 14) — AES-256
# httpx[http2]==0.27+ (already installed, just enable http2=True)
# h2==4.1.0 (transitive via httpx[http2], required for HTTP/2)
```

**Desktop requirements.txt additions (Task 15-16, separate file):**
```
# Local AI inference — GPU variant
torch==2.4.0               # GPU inference (CUDA 12.1)
torchvision==0.19.0
diffusers==0.30.0          # HuggingFace diffusers
transformers==4.44.0       # CLIP, Qwen
xformers==0.0.27           # Memory-efficient attention (GPU only)
accelerate==0.34.0         # Device management
huggingface_hub==0.25.0    # Model download
llama_cpp_python==0.3.0    # Local LLM (Qwen GGUF)
piper-tts==1.2.0           # Offline TTS

# Local AI inference — CPU variant (replaces GPU variant in CPU installer)
onnxruntime==1.19.0        # CPU inference (no torch dependency)
# diffusers/transformers/huggingface_hub/llama_cpp_python/piper-tts shared with GPU variant
```

All cloud deps are pure-Python or have C extensions pre-built for Windows/Linux/macOS. Desktop deps include native binaries (PyTorch wheels ship CUDA runtime; ONNX Runtime ships native libs). No user-side compilation required.

---

## 9. Risk Analysis

### 9.1 High-Risk Areas

1. **Alembic initial migration** — must exactly match current `create_all` output. **Mitigation**: Test migration on fresh DB, compare schema with `create_all` output.
2. **JWT shortening** — existing clients with 24h tokens will need refresh logic. **Mitigation**: Document migration in deployment guide; existing tokens remain valid until natural expiry, giving clients a graceful window to adopt refresh logic.
3. **Task 2 background task recovery** — interrupted tasks on restart. **Mitigation**: Mark as `failed` with reason, log clearly, allow user to resubmit.
4. **N+1 fix in BaseService** — changing `list()` signature could break subclasses. **Mitigation**: `eager_load` param is optional with default `None` (no change to default behavior).
5. **Result cache key collisions** — if two distinct inputs hash to same key, wrong cached result returned. **Mitigation**: Use SHA256 (collision-resistant); include all deterministic params; integration test with edge cases (negative prompts, sampler changes).
6. **Result cache storage growth** — unbounded cache could fill disk. **Mitigation**: LRU eviction at `result_cache_max_entries` (10k); also enforce max total size (sum of `size_bytes`) — if > 50GB, evict oldest.
7. **WebSocket connection leak** — abandoned connections exhaust `websocket_max_connections`. **Mitigation**: Heartbeat timeout (10s no pong → close); cleanup on disconnect in `finally` block; periodic sweep for stale connections.
8. **HTTP/2 + Pollinations compatibility** — some servers advertise HTTP/2 but fail mid-stream. **Mitigation**: Auto-fallback to HTTP/1.1 on `http2.UnsupportedProtocol`; configurable via `http_client_http2_enabled`.

### 9.2 Medium-Risk Areas

1. **Redis cache fallback** — if Redis goes down mid-request, must not crash. **Mitigation**: All Redis operations wrapped in try/except, fall back to memory.
2. **Concurrency semaphore deadlock** — if engine call holds slot and waits for another slot. **Mitigation**: Single-slot acquisition per request; no nested acquisitions.
3. **Gzip + ETag interaction** — ETag must be computed on uncompressed body. **Mitigation**: ETag middleware runs before Gzip in chain.
4. **In-flight dedup Future leak** — if caller cancels mid-request, future must resolve for other waiters. **Mitigation**: `asyncio.Future` callbacks handle cancellation; result cached regardless of original caller's state.
5. **WebP support in old Electron versions** — WebP needs Electron ≥3.0. **Mitigation**: Phase 4 already uses recent Electron (≥30), so safe.
6. **SSE stream + credit refund race** — if client disconnects mid-stream, partial refund logic could double-refund. **Mitigation**: Track token count at refund time; refund only if `tokens_received == 0`.
7. **WebSocket backpressure under high event rate** — fast video render (60fps progress events) could flood slow clients. **Mitigation**: Throttle progress events to 5/sec max; drop intermediate frames in queue if > backpressure_limit.
8. **CDN cost overage** — viral content could exceed R2/七牛 free tier. **Mitigation**: Cloudflare R2 has no egress fees (only storage + ops); 七牛 1GB/day egress cap auto-throttles; alert on `cdn_storage_bytes > 8GB` (80% of 10GB free tier).
9. **Provider failover masks root cause** — secondary always returns degraded results, users may not realize primary is down. **Mitigation**: `X-Provider: fallback` response header; admin alert on circuit open; Grafana dashboard shows fallback rate.
10. **Backup encryption key loss** — losing AES key means backups are unrecoverable. **Mitigation**: Key stored in env var + sealed copy in password manager + printed offline copy in safe; documented in runbook.
11. **Alert fatigue** — too many alerts lead to ignored critical ones. **Mitigation**: Alert routing groups by severity; warning alerts silenced between 23:00-07:00 (configurable); critical alerts always fire.
12. **Local inference model download size** — 10GB initial download may deter users. **Mitigation**: First-launch wizard explains benefit; CPU-only installer (600MB) for low-bandwidth users; models can be downloaded later; remote API still works without download.
13. **GPU driver incompatibility** — old NVIDIA drivers may not support CUDA 12.1. **Mitigation**: Detect driver version on startup; fallback to CPU ONNX if CUDA init fails; document minimum driver versions in install guide.
14. **PyInstaller + torch native lib bundling** — torch has many native DLLs (.pyd files) that PyInstaller may miss. **Mitigation**: Custom PyInstaller hooks for torch/onnxruntime; test on clean Windows install; ship Visual C++ Redistributable installer alongside.
15. **Model file corruption** — interrupted download may leave partial model file. **Mitigation**: HuggingFace `snapshot_download` uses atomic rename; verify SHA256 after download; re-download on corruption.
16. **VRAM exhaustion on low-end GPUs** — 4GB VRAM GPUs cannot run SDXL. **Mitigation**: `LocalRuntimeDetector` checks VRAM; SDXL requires ≥6GB; SD 1.5 fallback for 4GB GPUs; `enable_sequential_cpu_offload()` for borderline cases.

---

## 10. Success Criteria

Phase 7 is complete when:

1. ✅ All 504+ tests pass (338 existing + 166 new across 16 tasks)
2. ✅ Cloud production mode (`APP_ENV=production`) boots, `/ready` returns 200, `/metrics` exposes Prometheus format
3. ✅ Desktop app (all 4 installer variants) installs and boots without errors on clean Windows/Linux
4. ✅ Docker compose up brings up full stack (backend + frontend + nginx + redis + postgres + prometheus + grafana + alertmanager), all healthchecks pass
5. ✅ GitHub Actions CI runs green on push (matrix: [win, linux] × [gpu, cpu] + cloud)
6. ✅ **Cloud cache hit p99 latency on `/api/v1/ai/text2img` ≤50ms** (beats ComfyUI local GPU)
7. ✅ **Cloud cache miss p99 latency on `/api/v1/ai/text2img` ≤5s** (matches 即梦)
8. ✅ **Desktop local GPU p99 latency on text2img ≤3s** (matches ComfyUI local GPU)
9. ✅ **Desktop local CPU p99 latency on text2img ≤15s** (works offline, no API dependency)
10. ✅ p99 latency on `/api/v1/billing/balance` ≤50ms (metadata cached)
11. ✅ Background video compose returns 202 in <500ms, progress pushed via WebSocket at <100ms latency (cloud) / <5ms (desktop)
12. ✅ WebSocket `/ws` connection accepts JWT auth, pushes `task.progress` events at <100ms latency (cloud) / <5ms (desktop)
13. ✅ `/api/v1/ai/chat?stream=true` returns SSE stream, first token in <500ms (cloud) / <300ms (desktop local LLM)
14. ✅ WebP image size ≥30% smaller than PNG equivalent (measured on 10 sample images)
15. ✅ FFmpeg frame download 4x+ faster for 30-frame videos (parallel vs serial)
16. ✅ HTTP/2 enabled on all external AI API calls (verified via httpx info log)
17. ✅ Alembic `alembic upgrade head` produces identical schema to `create_all`
18. ✅ No regression: all Phase 1-6 user flows work unchanged (338 tests still pass)
19. ✅ Cloud cache hit rate ≥30% after 1 hour of typical usage
20. ✅ CDN upload succeeds for AI-generated assets; response `url` points to CDN URL when `cdn_provider != none`
21. ✅ Provider failover: simulated primary failure → circuit breaker opens → secondary/degraded mode returns result within 5s
22. ✅ Backup job runs successfully end-to-end (pg_dump + uploads tar + Redis BGSAVE); restore drill passes on staging
23. ✅ Prometheus alert rules validated (`promtool check rules alerts.yml` passes); Alertmanager delivers test alert to Feishu webhook
24. ✅ SLA report endpoint `/api/v1/admin/ops/sla` returns SLO compliance metrics for last 24h
25. ✅ Monthly uptime SLO ≥99.5% measured via `/health` external probe (UptimeRobot free tier)
26. ✅ Desktop three-tier fallback verified: local GPU → local CPU → remote API (each transition tested with simulated failures)
27. ✅ Desktop first-launch wizard detects GPU correctly; model download succeeds for default package
28. ✅ Desktop model manager UI: browse/download/activate/delete models; LoRA loading works
29. ✅ All 4 desktop installer variants build successfully: win-gpu (~2.5GB), win-cpu (~600MB), linux-gpu, linux-cpu

---

## 11. Open Questions (Resolved During Planning)

These will be finalized in the writing-plans phase:

1. **Cache key for `BillingService.get_balance`** — should it be per-user (`balance:{user_id}`) or per-user-per-minute (`balance:{user_id}:{minute}`)? → **Decision: per-user, TTL=30s, invalidate on deduct/recharge/refund**
2. **Task 2 task recovery on boot** — should `pending` tasks auto-resume or require user action? → **Decision: auto-mark as `failed` with reason "interrupted"; user must resubmit** (simpler, safer)
3. **ETag scope** — all GET endpoints or only specific ones? → **Decision: all GET endpoints; opt-out via `@no_etag` decorator if needed**
4. **Refresh token storage** — DB-backed blacklist or JWT-based stateless? → **Decision: DB-backed `RevokedToken` table for explicit invalidation; needed for security**
5. **Result cache credit policy** — should cache hits be free or charge credits? → **Decision: free by default (`result_cache_refund_on_hit=True`); admin can disable for monetization**
6. **Cache key scope for image** — include sampler/steps or not? → **Decision: include all params that affect output (prompt, negative_prompt, seed, width, height, model, sampler, steps, cfg_scale)**; even a step count change should miss
7. **WebSocket vs SSE for video progress** — WS only, or also expose SSE fallback? → **Decision: WS primary; SSE fallback at `/api/v1/tasks/{id}/events` for clients without WS support (proxy/gateway restrictions)**
8. **In-flight dedup cancellation** — if first caller cancels, should waiters be cancelled too? → **Decision: no, waiters continue; only the API call is shared, cancellation is per-client**
9. **WebP for character consistency (soft_provider)** — also optimize? → **Decision: yes, all image output paths go through ImageOptimizer uniformly**
10. **SSE stream + Gzip middleware interaction** — gzip might buffer SSE chunks. → **Decision: SSE responses bypass Gzip middleware (content-type `text/event-stream` exclusion)**

---

## 12. Out of Scope (Deferred to Phase 8+)

- Kubernetes Helm charts (Docker Compose with Nginx reverse proxy is sufficient for v1)
- Multi-region deployment (single-region with CDN edge caching is sufficient for v1)
- GraphQL API
- AMD ROCm / Intel OpenVINO / Apple MPS support (Phase 7 desktop supports NVIDIA CUDA + CPU only)
- AI model fine-tuning / LoRA training UI (users can load existing LoRA files but cannot train in-app)
- Mobile apps (iOS/Android)
- SSO / OAuth2 integration
- Webhook system for third-party integrations
- Advanced analytics dashboard (Phase 7 includes basic Grafana dashboards; advanced cohort/funnel analysis deferred)
- Vector-similarity prompt cache (semantic "similar prompt" reuse) — Phase 7 uses exact hash only
- Image super-resolution / upscaling pipeline
- Database read replica + write master split (Phase 8 scale-out)
- A/B testing framework
- Multi-currency billing (Phase 7 keeps CNY-only)

---

## 13. Implementation Order

Tasks are ordered to minimize dependencies. The 16 tasks span 4 categories: performance, observability, database/API, commercial ops + local inference.

1. **Task 1 (Metadata Cache)** — no deps; foundational
2. **Task 4 (Observability)** — no deps; foundational (used by all subsequent for metrics)
3. **Task 5 (Health)** — depends on Task 4 (metrics)
4. **Task 3 (Concurrency)** — depends on Task 4 (metrics)
5. **Task 11 (HTTP/2 + Image Opt)** — depends on Task 4 (metrics for cache hit/miss); standalone otherwise
6. **Task 9 (Result Cache + Dedup)** — depends on Task 1 (reuses CacheService for metadata layer) + Task 11 (image storage layout)
7. **Task 2 (Async Tasks)** — depends on Task 3 (semaphore for engine calls) + Task 9 (cache check before task submission)
8. **Task 10 (WebSocket)** — depends on Task 2 (pushes task progress events) + Task 4 (metrics)
9. **Task 6 (Migrations)** — no deps; can be parallel (must include `result_cache_entries`, `background_tasks`, `revoked_tokens`, `local_models` tables)
10. **Task 7 (API Production)** — depends on Task 6 (RevokedToken table) + Task 11 (image response schema changes)
11. **Task 12 (SSE Stream)** — depends on Task 7 (Gzip middleware exclusion for `text/event-stream`)
12. **Task 13 (CDN + Provider Failover)** — depends on Task 11 (storage layer) + Task 4 (metrics for circuit breaker)
13. **Task 14 (Backup + Alerting + SLA)** — depends on Task 4 (metrics) + Task 13 (CDN bucket for offsite backups)
14. **Task 15 (Local AI Inference Engine)** — depends on Task 10 (WebSocket for download/inference progress) + Task 4 (metrics); standalone otherwise
15. **Task 16 (Desktop Installer + Runtime)** — depends on Task 15 (bundles local inference code) + Task 8 partial (PyInstaller spec)
16. **Task 8 (CI/CD)** — depends on all (validates full stack, builds all installer variants)

Total: 16 Tasks, ~166 new tests, target 504 passing.

**Critical path:** Task 1 → Task 4 → Task 11 → Task 9 → Task 2 → Task 10 → Task 15 → Task 16 → Task 8 (9 tasks on critical path for desktop path); Task 1 → Task 4 → Task 11 → Task 9 → Task 2 → Task 10 → Task 6 → Task 7 → Task 12 → Task 13 → Task 14 → Task 8 (12 tasks on critical path for cloud path)

**Parallel opportunities:**
- Task 5 + Task 3 + Task 11 can run in parallel after Task 4
- Task 6 (migrations) can run in parallel with Tasks 9/10/12
- Task 13 (CDN+failover) can run in parallel with Task 7/12 after Task 11
- Task 15 (local inference) can run in parallel with Task 6/7/12/13/14 after Task 10 (independent codebase)
- Task 14 (backup/alerting) can run in parallel with Task 15/16 (independent)

---

**End of Spec.**
