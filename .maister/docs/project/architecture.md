# System Architecture

> **Full architecture reference**: [.github/docs/architecture.md](../../../.github/docs/architecture.md)
> This document provides a navigable summary. The authoritative detail is in the reference above.

## Overview

MindForge follows **Hexagonal Architecture** (Ports and Adapters). The backend is a single
installable Python package (`mindforge/`) with strict layer boundaries. A separate Angular
SPA frontend communicates exclusively via the FastAPI REST API.

## Architecture Pattern

**Pattern**: Hexagonal (Ports and Adapters) — fullstack monorepo, single-container deployment

The domain core has zero knowledge of infrastructure. All external systems (databases, LLM
providers, file systems, HTTP) are reached through abstract ports (Python Protocols), with
concrete adapters wired at composition roots. This allows swapping providers without
touching domain or application logic.

**Layer boundaries — never cross them:**

| Layer | Path | Rule |
|---|---|---|
| **Domain** | `mindforge/domain/` | Pure Python, zero I/O, zero framework imports |
| **Application** | `mindforge/application/` | Use-case orchestration; imports only `domain/` |
| **Infrastructure** | `mindforge/infrastructure/` | All I/O: DB, Redis, Neo4j, LiteLLM, parsers, storage |
| **Agents** | `mindforge/agents/` | Stateless AI agents; executed via `AgentContext`/`AgentResult` |
| **Adapters** | `mindforge/api/`, `mindforge/discord/`, `mindforge/slack/`, `mindforge/cli/` | Thin driving adapters; no business logic |

## System Structure

### Domain Layer (`mindforge/domain/`)
- **Purpose**: Core business entities, value objects, domain events, and port interfaces
- **Key files**: `models.py` (entities), `ports.py` (abstract port protocols), `events.py` (domain events), `agents.py` (agent protocols), `graph_keys.py` (Neo4j key constants)
- **Constraint**: No imports from infrastructure, application, or any framework

### Application Layer (`mindforge/application/`)
- **Purpose**: Use-case orchestration — coordinates domain objects and ports
- **Key files**: `pipeline.py` (ingestion orchestrator), `quiz.py`, `chat.py`, `search.py`, `flashcards.py`, `ingestion.py`, `knowledge_base.py`
- **Constraint**: Imports only `domain/`; never imports infrastructure adapters directly

### Infrastructure Layer (`mindforge/infrastructure/`)
- **Purpose**: All I/O adapters implementing domain ports
- **Sub-components**:
  - `persistence/` — SQLAlchemy async PostgreSQL repositories (9 repos)
  - `graph/` — Neo4j adapter (derived projection, rebuilt from PostgreSQL via outbox)
  - `ai/` — LiteLLM AI gateway with circuit breaker, retry, cost tracking
  - `ai/prompts/pl/` — 19 versioned Markdown prompt files (Polish locale)
  - `cache/` — Redis quiz sessions (falls back to PostgreSQL when Redis absent)
  - `parsing/` — ParserRegistry + MIME-dispatch parsers (Markdown, PDF, DOCX, TXT)
  - `events/` — Outbox pattern for at-least-once delivery to Neo4j and consumers
  - `security/` — Upload sanitizer, egress policy (allowlisted outbound HTTP)
  - `storage/` — MinIO S3-compatible object storage adapter
  - `tracing/` — Langfuse tracing + StdoutTracingAdapter fallback
  - `config.py` — Pydantic `AppSettings`; loaded once at startup

### AI Agents (`mindforge/agents/`)
- **Purpose**: Stateless AI agent implementations executed by the pipeline
- **Agents**: `summarizer`, `flashcard_generator`, `quiz_generator`, `quiz_evaluator`,
  `concept_mapper`, `image_analyzer`, `preprocessor`, `relevance_guard`, `article_fetcher`
- **Pattern**: Each agent is open/closed — new agents registered without modifying the orchestrator

### Driving Adapters

| Adapter | Path | Purpose |
|---|---|---|
| REST API | `mindforge/api/` | FastAPI; 14 routers; JWT + OAuth2 auth |
| Angular SPA | `frontend/src/app/` | Standalone components; lazy-loaded routes; served from API process |
| Discord Bot | `mindforge/discord/` | discord.py; guild allowlist; slash commands |
| Slack Bot | `mindforge/slack/` | slack-bolt async; interaction ownership enforcement |
| CLI | `mindforge/cli/` | `pipeline_runner`, `quiz_runner`, `backfill` |

## Data Flow

```
User uploads document
    ↓
API router (mindforge/api/routers/documents.py)
    ↓
Application ingestion service (mindforge/application/ingestion.py)
    ↓
Parser (mindforge/infrastructure/parsing/) → ContentBlocks
    ↓
Pipeline orchestrator (mindforge/application/pipeline.py)
    ↓  [step fingerprint check — skip if unchanged]
AI agents (mindforge/agents/) via AI gateway (mindforge/infrastructure/ai/)
    ↓  [checkpoint each step output to document_artifacts]
DocumentArtifact persisted to PostgreSQL
    ↓  [outbox event emitted]
Outbox relay → Neo4j graph projection updated (mindforge/infrastructure/graph/)
```

**Query flow:**
```
Frontend / Discord / Slack
    ↓
API router
    ↓
Application service (search / quiz / chat / flashcards)
    ↓
Graph traversal first → full-text/lexical second → vector embeddings last
    ↓
Response (with server-authoritative state; never exposes raw prompts or reference answers)
```

## Data Architecture

### PostgreSQL (Single Source of Truth)
- All business data: users, documents, artifacts, quiz interactions, chat history
- `document_artifacts` table: JSONB column stores full `DocumentArtifact` including step fingerprints
- Outbox table: `outbox_events` for at-least-once delivery

### Neo4j (Derived Projection)
- Concept nodes and relationships derived from `DocumentArtifact.concept_map`
- Rebuilt entirely from PostgreSQL on demand — never a source of truth
- Used for concept neighborhood queries and knowledge graph visualization

### Redis (Optional)
- Quiz session state with PostgreSQL fallback
- SSE event fan-out with outbox polling fallback
- Semantic response cache (disabled when absent)

## Security & Trust Model

- **Server-authoritative state**: Server owns all grading, scoring, and session state
- **Client redaction**: `reference_answer`, `grounding_context`, `raw_prompt`, `raw_completion` never sent to browser
- **Untrusted input**: All filenames and external URLs validated via `upload_sanitizer.py` and `egress_policy.py`
- **Lesson identity**: Deterministic resolution; hard reject if no valid identifier — never falls back to `"unknown"`
- **Auth enforcement**: Discord/Slack bots enforce allowlists and interaction ownership

## Idempotency & Reliability

- **Step fingerprinting**: Each pipeline step checksums its inputs + prompt version + model ID; unchanged steps are skipped on reruns
- **Outbox pattern**: Events written transactionally to `outbox_events`; relay delivers at-least-once to Neo4j
- **Composition roots**: One per runtime surface — no module-level singletons, no import-time side effects

## External Integrations

| Service | Role | Optional |
|---|---|---|
| LiteLLM gateway | Provider-agnostic LLM routing (OpenAI/Anthropic/Ollama/OpenRouter) | No |
| PostgreSQL | Primary data store | No |
| Neo4j | Graph read projection | Yes (degrades gracefully) |
| Redis | Cache + sessions | Yes (automatic fallback) |
| MinIO | Object storage for uploaded files | Yes |
| Langfuse | Distributed tracing + cost accounting | Yes (falls back to stdout) |

## Deployment Architecture

- **Single container**: Multi-stage Dockerfile — Node builds Angular → Python serves API + SPA
- **Docker Compose**: `api`, `quiz-agent`, `discord-bot`, `slack-bot`, Neo4j, Redis, Postgres,
  Langfuse stack (ClickHouse + MinIO + Postgres)
- **Status**: Documented; `Dockerfile` and `compose.yml` not yet committed (Phase 17)

---
*Based on codebase analysis performed 2026-04-22*
*Full detail*: [.github/docs/architecture.md](../../../.github/docs/architecture.md)
