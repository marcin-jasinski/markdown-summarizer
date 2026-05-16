# Gap Analysis: Phase 13 — Docker and Deployment

## Summary
- **Risk Level**: Low-Medium
- **Estimated Effort**: Medium
- **Detected Characteristics**: creates_new_entities, involves_data_operations (init containers / migrations), ui_heavy (SPA path coupling)

---

## Task Characteristics
- Has reproducible defect: no
- Modifies existing code: no (minor — Dockerfile couples to existing path logic in `main.py` and `db.py`)
- Creates new entities: yes — `Dockerfile`, `compose.yml`, `.dockerignore`, `scripts/STARTUP_GUIDE.md`
- Involves data operations: yes — Alembic migrations run at container startup against PostgreSQL
- UI heavy: yes — Angular SPA build output must land at exact Docker path FastAPI resolves at startup

---

## Gaps Identified

### Missing Features (all greenfield — nothing exists yet)

1. **`Dockerfile`** — Multi-stage build (Node → Python) does not exist.
2. **`compose.yml`** — Docker Compose orchestration does not exist.
3. **`.dockerignore`** — Not present; build context would send `node_modules`, `.venv`, `__pycache__`, `tests/` etc. to daemon.
4. **`scripts/STARTUP_GUIDE.md`** — Referenced in `copilot-instructions.md` ("Refer to scripts/STARTUP_GUIDE.md") but file is absent. Only `.gitkeep` exists in `scripts/`.

### Incomplete Features

None — this is a fully greenfield addition.

### Behavioral Changes Needed

- **None** to existing Python/Angular code, provided the Docker path constraints below are respected.

---

## Critical Path Coupling Analysis

### 1. SPA Path Resolution (CRITICAL)

`mindforge/api/main.py` line ~333:
```python
spa_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "dist", "frontend", "browser"
)
```

Resolution chain in Docker with `WORKDIR /app`:
```
/app/mindforge/api/main.py
  → os.path.dirname = /app/mindforge/api
  → ../..            = /app
  → frontend/dist/frontend/browser = /app/frontend/dist/frontend/browser
```

**Angular build output path** (`angular.json` `outputPath: "dist/frontend"`):
- Angular 17+ application builder places files in `dist/frontend/browser/`
- Docker `COPY --from=builder /app/frontend/dist/frontend /app/frontend/dist/frontend` is the required target

**Constraint**: Dockerfile must place the Angular build at `/app/frontend/dist/frontend/browser`. If `WORKDIR` changes or the COPY target differs by even one directory level, the SPA silently goes unmounted (no error, just missing static files).

### 2. Alembic Migrations Relative Path (CRITICAL)

`mindforge/infrastructure/db.py` line ~46:
```python
cfg = Config("migrations/alembic.ini")
```

This is a **relative path** resolved against the process working directory at startup.
`mindforge-api` and `mindforge-pipeline` both call `run_migrations` on startup.

**Constraint**: `WORKDIR /app` in Dockerfile is mandatory. If any CMD or entrypoint changes directory, migrations will fail with `FileNotFoundError: migrations/alembic.ini`.

`alembic.ini` also has `prepend_sys_path = .` — adds CWD to `sys.path`.

### 3. Discord/Slack Bots Are Stubs (IMPORTANT)

`mindforge/discord/bot.py`:
```python
def main() -> None:
    print("mindforge-discord: not yet implemented")
```

`mindforge/slack/app.py`:
```python
def main() -> None:
    print("mindforge-slack: not yet implemented")
```

Both entry points exit immediately (no blocking call). If `compose.yml` includes them as services without `restart: "no"`, Docker will restart them in a tight loop. Needs a decision on how to handle (see Decisions section).

### 4. Two Separate PostgreSQL Instances in Stack (IMPORTANT)

The Langfuse stack requires its own PostgreSQL database. The compose file must include:
- `postgres` — MindForge primary DB on port 5432
- `langfuse-db` — Langfuse's PostgreSQL on a separate internal port (no host binding needed)

Both use `postgres:15` but must be independent services with separate named volumes.

### 5. MinIO Initialization (IMPORTANT)

MinIO requires bucket creation before the API starts. MinIO does not auto-create buckets. The bucket name defaults to `mindforge-assets` (from `env.example`). An init container or entrypoint script is needed to create the bucket after MinIO is healthy, or the application code must auto-create on first write (verify this against `mindforge/infrastructure/storage/`).

---

## Data Lifecycle Analysis

### Entity: PostgreSQL Database Init

| Operation | Backend | Container/Init | Status |
|-----------|---------|----------------|--------|
| CREATE schema | Alembic runs in `run_migrations()` at API/worker startup | Requires postgres healthy before api starts | ✅ (handled via `depends_on`) |
| READ | `SELECT 1` health check | `/api/health` | ✅ |

**Constraint**: `depends_on` with `condition: service_healthy` needed for `api` → `postgres` and `quiz-agent` → `postgres`.

### Entity: Neo4j Graph Init

Neo4j 5 in Docker requires `NEO4J_AUTH=neo4j/<password>` environment variable.
`ENABLE_GRAPH=false` skips Neo4j at startup — useful for minimal profiles.

| Operation | Docker Concern | Status |
|-----------|---------------|--------|
| Auth | `NEO4J_AUTH` env var must match `NEO4J_PASSWORD` in mindforge env | ⚠️ Must be synchronized |
| Init | No schema migration needed; Neo4j is a derived projection | ✅ |

### Entity: MinIO Bucket

| Operation | Concern | Status |
|-----------|---------|--------|
| CREATE bucket | MinIO does not auto-create buckets | ❌ Needs explicit init |
| READ/WRITE | Storage adapter in `mindforge/infrastructure/storage/` | Needs verification |

---

## User Journey Impact Assessment

| Dimension | Current | After | Assessment |
|-----------|---------|-------|------------|
| Developer onboarding | Requires manual venv + service setup | `docker compose up` starts everything | ✅ Major improvement |
| Production deployment | Not possible (no container) | Single `docker build` + `compose.yml` | ✅ |
| SPA serving | Works locally via relative path | Must be verified in Docker via path constraint | ⚠️ |

---

## Integration Points

### Files to Create
| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage: Node 20 builder + Python 3.12 runner |
| `compose.yml` | All 11 services with healthchecks and named volumes |
| `.dockerignore` | Exclude `node_modules`, `.venv`, `__pycache__`, `tests/`, `.git`, `*.pyc` |
| `scripts/STARTUP_GUIDE.md` | Developer guide for local, Docker, and production startup |

### Patterns to Follow
- `mindforge/api/main.py` — composition root pattern (no module-level singletons)
- `env.example` — canonical env reference; Docker compose should generate service-network versions of host vars

### Environment Variable Differences (localhost vs Docker)
| Variable | env.example (local) | Docker network value |
|----------|---------------------|---------------------|
| `DATABASE_URL` | `...@localhost:5432/...` | `...@postgres:5432/...` |
| `REDIS_URL` | `redis://localhost:6379/0` | `redis://redis:6379/0` |
| `NEO4J_URI` | `bolt://localhost:7687` | `bolt://neo4j:7687` |
| `MINIO_ENDPOINT` | `localhost:9000` | `minio:9000` |
| `LANGFUSE_HOST` | `http://localhost:3000` | `http://langfuse:3000` |

---

## Issues Requiring Decisions

### Critical (Must Decide Before Proceeding)

1. **Discord/Slack stub containers — restart behavior**
   - **Issue**: `mindforge-discord` and `mindforge-slack` exit immediately (stubs). Including them in compose without `restart: "no"` causes infinite restart loops consuming resources.
   - Options:
     - A) Include with `restart: "no"` (exits cleanly, compose reports them as exited — noisy)
     - B) Use a `--profile bots` opt-in profile (they don't start by default, clean compose output)
     - C) Exclude entirely from Phase 13 compose.yml (add in Phase 14/15)
   - Recommendation: **Option B** — profiles keep them in the file for Phase 14/15 completion without noise
   - Rationale: Aligns with `copilot-instructions.md` which lists them in compose, but stubs shouldn't pollute default `compose up`

2. **MinIO bucket initialization — how to create `mindforge-assets` bucket**
   - **Issue**: MinIO does not auto-create buckets on startup. The API will fail on first file upload without the bucket.
   - Options:
     - A) Add an init container (`minio/mc` client) that runs `mc mb` after MinIO is healthy
     - B) Add bucket auto-creation in the MinIO storage adapter at first write
     - C) Add a one-time setup script documented in `STARTUP_GUIDE.md`
   - Recommendation: **Option A** — init container is idempotent and doesn't require code changes
   - Rationale: Keeps infrastructure concern in Docker layer, not application code

### Important (Should Decide)

3. **Compose profile strategy — minimal vs full stack**
   - **Issue**: The full stack (Langfuse + ClickHouse + MinIO + Neo4j) is heavyweight for local development.
   - Options:
     - A) Single compose.yml, no profiles (all services always start)
     - B) Profiles: default starts `api + postgres + redis + neo4j + minio`, `--profile observability` adds Langfuse/ClickHouse, `--profile bots` adds Discord/Slack
     - C) Separate `compose.override.yml` for dev-only services
   - Recommendation: **Option B**
   - Rationale: Matches the pattern in `copilot-instructions.md` ("compose.yml profiles")

4. **`STARTUP_GUIDE.md` scope**
   - **Issue**: File is referenced in `copilot-instructions.md` but doesn't exist. Should it be created as part of Phase 13?
   - Options:
     - A) Create comprehensive guide in Phase 13 (local, Docker, production modes)
     - B) Create minimal placeholder and expand in later phases
   - Recommendation: **Option A** — already referenced, should exist before Docker instructions are needed
   - Default: Create it

5. **Image tag strategy for custom services**
   - **Issue**: `compose.yml` can either `build:` inline (rebuilds on `compose up --build`) or reference tagged images.
   - Options:
     - A) Inline `build: .` context in compose.yml (simpler, always uses local Dockerfile)
     - B) Use `image: mindforge:latest` with explicit `docker build` step
   - Recommendation: **Option A** — simpler for development workflow
   - Default: Inline build context

6. **Quiz-agent container — long-running poll vs on-demand**
   - **Issue**: `mindforge-pipeline` polls `pipeline_tasks` table via `SELECT … FOR UPDATE SKIP LOCKED`. As a Docker container it needs to run indefinitely. Its compose entry needs `restart: unless-stopped`.
   - Options:
     - A) Single quiz-agent container, always running (straightforward)
     - B) Scale with `--scale quiz-agent=N` (pipeline worker supports parallel execution per `max_concurrent_pipelines`)
   - Recommendation: **Option A** with a note about scaling in `STARTUP_GUIDE.md`
   - Default: Single container, note about scaling

---

## Recommendations

1. Use `WORKDIR /app` throughout Dockerfile — the Alembic relative-path constraint makes this non-negotiable.
2. Use `--no-install-recommends` for system package installs to minimize image size.
3. Run Python as a non-root user in the final stage (security hardening, aligns with Phase 18 review).
4. Use `depends_on` with `condition: service_healthy` for `api` and `quiz-agent` → `postgres`; `api` → `neo4j` (if `ENABLE_GRAPH=true`).
5. Name volumes explicitly (not anonymous) so data survives `compose down` without `-v`.
6. Add `NEO4J_PLUGINS=["apoc"]` env var if graph features require APOC procedures (verify against `mindforge/infrastructure/graph/`).
7. Expose only necessary ports externally: `api:8080`, `postgres:5432` (dev only), `neo4j:7474+7687` (dev only), `minio:9000+9001`, `langfuse:3000`.

---

## Risk Assessment

- **Complexity Risk**: Low — all components are independent services with well-understood Docker images. The main complexity is the multi-stage build and path coupling.
- **Integration Risk**: Medium — SPA path coupling (`/app/frontend/dist/frontend/browser`) is a silent failure mode if misconfigured. The Alembic relative path is a hard failure if `WORKDIR` is wrong.
- **Regression Risk**: Low — no existing code is modified. Only new files are added.
- **Stub Bot Risk**: Low-Medium — stub containers will restart-loop if misconfigured; mitigated by profiles decision.
