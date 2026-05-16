# Codebase Analysis Report

**Date**: 2026-04-23
**Task**: Implement Phase 13 - Docker multi-stage build, Docker Compose orchestration, and deployment configuration for MindForge 2.0 (FastAPI + Angular).
**Description**: Implement Phase 13 - Docker multi-stage build, Docker Compose orchestration, and deployment configuration for MindForge 2.0 (FastAPI + Angular).
**Analyzer**: codebase-analyzer skill (3 Explore agents: File Discovery, Code Analysis, Pattern Mining)

---

## Summary

No Docker configuration files exist yet — this is a greenfield Docker implementation. All service entry points, environment variable requirements, port mappings, and architectural conventions are well-documented in `pyproject.toml`, `mindforge/api/main.py`, and `.github/copilot-instructions.md`. The implementation is straightforward: one multi-stage `Dockerfile` (Node build + Python runtime) and one `compose.yml` orchestrating ~10 services with named volumes, healthchecks, and an init pattern for migrations.

---

## Files Identified

### Primary Files

**pyproject.toml** (~60 lines)
- Defines all Python dependencies and CLI entry points (`mindforge-api`, `mindforge-pipeline`, `mindforge-discord`, `mindforge-slack`, `mindforge-quiz`, `mindforge-backfill`)
- Python `>=3.12` requirement constrains the base image

**mindforge/api/main.py**
- FastAPI app; lifespan handler orders initialization: postgres → neo4j → AI gateway → redis → outbox → retrieval → parsers → JWT → event consumers → quiz agents
- Serves Angular SPA via `StaticFiles` from `frontend/dist/frontend/browser` when the directory exists
- Binds `0.0.0.0:8080`; entry point for the `api` container

**mindforge/infrastructure/config.py**
- Pydantic settings; all `os.environ` access is centralized here — no request-time env reads
- Covers 50+ variables; defaults allow most features to be disabled

**mindforge/cli/pipeline_runner.py**
- Entry point for `quiz-agent` / background pipeline worker container
- No HTTP server; runs as a worker process

**mindforge/discord/bot.py** and **mindforge/slack/app.py**
- Stub entry points for Phase 14/15 services; must be wired in `compose.yml` now but can use a `profiles` guard

**migrations/env.py** + **migrations/versions/**
- Alembic migrations; executed automatically at `api` startup with an advisory lock (safe for single-instance)
- No separate migration init container required, but an init container pattern is an option for multi-replica safety

**frontend/angular.json** + **frontend/package.json**
- Angular CLI v21.2.2, npm `11.9.0` → Node 20+ required for the build stage
- Build output: `frontend/dist/frontend/browser`

**env.example**
- Canonical list of all environment variables; must remain the reference for `compose.yml` env definitions

### Related Files

**mindforge/api/routers/health.py**
- `GET /api/health` → `HealthResponse{status, database, neo4j, redis}`; used as the `healthcheck` target for the `api` container

**mindforge/agents/** (all agent modules)
- Stateless; run inside the `api` process or the `quiz-agent` process depending on routing
- No per-agent Docker service needed

**scripts/export_openapi.py**
- Only existing script; no deployment scripts yet — `scripts/` directory is where new helper scripts should land

---

## Current Functionality

There is no existing Docker or Compose configuration. The application is runnable locally via `pip install -e .` + CLI entry points. The API startup sequence is deterministic and self-contained; Alembic migrations run at boot under an advisory lock.

### Key Components/Functions

- **`mindforge-api`** (`mindforge.api.main:app` via uvicorn): Primary HTTP service, serves API + Angular SPA
- **`mindforge-pipeline`** (`mindforge.cli.pipeline_runner`): Background document processing worker
- **`mindforge-discord`** (`mindforge.discord.bot`): Discord bot stub (Phase 14)
- **`mindforge-slack`** (`mindforge.slack.app`): Slack bot stub (Phase 15)
- **Lifespan handler**: Orders infra initialization; must complete before first request
- **SPA mount**: `app.mount("/", StaticFiles(..., html=True))` — path is relative to `mindforge/api/main.py`; must be kept in sync with Dockerfile COPY destination

### Data Flow

```
Client → api:8080 → FastAPI router → application services
                                   → domain / agents
                                   → postgres (source of truth)
                                   → neo4j (derived projection)
                                   → redis (optional cache/sessions)
                                   → minio (object storage)
                                   → litellm/langfuse (AI + tracing)
```

---

## Dependencies

### Python Package Imports (pyproject.toml)

| Package | Purpose |
|---------|---------|
| fastapi, uvicorn[standard] | HTTP framework + ASGI server |
| sqlalchemy[asyncio], asyncpg | PostgreSQL async ORM |
| alembic | DB migrations |
| neo4j | Graph DB driver |
| redis[hiredis] | Cache / quiz sessions |
| litellm | LLM gateway |
| langfuse | LLM observability |
| pydantic, pydantic-settings | Config + schemas |
| httpx | Async HTTP client |
| minio | Object storage |
| discord.py | Discord bot |
| slack-bolt[async] | Slack bot |
| bcrypt, pyjwt[crypto] | Auth |
| python-frontmatter, pymupdf, python-docx | Document parsing |
| python-multipart | File upload |

### External Services (Compose targets)

| Service | Image | Port(s) | Role |
|---------|-------|---------|------|
| postgres | postgres (official) | 5432 | Source of truth |
| neo4j | neo4j (official) | 7687, 7474 | Graph projection |
| redis | redis (official) | 6379 | Cache / sessions (optional) |
| minio | minio/minio | 9000 | Object storage |
| langfuse | langfuse/langfuse | 3000 | LLM tracing |
| clickhouse | clickhouse/clickhouse-server | 8123 | Langfuse backend |
| langfuse-postgres | postgres (official) | internal | Langfuse metadata |

### Consumers (What Depends On This)

All five MindForge services (`api`, `quiz-agent`, `discord-bot`, `slack-bot`, `backfill`) share the same installable package and reference the same `config.py`. The `api` container is the only one that serves HTTP and mounts the SPA.

**Consumer Count**: 5 container services
**Impact Scope**: High — `Dockerfile` and `compose.yml` are the single point of deployment truth for all services

---

## Test Coverage

### Test Files

- **tests/unit/**: Fast unit tests, no I/O — runnable inside the build stage as a smoke check
- **tests/integration/**: Require real DB — run against compose-up stack
- **tests/e2e/**: Full stack — run after `compose up`

### Coverage Assessment

- **Test count**: Present but not quantified by agents
- **Gaps**: No Docker-specific tests exist (expected); no smoke test script for post-deploy health check
- **Opportunity**: `scripts/smoke_test.sh` calling `GET /api/health` after `docker compose up` would close the gap

---

## Coding Patterns

### Naming Conventions

- **Compose file**: `compose.yml` (not `docker-compose.yml`) per copilot-instructions
- **Service names**: lowercase hyphenated (`quiz-agent`, `discord-bot`, `slack-bot`)
- **Scripts**: snake_case Python or bash in `scripts/`

### Architecture Patterns

- **Multi-stage Dockerfile**: Stage 1 `node:20-alpine` builds Angular; Stage 2 `python:3.12-slim` runs the package
- **Single installable package**: All entry points from one `pip install -e .` — one image, multiple CMD overrides
- **Compose profiles**: `discord-bot` and `slack-bot` should use a `profiles: [bots]` guard (stubs in Phase 13)
- **Named volumes**: All stateful services must use named volumes (postgres data, neo4j data, redis data, minio data)
- **Healthchecks**: Every stateful service + `api` needs a healthcheck; `api` uses `GET /api/health`
- **Init containers / depends_on**: `api` must declare `depends_on` with `condition: service_healthy` for postgres; migrations run at api startup

---

## Complexity Assessment

| Factor | Value | Level |
|--------|-------|-------|
| File count | ~8 primary files | Medium |
| External services | 7 services | High |
| Feature flags / env vars | 50+ | High |
| Test coverage | Unit present | Medium |

### Overall: Moderate

Well-understood greenfield Docker task with clear conventions from copilot-instructions. The main complexity is correctly wiring 7 external services with healthchecks, named volumes, and the Langfuse observability sub-stack.

---

## Key Findings

### Strengths

- All entry points, ports, and env vars are fully catalogued — no discovery gaps
- `copilot-instructions.md` prescribes the exact multi-stage build pattern and compose structure
- Single installable package means one Docker image covers all MindForge services (CMD override pattern)
- Alembic advisory-lock migration at startup avoids an init container for the simple single-replica case
- SPA is served directly by FastAPI — no separate nginx container needed

### Concerns

- SPA path in `mindforge/api/main.py` is relative (`../../frontend/dist/frontend/browser`) — must be kept in sync with COPY destination in the Dockerfile's Python stage
- `discord-bot` and `slack-bot` are stubs — they should be guarded with Compose `profiles` so `docker compose up` without `--profile bots` doesn't fail on missing credentials
- Langfuse sub-stack (langfuse + clickhouse + minio-for-langfuse + langfuse-postgres) adds significant compose complexity; it should be isolated under a `profiles: [observability]` or a separate override file
- No `env.example` Docker-specific section yet — compose will need a `.env` file with Docker host names replacing `localhost`

### Opportunities

- Add `scripts/smoke_test.sh` for post-deploy health verification
- Add a `compose.override.yml` for local dev (volume-mount source, hot reload)
- Consider a `profiles: [observability]` for the Langfuse stack so teams without tracing needs get a lighter stack

---

## Impact Assessment

### Files to Create

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build (node → python) |
| `compose.yml` | Full service orchestration |
| `.dockerignore` | Exclude `.venv`, `__pycache__`, `node_modules`, `.git`, test fixtures |
| `scripts/docker-entrypoint.sh` (optional) | Wrapper for CMD selection if needed |

### Files to Modify

| File | Change |
|------|--------|
| `env.example` | Add Docker-specific variable section (postgres/redis/neo4j host names) |
| `.github/copilot-instructions.md` | Already references compose.yml — no changes needed |

### Risk Level: Low-Medium

Greenfield Docker work with no existing configuration to break. Risk comes from:
- Keeping SPA path aligned between `main.py` and `Dockerfile` COPY
- Correctly ordering `depends_on` healthchecks so `api` doesn't start before postgres is ready
- Langfuse sub-stack credential wiring

---

## Recommendations

### Implementation Strategy

1. **`.dockerignore` first** — prevents accidental bloat; include `.venv/`, `__pycache__/`, `*.pyc`, `node_modules/`, `.git/`, `tests/`, `*.md`, `.maister/`
2. **`Dockerfile`** — two stages:
   - `FROM node:20-alpine AS frontend-builder`: `WORKDIR /app/frontend`, `COPY frontend/package*.json .`, `RUN npm ci`, `COPY frontend/ .`, `RUN npm run build`
   - `FROM python:3.12-slim AS runtime`: install build deps, `COPY pyproject.toml .`, `RUN pip install --no-cache-dir .`, `COPY mindforge/ mindforge/`, `COPY migrations/ migrations/`, `COPY --from=frontend-builder /app/frontend/dist frontend/dist`, `EXPOSE 8080`, default `CMD ["mindforge-api"]`
3. **`compose.yml`** — define services in dependency order:
   - Infrastructure tier: `postgres`, `redis`, `neo4j`, `minio`
   - App tier: `api` (depends_on postgres healthy), `quiz-agent` (depends_on api healthy — or postgres directly)
   - Bot tier (profiles: bots): `discord-bot`, `slack-bot`
   - Observability tier (profiles: observability): `langfuse-postgres`, `clickhouse`, `langfuse`
4. **Named volumes** for all stateful services; no bind-mount for production data
5. **Healthchecks**:
   - `postgres`: `pg_isready -U mindforge`
   - `redis`: `redis-cli ping`
   - `neo4j`: `wget --no-verbose --tries=1 --spider http://localhost:7474 || exit 1`
   - `api`: `curl -f http://localhost:8080/api/health || exit 1`
6. **`.env` mapping** — document Docker host name substitutions in `env.example`

### Backward Compatibility

- Local dev (`pip install -e .` + `.env`) must continue working — `compose.yml` does not interfere
- `compose.override.yml` pattern recommended for dev volume mounts

### Testing Requirements

- After `docker compose up -d`, `GET /api/health` must return `{"status":"ok"}`
- Integration tests runnable with `docker compose run --rm api pytest tests/integration/`

---

## Next Steps

Invoke the **gap-analyzer** (or proceed directly to specification/planning) with this report. The implementation is well-scoped — proceed to creating `Dockerfile`, `compose.yml`, `.dockerignore`, and the `env.example` Docker section. No ambiguous requirements remain; all conventions are prescribed by `copilot-instructions.md`.
