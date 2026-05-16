# Production Readiness Report

**Date**: 2026-04-28
**Path**: `d:\Dokumenty\Projekty\mindforge`
**Target**: production
**Status**: Not Ready

---

## Executive Summary

| Field | Value |
|---|---|
| **Recommendation** | **NO-GO** |
| **Overall Readiness** | 68% (+9 pp since 2026-04-23) |
| **Deployment Risk** | High |
| **Blockers** | 3 |
| **Concerns** | 11 |
| **Recommendations** | 5 |

This is an updated assessment following the 2026-04-23 report. Five of the original blockers were resolved (non-root Docker user, restart policies, circuit breaker, explicit connection pool, partial image pinning). Three blockers remain and must be fixed before a production deploy:

1. **JWT_SECRET default guard is still a soft warning** — the application starts with the well-known insecure default when `AUTH_SECURE_COOKIES=false`.
2. **Two unpinned `latest` image tags** — `minio/minio:latest` and `minio/mc:latest`.
3. **No application-level error tracking** — unhandled exceptions and 5xx errors produce no alert; silent failures surface only when users report them.

The core architecture is solid: hexagonal layering is respected, graceful shutdown works end-to-end, migrations have full downgrade paths, health checks are comprehensive, and the AI gateway has a circuit breaker with retry/backoff. With the three blockers resolved, this project could reach GO with mitigations on the concerns.

---

## Category Breakdown

| Category | Score | Delta | Status |
|---|---|---|---|
| Configuration | 72% | +0 pp | ⚠️ Needs work |
| Monitoring | 55% | +10 pp | ❌ Failing |
| Resilience | 70% | +20 pp | ⚠️ Needs work |
| Performance | 85% | +3 pp | ✅ Passing |
| Security | 52% | +10 pp | ❌ Failing |
| Deployment | 72% | +4 pp | ⚠️ Needs work |

---

## What Was Fixed Since 2026-04-23

| Previous Blocker/Concern | Resolution |
|---|---|
| B1 — Dockerfile runs as root | ✅ Fixed: `useradd -r -m -s /bin/false appuser` + `USER appuser` added |
| B2 — No restart policies on core services | ✅ Fixed: `restart: unless-stopped` on postgres, neo4j, redis, minio, api, quiz-agent |
| B4 (partial) — ClickHouse unpinned `latest` | ✅ Fixed: `clickhouse/clickhouse-server:24.3` |
| R2 — Implicit SQLAlchemy pool defaults | ✅ Fixed: `pool_size=5, max_overflow=10, pool_recycle=3600, pool_pre_ping=True` |
| R4 — No circuit breaker for AI calls | ✅ Fixed: `_CircuitBreaker` in `LiteLLMGateway` (open after 5 failures, 60s cooldown) |
| Missing `git` in Dockerfile | ✅ Fixed: `git` now in `apt-get install` block |

---

## Blockers (Must Fix Before Deploy)

### B1 — JWT_SECRET default guard is a soft warning, not a hard error

**Location**: `mindforge/infrastructure/config.py` → `validate_settings()` (lines ~274–286)

**Issue**: The validation block contains:
```python
if jwt_secret == _DEFAULT_JWT_SECRET:
    if settings.auth_secure_cookies:
        errors.append("JWT_SECRET is set to the default placeholder value…")
    else:
        log.warning("JWT_SECRET is still the default placeholder…")
```
Because `AUTH_SECURE_COOKIES=false` by default, the application starts successfully with the well-known default `"change-me-in-production-min-32-bytes"`. Any attacker can forge arbitrary JWT tokens granting themselves full authenticated sessions.

**Fix**: Always raise a hard error when `jwt_secret == _DEFAULT_JWT_SECRET`, regardless of `auth_secure_cookies`. The soft branch must be removed:
```python
if jwt_secret == _DEFAULT_JWT_SECRET:
    errors.append(
        "JWT_SECRET is set to the default placeholder value. "
        "Generate a strong secret: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
```
**Fixable**: ✅ — 10-minute change in one function.

---

### B2 — Two MinIO image tags remain unpinned (`latest`)

**Location**: `compose.yml` — `minio` (line ~50) and `mc-init` (line ~63)

**Issue**: Both services still use `minio/minio:latest` and `minio/mc:latest` with a `# TODO: pin` comment. Unpinned tags pull a different image on each `docker compose pull`, making builds non-reproducible and introducing silent breaking changes.

**Fix**: Pin to named stable releases:
```yaml
minio/minio:RELEASE.2024-11-07T00-52-20Z
minio/mc:RELEASE.2024-11-17T19-35-25Z
```
Check [hub.docker.com/r/minio/minio/tags](https://hub.docker.com/r/minio/minio/tags) for the latest stable release at deploy time.

**Fixable**: ✅ — 5-minute change.

---

### B3 — No application-level error tracking

**Location**: codebase-wide; `mindforge/api/main.py`

**Issue**: Langfuse provides LLM-call tracing, but there is no integration for application errors (unhandled exceptions, 5xx responses, pipeline failures). The `_unhandled_exception_handler` and `register_exception_handlers` log to stdout, but logs are not aggregated or alerted. Silent failures in the pipeline or API will not surface until a user reports them. Per production-readiness standards, error tracking is a required blocker.

**Fix**: Integrate Sentry (or an OSS equivalent like GlitchTip). Minimum viable wiring in `lifespan` before `yield`:
```python
if settings.sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
```
Add to `AppSettings`:
```python
sentry_dsn: str | None = None
```
Add `SENTRY_DSN=` to `env.example`. Wrap the lifespan startup path so initialisation failures are also captured.

**Fixable**: ✅ — 2–4 hours including testing.

---

## Concerns (Should Fix Before or Shortly After Deploy)

### C1 — No security response headers

**Location**: `mindforge/api/middleware.py` → `add_middleware()`

**Issue**: No `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, or `Content-Security-Policy` headers are emitted. Without these, browsers have no defence against clickjacking, MIME-sniffing, or protocol downgrade.

**Fix**: Add a `SecurityHeadersMiddleware` that injects at minimum:
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```
Add `Strict-Transport-Security: max-age=31536000; includeSubDomains` once TLS termination is confirmed in production.

---

### C2 — CORS method and header wildcards

**Location**: `mindforge/api/middleware.py` → `add_middleware()` (line ~168)

**Issue**: `allow_methods=["*"]` and `allow_headers=["*"]` grant broader permission than needed. In production the Angular SPA is served from the same origin as the API, so CORS is mainly needed for dev mode or external API consumers, not the primary user flow.

**Additional gap**: `cors_origins` is never passed from `AppSettings`; `add_middleware(app)` is always called without the parameter, so the allowed origin is permanently `["http://localhost:4200"]` with no way to reconfigure it via environment variable for a different production domain.

**Fix**: Add a `cors_origins` setting to `AppSettings` and wire it through `create_app()`. Restrict methods and headers:
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
```

---

### C3 — `auth_secure_cookies=False` default

**Location**: `mindforge/infrastructure/config.py`, `env.example`

**Issue**: Cookies are issued without the `Secure` flag by default, meaning session cookies are transmitted in plaintext if a production operator forgets to set `AUTH_SECURE_COOKIES=true`. This is the expected dev default, but there is no validation guard to enforce it in production.

**Fix**: Add a `validate_settings()` check that logs a prominent warning (or errors) when `auth_secure_cookies=False` and the application is not clearly running in local mode (e.g., when `DATABASE_URL` does not contain `localhost`).

---

### C4 — Weak default passwords with no enforcement guard

**Location**: `compose.yml`

**Issue**: Default values `${POSTGRES_PASSWORD:-secret}`, `${NEO4J_PASSWORD:-secret}`, `${MINIO_ACCESS_KEY:-minioadmin}`, and `${MINIO_SECRET_KEY:-minioadmin}` are silently used when the corresponding env vars are absent. A production deployment with an incomplete `.env` runs with these well-known credentials.

**Fix**: Add `validate_settings()` checks that reject known placeholder values when `auth_secure_cookies=True`. Alternatively, document these as required overrides in a "Pre-production checklist" section of `STARTUP_GUIDE.md`.

---

### C5 — Internal database ports exposed on host `0.0.0.0`

**Location**: `compose.yml` — `neo4j` (ports `7474`, `7687`)

**Issue**: Neo4j Bolt and Browser are bound to `0.0.0.0` on the host. In a cloud VM, these ports are reachable from the public internet unless a firewall rule blocks them, bypassing application-layer authentication.

**Fix**: Bind to `127.0.0.1` or remove host port mappings for services that do not need external access:
```yaml
ports:
  - "127.0.0.1:7474:7474"
  - "127.0.0.1:7687:7687"
```
Similarly restrict `minio` ports `9000` and `9001` to `127.0.0.1` in production.

---

### C6 — No network isolation between services

**Location**: `compose.yml`

**Issue**: All services share the default `mindforge` bridge network. Any compromised container can reach any other service (PostgreSQL, Neo4j, MinIO, Redis) without restriction, maximising lateral movement blast radius.

**Fix**: Define named networks with explicit attachment:
```yaml
networks:
  backend:
  observability:
```
Attach `api`, `quiz-agent`, `postgres`, `neo4j`, `redis`, `minio` to `backend`; Langfuse services to `observability`.

---

### C7 — `build-essential` retained in production runtime image

**Location**: `Dockerfile` — Stage 2

**Issue**: `build-essential` is installed to compile Python C extensions but is never removed from the final image. This adds ~200 MB of compilers and development libraries to the runtime container, aiding post-exploitation if the container is compromised.

**Fix**: Purge the build toolchain after the `pip install` step:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential libpq-dev \
    && pip install --no-cache-dir -e . \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*
```

---

### C8 — No structured (JSON) logging

**Location**: `mindforge/api/main.py` → `_configure_app_logging()`

**Issue**: Log aggregation systems (ELK, Datadog, CloudWatch) parse JSON logs far more reliably than freeform text. The `X-Request-ID` is attached to `request.state` but never emitted as a log field, making it impossible to correlate all log lines for a single request.

**Fix**: Configure a JSON formatter at startup (`python-json-logger` or `structlog`) and inject `request_id` into the log context via `contextvars`. Replace the plain `Formatter` in `_configure_app_logging()`.

---

### C9 — No metrics instrumentation

**Location**: codebase-wide

**Issue**: No Prometheus or equivalent metrics are emitted. There is no visibility into request latency, pipeline queue depth, or DB connection pool exhaustion until errors occur.

**Fix**: Add `prometheus-fastapi-instrumentator` or equivalent. Expose `/metrics` on a non-public port or behind admin auth. At minimum track: HTTP request duration/count per endpoint, pipeline task queue depth, LLM call latency and error rate.

---

### C10 — No rollback runbook

**Location**: `scripts/STARTUP_GUIDE.md`

**Issue**: The guide covers startup modes comprehensively but has no section on what to do if a deployment fails mid-migration or a release must be reverted. All three migrations have `downgrade()` functions, but operators have no documented rollback procedure.

**Fix**: Add a "Rollback" section to `STARTUP_GUIDE.md` covering:
1. `docker compose pull <previous-tag>` to revert the image
2. `alembic downgrade -1` (or `-N`) inside the API container to revert the schema
3. Health verification steps post-rollback

---

### C11 — OpenAPI docs exposed without authentication in production

**Location**: `mindforge/api/main.py` → `create_app()` (lines ~345–352)

**Issue**: `/api/docs`, `/api/redoc`, and `/api/openapi.json` are always available without authentication. In production, the full API schema (endpoint names, parameter shapes, error responses) is exposed to unauthenticated users, providing an attack surface roadmap.

**Fix**: Set `docs_url=None, redoc_url=None, openapi_url=None` in the `FastAPI(...)` constructor for production builds, or gate them behind an `is_admin` middleware check. At minimum disable `openapi_url` in production.

---

## Recommendations (Nice to Have)

### R1 — Pin `node:20-alpine` and `python:3.12-slim` to patch versions
**Location**: `Dockerfile`
Use `node:20.18-alpine3.20` and `python:3.12.7-slim` for fully reproducible builds.

### R2 — Rate limiting beyond auth endpoints
**Location**: `mindforge/api/middleware.py`
The in-process token bucket applies only to `/api/auth`. Document upload (`/api/documents`) and pipeline trigger endpoints should also be rate-limited per user to prevent abuse. Consider adding a user-level rate limiter or delegating to a WAF/gateway.

### R3 — Separate production compose override
The current `compose.yml` serves double duty as dev and production config. A `compose.prod.yml` override that removes host port bindings for internal services, enforces secrets, and adds resource limits would reduce human error on production deploys.

### R4 — Dependency vulnerability scan in CI
Add `pip-audit` and `npm audit` to the CI pipeline (once GitHub Actions workflows are created). Currently there is no automated check for known CVEs in the dependency tree.

### R5 — Resource limits on containers
No CPU or memory limits are set on any service. Under high load, a single service can starve all others on the same host. Add `deploy.resources.limits` (Swarm/prod) or `mem_limit`/`cpus` (Compose) to at minimum `api`, `quiz-agent`, and `neo4j`.

---

## Detailed Assessment by Area

### Configuration ✅ / ⚠️
All settings load from environment via Pydantic `BaseSettings` with `SettingsConfigDict`. Cross-field validation runs once at startup via `validate_settings()`. `env.example` documents every variable with clear required/optional annotations. No `os.environ` reads at request time. **Gap**: `cors_origins` is not wired from settings; the JWT soft guard is a code defect; `AUTH_SECURE_COOKIES=false` default requires explicit production override.

### Health Checks ✅
All stateful services define healthchecks with reasonable intervals. The `/api/health` endpoint probes PostgreSQL, Neo4j (if enabled), and Redis (if enabled), returning an `"ok"` or `"degraded"` status. Service dependency chains ensure the API does not start before its dependencies are healthy.

### Graceful Shutdown ✅
The FastAPI `lifespan` context manager tears down all consumers, the outbox relay, Neo4j context, Redis client, and the DB engine in the correct order. The `PipelineWorker` handles `SIGTERM`/`SIGINT` and drains in-flight tasks (30s timeout). This is production-quality.

### Error Handling ✅ / ❌
Centralized exception handlers log 5xx errors with `request_id` and return sanitised error messages (Polish UX copy, no stack traces). Unhandled exceptions are caught and returned as HTTP 500. **Gap**: No external error tracking means failures are not alerted — they exist only in logs.

### Resilience ✅
Circuit breaker in `LiteLLMGateway` (opens after 5 consecutive failures, half-opens after 60s). Retry with exponential backoff + jitter on transient LLM errors. Respect for `Retry-After` headers from rate-limited providers. Redis/Neo4j optional with graceful feature degradation. Stale pipeline task recovery on worker restart.

### Connection Pooling ✅
Explicit `pool_size=5, max_overflow=10, pool_recycle=3600, pool_pre_ping=True` in `db.py`. Neo4j pool capped at 50 connections. Redis client from `aioredis` uses connection pooling by default.

### Rate Limiting ⚠️
In-process token bucket (20 req/min per IP) on `/api/auth` paths. No rate limiting on document upload, pipeline trigger, or semantic search endpoints. Middleware comment correctly notes this is not a substitute for a WAF in production.

### Security Hardening ⚠️
Strong positives: non-root Docker user, bcrypt (cost 12), JWT with HttpOnly cookies, OAuth CSRF state validation, upload sanitizer (path traversal, MIME type, size limits), SSRF protection (`EgressPolicy` with DNS IP pinning). Negatives: no security response headers, CORS wildcards, Neo4j ports on `0.0.0.0`, build-essential in runtime image, OpenAPI docs exposed, soft JWT default guard.

### Migrations ✅
Three Alembic migrations (`001_initial_schema`, `002_add_prompt_locale`, `003_add_user_is_admin`) all have `downgrade()` functions. An advisory lock (`pg_advisory_xact_lock`) prevents concurrent migration runs during horizontal scaling. Migrations run automatically on startup before the app starts serving traffic. Zero-downtime concern: the initial migration creates many tables in a single transaction — appropriate for a first deploy, but future large schema changes should use concurrent index creation.

### Restart Policies ✅
`postgres`, `neo4j`, `redis`, `minio`, `api`, and `quiz-agent` all have `restart: unless-stopped`. Bot stubs correctly use `restart: "no"`.

### Data Persistence ✅
Named volumes: `postgres_data`, `neo4j_data`, `neo4j_logs`, `redis_data`, `minio_data`, `langfuse_db_data`, `clickhouse_data` — all declared in the `volumes:` section.

### Continuous Integration ❌
No GitHub Actions workflows or equivalent CI pipelines exist. There are no automated gates for linting, type checking, test execution, dependency audits, or Docker image builds on push. This is the most significant long-term gap for production sustainability.

---

## Risk Assessment

| Risk | Likelihood | Impact | Severity |
|---|---|---|---|
| Default JWT secret used in prod (B1) | Medium | Critical | Critical |
| Unpinned MinIO image breaks deploy (B2) | Low | High | High |
| Silent pipeline failure undetected (B3) | High | Medium | High |
| Neo4j port exposed to internet (C5) | Medium | High | High |
| Auth cookie not Secure in prod (C3) | Medium | High | High |
| CORS misconfiguration blocking prod SPA | Medium | Medium | Medium |
| Container escapes to root after exploit (C7) | Low | High | Medium |

---

## Rollback Criteria

If any of the following occur during or after deployment, initiate rollback immediately:

1. `/api/health` returns `"degraded"` or HTTP 5xx for more than 60 seconds
2. Alembic migration fails or reports a version mismatch
3. Error rate on any endpoint exceeds 5% over a 5-minute window
4. JWT authentication failures spike (potential broken secret)
5. Database connection pool exhaustion events appear in logs

**Rollback procedure (once documented in STARTUP_GUIDE.md — see C10)**:
1. `docker compose pull api:previous-tag` or revert image reference
2. `docker compose up -d api quiz-agent` to restart with previous image
3. If migration must be reverted: `docker compose exec api alembic downgrade -1`
4. Verify `/api/health` returns `{"status": "ok"}` before declaring success

---

## Post-Deployment Verification Checklist

After deploying to production, verify each item within 15 minutes:

- [ ] `curl https://<host>/api/health` returns `{"status":"ok","database":"ok"}`
- [ ] Authenticated login flow works end-to-end (creates JWT cookie)
- [ ] Document upload completes and appears as `processing` in the task list
- [ ] Pipeline processes at least one document to `done` status
- [ ] Quiz generation returns questions for a processed document
- [ ] Redis `PING` returns `PONG` (from within the container)
- [ ] No unhandled exceptions in API logs in the first 5 minutes
- [ ] `JWT_SECRET` is confirmed NOT equal to the default placeholder (check startup log — `validate_settings` warning line)
- [ ] `AUTH_SECURE_COOKIES=true` is in the running container's environment
- [ ] Neo4j and MinIO ports are NOT reachable from the public internet (verify firewall)

---

## Next Steps (Prioritised)

| # | Action | Effort | Blocker/Concern |
|---|---|---|---|
| 1 | Change JWT_SECRET guard to always hard-error on default value | 10 min | B1 |
| 2 | Pin `minio/minio` and `minio/mc` to named stable releases | 5 min | B2 |
| 3 | Integrate Sentry or GlitchTip error tracking | 2–4 h | B3 |
| 4 | Add security headers middleware (X-Frame-Options, X-Content-Type-Options, Referrer-Policy) | 30 min | C1 |
| 5 | Narrow CORS allow_methods/allow_headers + add env-configurable CORS_ORIGINS | 20 min | C2 |
| 6 | Bind Neo4j and MinIO host ports to 127.0.0.1 | 10 min | C5 |
| 7 | Disable OpenAPI docs URL in production config | 10 min | C11 |
| 8 | Purge build-essential from final Dockerfile image | 15 min | C7 |
| 9 | Add rollback runbook to STARTUP_GUIDE.md | 30 min | C10 |
| 10 | Add JSON structured logging with request_id propagation | 1–2 h | C8 |
| 11 | Create GitHub Actions CI pipeline (lint, tests, pip-audit, npm audit) | 4–8 h | R4 |
| 12 | Add network isolation to compose.yml | 30 min | C6 |
| 13 | Add Prometheus metrics endpoint | 2–4 h | C9 |

---

## Structured Result

```yaml
status: "not_ready"
recommendation: "NO-GO"
report_path: "d:/Dokumenty/Projekty/mindforge/production-readiness-report.md"

overall_readiness: 68
deployment_risk: "high"

categories:
  configuration: { score: 72, status: "needs_work" }
  monitoring: { score: 55, status: "failing" }
  resilience: { score: 70, status: "needs_work" }
  performance: { score: 85, status: "passing" }
  security: { score: 52, status: "failing" }
  deployment: { score: 72, status: "needs_work" }

issues:
  - source: "production_readiness"
    severity: "critical"
    category: "security"
    description: "JWT_SECRET default guard is a soft warning — app starts with insecure default when AUTH_SECURE_COOKIES=false"
    location: "mindforge/infrastructure/config.py:validate_settings()"
    fixable: true
    suggestion: "Always raise hard error when jwt_secret == _DEFAULT_JWT_SECRET, remove soft branch"

  - source: "production_readiness"
    severity: "critical"
    category: "deployment"
    description: "minio/minio:latest and minio/mc:latest image tags are unpinned"
    location: "compose.yml lines ~50, ~63"
    fixable: true
    suggestion: "Pin to minio/minio:RELEASE.2024-11-07T00-52-20Z and minio/mc:RELEASE.2024-11-17T19-35-25Z"

  - source: "production_readiness"
    severity: "critical"
    category: "monitoring"
    description: "No application-level error tracking — unhandled exceptions produce no alerts"
    location: "codebase-wide"
    fixable: true
    suggestion: "Integrate Sentry or GlitchTip via sentry_sdk.init() in lifespan; add SENTRY_DSN to AppSettings"

  - source: "production_readiness"
    severity: "warning"
    category: "security"
    description: "No security response headers (X-Frame-Options, X-Content-Type-Options, HSTS, CSP)"
    location: "mindforge/api/middleware.py:add_middleware()"
    fixable: true
    suggestion: "Add SecurityHeadersMiddleware injecting X-Frame-Options: DENY and X-Content-Type-Options: nosniff at minimum"

  - source: "production_readiness"
    severity: "warning"
    category: "security"
    description: "CORS allow_methods=[*] and allow_headers=[*]; origins hardcoded to localhost:4200 with no env override"
    location: "mindforge/api/middleware.py lines ~168-170"
    fixable: true
    suggestion: "Restrict to explicit methods/headers; add CORS_ORIGINS env var wired through AppSettings"

  - source: "production_readiness"
    severity: "warning"
    category: "security"
    description: "auth_secure_cookies defaults to False; session cookies transmitted in plaintext if not overridden"
    location: "mindforge/infrastructure/config.py"
    fixable: true
    suggestion: "Add validate_settings() guard that warns (or errors) when auth_secure_cookies=False in non-local mode"

  - source: "production_readiness"
    severity: "warning"
    category: "security"
    description: "Neo4j ports 7474 and 7687 bound to 0.0.0.0 — reachable from internet without firewall"
    location: "compose.yml"
    fixable: true
    suggestion: "Change to 127.0.0.1:7474:7474 and 127.0.0.1:7687:7687"

  - source: "production_readiness"
    severity: "warning"
    category: "security"
    description: "No network isolation — all services share single bridge network"
    location: "compose.yml"
    fixable: true
    suggestion: "Define named backend/observability networks and attach services explicitly"

  - source: "production_readiness"
    severity: "warning"
    category: "security"
    description: "build-essential retained in production runtime image (~200 MB compilers)"
    location: "Dockerfile Stage 2"
    fixable: true
    suggestion: "Purge with apt-get purge -y --auto-remove build-essential after pip install"

  - source: "production_readiness"
    severity: "warning"
    category: "monitoring"
    description: "No structured JSON logging; request_id not propagated to log fields"
    location: "mindforge/api/main.py:_configure_app_logging()"
    fixable: true
    suggestion: "Use python-json-logger or structlog; inject request_id via contextvars"

  - source: "production_readiness"
    severity: "warning"
    category: "monitoring"
    description: "No Prometheus or equivalent metrics instrumentation"
    location: "codebase-wide"
    fixable: true
    suggestion: "Add prometheus-fastapi-instrumentator or equivalent; expose /metrics endpoint"

  - source: "production_readiness"
    severity: "warning"
    category: "deployment"
    description: "No rollback runbook in STARTUP_GUIDE.md"
    location: "scripts/STARTUP_GUIDE.md"
    fixable: true
    suggestion: "Add Rollback section covering alembic downgrade, image revert, and verification steps"

  - source: "production_readiness"
    severity: "warning"
    category: "security"
    description: "OpenAPI docs (/api/docs, /api/redoc, /api/openapi.json) exposed without authentication in production"
    location: "mindforge/api/main.py:create_app()"
    fixable: true
    suggestion: "Set docs_url=None, redoc_url=None, openapi_url=None in production or gate behind admin auth"

  - source: "production_readiness"
    severity: "info"
    category: "deployment"
    description: "No CI/CD pipeline — no automated tests, lint, or dependency audits on push"
    location: ".github/workflows/ (absent)"
    fixable: true
    suggestion: "Create GitHub Actions workflow with pytest, ruff, pyright, pip-audit, npm audit gates"

issue_counts:
  critical: 3
  warning: 10
  info: 1
```
