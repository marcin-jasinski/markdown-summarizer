# Production Readiness Report

**Date**: 2026-04-23
**Path**: `d:\Dokumenty\Projekty\mindforge` (Dockerfile, compose.yml, env.example, scripts/STARTUP_GUIDE.md)
**Target**: production
**Status**: Not Ready

---

## Executive Summary

| Field | Value |
|---|---|
| **Recommendation** | **NO-GO** |
| **Overall Readiness** | 59% |
| **Deployment Risk** | High |
| **Blockers** | 5 |
| **Concerns** | 10 |
| **Recommendations** | 5 |

The implementation is well-structured — config validation, graceful shutdown, health endpoints, and migrations are all solid. However five blockers must be resolved before a production deploy: the container runs as root, core services have no restart policies, the JWT_SECRET startup guard only warns (not fails) when the insecure default is present, three image tags are unpinned (`latest`), and no application-level error tracking is wired.

---

## Category Breakdown

| Category | Score | Status |
|---|---|---|
| Configuration | 75% | ⚠️ Needs work |
| Monitoring | 45% | ❌ Failing |
| Resilience | 50% | ❌ Failing |
| Performance | 82% | ✅ Passing |
| Security | 42% | ❌ Failing |
| Deployment | 68% | ⚠️ Needs work |

---

## Blockers (Must Fix)

### B1 — Dockerfile runs as root
**Location**: `Dockerfile` — Stage 2 (Python runtime)
**Issue**: No `USER` instruction is present. The container process runs as UID 0 (root), maximising blast radius on container escape.
**Fix**:
```dockerfile
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser
```
Add these two lines after `RUN pip install ...` and before `COPY --from=builder`.
**Fixable**: ✅

---

### B2 — No restart policies on core services
**Location**: `compose.yml` — `postgres`, `neo4j`, `redis`, `minio`, `api`, `quiz-agent`
**Issue**: All six services have no `restart:` key. A transient OOM, driver crash, or node reboot leaves the stack permanently down until a human intervenes. The three bot stubs correctly use `restart: "no"` because they intentionally exit; all persistent services must survive crashes.
**Fix**: Add `restart: unless-stopped` (or `always`) to `postgres`, `neo4j`, `redis`, `minio`, `api`, and `quiz-agent`. Example:
```yaml
api:
  restart: unless-stopped
```
**Fixable**: ✅

---

### B3 — JWT_SECRET startup guard only warns when default is used
**Location**: `mindforge/infrastructure/config.py` → `validate_settings()`
**Issue**: The validation block:
```python
if settings.jwt_secret == _DEFAULT_JWT_SECRET:
    if settings.auth_secure_cookies:
        errors.append("...")   # hard error only here
    else:
        log.warning("...")     # soft warning — app starts fine
```
Because `auth_secure_cookies=False` by default, the application starts successfully with the well-known default key `"change-me-in-production"`. Any attacker can forge arbitrary JWT tokens.
**Fix**: Always raise a hard error when `jwt_secret == _DEFAULT_JWT_SECRET`, regardless of `auth_secure_cookies`. The soft path should be removed:
```python
if settings.jwt_secret == _DEFAULT_JWT_SECRET:
    errors.append(
        "JWT_SECRET is set to the default placeholder value. "
        "Generate a strong secret: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
```
**Fixable**: ✅

---

### B4 — Unpinned `latest` image tags
**Location**: `compose.yml`
**Issue**: Three images use floating `latest` tags:
- `minio/minio:latest` (line ~49)
- `minio/mc:latest` (line ~63)
- `clickhouse/clickhouse-server:latest` (line ~141)

Unpinned tags pull a different image on each `docker compose pull`, making builds non-reproducible and introducing silent breaking changes.
**Fix**: Pin to specific digests or at minimum named stable releases, e.g.:
```yaml
minio/minio:RELEASE.2024-11-07T00-52-20Z
minio/mc:RELEASE.2024-11-17T19-35-25Z
clickhouse/clickhouse-server:24.10
```
Also consider pinning `neo4j:5` to `neo4j:5.24` for the same reason (current tag floats across minor releases).
**Fixable**: ✅

---

### B5 — No application-level error tracking
**Location**: codebase-wide; `mindforge/api/main.py`
**Issue**: Langfuse provides LLM-call tracing, but there is no integration for application errors (unhandled exceptions, 5xx responses, infrastructure failures). Silent failures in the pipeline or API will not surface until a user reports them. Per the production-readiness rubric, error tracking is a required blocker.
**Fix**: Integrate Sentry (or equivalent). Minimum viable wiring in `create_app()`:
```python
import sentry_sdk
sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
```
Add `SENTRY_DSN` to `env.example` and `AppSettings`. Wrap the lifespan startup path to capture initialisation failures.
**Fixable**: ✅

---

## Concerns (Should Fix)

### C1 — `auth_secure_cookies=False` default
**Location**: `mindforge/infrastructure/config.py`, `env.example`
**Issue**: Cookies are issued without the `Secure` flag by default. In production over HTTPS, session cookies are transmitted in plaintext if this flag is not explicitly flipped.
**Fix**: Document in `env.example` and `STARTUP_GUIDE.md` as a mandatory production override. Consider having `validate_settings()` warn more prominently (or error) when `auth_secure_cookies=False` and the server is not clearly running behind a TLS terminator.

---

### C2 — No security response headers
**Location**: `mindforge/api/middleware.py` — `add_middleware()`
**Issue**: No `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, or `Content-Security-Policy` headers are emitted. Without these, browsers have no defence against clickjacking, MIME-sniffing, or protocol downgrade.
**Fix**: Add a `SecurityHeadersMiddleware` (or use `starlette-exceptionhandlers` / custom middleware) that injects at minimum:
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```
`Strict-Transport-Security` and `Content-Security-Policy` should be added once TLS termination is confirmed.

---

### C3 — Broad CORS configuration
**Location**: `mindforge/api/middleware.py` — `add_middleware()`
**Issue**: `allow_methods=["*"]` and `allow_headers=["*"]` are used. While the origin list is correctly restricted (default `localhost:4200`), method and header wildcards grant more permission than needed and must be narrowed before production.
**Fix**: Restrict to the actual methods and headers the API uses:
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
```

---

### C4 — Weak default passwords with no mandatory-change enforcement
**Location**: `compose.yml`
**Issue**: The following secrets default to known weak values:
- `POSTGRES_PASSWORD:-secret`
- `NEO4J_PASSWORD:-secret`
- `MINIO_ACCESS_KEY:-minioadmin` / `MINIO_SECRET_KEY:-minioadmin`
- `LANGFUSE_DB_PASSWORD:-langfuse`

These defaults are documented as dev-only, but there is no runtime guard that prevents a production deployment from using them.
**Fix**: Add `validate_settings()` checks (or compose-level required-variable assertions) that reject known placeholder values when `AUTH_SECURE_COOKIES=true` (as a proxy for "production mode").

---

### C5 — Internal database ports exposed on host
**Location**: `compose.yml` — `neo4j` (7474, 7687), `minio` (9000, 9001)
**Issue**: Neo4j Bolt and Browser, MinIO S3 and Console are bound to `0.0.0.0` on the host. In a cloud VM these ports are reachable from the public internet unless a firewall rule blocks them, bypassing application-layer authentication.
**Fix**: For production, bind to `127.0.0.1` or remove host port mappings entirely and access via the Docker network only:
```yaml
ports:
  - "127.0.0.1:7474:7474"
  - "127.0.0.1:7687:7687"
```

---

### C6 — No network isolation between services
**Location**: `compose.yml`
**Issue**: All services share the default `mindforge` bridge network. Any compromised container can reach any other service (database, Neo4j, MinIO) without restriction.
**Fix**: Define named networks with explicit attachment:
```yaml
networks:
  backend:
  observability:
```
Attach `api`, `postgres`, `neo4j`, `redis`, `minio` to `backend`; Langfuse services to `observability`. This limits lateral movement.

---

### C7 — `build-essential` present in production runtime image
**Location**: `Dockerfile` — Stage 2
**Issue**: `build-essential` is installed to compile Python C extensions (`libpq-dev` requires it) but is retained in the final image, increasing the image size and providing compilers that could aid post-exploitation.
**Fix**: Use a two-step approach — install build tools, compile, then remove them:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq-dev build-essential \
    && pip install --no-cache-dir -e . \
    && apt-get purge -y build-essential \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
```

---

### C8 — No structured (JSON) logging
**Location**: All modules use `logging.getLogger(__name__)` with default text formatter
**Issue**: Log aggregation systems (ELK, Datadog, CloudWatch) parse JSON logs far more reliably than freeform text. Request IDs (`X-Request-ID`) are attached to the request state but never emitted as a log field.
**Fix**: Configure a JSON formatter at application startup (e.g. `python-json-logger`) and inject `request_id` into the log context via `contextvars`.

---

### C9 — No metrics instrumentation
**Location**: codebase-wide
**Issue**: No Prometheus or equivalent metrics are emitted. There is no visibility into request latency, pipeline queue depth, or DB connection pool exhaustion until errors occur.
**Fix**: Add `prometheus-fastapi-instrumentator` or equivalent. Expose `/metrics` on a non-public port. At minimum track: HTTP request duration/count, pipeline task queue depth, LLM call latency.

---

### C10 — No rollback runbook documented
**Location**: `scripts/STARTUP_GUIDE.md`
**Issue**: The guide covers startup modes comprehensively but does not document what to do if a deployment fails mid-migration or a release must be reverted. Down migrations exist in all three migration files, but no operator runbook describes the rollback steps.
**Fix**: Add a "Rollback" section to `STARTUP_GUIDE.md` covering:
1. How to run `alembic downgrade -1`
2. How to revert the Docker image tag
3. How to verify the rollback is complete

---

## Recommendations (Nice to Have)

### R1 — Pin `node:20-alpine` and `python:3.12-slim` to patch versions
**Location**: `Dockerfile`
Use `node:20.18-alpine3.20` and `python:3.12.7-slim` (or equivalent current patch) for fully reproducible builds.

### R2 — Explicit SQLAlchemy pool size configuration
**Location**: `mindforge/infrastructure/db.py`
`create_async_engine` is called without explicit `pool_size` or `max_overflow`. Under high concurrency, the default pool (5 + 10 overflow) may be too small. Add `pool_size` and `max_overflow` from `AppSettings`.

### R3 — Separate production compose file
The current `compose.yml` serves double duty as dev and production config (port bindings, no restart policies, weak defaults). Consider a `compose.prod.yml` override that tightens restart policies, removes host port bindings for internal services, and enforces secrets.

### R4 — Circuit breaker for external AI calls
`LiteLLMGateway` already has retries (`max_retries=3`). Adding a circuit breaker (e.g. via `tenacity` `CircuitBreaker`) would prevent cascading failures when an upstream provider is down.

### R5 — Dependency vulnerability scan in CI
Add `pip-audit` and `npm audit` to CI. Currently there is no automated check for known CVEs in the dependency tree.

---

## Detailed Assessment by Area

### Healthchecks ✅
All stateful services define healthchecks with reasonable intervals:
- `postgres`: `pg_isready` every 5 s — good
- `neo4j`: HTTP probe every 10 s with 30 s start_period — good
- `redis`: `redis-cli ping` every 5 s — good
- `minio`: `/minio/health/live` every 10 s — good
- `api`: `/api/health` every 10 s with 60 s start_period — good
- `langfuse`: `/api/public/health` every 15 s — good

The `/api/health` endpoint itself checks DB, Neo4j, and Redis connectivity — solid dependency health propagation.

### Restart Policies ❌
`postgres`, `neo4j`, `redis`, `minio`, `api`, and `quiz-agent` all lack `restart:` keys. This is blocker B2.

### Secret Handling ⚠️
Secrets are properly externalized via env vars. `env.example` is thorough and documents every variable. The weak default password problem (C4) is dev-convenience, not a code defect, but the JWT_SECRET guard weakness (B3) is a genuine code fix.

### Resource Limits ℹ️
No CPU or memory limits are set — noted per the assessment criteria as acceptable for a dev compose file. For production, limits should be added to prevent a single service from starving others.

### Non-Root User ❌
Dockerfile runs as root. See blocker B1.

### Image Pinning ⚠️
`postgres:17-alpine`, `neo4j:5`, `redis:7-alpine`, `python:3.12-slim`, `node:20-alpine`, `langfuse/langfuse:3` are all reasonably versioned (though not patch-pinned). `minio/minio:latest`, `minio/mc:latest`, and `clickhouse/clickhouse-server:latest` are unpinned — see blocker B4.

### Data Persistence ✅
All stateful services use named volumes:
- `postgres_data`, `neo4j_data`, `neo4j_logs`, `redis_data`, `minio_data`, `langfuse_db_data`, `clickhouse_data` — all declared in the `volumes:` section.

### Network Isolation ⚠️
Single shared bridge network — see concern C6.

---

## Next Steps (Prioritised)

| Priority | Action | Effort |
|---|---|---|
| 1 | **B1**: Add non-root USER to Dockerfile | 5 min |
| 2 | **B2**: Add `restart: unless-stopped` to 6 services in compose.yml | 5 min |
| 3 | **B3**: Change JWT_SECRET guard to always error on default value | 10 min |
| 4 | **B4**: Pin minio/minio, minio/mc, clickhouse image tags | 10 min |
| 5 | **C2**: Add security headers middleware | 30 min |
| 6 | **C3**: Narrow CORS allow_methods and allow_headers | 10 min |
| 7 | **C5**: Bind internal ports to 127.0.0.1 | 10 min |
| 8 | **B5**: Integrate Sentry (or OSS equivalent like GlitchTip) | 2–4 h |
| 9 | **C8**: Add JSON logging with request_id propagation | 1–2 h |
| 10 | **C10**: Add rollback runbook to STARTUP_GUIDE.md | 30 min |
