# Implementation Plan: Phase 13 — Docker and Deployment

## Overview

Total Steps: 19
Task Groups: 4
Expected Tests: 8–16 implementation tests + up to 10 gap tests (~18–26 total)

---

## Implementation Steps

### Task Group 1: Dockerfile + .dockerignore
**Dependencies:** None
**Estimated Steps:** 6

- [x] 1.0 Complete container image layer
  - [x] 1.1 Write 4 build-verification tests (manual shell assertions)
    - Test A: `docker build -t mindforge:test .` exits 0
    - Test B: `docker run --rm mindforge:test which mindforge-api` prints a path (entry point installed)
    - Test C: `docker run --rm mindforge:test test -f /app/frontend/dist/frontend/browser/index.html` exits 0 (SPA present at the exact path FastAPI resolves)
    - Test D: `docker run --rm mindforge:test python -c "from mindforge.api.main import app"` exits 0 (package importable)
  - [x] 1.2 Create `.dockerignore` at repo root
    - Exclude: `node_modules/`, `frontend/dist/`, `frontend/.angular/`, `.git/`, `.venv/`
    - Exclude: `**/__pycache__/`, `**/*.pyc`, `.pytest_cache/`, `.coverage`, `.mypy_cache/`, `.ruff_cache/`
    - Exclude: `.env`, `.env.*`, `tests/`, `*.egg-info/`, `.maister/`
    - Use LF line endings; no trailing whitespace
  - [x] 1.3 Create `Dockerfile` — Stage 1 (builder, `node:20-alpine`)
    - `FROM node:20-alpine AS builder`
    - `WORKDIR /build/frontend`
    - Copy `frontend/package.json` and `frontend/package-lock.json` first (layer cache)
    - `RUN npm ci`
    - Copy remaining `frontend/` source
    - `RUN npm run build` — produces `dist/frontend/browser/` per `angular.json` outputPath
  - [x] 1.4 Create `Dockerfile` — Stage 2 (runtime, `python:3.12-slim`)
    - `FROM python:3.12-slim`
    - Install system deps: `curl` (HEALTHCHECK), `build-essential`, `libpq-dev` (asyncpg C extensions), `git` (needed by some pip extras)
    - `WORKDIR /app`
    - Copy `pyproject.toml`, `mindforge/`, `migrations/` to `/app/`
    - `RUN pip install --no-cache-dir -e .` — MUST be editable (`-e`) so `__file__` stays at `/app/mindforge/api/main.py`; regular install copies to site-packages and breaks SPA path resolution
    - `COPY --from=builder /build/frontend/dist/ /app/frontend/dist/` — preserves nested `frontend/browser/` sub-path that FastAPI resolves
    - Add OCI labels: `org.opencontainers.image.version` and `org.opencontainers.image.source`
    - `EXPOSE 8080`
    - `CMD ["mindforge-api"]`
  - [x] 1.5 Verify SPA path alignment explicitly
    - Path FastAPI computes: `os.path.dirname("/app/mindforge/api/main.py") + "/../../frontend/dist/frontend/browser"` = `/app/frontend/dist/frontend/browser`
    - The `COPY --from=builder /build/frontend/dist/ /app/frontend/dist/` places files at `/app/frontend/dist/frontend/browser/index.html` — confirm match
    - Note: `alembic.ini` arrives at `/app/migrations/alembic.ini` via `COPY migrations/` — no separate copy needed; `Config("migrations/alembic.ini")` works with `WORKDIR /app`
  - [x] 1.n Run build-verification tests 1.1 A–D
    - All 4 assertions must pass before moving to Group 2

**Acceptance Criteria:**
- `docker build -t mindforge:test .` completes without error
- `/app/frontend/dist/frontend/browser/index.html` exists inside the image
- `mindforge-api` entry point is on PATH inside the image
- `mindforge` package importable without sys.path manipulation

---

### Task Group 2: compose.yml
**Dependencies:** Group 1 (image must build successfully)
**Estimated Steps:** 6

- [x] 2.0 Complete service orchestration layer
  - [x] 2.1 Write 4 smoke tests (manual curl/docker assertions)
    - Test A: `docker compose config` exits 0 with no warnings (default profile)
    - Test B: `docker compose --profile observability config` exits 0
    - Test C: `docker compose --profile bots config` exits 0
    - Test D: after `docker compose up -d`, `curl -sf http://localhost:8080/api/health` returns `{"status":"ok","database":"ok"}` within 120 s
  - [x] 2.2 Define core profile services in `compose.yml`
    - `postgres:17-alpine`: env `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`; volume `postgres_data`; healthcheck `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}`; interval 5s, retries 10
    - `neo4j:5`: env `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`; volumes `neo4j_data`, `neo4j_logs`; healthcheck `wget -qO- http://localhost:7474 || exit 1`; ports 7474+7687 (host-bound optional for dev)
    - `redis:7-alpine`: volume `redis_data`; healthcheck `redis-cli ping`
    - `minio/minio`: command `server /data --console-address :9001`; volume `minio_data`; env `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`; healthcheck `curl -f http://localhost:9000/minio/health/live`; ports 9000+9001
    - `mc-init` (no image build, use `minio/mc`): depends_on minio (condition: service_healthy); restart: no; entrypoint shell command: alias set + `mc mb --ignore-existing local/mindforge-assets`
    - `api` (custom image): depends_on postgres+neo4j+redis+minio all `condition: service_healthy`; env overrides for Docker hostnames (DATABASE_URL, REDIS_URL, NEO4J_URI, MINIO_ENDPOINT); healthcheck `curl -f http://localhost:8080/api/health`; port 8080:8080
    - `quiz-agent` (custom image): depends_on api (condition: service_healthy); command `mindforge-pipeline`; env same as api minus port exposure
  - [x] 2.3 Define observability profile services
    - `langfuse-db` profile: `observability`; `postgres:17-alpine`; env `POSTGRES_USER=langfuse`, `POSTGRES_PASSWORD=langfuse`, `POSTGRES_DB=langfuse`; volume `langfuse_db_data`; healthcheck `pg_isready -U langfuse`
    - `clickhouse` profile: `observability`; `clickhouse/clickhouse-server:latest`; volume `clickhouse_data`; healthcheck `wget -qO- http://localhost:8123/ping || exit 1`
    - `langfuse` profile: `observability`; `langfuse/langfuse:3`; depends_on langfuse-db+clickhouse (condition: service_healthy); port 3000:3000; env: `NEXTAUTH_SECRET=${NEXTAUTH_SECRET}`, `SALT=${SALT}`, `NEXTAUTH_URL=http://localhost:3000`, `TELEMETRY_ENABLED=false`, `DATABASE_URL=postgresql://langfuse:langfuse@langfuse-db:5432/langfuse`, `CLICKHOUSE_URL=http://clickhouse:8123`, `CLICKHOUSE_USER=default`, `CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}`; optional bootstrap vars: `LANGFUSE_INIT_ORG_ID`, `LANGFUSE_INIT_PROJECT_PUBLIC_KEY`, `LANGFUSE_INIT_PROJECT_SECRET_KEY`; healthcheck `curl -f http://localhost:3000/api/public/health`
  - [x] 2.4 Define bots profile services
    - `discord-bot` profile: `bots`; custom image; command `mindforge-discord`; restart: no; env same subset as api
    - `slack-bot` profile: `bots`; custom image; command `mindforge-slack`; restart: no; env same subset as api
    - Both are stubs (Phase 14/15); `restart: no` prevents Compose restart loops on exit
  - [x] 2.5 Declare named volumes block
    - Top-level `volumes:` block listing all 7: `postgres_data`, `neo4j_data`, `neo4j_logs`, `redis_data`, `minio_data`, `langfuse_db_data`, `clickhouse_data`
    - All volume declarations use empty value (`{}`) to let Docker manage them
    - Verify no service references an undeclared volume
  - [x] 2.n Run smoke tests 2.1 A–D
    - All `docker compose config` validations must exit 0
    - Core stack health endpoint must return 200 OK with correct JSON

**Acceptance Criteria:**
- `docker compose config` validates cleanly for all three profile combinations
- Core stack starts; all 7 services pass healthchecks within 120 s
- `GET /api/health` returns `{"status":"ok","database":"ok"}`
- `GET /` returns 200 HTML (Angular SPA served)
- MinIO console accessible at port 9001; `mindforge-assets` bucket exists after `mc-init` exits
- Langfuse accessible at port 3000 with `--profile observability`

---

### Task Group 3: scripts/STARTUP_GUIDE.md
**Dependencies:** Groups 1 and 2 (guide must reflect working commands)
**Estimated Steps:** 3

- [x] 3.0 Complete deployment documentation layer
  - [x] 3.1 Write 2 doc-coverage tests (manual checklist)
    - Test A: walk through the local venv quick-start section on a clean terminal; all commands succeed as written
    - Test B: walk through Docker quick-start section; `docker compose up -d` + health check sequence matches the guide
  - [x] 3.2 Write `scripts/STARTUP_GUIDE.md` covering all modes
    - **Prerequisites**: Python ≥ 3.12, Node 20+, Docker + Compose plugin, `git`
    - **Local venv dev** (mode 1): `cp env.example .env` → edit → `python -m venv .venv` → activate → `pip install -e .` → start infra (`docker compose up -d postgres neo4j redis minio`) → `mindforge-api`
    - **Docker quick start** (mode 2): `cp env.example .env` → edit required vars → `docker compose up -d` → wait for health → verification commands
    - **With observability** (mode 3): `docker compose --profile observability up -d` → Langfuse at `http://localhost:3000`; note `NEXTAUTH_SECRET`/`SALT` generation: `openssl rand -hex 32`
    - **With bots** (mode 4): `docker compose --profile bots up -d`; note stubs — full implementation in Phase 14/15
    - **Env var reference table**: all vars from `env.example` with localhost default, Docker override, required/optional flag, and description
    - **Health verification**: per-service `curl`/`pg_isready`/`redis-cli` commands to confirm stack is up
    - **Troubleshooting**: common issues — port conflicts (5432, 7474, 7687, 6379, 9000, 9001, 8080, 3000), missing `.env` vars, MinIO bucket not created (re-run `docker compose up mc-init`), Neo4j auth mismatch
  - [x] 3.n Run doc-coverage tests 3.1 A–B
    - Both quick-start walkthroughs must complete without undocumented manual steps

**Acceptance Criteria:**
- Guide covers all four runnable modes
- Env var table is complete and accurate against `env.example`
- Troubleshooting section addresses all known startup failure modes
- All commands in the guide are copy-pasteable and verified correct

---

### Task Group 4: Test Review & Gap Analysis
**Dependencies:** Groups 1, 2, and 3
**Estimated Steps:** 4

- [x] 4.0 Review and fill critical gaps
  - [x] 4.1 Review tests from Groups 1–3 (8 existing tests total)
    - Group 1: 4 build/image tests (A–D)
    - Group 2: 4 compose smoke tests (A–D)
    - Group 3: 2 doc-coverage tests (A–B)
  - [x] 4.2 Analyze gaps for Phase 13 scope only
    - Check: `.dockerignore` actually excludes `.env` from build context (secret leakage risk)
    - Check: `quiz-agent` only starts after `api` healthcheck passes (startup ordering)
    - Check: `mc-init` idempotency — re-running after bucket exists does not fail
    - Check: `STARTUP_GUIDE.md` `mc-init` re-run documented in troubleshooting
  - [x] 4.3 Write up to 10 additional targeted tests if gaps found
    - Gap test 1: build with `.env` present in repo root → verify it does NOT appear in image (`docker run --rm mindforge:test test ! -f /app/.env` exits 0)
    - Gap test 2: `docker compose up -d`; stop api; bring it back up → `quiz-agent` remains stopped until api is healthy again (ordering preserved on restart)
    - Gap test 3: run `docker compose up mc-init` a second time (bucket already exists) → `mc-init` exits 0 (idempotent)
    - Add further tests only if the gap analysis in 4.2 reveals additional uncovered scenarios
  - [x] 4.4 Run all Phase 13 feature tests (8 base + any additional)
    - Target: all pass; no cross-feature test regression

**Acceptance Criteria:**
- All feature tests pass (8 base + up to 10 additional = max 18 total)
- No `.env` file reachable inside the Docker image
- `mc-init` idempotency confirmed
- Startup ordering invariant confirmed

---

## Execution Order

1. Group 1: Dockerfile + .dockerignore (5 steps — no dependencies)
2. Group 2: compose.yml (5 steps — depends on Group 1)
3. Group 3: scripts/STARTUP_GUIDE.md (2 steps — depends on Groups 1 and 2)
4. Group 4: Test Review & Gap Analysis (3 steps — depends on all previous groups)

---

## Standards Compliance

Follow standards from `.maister/docs/standards/`:
- `global/` — minimal-implementation (no speculative services), conventions (LF line endings, no trailing whitespace)
- `global/security` — no credentials hardcoded; all secrets via `${VAR}` references; `JWT_SECRET` has no default in compose.yml
- `backend/python-conventions` — no new Python modules; existing conventions preserved

---

## Notes

- **Test-Driven:** Each group starts with 2–5 manual tests before implementation
- **Run Incrementally:** Only run the group's own tests after completing that group; do NOT run the full test suite
- **Mark Progress:** Check off steps as completed using the checkboxes above
- **Reuse First:** All 6 existing CLI entry points from `pyproject.toml` are reused as Docker `command` values — no new entrypoint scripts needed
- **Critical Invariant:** `pip install -e .` (editable) is mandatory in the Dockerfile; never change to `pip install .` — SPA path resolution depends on `__file__` pointing to `/app/mindforge/api/main.py`
- **alembic.ini location:** `migrations/alembic.ini` (not repo root) — covered by `COPY migrations/ /app/migrations/`; no extra step needed
