# Requirements — Phase 13: Docker and Deployment

**Task:** Implement Phase 13 - Docker multi-stage build, Docker Compose orchestration, and deployment documentation
**Date:** 2026-04-23

---

## Initial Description

Complete Docker multi-stage build, Docker Compose orchestration, and deployment documentation for MindForge 2.0.

**Completion Checklist (from implementation-plan.md Phase 13):**
- `docker build` creates multi-stage image
- `docker compose up` starts all services
- All health checks passing

---

## Requirements Q&A

**Q: Which base image versions?**
A: `node:20-alpine` (builder) + `python:3.12-slim` (runtime)

**Q: Which Langfuse version?**
A: Langfuse v3 (ClickHouse-backed)

**Q: Which PostgreSQL version?**
A: PostgreSQL 17 (postgres:17-alpine)

---

## Similar Features / Reusability

- `mindforge/api/main.py` — lifespan handler pattern (composition root)
- `env.example` — complete environment variable reference; Docker service hostnames differ from localhost defaults
- `mindforge/api/routers/health.py` — `GET /api/health` endpoint used for Docker healthchecks
- `frontend/angular.json` — `outputPath: "dist/frontend"` with browser sub-directory
- `pyproject.toml` — all Python deps and 6 CLI entry points

---

## Functional Requirements

### FR-1: Dockerfile (Multi-Stage)
- **Stage 1 (builder):** `node:20-alpine`
  - Install npm deps with `npm ci`
  - Run production build: `npm run build`
  - Output: `frontend/dist/frontend/browser`
- **Stage 2 (runtime):** `python:3.12-slim`
  - Install system deps (curl for healthchecks, build-essential for C extensions if needed)
  - Copy `pyproject.toml`, `mindforge/`, `migrations/` from repo
  - Install package: `pip install --no-cache-dir .`
  - Copy Angular build from Stage 1 to `/app/frontend/dist/`
  - Expose port 8080
  - Default CMD: `["mindforge-api"]`
  - Label with version/build metadata

### FR-2: .dockerignore
- Exclude: `node_modules/`, `frontend/dist/`, `frontend/.angular/`, `.git/`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.coverage`, `.mypy_cache/`, `.ruff_cache/`, `.env`, `.env.*`, `tests/`

### FR-3: compose.yml (3 Profiles)

**Profile: core (default — always starts)**
Services:
- `postgres` — postgres:17-alpine, named volume, healthcheck via `pg_isready`
- `neo4j` — neo4j:5, named volumes for data/logs, healthcheck via bolt
- `redis` — redis:7-alpine, named volume, healthcheck via `redis-cli ping`
- `minio` — minio/minio:latest, named volume, healthcheck via /minio/health/live, console on :9001
- `mc-init` — minio/mc:latest (init container), creates `mindforge-assets` bucket, depends_on minio
- `api` — custom image, port 8080:8080, depends_on postgres/neo4j/redis/minio, healthcheck via `GET /api/health`
- `quiz-agent` — custom image, CMD: `mindforge-pipeline`, depends_on api (for DB readiness via migrations)

**Profile: observability**
Services:
- `langfuse-db` — postgres:17-alpine, named volume
- `clickhouse` — clickhouse/clickhouse-server:latest, named volume
- `langfuse` — langfuse/langfuse:3, port 3000:3000, depends_on langfuse-db + clickhouse

**Profile: bots**
Services:
- `discord-bot` — custom image, CMD: `mindforge-discord`, restart: no (stub)
- `slack-bot` — custom image, CMD: `mindforge-slack`, restart: no (stub)

All named volumes with explicit volume declarations at bottom of file.

### FR-4: scripts/STARTUP_GUIDE.md
Sections:
1. Prerequisites (Docker, docker compose, Node 20+, Python 3.12+)
2. Local development (venv + uvicorn)
3. Docker quick start (core services)
4. Running with observability (`--profile observability`)
5. Running bots (`--profile bots`)
6. Environment variables reference
7. Health check verification
8. Common troubleshooting

---

## Scope Boundaries

### In Scope
- `Dockerfile` at repo root
- `compose.yml` at repo root with 3 profiles
- `.dockerignore` at repo root
- `scripts/STARTUP_GUIDE.md`

### Out of Scope
- Production Kubernetes manifests
- CI/CD pipeline (GitHub Actions)
- Nginx reverse proxy
- Discord/Slack bot implementation (Phase 14/15)
- TLS/HTTPS configuration

---

## Technical Considerations

### SPA Path Alignment (Critical)
FastAPI mounts SPA via relative path from `mindforge/api/main.py`:
```
../../frontend/dist/frontend/browser → /app/frontend/dist/frontend/browser
```
Docker `COPY --from=builder` must target exactly `/app/frontend/dist/`

### Startup Ordering
`api` must start after `postgres` (migrations run at startup with advisory lock).
Use `depends_on` with `condition: service_healthy` to enforce ordering.

### MinIO Init Container
`mc-init` service uses `minio/mc:latest`, waits for MinIO ready, then:
```sh
mc alias set local http://minio:9000 minioadmin minioadmin && mc mb --ignore-existing local/mindforge-assets
```
Exits after bucket creation. `restart: no`.

### Alembic Migrations Path
`alembic.ini` uses relative path `script_location = migrations`. With `WORKDIR /app`, migrations directory must be at `/app/migrations/`.
