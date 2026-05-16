# MindForge — Startup Guide

This guide covers every way to run MindForge: local development, Docker quick
start, full observability with Langfuse, and the bot surfaces.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | ≥ 3.12 | Backend + pipeline |
| Node.js | 20 LTS | Angular frontend |
| Docker + Compose v2 | latest | All infra services |

---

## Mode 1 — Local venv development

Use this mode when you want rapid iteration on the Python backend and Angular
frontend with real infrastructure running in Docker.

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate
```

### 2. Install the package in editable mode

```bash
pip install -e .
```

This registers the `mindforge-api`, `mindforge-pipeline`, `mindforge-quiz`,
`mindforge-discord`, `mindforge-slack`, and `mindforge-backfill` entry points.

### 3. Copy and edit the environment file

```bash
cp env.example .env
```

Edit `.env` and at minimum provide:

```dotenv
DATABASE_URL=postgresql+asyncpg://mindforge:secret@localhost:5432/mindforge
JWT_SECRET=<generate below>
MODEL_SMALL=openai/gpt-4o-mini
MODEL_LARGE=openai/gpt-4o
OPENROUTER_API_KEY=sk-or-...
```

Generate `JWT_SECRET`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Start only the infrastructure services

```bash
docker compose up -d postgres neo4j redis minio mc-init
```

Wait until all healthchecks pass (typically 30–60 s):

```bash
docker compose ps
```

All listed services should show `(healthy)` or `Exited (0)` for `mc-init`.

### 5. Start the API

```bash
mindforge-api
```

The FastAPI server listens on **http://localhost:8080**.

### 6. Start the Angular dev server (optional)

```bash
cd frontend
npm install        # first time only
npm start
```

Angular dev server listens on **http://localhost:4200** and proxies `/api/*`
to `:8080` via `proxy.conf.json`. Use port 4200 during development.

---

## Mode 2 — Docker quick start (core)

Runs the full stack (API + pipeline worker + all infra) inside Docker.

### 1. Copy and edit the environment file

```bash
cp env.example .env
```

Minimum required variables — **use Docker hostnames** for service URLs:

```dotenv
# Overrides for Docker networking (services communicate by service name)
DATABASE_URL=postgresql+asyncpg://mindforge:secret@postgres:5432/mindforge
REDIS_URL=redis://redis:6379/0
NEO4J_URI=bolt://neo4j:7687
MINIO_ENDPOINT=minio:9000

JWT_SECRET=<generate: python -c "import secrets; print(secrets.token_hex(32))">
MODEL_SMALL=openai/gpt-4o-mini
MODEL_LARGE=openai/gpt-4o
OPENROUTER_API_KEY=sk-or-...
```

> **Note:** `DATABASE_URL`, `REDIS_URL`, `NEO4J_URI`, and `MINIO_ENDPOINT`
> are automatically overridden in the `api` and `quiz-agent` services by
> `compose.yml`, so the above values in `.env` are a safety net / reference.

### 2. Build and start all services

```bash
docker compose up -d
```

### 3. Wait for the API to become healthy

```bash
docker compose ps
# api should show (healthy)
```

### 4. Verify

```bash
curl http://localhost:8080/api/health
# Expected: {"status": "ok", ...}
```

---

## Mode 3 — With observability (Langfuse)

Langfuse provides LLM tracing, cost tracking, and prompt management.

### 1. Add Langfuse secrets to .env

```bash
# Generate two separate secrets — one for NEXTAUTH_SECRET, one for SALT
python -c "import secrets; print(secrets.token_hex(32))"
python -c "import secrets; print(secrets.token_hex(32))"
```

Add to `.env`:

```dotenv
NEXTAUTH_SECRET=<first value>
SALT=<second value>

# MindForge → Langfuse connection (fill after creating a project in Langfuse UI)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000
```

### 2. Start with the observability profile

```bash
docker compose --profile observability up -d
```

This adds `langfuse-db`, `clickhouse`, and `langfuse` to the running stack.

### 3. Open Langfuse

Navigate to **http://localhost:3000** and create an account + project.
Copy the project's public and secret keys back into `.env`, then restart the
API:

```bash
docker compose restart api
```

---

## Mode 4 — With bots (Phase 14/15 stubs)

Discord and Slack bots are scaffolded but not yet functional. They will become
useful in Phase 14 (Discord) and Phase 15 (Slack).

### Discord prerequisites

Set in `.env`:

```dotenv
DISCORD_BOT_TOKEN=<your bot token>
DISCORD_ALLOWED_GUILDS=<comma-separated guild IDs>
DISCORD_CLIENT_ID=<OAuth2 application ID>
DISCORD_CLIENT_SECRET=<OAuth2 application secret>
```

### Slack prerequisites

Set in `.env`:

```dotenv
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...
SLACK_ALLOWED_WORKSPACES=<comma-separated workspace IDs>
```

### Start with the bots profile

```bash
docker compose --profile bots up -d
```

> **Note:** Both bots have `restart: "no"` because they will exit immediately
> until Phase 14/15 wires up their handlers. This is expected.

---

## Ports reference

| Service | URL / Address | Notes |
|---|---|---|
| API | http://localhost:8080 | FastAPI + Angular SPA |
| Angular dev | http://localhost:4200 | Mode 1 only — proxies /api to :8080 |
| PostgreSQL | localhost:5432 | Primary data store |
| Neo4j browser | http://localhost:7474 | Graph projection UI |
| Neo4j bolt | localhost:7687 | Driver connection |
| Redis | localhost:6379 | Sessions / cache |
| MinIO API | localhost:9000 | S3-compatible object storage |
| MinIO console | http://localhost:9001 | Web UI for buckets |
| Langfuse | http://localhost:3000 | Observability profile only |

---

## Health verification

```bash
# API
curl http://localhost:8080/api/health

# PostgreSQL (from host, requires postgres client; or via Docker)
docker compose exec postgres pg_isready -U mindforge

# Redis
docker compose exec redis redis-cli ping

# MinIO bucket
docker compose exec mc-init mc ls local/
# or after mc-init has exited:
docker compose run --rm mc-init mc ls local/
```

---

## Environment variables reference

The table below covers every variable in `env.example`. The **Docker override**
column shows the value automatically injected by `compose.yml` for container
services — you only need the local value when running Mode 1.

### Database

| Variable | Default (local) | Docker override | Required | Description |
|---|---|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://mindforge:secret@localhost:5432/mindforge` | `...@postgres:5432/...` | **Yes** | PostgreSQL connection string (asyncpg driver) |

### Redis

| Variable | Default (local) | Docker override | Required | Description |
|---|---|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | `redis://redis:6379/0` | No | Redis URL. Falls back to PostgreSQL when absent. |

### Neo4j

| Variable | Default (local) | Docker override | Required | Description |
|---|---|---|---|---|
| `NEO4J_URI` | `bolt://localhost:7687` | `bolt://neo4j:7687` | No* | Bolt URI. *Required when `ENABLE_GRAPH=true`. |
| `NEO4J_USERNAME` | `neo4j` | — | No | Neo4j username |
| `NEO4J_PASSWORD` | `secret` | `${NEO4J_PASSWORD:-secret}` | No | Must match `NEO4J_AUTH` in compose.yml |
| `NEO4J_DATABASE` | `neo4j` | — | No | Database name |

### AI models

| Variable | Default | Docker override | Required | Description |
|---|---|---|---|---|
| `MODEL_SMALL` | `openai/gpt-4o-mini` | — | **Yes** | Fast/cheap model (LiteLLM string) |
| `MODEL_LARGE` | `openai/gpt-4o` | — | **Yes** | High-quality model (LiteLLM string) |
| `MODEL_VISION` | `openai/gpt-4o` | — | No | Vision-capable model |
| `MODEL_EMBEDDING` | `openai/text-embedding-3-small` | — | No | Embedding model |
| `MODEL_FALLBACK` | `anthropic/claude-3-haiku-20240307` | — | No | Fallback model on primary failure |
| `OPENROUTER_API_KEY` | `sk-or-...` | — | **Yes*** | *At least one provider key required |

> **Local models (Ollama):** Uncomment the `MODEL_*=ollama/...` and
> `OLLAMA_API_BASE` lines in `env.example` to route all LLM calls to a local
> Ollama instance instead of cloud providers.

### Auth — OAuth providers

| Variable | Default | Required | Description |
|---|---|---|---|
| `DISCORD_CLIENT_ID` | _(empty)_ | When Discord OAuth enabled | Discord OAuth2 application ID |
| `DISCORD_CLIENT_SECRET` | _(empty)_ | When Discord OAuth enabled | Discord OAuth2 secret |
| `DISCORD_REDIRECT_URI` | `http://localhost:8080/api/auth/callback/discord` | No | OAuth redirect target |
| `GOOGLE_CLIENT_ID` | _(empty)_ | No | Google OAuth (future) |
| `GOOGLE_CLIENT_SECRET` | _(empty)_ | No | Google OAuth (future) |
| `GITHUB_CLIENT_ID` | _(empty)_ | No | GitHub OAuth (future) |
| `GITHUB_CLIENT_SECRET` | _(empty)_ | No | GitHub OAuth (future) |

### Auth — Basic / JWT

| Variable | Default | Required | Description |
|---|---|---|---|
| `ENABLE_BASIC_AUTH` | `true` | No | Enable email + password login |
| `BCRYPT_COST_FACTOR` | `12` | No | bcrypt rounds (increase in prod) |
| `JWT_SECRET` | _(empty)_ | **Yes** | Signing key — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `JWT_ACCESS_TOKEN_TTL_MINUTES` | `60` | No | Access token lifetime |
| `JWT_REFRESH_TOKEN_TTL_DAYS` | `30` | No | Refresh token lifetime |
| `AUTH_SECURE_COOKIES` | `false` | No | Set `true` in production (requires HTTPS) |

### Discord bot

| Variable | Default | Required | Description |
|---|---|---|---|
| `DISCORD_BOT_TOKEN` | _(empty)_ | When running discord-bot | Bot token from Discord Developer Portal |
| `DISCORD_ALLOWED_GUILDS` | _(empty)_ | When running discord-bot | Comma-separated guild IDs (allowlist) |

### Slack bot

| Variable | Default | Required | Description |
|---|---|---|---|
| `SLACK_BOT_TOKEN` | `xoxb-` | When running slack-bot | Bot OAuth token |
| `SLACK_APP_TOKEN` | `xapp-` | When running slack-bot | App-level token (socket mode) |
| `SLACK_SIGNING_SECRET` | _(empty)_ | When running slack-bot | Request signing secret |
| `SLACK_ALLOWED_WORKSPACES` | _(empty)_ | When running slack-bot | Comma-separated workspace IDs (allowlist) |

### Object storage (MinIO / S3)

| Variable | Default (local) | Docker override | Required | Description |
|---|---|---|---|---|
| `MINIO_ENDPOINT` | `localhost:9000` | `minio:9000` | **Yes** | MinIO/S3 endpoint (no scheme) |
| `MINIO_ACCESS_KEY` | `minioadmin` | `${MINIO_ACCESS_KEY:-minioadmin}` | **Yes** | Access key |
| `MINIO_SECRET_KEY` | `minioadmin` | `${MINIO_SECRET_KEY:-minioadmin}` | **Yes** | Secret key |
| `MINIO_BUCKET` | `mindforge-assets` | — | No | Bucket name |
| `MINIO_SECURE` | `false` | — | No | Set `true` for TLS / AWS S3 |

### Feature flags

| Variable | Default | Description |
|---|---|---|
| `ENABLE_GRAPH` | `true` | Enable Neo4j knowledge graph |
| `ENABLE_IMAGE_ANALYSIS` | `true` | Enable image-analysis pipeline stage |
| `ENABLE_FLASHCARDS` | `true` | Enable flashcard generation |
| `ENABLE_DIAGRAMS` | `true` | Enable diagram extraction |
| `ENABLE_TRACING` | `true` | Enable Langfuse tracing |
| `ENABLE_EMBEDDINGS` | `true` | Enable vector embeddings |
| `ENABLE_RELEVANCE_GUARD` | `true` | Enable relevance guard agent |
| `ENABLE_ARTICLE_FETCH` | `true` | Enable outbound article fetching |

### Limits

| Variable | Default | Description |
|---|---|---|
| `MAX_DOCUMENT_SIZE_MB` | `10` | Maximum upload size in MB |
| `MAX_CONCURRENT_PIPELINES` | `2` | Concurrent document processing jobs |
| `MAX_PENDING_TASKS_PER_USER` | `10` | Pending pipeline tasks cap per user |
| `PIPELINE_TASK_STALE_THRESHOLD_MINUTES` | `30` | Minutes before a running task is re-claimable |
| `QUIZ_SESSION_TTL_SECONDS` | `1800` | Idle quiz session expiry (30 min) |

### Chunking

| Variable | Default | Description |
|---|---|---|
| `CHUNK_MAX_TOKENS` | `512` | Maximum tokens per text chunk |
| `CHUNK_MIN_TOKENS` | `64` | Minimum tokens per text chunk |
| `CHUNK_OVERLAP_TOKENS` | `64` | Token overlap between adjacent chunks |

### Observability — Langfuse

| Variable | Default | Required | Description |
|---|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | _(empty)_ | When `ENABLE_TRACING=true` | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | _(empty)_ | When `ENABLE_TRACING=true` | Langfuse project secret key |
| `LANGFUSE_HOST` | `http://localhost:3000` | No | Langfuse server URL |
| `NEXTAUTH_SECRET` | _(empty)_ | Observability profile | NextAuth signing secret for Langfuse |
| `SALT` | _(empty)_ | Observability profile | Password hashing salt for Langfuse |
| `LANGFUSE_DB_PASSWORD` | `langfuse` | No | Langfuse internal Postgres password |
| `CLICKHOUSE_PASSWORD` | _(empty)_ | No | ClickHouse password (default: no auth) |

---

## Troubleshooting

### Port already in use

Check which process holds a port:

```bash
# Linux / macOS
ss -tulpn | grep 8080
# or
lsof -i :8080

# Windows
netstat -ano | findstr :8080
```

Ports used by MindForge: **8080, 5432, 7474, 7687, 6379, 9000, 9001, 3000**.

---

### API does not start — missing .env vars

```bash
docker compose logs api
```

Look for `ValidationError` from Pydantic settings. The error message lists
every missing/invalid variable.

---

### MinIO bucket not created

`mc-init` is a one-shot container. If MinIO wasn't ready in time, re-run it:

```bash
docker compose up mc-init
```

---

### Neo4j authentication mismatch

`NEO4J_PASSWORD` in `.env` must match the value used for `NEO4J_AUTH` in
`compose.yml` (format: `neo4j/${NEO4J_PASSWORD:-secret}`). If you change the
password after the volume is initialised, delete the volume and restart:

```bash
docker compose down -v   # WARNING: deletes all Neo4j data
docker compose up -d neo4j
```

---

### JWT_SECRET is still the default / empty

The API emits a startup warning and continues running. This is acceptable for
local development. For any shared or production environment:

1. Generate a secret: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Add it to `.env` as `JWT_SECRET=<value>`
3. Set `AUTH_SECURE_COOKIES=true` (requires HTTPS)

---

### Alembic migration fails on first start

The `api` service waits for `postgres` to be healthy before starting, but if
you are running without Docker healthchecks or starting services manually:

```bash
# Start Postgres first and wait
docker compose up -d postgres
docker compose exec postgres pg_isready -U mindforge
# Then start the API
docker compose up -d api
```

---

### After adding `--profile observability` — Langfuse stays unhealthy

Langfuse requires both `NEXTAUTH_SECRET` and `SALT` to be set. Generate them
and add to `.env`, then restart:

```bash
docker compose --profile observability up -d --force-recreate langfuse
```
