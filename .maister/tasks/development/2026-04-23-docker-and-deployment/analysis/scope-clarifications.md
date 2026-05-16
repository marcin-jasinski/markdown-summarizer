# Scope Clarifications

**Task:** Phase 13 — Docker and Deployment
**Date:** 2026-04-23

## Decisions Made

### Critical: Discord/Slack Bot Stubs
- **Decision:** Use `--profile bots` (opt-in)
- **Rationale:** Bots are stubs that exit immediately. Default `docker compose up` won't start them; users add `--profile bots` explicitly for Phase 14/15 testing.

### Critical: MinIO Bucket Initialization
- **Decision:** Init container using `mc` (minio/mc) client
- **Rationale:** Idempotent init service that creates `mindforge-assets` bucket once and exits. No code changes to the application layer needed.

### Important: Compose Profiles
- **Decision:** Profiles: core (default) + `--profile observability` for Langfuse stack
- **Profiles:**
  - **core** (default): api, quiz-agent, postgres, neo4j, redis, minio, mc-init
  - **observability**: langfuse, clickhouse, langfuse-db
  - **bots**: discord-bot, slack-bot

### UI Mockups
- **Decision:** Skip Phase 4 (UI mockup generation)
- **Rationale:** Infrastructure/deployment task — no Angular UI components are being created.

## Scope Boundaries

### In Scope
- `Dockerfile` — multi-stage: Node 20 Alpine builder + Python 3.12-slim runner
- `compose.yml` — 3 profiles: core, observability, bots
- `.dockerignore` — exclude node_modules, __pycache__, .venv, .git, test files
- `scripts/STARTUP_GUIDE.md` — local dev and Docker deployment instructions
- Health checks for all services in compose.yml

### Out of Scope
- Production Kubernetes manifests (future phase)
- CI/CD pipeline configuration (future phase)
- Discord/Slack bot implementation (Phase 14/15)
- Nginx reverse proxy (FastAPI serves SPA directly)
