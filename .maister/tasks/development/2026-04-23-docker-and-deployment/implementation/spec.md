# Specification: Phase 13 — Docker and Deployment

## Goal

Package MindForge 2.0 as a single Docker image (FastAPI + Angular SPA) and orchestrate all
infrastructure services via `compose.yml` with three optional profiles, accompanied by a
comprehensive `scripts/STARTUP_GUIDE.md`.

---

## User Stories

- As a developer, I want to run `docker compose up` and have all core services start correctly,
  so I can develop against a realistic environment without manual setup.
- As a developer, I want to add `--profile observability` to enable Langfuse tracing, so I can
  debug AI agent performance in isolation.
- As an operator, I want health checks on every service, so I can confirm the stack is healthy
  before routing traffic.
- As a new contributor, I want a `STARTUP_GUIDE.md`, so I can get from zero to running locally
  (both venv and Docker) within minutes.

---

## Core Requirements

1. `Dockerfile` at repo root builds a single production image from two stages (Angular builder +
   Python runtime).
2. Angular SPA is served by FastAPI at the correct relative path (`/app/frontend/dist/`) so
   `mindforge/api/main.py`'s SPA mount resolves without code changes.
3. `compose.yml` at repo root defines all services across three profiles with healthchecks and
   correct startup ordering.
4. The `mc-init` init container idempotently creates the `mindforge-assets` MinIO bucket and
   exits cleanly.
5. All named volumes are explicitly declared in a `volumes:` block.
6. Alembic migrations run automatically at API startup (advisory-lock protected — already
   implemented in `lifespan`); the `api` service must wait for `postgres` to be healthy.
7. `quiz-agent` (`mindforge-pipeline`) depends on `api` being healthy, ensuring the DB is
   migrated before the worker connects.
8. Bot services (`discord-bot`, `slack-bot`) start only with `--profile bots` and use
   `restart: no` (entry points are stubs — Phase 14/15).
9. `.dockerignore` prevents build-time inclusion of dev artefacts, local envs, and test files.
10. `scripts/STARTUP_GUIDE.md` covers local venv dev, Docker quick start, all profile
    combinations, env var reference, health verification, and troubleshooting.

---

## Reusable Components

### Existing Code to Leverage

| Component | Path | How to leverage |
|-----------|------|-----------------|
| SPA mount | [mindforge/api/main.py](../../../../../mindforge/api/main.py#L325-L329) | Resolve path `../../frontend/dist/frontend/browser` from `mindforge/api/`; Docker must copy SPA to `/app/frontend/dist/` |
| Health endpoint | [mindforge/api/routers/health.py](../../../../../mindforge/api/routers/health.py) | Use `GET /api/health` for Docker `HEALTHCHECK` and compose healthcheck probes |
| CLI entry points | [pyproject.toml](../../../../../pyproject.toml#L62-L67) | 6 scripts installed by `pip install .`; `mindforge-api`, `mindforge-pipeline`, `mindforge-discord`, `mindforge-slack` are the compose CMDs |
| Env var reference | [env.example](../../../../../env.example) | Source for all variable names and Docker-specific values (service hostnames replacing `localhost`) |
| Angular output path | [frontend/angular.json](../../../../../frontend/angular.json#L23) | `outputPath: "dist/frontend"` → builder output at `frontend/dist/frontend/browser/` |
| Migration runner | [mindforge/api/main.py](../../../../../mindforge/api/main.py#L46-L53) | Already runs at startup with advisory lock; no extra migration service needed |

### New Components Required

| Deliverable | Justification |
|-------------|---------------|
| `Dockerfile` | No containerisation exists; single-image multi-stage build cannot reuse existing files |
| `.dockerignore` | New file; content derived from repo structure |
| `compose.yml` | New file; orchestrates all infrastructure services |
| `scripts/STARTUP_GUIDE.md` | New documentation file; no prior deployment guide exists |

---

## Technical Approach

### Dockerfile — Two-Stage Build

**Stage 1 (`builder`, `node:20-alpine`)**

1. Set `WORKDIR /build/frontend`.
2. Copy `frontend/package.json` and `frontend/package-lock.json`; run `npm ci`.
3. Copy remaining `frontend/` source; run `npm run build` (defaults to production config).
4. Output: `frontend/dist/frontend/browser/` (as defined by `outputPath` in `angular.json`).

**Stage 2 (`runtime`, `python:3.12-slim`)**

1. Install system packages: `curl` (for `HEALTHCHECK`), `build-essential` and `libpq-dev` (for
   asyncpg C extensions).
2. Set `WORKDIR /app`.
3. Copy `pyproject.toml`, `mindforge/`, `migrations/` to `/app/`.
4. Run `pip install --no-cache-dir -e .` — editable install that registers CLI entry points
   while keeping source at `/app/mindforge/`. **This is critical**: a regular `pip install .`
   copies source to site-packages, so `__file__` would resolve to
   `/usr/local/lib/python3.12/site-packages/mindforge/api/main.py` and the relative SPA path
   would fail. Editable install ensures `__file__` stays at `/app/mindforge/api/main.py`.
5. Copy Angular build from Stage 1: `COPY --from=builder /build/frontend/dist/ /app/frontend/dist/`
   — this makes the SPA available at the path FastAPI resolves relative to `__file__`.
6. Add `LABEL` with `org.opencontainers.image.version` and `org.opencontainers.image.source`.
7. `EXPOSE 8080`.
8. `CMD ["mindforge-api"]`.

**SPA Path Resolution (critical)**

`main.py` computes the SPA path as:
```
os.path.dirname(__file__)  →  /app/mindforge/api   (with editable install)
../../frontend/dist/frontend/browser  →  /app/frontend/dist/frontend/browser
```
With a regular (non-editable) install, `__file__` would point into site-packages and the
relative resolution would produce a wrong path. Editable install (`pip install -e .`) is
mandatory to preserve the correct relative path.

**`alembic.ini` note:** `alembic.ini` lives at `migrations/alembic.ini` (not repo root).
`run_migrations()` already calls `Config("migrations/alembic.ini")` relative to CWD `/app`.
Since `COPY migrations/ /app/migrations/` is part of Stage 2, `alembic.ini` arrives at the
correct path automatically — no separate root-level copy is needed.

### compose.yml — Service Topology

**Profile: core** (default — no `--profile` flag needed)

Startup order enforced via `depends_on` + `condition: service_healthy`:

```
postgres ──┐
neo4j ─────┤
redis ──────┤──► api ──► quiz-agent
minio ──────┤
mc-init ───┘  (must complete before api starts? → no: api depends on minio healthy, mc-init depends on minio healthy, restart: no)
```

Notes:
- `mc-init` depends on `minio` (condition: service_healthy) and exits after bucket creation.
  `api` also depends on `minio` (condition: service_healthy). No explicit ordering between
  `mc-init` and `api` is needed — both wait for MinIO health independently.
- `quiz-agent` depends on `api` (condition: service_healthy) so the DB is migrated before the
  pipeline worker connects.

**Profile: observability**

- `langfuse-db`: isolated postgres instance for Langfuse metadata, named volume `langfuse_db_data`.
- `clickhouse`: ClickHouse for Langfuse event storage, named volume `clickhouse_data`.
- `langfuse`: `langfuse/langfuse:3`, depends on `langfuse-db` + `clickhouse` healthy, port
  `3000:3000`.
- Main `api` service in core profile reads `LANGFUSE_HOST=http://langfuse:3000` from
  environment when observability profile is active.

**Profile: bots**

- `discord-bot` and `slack-bot` each use the same custom image as `api`, override `command`,
  set `restart: no` (stubs — see Phase 14/15).

**Healthchecks**

| Service | Healthcheck |
|---------|-------------|
| postgres | `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}` |
| neo4j | `wget -qO- http://localhost:7474 \|\| exit 1` |
| redis | `redis-cli ping` |
| minio | `curl -f http://localhost:9000/minio/health/live` |
| api | `curl -f http://localhost:8080/api/health` |
| langfuse-db | `pg_isready -U langfuse` |
| clickhouse | `wget -qO- http://localhost:8123/ping \|\| exit 1` |
| langfuse | `curl -f http://localhost:3000/api/public/health` |

**MinIO Init Container**

`mc-init` runs a shell command equivalent to:
```sh
until mc alias set local http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}; do sleep 1; done
mc mb --ignore-existing local/mindforge-assets
```
`restart: no` — Compose will not restart it after it exits 0.

**Named Volumes** (all declared in top-level `volumes:` block)

`postgres_data`, `neo4j_data`, `neo4j_logs`, `redis_data`, `minio_data`, `langfuse_db_data`,
`clickhouse_data`

### Environment Variables

`compose.yml` services must override localhost defaults from `env.example` with Docker service
hostnames:

| Variable | Docker value |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://mindforge:secret@postgres:5432/mindforge` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `NEO4J_URI` | `bolt://neo4j:7687` |
| `MINIO_ENDPOINT` | `minio:9000` |
| `LANGFUSE_HOST` | `http://langfuse:3000` |

Sensitive values (`JWT_SECRET`, API keys) are loaded from `${VAR}` references with no
defaults — operators must supply them via `.env` file.

**Langfuse v3 required env vars** (for the `langfuse` container, not MindForge app):

| Variable | Value |
|----------|-------|
| `NEXTAUTH_SECRET` | `${NEXTAUTH_SECRET}` (generate: `openssl rand -hex 32`) |
| `SALT` | `${SALT}` (generate: `openssl rand -hex 32`) |
| `NEXTAUTH_URL` | `http://localhost:3000` |
| `TELEMETRY_ENABLED` | `false` |
| `DATABASE_URL` | `postgresql://langfuse:langfuse@langfuse-db:5432/langfuse` |
| `CLICKHOUSE_URL` | `http://clickhouse:8123` |
| `CLICKHOUSE_USER` | `default` |
| `CLICKHOUSE_PASSWORD` | `${CLICKHOUSE_PASSWORD}` |
| `LANGFUSE_INIT_ORG_ID` | optional bootstrap |
| `LANGFUSE_INIT_PROJECT_PUBLIC_KEY` | optional bootstrap |
| `LANGFUSE_INIT_PROJECT_SECRET_KEY` | optional bootstrap |

**Neo4j container auth:**
| Variable | Value |
|----------|-------|
| `NEO4J_AUTH` | `neo4j/${NEO4J_PASSWORD}` |

### .dockerignore Content

Exclude from build context:
- `node_modules/`
- `frontend/dist/`
- `frontend/.angular/`
- `.git/`
- `.venv/`
- `**/__pycache__/`
- `**/*.pyc`
- `.pytest_cache/`
- `.coverage`
- `.mypy_cache/`
- `.ruff_cache/`
- `.env`
- `.env.*`
- `tests/`
- `*.egg-info/`
- `.maister/`

---

## Implementation Guidance

### Testing Approach

Each implementation step should be verified with 2–8 focused tests (not the entire suite):

1. **Dockerfile build** — `docker build -t mindforge:test .` succeeds; `docker run --rm
   mindforge:test mindforge-api --help` exits 0; SPA directory exists at expected path inside
   image.
2. **SPA path alignment** — inside the built image, verify
   `/app/frontend/dist/frontend/browser/index.html` exists.
3. **compose.yml syntax** — `docker compose config` validates without errors for each profile
   combination.
4. **Core stack smoke test** — `docker compose up -d` with `.env` populated; `curl
   http://localhost:8080/api/health` returns `{"status":"ok","database":"ok"}`.
5. **MinIO bucket creation** — after `mc-init` exits, `mc ls local/` shows `mindforge-assets`.
6. **Startup ordering** — `api` logs migration completion before `quiz-agent` logs DB connection.
7. **Observability profile** — `docker compose --profile observability up -d langfuse`; Langfuse
   UI accessible at `http://localhost:3000`.
8. **STARTUP_GUIDE** — manually walk through the quick-start section on a clean environment.

### Standards Compliance

- **Python conventions** ([standards/backend/python-conventions.md]): No new Python modules
  introduced; existing conventions preserved.
- **Minimal implementation** ([standards/global/minimal-implementation.md]): No speculative
  services; only the three profiles described in requirements. Bot services remain stubs.
- **Conventions** ([standards/global/conventions.md]): `.dockerignore` follows the
  no-trailing-whitespace rule; `compose.yml` uses LF line endings.
- **Security** ([.github/copilot-instructions.md]): No credentials hardcoded in `Dockerfile` or
  `compose.yml` — secrets always via `${VAR}` references; `JWT_SECRET` has no default.

---

## Out of Scope

- Kubernetes / Helm manifests
- GitHub Actions CI/CD pipeline
- Nginx reverse proxy or TLS termination
- Discord / Slack bot implementation (Phase 14 and 15)
- Production secrets management (Vault, AWS Secrets Manager)
- Image pushing to a container registry
- Multi-architecture builds (arm64/amd64)

---

## Success Criteria

1. `docker build -t mindforge .` completes without error on the repo as-is.
2. `docker compose up -d` (core profile) starts all 7 services; all healthchecks pass within
   120 seconds.
3. `GET http://localhost:8080/api/health` returns HTTP 200 with `{"status":"ok","database":"ok"}`.
4. `GET http://localhost:8080/` serves the Angular SPA (200 HTML response).
5. MinIO console accessible at `http://localhost:9001`; `mindforge-assets` bucket exists.
6. `docker compose --profile observability up -d` starts Langfuse at `http://localhost:3000`.
7. `docker compose --profile bots up -d` starts `discord-bot` and `slack-bot` without error.
8. `docker compose config` validates without warnings for all profile combinations.
9. `scripts/STARTUP_GUIDE.md` covers all four runnable modes (local venv, core, observability,
   bots) and is verified against the actual startup steps.

---

## Key Implementation Notes

### SPA Path (must be exact)

`mindforge/api/main.py` resolves the SPA directory via:
```
os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist", "frontend", "browser")
```
With `WORKDIR /app` and package installed to `/app/mindforge/`, this resolves to
`/app/frontend/dist/frontend/browser`. The Dockerfile `COPY` must target
`/app/frontend/dist/` (not `/app/frontend/dist/frontend/browser/` directly) so the nested
path structure is preserved.

### Startup Ordering

`api` depends on `postgres`, `neo4j`, `redis`, and `minio` all passing healthchecks because:
- Alembic migrations run at `lifespan` startup (requires postgres)
- Neo4j context is established at startup (requires neo4j)
- Redis client is pinged at startup (soft dependency — falls back gracefully)
- MinIO endpoint is accessed by document ingestion (requires minio)

`quiz-agent` depends on `api` being healthy, which guarantees migrations are complete before
the pipeline worker starts its own DB connections.

### Alembic Working Directory

`alembic.ini` uses `script_location = migrations` (relative path). With `WORKDIR /app` and
`COPY migrations/ /app/migrations/`, the runtime working directory must be `/app` when the API
starts — `uvicorn` launched via `mindforge-api` CLI will inherit `WORKDIR`.

### mc-init Idempotency

`mc mb --ignore-existing` ensures re-running the init container (e.g., after `docker compose
restart mc-init`) does not fail if the bucket already exists. `restart: no` prevents Compose
from looping the init container.

### Redis Fallback

The `api` service logs a warning but starts successfully when Redis is unreachable. The compose
stack includes Redis in the core profile, so this fallback is only relevant for
stripped-down local dev without Docker.
