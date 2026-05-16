# MindForge Workspace Guidelines

## Coding Standards & Conventions

Read @.maister/docs/INDEX.md before starting any task. It indexes the project's coding standards and conventions:
- Coding standards organized by domain (frontend, backend, testing, etc.)
- Project vision, tech stack, and architecture decisions

Follow standards in `.maister/docs/standards/` when writing code — they represent team decisions. If standards conflict with the task, ask the user.

### Standards Evolution

When you notice recurring patterns, fixes, or conventions during implementation that aren't yet captured in standards — suggest adding them. Examples:
- A bug fix reveals a pattern that should be standardized (e.g., "always validate X before Y")
- PR review feedback identifies a convention the team wants enforced
- The same type of fix is needed across multiple files
- A new library/pattern is adopted that should be documented

When this happens, briefly suggest the standard to the user. If approved, invoke `/maister-standards-update` with the identified pattern.

## Maister Workflows

This project uses the maister plugin for structured development workflows. When any `/maister-*` command is invoked, execute it via the Skill tool immediately — do not skip workflows for "straightforward" tasks. The user chose the workflow intentionally; complexity assessment is the workflow's job.

## Architecture

MindForge 2.0 follows **hexagonal architecture** (Ports and Adapters). The entire backend lives in the `mindforge/` installable package. See [docs/architecture.md](./docs/architecture.md) for the full design.

**Layer boundaries — never cross them:**
- `mindforge/domain/` — pure Python, zero I/O, zero framework imports. Entities, value objects, domain events, agent protocols, and port interfaces (abstract ABCs/Protocols) live here.
- `mindforge/application/` — use-case orchestration. Imports only `domain/`. No database drivers, no HTTP clients, no LLM SDKs.
- `mindforge/infrastructure/` — all I/O: PostgreSQL repositories, Neo4j graph adapter, Redis, LiteLLM AI gateway, parsers, object storage, outbox, security helpers.
- `mindforge/agents/` — stateless AI agent implementations that execute via `AgentContext`/`AgentResult`. Agents never call each other directly; all inter-agent data flows through `DocumentArtifact` orchestrated by `mindforge/application/pipeline.py`.
- `mindforge/api/`, `mindforge/discord/`, `mindforge/slack/`, `mindforge/cli/` — thin driving adapters. No business logic; delegate immediately to application services.

**Composition roots:** Each runtime surface (`mindforge/api/main.py`, `mindforge/discord/bot.py`, `mindforge/slack/app.py`, `mindforge/cli/pipeline_runner.py`) has exactly **one** composition root. No module-level singletons, no import-time side effects, no `sys.path` manipulation.

**Open/Closed:** Adding a new AI agent, document format parser, or auth provider means registering a new adapter — never modifying the orchestrator, `ParserRegistry`, or auth framework.

**Data stores:**
- PostgreSQL is the single source of truth for all business data.
- Neo4j is a **derived projection** rebuilt from PostgreSQL artifacts; it is never a source of truth and can be fully rebuilt from the canonical store.
- Redis is optional: quiz sessions fall back to PostgreSQL, SSE falls back to polling `outbox_events`, semantic cache is disabled. A startup warning is emitted when Redis is absent.

## Build And Test

- Local dev: copy `env.example` → `.env`, create a venv, then `pip install -e .` (editable install).
- Available CLI entry points after install:
  - `mindforge-pipeline` — run the document processing pipeline
  - `mindforge-api` — start the FastAPI server (`:8080`)
  - `mindforge-quiz` — interactive quiz CLI
  - `mindforge-discord` — Discord bot
  - `mindforge-slack` — Slack bot
  - `mindforge-backfill` — backfill and reindex operations
- Direct uvicorn: `python -m uvicorn mindforge.api.main:app --host 0.0.0.0 --port 8080 --reload`
- Tests: `pytest tests/` — `tests/unit/` (no I/O, fast), `tests/integration/` (real DB, mocked LLM), `tests/e2e/` (full stack).
- Frontend (`frontend/`): `npm install`, `npm start` (dev server `:4200`), `npm run build`, `npm test`.
- For Docker, use scripts in `scripts/` or `compose.yml` profiles. Refer to [scripts/STARTUP_GUIDE.md](../scripts/STARTUP_GUIDE.md).

## Docker And Runtime

- `Dockerfile` is multi-stage: Node builds Angular, then Python runs the API, pipeline worker, or bot entry points.
- `compose.yml` orchestrates `api`, `quiz-agent`, `discord-bot`, `slack-bot` plus Neo4j, Redis, Postgres, and the Langfuse observability stack (ClickHouse, MinIO, Postgres). Keep healthchecks, init containers, and named volumes aligned when changing services.
- The FastAPI process serves the built Angular SPA from `frontend/dist/frontend/browser`. Keep static serving config and Docker build output synchronized.
- Prefer official upstream images for all external services. Custom container logic only for MindForge-owned code.

## Security And Cost Guardrails

- **Server-authoritative state:** The server owns all grading, scoring, and session state. Browser payloads must never expose `reference_answer`, `grounding_context`, `raw_prompt`, or `raw_completion`. Redaction is enforced in `InteractionStore.list_for_user()` (defense-in-depth — not just in routers). Follow `mindforge/api/routers/quiz.py` and `mindforge/application/quiz.py`.
- **Untrusted input:** All uploaded filenames, external URLs, and image URLs are untrusted. Use `mindforge/infrastructure/security/upload_sanitizer.py` and `egress_policy.py`. Never write ad-hoc filesystem or HTTP handling.
- **Retrieval cost discipline:** Graph traversal first → full-text/lexical second → vector embeddings last. Reuse the stored `reference_answer` from the artifact during grading; do not regenerate it.
- **Lesson identity:** `lesson_id` is resolved deterministically: frontmatter `lesson_id:` → frontmatter `title:` (slugified) → PDF metadata `Title` → filename. Never fall back to a placeholder like `"unknown"` — reject the upload if no valid identifier can be produced.
- **Discord/Slack:** Enforce allowlists and interaction ownership. See `mindforge/discord/auth.py` and `mindforge/slack/auth.py`.
- **Idempotency:** Every pipeline step checkpoints its output and `StepFingerprint` to `document_artifacts` after execution. Do not break checkpoint or outbox patterns; outbox guarantees at-least-once event delivery to Neo4j and other consumers.
- Security review baseline: [reviews/mindforge-deep-code-review-2026-04-01.md](./reviews/mindforge-deep-code-review-2026-04-01.md).

## Conventions

- **No `sys.path` manipulation.** The package is installed via `pip install -e .` and imported as `mindforge.*`. Never add the repo root to `sys.path` in new code.
- **Configuration is explicit and validated once.** Load settings via `mindforge/infrastructure/config.py` (Pydantic). Never call `os.environ` at request time or in module-level code.
- **All imports at module top level.** Optional/heavy packages use `try/except ImportError` guards.
- **API contracts:** Keep `mindforge/api/schemas.py` (Pydantic models) and `frontend/src/app/core/models/api.models.ts` in sync.
- **Angular:** All HTTP integration belongs in `frontend/src/app/core/services/`; follow the standalone, lazy-loaded routing pattern in `frontend/src/app/app.routes.ts`.
- **Representative files before introducing new patterns:** `mindforge/application/pipeline.py` (orchestration), `mindforge/api/main.py` + routers (API), `mindforge/agents/summarizer.py` (agent), `mindforge/infrastructure/ai/gateway.py` (LLM gateway), `frontend/src/app/core/services/api.service.ts` (Angular HTTP client).
- Preserve user-facing Polish content unless the task explicitly changes product language.

## Reference Docs

- System overview and pipeline details: [README.md](../README.md)
- Startup modes, local/Docker workflows, and troubleshooting: [scripts/STARTUP_GUIDE.md](../scripts/STARTUP_GUIDE.md)
- Architecture reference: [docs/architecture.md](./docs/architecture.md)
- Delivery roadmap: [docs/implementation-plan.md](./docs/implementation-plan.md)
- Security and cost review baseline: [reviews/mindforge-deep-code-review-2026-04-01.md](./reviews/mindforge-deep-code-review-2026-04-01.md)
- Angular CLI basics for the SPA: [frontend/README.md](../frontend/README.md)
