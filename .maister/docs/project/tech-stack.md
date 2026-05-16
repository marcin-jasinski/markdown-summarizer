# Technology Stack

## Overview

MindForge 2.0 is a fullstack monorepo with a Python backend and Angular SPA frontend,
deployed as a single Docker container. The stack prioritizes correctness, AI cost
discipline, and strict architectural boundaries over operational simplicity.

---

## Languages

### Python (3.12+)
- **Usage**: ~90% of backend codebase
- **Rationale**: Dominant AI/ML ecosystem; async-native via asyncio; strict typing with mypy;
  excellent FastAPI and SQLAlchemy integration
- **Key features used**: `asyncio`, `dataclasses`, `from __future__ import annotations`,
  `match` statements, structural pattern matching, `TypeAlias`

### TypeScript (~5.9.2)
- **Usage**: 100% of frontend codebase
- **Rationale**: Type safety for API contract adherence; generated types from OpenAPI spec
  via `openapi-typescript` keep frontend in sync with backend schemas automatically

---

## Frameworks

### Backend

| Framework | Version | Rationale |
|---|---|---|
| **FastAPI** | ≥0.135.0 | Async-native, auto OpenAPI spec generation, dependency injection via `Depends` |
| **Uvicorn** | ≥0.44.0 | ASGI server with `[standard]` extras for production performance |
| **SQLAlchemy** | ≥2.0.49 (async) | Industry-standard async ORM; type-safe query building; Alembic migrations |
| **Pydantic** | ≥2.12.0 | Request/response validation; AppSettings config loading (single config-load-at-startup) |
| **Alembic** | ≥1.18.0 | Reversible database migrations; zero-downtime-aware |

### Frontend

| Framework | Version | Rationale |
|---|---|---|
| **Angular** | ^21.2.0 | Standalone components, signals, lazy-loaded routing; mature toolchain |
| **Angular Material + CDK** | ^21.2.7 | Consistent UI component library; accessible by default |
| **Cytoscape.js** | ^3.33.2 | Interactive force-directed graph visualization for concept maps |
| **RxJS** | ~7.8.0 | Reactive streams for HTTP and event handling |

### Testing

| Framework | Version | Context |
|---|---|---|
| **pytest** | ≥9.0.0 | Python test runner; 3-tier test structure (unit/integration/e2e) |
| **pytest-asyncio** | ≥1.3.0 | Async test support (mode: auto) |
| **testcontainers** | ≥4.14.0 | Spins up real PostgreSQL/Neo4j in integration tests — no DB mocks |
| **Vitest** | ^4.0.8 | Frontend test runner (replaces Karma); faster than Jest |
| **jsdom** | ^28.0.0 | DOM simulation for Vitest frontend tests |

---

## Databases

### PostgreSQL (15+)
- **Type**: Relational
- **ORM**: SQLAlchemy 2.0 async with asyncpg driver
- **Role**: Single source of truth for all business data
- **Features used**: JSONB (artifact storage), `gen_random_uuid()`, full-text search,
  advisory locks for migrations
- **Rationale**: Proven reliability; rich query capabilities; JSONB avoids rigid schema
  for evolving AI artifact structures

### Neo4j (driver ≥6.1.0)
- **Type**: Graph database
- **Role**: Derived read projection of concept/document relationships; rebuilt from
  PostgreSQL artifacts via outbox events — never a source of truth
- **Rationale**: Native graph traversal for concept neighborhood queries; decoupled
  from canonical store via outbox pattern so it can be fully rebuilt at any time

---

## Cache

### Redis (≥7.4.0, optional)
- **Driver**: `redis[hiredis]`
- **Usage**: Quiz session state, SSE event fan-out, semantic response cache
- **Fallback behavior**: Quiz sessions fall back to PostgreSQL; SSE falls back to
  outbox polling; semantic cache disabled. A startup warning is emitted when absent.
- **Limitation**: In-memory rate limiter (not Redis-backed) — ineffective behind
  multiple workers (known gap, acceptable for single-instance deployment)

---

## Object Storage

### MinIO (≥7.2.0)
- **Type**: S3-compatible object storage
- **Usage**: Uploaded document assets (original files, parsed images)
- **Rationale**: Self-hosted S3-compatible API; no vendor lock-in; runs in Docker Compose

---

## AI & LLM

### LiteLLM (≥1.83.0)
- **Role**: Provider-agnostic LLM routing gateway
- **Supported providers**: OpenAI, Anthropic, Ollama, OpenRouter
- **Model tiers**: `SMALL` (gpt-4o-mini), `LARGE` (gpt-4o), `VISION` (gpt-4o),
  `EMBEDDING` (text-embedding-3-small), `FALLBACK` (claude-3-haiku)
- **Cost discipline**: Deterministic logic first → small model → frontier model last;
  circuit breaker + exponential backoff + Retry-After header respect

### Langfuse (≥4.2.0)
- **Role**: Distributed tracing with per-call token/cost accounting
- **Fallback**: `StdoutTracingAdapter` when `LANGFUSE_PUBLIC_KEY` is absent
- **Stack**: Langfuse server + ClickHouse + MinIO + Postgres (runs in Docker Compose)

---

## Auth

| Component | Library | Notes |
|---|---|---|
| Password hashing | `bcrypt ≥4.2.0` | Standard bcrypt |
| JWT | `PyJWT[crypto] ≥2.10.0` | Signed JWTs for session tokens |
| OAuth2 providers | Discord, Google, GitHub | Pluggable provider architecture |

---

## Document Parsing

| Format | Library | Notes |
|---|---|---|
| Markdown | `python-frontmatter ≥1.1.0` | YAML frontmatter extraction for `lesson_id`, `title` |
| PDF | `pymupdf ≥1.25.0` | Text extraction with metadata (Title field for lesson identity) |
| DOCX | `python-docx ≥1.2.0` | Word document parsing |
| TXT | Built-in | Plain text ingestion |

Registry pattern: `ParserRegistry` dispatches by MIME type — open/closed for new formats.

---

## Chat Platform Integrations

| Platform | Library | Version |
|---|---|---|
| Discord | `discord.py` | ≥2.4.0 |
| Slack | `slack-bolt[async]` | ≥1.28.0 |

---

## Build Tools & Package Management

| Tool | Context |
|---|---|
| **hatchling** (PEP 517) | Python package build backend |
| `pip install -e .` | Editable install — no `sys.path` manipulation |
| **npm 11.9.0** | Frontend package management |
| **@angular/build ^21.2.2** | Angular application builder |
| **Prettier ^3.8.1** | Frontend code formatting |

---

## Development Tools

### Linting & Formatting
- **ruff ≥0.15.0** — Python linter + formatter; rules: `E, F, I, N, UP, S, B, A, C4, PT, RUF`; line length 100; target `py312`

### Type Checking
- **mypy ≥1.20.0** — Strict mode (`--strict`); `ignore_missing_imports=true`
- **TypeScript ~5.9.2** — Strict mode on frontend

### API Type Generation
- **openapi-typescript ^7.6.1** — Generates TypeScript types from live FastAPI OpenAPI spec;
  run after any schema change to keep `frontend/src/app/core/models/api.models.ts` in sync

### HTTP Client (backend)
- **httpx ≥0.28.1** — Used for article fetcher and egress-policy-governed external HTTP

---

## Infrastructure

### Containerization
- Multi-stage Dockerfile: Node builds Angular SPA → Python serves API + SPA static files
- Docker Compose orchestrates: `api`, `quiz-agent`, `discord-bot`, `slack-bot`,
  Neo4j, Redis, Postgres, Langfuse stack (ClickHouse + MinIO + Postgres)
- Status: **Referenced in docs, files not yet committed** (Phase 17 gap)

### CI/CD
- Status: **Not configured** (Phase 19 gap — highest priority)
- Planned: GitHub Actions for ruff + mypy + pytest on every PR

---

## Key Dependencies Summary

| Package | Purpose |
|---|---|
| `litellm ≥1.83.0` | Provider-agnostic LLM routing |
| `langfuse ≥4.2.0` | Distributed tracing + cost accounting |
| `neo4j ≥6.1.0` | Graph database driver (derived projection) |
| `testcontainers ≥4.14.0` | Real DB containers in integration tests |
| `pymupdf ≥1.25.0` | PDF extraction with metadata |
| `cytoscape ^3.33.2` | Interactive concept map visualization |
| `openapi-typescript ^7.6.1` | Frontend type generation from live spec |
| `python-frontmatter ≥1.1.0` | Markdown frontmatter parsing |
| `minio ≥7.2.0` | S3-compatible object storage client |
| `slack-bolt[async] + discord.py` | Async Slack and Discord adapters |

---

*Last Updated*: 2026-04-22
*Auto-detected*: all technologies above via pyproject.toml, package.json, codebase analysis
