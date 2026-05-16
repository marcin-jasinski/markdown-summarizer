# MindForge 2.0 — Implementation Plan

> **Version:** 1.2
> **Date:** 2026-04-12
> **Status:** Active
> **Reference:** [architecture.md](./architecture.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 0 — Project Scaffolding and Tooling](#phase-0--project-scaffolding-and-tooling)
3. [Phase 1 — Domain Layer](#phase-1--domain-layer)
4. [Phase 2 — Infrastructure Foundation](#phase-2--infrastructure-foundation)
5. [Phase 3 — AI Gateway](#phase-3--ai-gateway)
6. [Phase 4 — Document Parsing and Ingestion](#phase-4--document-parsing-and-ingestion)
7. [Phase 5 — Agent Framework and Pipeline Orchestration](#phase-5--agent-framework-and-pipeline-orchestration)
8. [Phase 6 — Concrete Processing Agents](#phase-6--concrete-processing-agents)
9. [Phase 7 — Neo4j Graph Layer](#phase-7--neo4j-graph-layer)
10. [Phase 8 — Event System](#phase-8--event-system)
11. [Phase 9 — API Layer (FastAPI)](#phase-9--api-layer-fastapi)
12. [Phase 10 — Quiz and Flashcard Services](#phase-10--quiz-and-flashcard-services)
13. [Phase 11 — Search and Conversational RAG](#phase-11--search-and-conversational-rag)
14. [Phase 12 — Angular Frontend](#phase-12--angular-frontend)
15. [Phase 13 — Docker and Deployment](#phase-13--docker-and-deployment)
16. [Phase 14 — Slack Bot](#phase-14--slack-bot)
17. [Phase 15 — CLI Entry Points](#phase-15--cli-entry-points)
18. [Phase 16 — Observability and Tracing](#phase-16--observability-and-tracing)
19. [Phase 17 — Security Hardening (Penetration Testing and Regression)](#phase-17--security-hardening-penetration-testing-and-regression)
20. [Phase 18 — End-to-End Testing and Quality Gates](#phase-18--end-to-end-testing-and-quality-gates)
22. [Dependency Graph](#dependency-graph)

---

## Overview

This plan decomposes the MindForge 2.0 greenfield rewrite into 20 sequential
phases.  Each phase is self-contained and produces verifiable deliverables.
Phases must be completed in order because later phases depend on the artifacts
of earlier ones (see [Dependency Graph](#dependency-graph) at the end).

**Conventions used in this document:**

- `[ ]` — task or phase not started
- `[X]` — task or phase completed
- Each phase has a completion checklist.  A phase is DONE when every task
  and subtask in it is `[X]`.
- Code references (file paths, class names) correspond exactly to the package
  structure defined in `architecture.md` Section 5.

---

## [x] Phase 0 — Project Scaffolding and Tooling

**Goal:** Establish the installable Python package skeleton, configuration
loading, developer environment, and CI prerequisites so that all subsequent
phases have a stable foundation.

### Tasks

- [x] **0.1 — Create `pyproject.toml` with PEP 621 metadata**
  - Project name: `mindforge`, requires-python `>=3.12`.
  - Define all six `[project.scripts]` entry points (`mindforge-pipeline`,
    `mindforge-quiz`, `mindforge-backfill`, `mindforge-discord`, `mindforge-slack`,
    `mindforge-api`) pointing to their target modules (stubs are fine).
  - Include all runtime dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`,
    `asyncpg`, `alembic`, `litellm`, `neo4j`, `redis[hiredis]`, `httpx`, `pydantic`,
    `pydantic-settings`, `python-frontmatter`, `pymupdf`, `python-docx`,
    `langfuse`, `discord.py`, `slack-bolt[async]`, `bcrypt`, `pyjwt[crypto]`,
    `minio`, `cytoscape` (if any Python dependency), and any others from
    Appendix A.
  - Include dev dependencies group: `pytest`, `pytest-asyncio`, `httpx` (test
    client), `testcontainers`, `ruff`, `mypy`.

- [x] **0.2 — Create the package directory tree**
  - Scaffold every `__init__.py` listed in architecture Section 5 as empty files.
    Directories: `mindforge/`, `mindforge/domain/`, `mindforge/application/`,
    `mindforge/infrastructure/`, `mindforge/infrastructure/persistence/`,
    `mindforge/infrastructure/graph/`, `mindforge/infrastructure/ai/`,
    `mindforge/infrastructure/ai/prompts/`, `mindforge/infrastructure/parsing/`,
    `mindforge/infrastructure/cache/`, `mindforge/infrastructure/storage/`,
    `mindforge/infrastructure/tracing/`, `mindforge/infrastructure/events/`,
    `mindforge/infrastructure/security/`, `mindforge/agents/`,
    `mindforge/api/`, `mindforge/api/routers/`, `mindforge/discord/`,
    `mindforge/discord/cogs/`, `mindforge/slack/`, `mindforge/slack/handlers/`,
    `mindforge/cli/`.
  - Scaffold `tests/`, `tests/unit/`, `tests/unit/domain/`,
    `tests/unit/application/`, `tests/unit/agents/`, `tests/integration/`,
    `tests/integration/persistence/`, `tests/integration/graph/`,
    `tests/integration/api/`, `tests/e2e/`, `tests/conftest.py`.
  - Scaffold `frontend/` (Angular project created in Phase 12).
  - Scaffold `migrations/`, `migrations/versions/`.
  - Scaffold `scripts/`.

- [x] **0.3 — Create `env.example`**
  - Include every environment variable documented in Appendix B of the
    architecture, with sensible defaults and comments indicating which are
    required vs. optional.

- [x] **0.4 — Create `requirements.txt`**
  - Pin exact versions for reproducibility (`pip-compile` or manual).
  - Must stay in sync with `pyproject.toml` dependencies.

- [x] **0.5 — Create `.gitignore`**
  - Python: `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `dist/`, `*.egg-info/`.
  - Node: `node_modules/`, `frontend/dist/`.
  - IDE: `.vscode/`, `.idea/`.
  - Environment: `.env` (not `env.example`).
  - Docker: volumes, local overrides.

- [x] **0.6 — Verify editable install**
  - `pip install -e .` succeeds in a fresh venv.
  - All six entry points resolve (even if they just print "not yet implemented").
  - No `sys.path` manipulation anywhere.

- [x] **0.7 — Scaffold `tests/conftest.py`**
  - Create shared pytest fixtures: `settings()` returning an `AppSettings`
    instance, `mock_gateway()` returning a `StubAIGateway`,
    `stub_retrieval()` returning a `StubRetrievalAdapter`.
  - Actual fixture bodies will be fleshed out in later phases; stubs are
    sufficient here.

### Completion Checklist

- [x] `pip install -e .` succeeds; all entry points callable.
- [x] `pytest tests/` runs (zero tests, zero errors).
- [x] Every `__init__.py` exists per architecture Section 5.

---

## [x] Phase 1 — Domain Layer

**Goal:** Implement the pure Python domain layer (`mindforge/domain/`) with
zero I/O and zero framework imports.  This layer is the foundation for
everything else.

### Tasks

- [x] **1.1 — Implement `mindforge/domain/models.py`**
  - [x] 1.1.1 — Define enums: `DocumentStatus` (PENDING, PROCESSING, DONE,
    FAILED), `UploadSource` (API, DISCORD, SLACK, FILE_WATCHER), `BlockType`
    (TEXT, IMAGE, CODE, AUDIO, VIDEO), `CardType` (BASIC, CLOZE, REVERSE),
    `ModelTier` (SMALL, LARGE, VISION), `CostTier` (LOW, MEDIUM, HIGH),
    `DeadlineProfile` (INTERACTIVE, BATCH, BACKGROUND).
  - [x] 1.1.2 — Implement `ContentHash` frozen dataclass with `sha256: str`
    field and `compute(raw_bytes: bytes) -> ContentHash` static method using
    `hashlib.sha256`.
  - [x] 1.1.3 — Implement `LessonIdentity` frozen dataclass with `lesson_id: str`
    and `title: str`.  Include a `resolve()` class method implementing the
    five-step deterministic resolution algorithm (Section 6.2): frontmatter
    `lesson_id` → frontmatter `title` (slugified) → PDF metadata `Title` →
    filename.  **Important I/O boundary:** `resolve()` accepts
    `metadata: dict, filename: str` as already-parsed inputs (constructed by
    parsers in infrastructure layer).  It never reads files or performs I/O
    itself — the domain layer must remain pure.  Validation rules: max 80
    chars, `[a-z0-9\-_]` only, not empty, not in reserved names (`__init__`,
    `index`, `default`).  Raise `LessonIdentityError` on step 5 failure.
  - [x] 1.1.4 — Implement `ContentBlock` dataclass (Section 6.2): `block_type`,
    `content`, `media_ref`, `media_type`, `metadata: dict`, `position: int`.
  - [x] 1.1.5 — Implement `Document` dataclass (Section 6.2): all fields
    including `document_id: UUID`, `knowledge_base_id: UUID`,
    `lesson_identity: LessonIdentity`, `content_hash: ContentHash`,
    `source_filename: str`, `mime_type: str`, `original_content: str`,
    `content_blocks: list[ContentBlock]`, `upload_source: UploadSource`,
    `uploaded_by: UUID | None`, `status: DocumentStatus`, timestamps.
  - [x] 1.1.6 — Implement `KnowledgeBase` dataclass: `kb_id`, `owner_id`,
    `name`, `description`, `created_at`, `document_count`.
  - [x] 1.1.7 — Implement `User` dataclass: `user_id`, `display_name`, `email`,
    `password_hash`, `avatar_url`, `created_at`, `last_login_at`.
  - [x] 1.1.8 — Implement `DocumentArtifact` dataclass (Section 6.2): all
    fields including `step_fingerprints: dict[str, StepCheckpoint]`,
    `completed_step: str | None`.  Sub-structures: `SummaryData`,
    `FlashcardData` (with deterministic `card_id` via
    `sha256(kb_id|lesson_id|card_type|front|back)[:16]`), `ConceptMapData`,
    `ImageDescription`, `FetchedArticle`, `ValidationResult`.
  - [x] 1.1.9 — Implement `StepFingerprint` frozen dataclass: `input_hash`,
    `prompt_version`, `model_id`, `agent_version`.  `compute()` method
    returns `sha256(f"{input_hash}|{prompt_version}|{model_id}|{agent_version}").hexdigest()[:16]`.
  - [x] 1.1.10 — Implement `StepCheckpoint` dataclass: `output_key`,
    `fingerprint`, `completed_at`.
  - [x] 1.1.11 — Implement `CompletionResult` frozen dataclass (Section 8.2):
    `content`, `input_tokens`, `output_tokens`, `model`, `provider`,
    `latency_ms`, `cost_usd`.
  - [x] 1.1.12 — Implement `Interaction`, `InteractionTurn`, `ChatSession`,
    `ChatTurn` dataclasses for audit and chat.
  - [x] 1.1.13 — Implement `ReviewResult` dataclass: `rating` (int 0-5),
    `quality_flag` (optional literal).
  - [x] 1.1.14 — Implement retrieval result types: `ConceptNode`,
    `ConceptNeighborhood`, `RelatedConceptSummary`, `WeakConcept`,
    `RetrievalResult`.
  - [x] 1.1.15 — Implement `TokenBudget` dataclass with
    `available_for_context` property.

- [x] **1.2 — Implement `mindforge/domain/events.py`**
  - [x] 1.2.1 — Define `DomainEvent` base frozen dataclass with a `to_dict()`
    method for JSON serialization.
  - [x] 1.2.2 — Implement all events from Section 6.3: `DocumentIngested`,
    `PipelineStepCompleted`, `ProcessingCompleted`, `ProcessingFailed`,
    `GraphProjectionUpdated`, `QuizSessionStarted`, `QuizAnswerEvaluated`,
    `ReviewRecorded`.  Each carries the fields described in the architecture.

- [x] **1.3 — Implement `mindforge/domain/agents.py`**
  - [x] 1.3.1 — Define `Agent` Protocol with `name` property, `capabilities`
    property, and `async execute(context: AgentContext) -> AgentResult` method.
  - [x] 1.3.2 — Define `AgentCapability` frozen dataclass: `name`,
    `description`, `input_types`, `output_types`, `required_model_tier`,
    `estimated_cost_tier`.
  - [x] 1.3.3 — Define `AgentContext` dataclass: `document_id`, `knowledge_base_id`,
    `artifact`, `gateway`, `retrieval`, `settings`, `tracer`, `metadata`.
  - [x] 1.3.4 — Define `AgentResult` dataclass: `success`, `output_key`,
    `tokens_used`, `cost_usd`, `duration_ms`, `error`.
  - [x] 1.3.5 — Define `ProcessingSettings` dataclass holding chunking configs,
    feature flags, and model-tier mappings used by agents.

- [x] **1.4 — Implement `mindforge/domain/ports.py`**
  - [x] 1.4.1 — Define `DocumentRepository` Protocol with all methods from
    Section 6.4: `save`, `get_by_id`, `get_by_content_hash`, `update_status`,
    `list_by_knowledge_base`.
  - [x] 1.4.2 — Define `ArtifactRepository` Protocol: `save_checkpoint`,
    `load_latest`, `count_flashcards`.
  - [x] 1.4.3 — Define `RetrievalPort` Protocol: `retrieve`,
    `retrieve_concept_neighborhood`, `find_weak_concepts`, `get_concepts`,
    `get_lesson_concepts`.
  - [x] 1.4.4 — Define `AIGateway` Protocol: `complete` (with
    `deadline: DeadlineProfile` parameter), `embed`.
  - [x] 1.4.5 — Define `StudyProgressStore` Protocol: `get_due_cards`,
    `save_review`, `due_count`.
  - [x] 1.4.6 — Define `EventPublisher` Protocol:
    `publish_in_tx(event, connection)`.  The `connection` parameter type is
    `Any` at the domain level (no SQLAlchemy import here).
  - [x] 1.4.7 — Define `InteractionStore` Protocol: `create_interaction`,
    `add_turn`, `get_interaction`, `list_for_user` (returns redacted data),
    `list_unredacted`.
  - [x] 1.4.8 — Define `ExternalIdentityRepository` Protocol: `find_user_id`,
    `link`, `create_user_and_link`.
  - [x] 1.4.9 — Define `QuizSessionStore` Protocol for quiz session
    persistence (Redis or PostgreSQL-backed).
  - [x] 1.4.10 — Define `GraphIndexer` Protocol for writing graph projections.

- [x] **1.5 — Write unit tests for domain layer**
  - [x] 1.5.1 — Tests for `LessonIdentity.resolve()`: all five resolution
    steps, validation rules, reserved name rejection, boundary cases (80 chars,
    empty after sanitization).
  - [x] 1.5.2 — Tests for `ContentHash.compute()`.
  - [x] 1.5.3 — Tests for `FlashcardData.card_id` deterministic generation:
    same inputs produce same ID, different `kb_id` with same content produces
    different ID.
  - [x] 1.5.4 — Tests for `StepFingerprint.compute()`: same inputs produce
    same hash, any input change produces a different hash.
  - [x] 1.5.5 — Tests for `DomainEvent.to_dict()` serialization.
  - [x] 1.5.6 — Tests for `TokenBudget.available_for_context` computation.

### Completion Checklist

- [x] All domain classes importable as `from mindforge.domain.models import ...`.
- [x] All protocols importable as `from mindforge.domain.ports import ...`.
- [x] Zero framework imports in `mindforge/domain/`.
- [x] `pytest tests/unit/domain/` passes with full coverage of validation logic.

> **Completed:** 2026-04-12

---

## [x] Phase 2 — Infrastructure Foundation

**Goal:** Implement configuration loading, database engine setup, PostgreSQL
schema (via Alembic migrations), and all persistence repository adapters.

### Tasks

- [x] **2.1 — Implement `mindforge/infrastructure/config.py`**
  - [x] 2.1.1 — Define `AppSettings` Pydantic `BaseSettings` class loading
    all variables from Appendix B: `database_url`, `redis_url`, `neo4j_uri`,
    `neo4j_username`, `neo4j_password`, `neo4j_database`, model map
    (`model_small`, `model_large`, `model_vision`, `model_embedding`,
    `model_fallback`), auth settings (`discord_client_id`, `discord_client_secret`,
    `discord_redirect_uri`, `jwt_secret`, `jwt_access_token_ttl_minutes`,
    `jwt_refresh_token_ttl_days`, `auth_secure_cookies`, `enable_basic_auth`,
    `bcrypt_cost_factor`), Slack settings (`slack_bot_token`, `slack_app_token`,
    `slack_signing_secret`, `slack_allowed_workspaces`), MinIO settings, feature
    flags (`enable_graph`, `enable_image_analysis`, etc.), limits
    (`max_document_size_mb`, `max_concurrent_pipelines`,
    `max_pending_tasks_per_user`, `pipeline_task_stale_threshold_minutes`,
    `quiz_session_ttl_seconds`), tracing settings, chunking settings
    (`chunk_max_tokens`, `chunk_min_tokens`, `chunk_overlap_tokens`).
  - [x] 2.1.2 — Define `EgressSettings` frozen dataclass (Section 16.3):
    `allow_private_networks`, `allow_nonstandard_ports`, `allowed_protocols`,
    `max_response_bytes`, `timeout_seconds`.
  - [x] 2.1.3 — Implement `load_settings()`, `load_credentials()`,
    `load_auth_settings()`, `load_egress_settings()` functions.  Settings are
    loaded once, validated on startup — never read at request time.
  - [x] 2.1.4 — Implement `validate_settings()` that performs cross-field
    validation (e.g., if `enable_graph=true` then `neo4j_uri` is required).
    Raise descriptive errors on startup, not at request time.
  - [x] 2.1.5 — Implement `model_map` property that returns the logical-name to
    LiteLLM-string mapping: `{"small": settings.model_small, "large": settings.model_large, ...}`.

- [x] **2.2 — Implement `mindforge/infrastructure/db.py`**
  - [x] 2.2.1 — Implement `create_async_engine(database_url)` returning a
    SQLAlchemy `AsyncEngine`.  Configure pool size, pool recycle, echo settings.
  - [x] 2.2.2 — Implement `run_migrations(conn)` that runs Alembic migrations
    programmatically within the provided connection.

- [x] **2.3 — Set up Alembic and create initial migration**
  - [x] 2.3.1 — Initialize Alembic: `migrations/alembic.ini`, `migrations/env.py`.
    Configure to use `DATABASE_URL` from settings.
  - [x] 2.3.2 — Create migration `001_initial_schema.py` implementing the
    **full** SQL schema from Section 7.1: tables `users`,
    `external_identities`, `knowledge_bases`, `documents` (with
    `uq_active_lesson` partial unique index), `document_artifacts`,
    `document_content_blocks`, `media_assets`, `study_progress`,
    `interactions`, `interaction_turns`, `pipeline_tasks`, `outbox_events`
    (with `ix_outbox_unpublished` partial index), `consumer_cursors`,
    `lesson_projections`.  Every column, constraint, default, and index must
    match the architecture exactly.

- [x] **2.4 — Implement `mindforge/infrastructure/persistence/models.py`**
  - [x] 2.4.1 — Define SQLAlchemy 2.0 Mapped classes for every table in the
    schema: `UserModel`, `ExternalIdentityModel`, `KnowledgeBaseModel`,
    `DocumentModel`, `DocumentArtifactModel`, `ContentBlockModel`,
    `MediaAssetModel`, `StudyProgressModel`, `InteractionModel`,
    `InteractionTurnModel`, `PipelineTaskModel`, `OutboxEventModel`,
    `ConsumerCursorModel`, `LessonProjectionModel`.
  - [x] 2.4.2 — Map relationships: `User.external_identities`,
    `KnowledgeBase.documents`, `Document.artifacts`, etc.

- [x] **2.5 — Implement `mindforge/infrastructure/persistence/document_repo.py`**
  - [x] 2.5.1 — Implement `PostgresDocumentRepository` fulfilling
    `DocumentRepository` protocol.
  - [x] 2.5.2 — `save(document, connection)` — INSERT into `documents` within
    the caller's transaction.
  - [x] 2.5.3 — `get_by_id(document_id)` — SELECT with domain model mapping.
  - [x] 2.5.4 — `get_by_content_hash(kb_id, hash)` — dedup check scoped to
    knowledge base.
  - [x] 2.5.5 — `update_status(document_id, status)`.
  - [x] 2.5.6 — `list_by_knowledge_base(kb_id, ...)` — paginated listing with
    filters.

- [x] **2.6 — Implement `mindforge/infrastructure/persistence/artifact_repo.py`**
  - [x] 2.6.1 — `save_checkpoint(artifact, connection)` — UPSERT artifact JSON,
    per-step fingerprints, and completed_step within caller's transaction.
  - [x] 2.6.2 — `load_latest(document_id)` — load highest-version artifact,
    deserialize into `DocumentArtifact`.
  - [x] 2.6.3 — `count_flashcards(kb_id, lesson_id)`.

- [x] **2.7 — Implement `mindforge/infrastructure/persistence/interaction_repo.py`**
  - [x] 2.7.1 — `create_interaction`, `add_turn`, `get_interaction`.
  - [x] 2.7.2 — `list_for_user(user_id)` — must enforce redaction policy:
    strip `reference_answer`, `grounding_context`, `raw_prompt`,
    `raw_completion` from `output_data`, and hide `cost` for non-admin users.
    Redaction happens in the store, not the router (defense in depth).
  - [x] 2.7.3 — `list_unredacted()` — admin-only, returns full data.

- [x] **2.8 — Implement `mindforge/infrastructure/persistence/identity_repo.py`**
  - [x] 2.8.1 — `find_user_id(provider, external_id)` — lookup.
  - [x] 2.8.2 — `link(user_id, provider, external_id, email, metadata)` —
    INSERT into `external_identities`.
  - [x] 2.8.3 — `create_user_and_link(provider, external_id, display_name, ...)`
    — atomically create `users` + `external_identities` rows, return `user_id`.

- [x] **2.9 — Implement `mindforge/infrastructure/persistence/study_progress_repo.py`**
  - [x] 2.9.1 — `get_due_cards(user_id, kb_id, today)` — SELECT cards where
    `next_review <= today`.
  - [x] 2.9.2 — `save_review(user_id, kb_id, card_id, result)` — UPSERT with
    SM-2 updated fields.
  - [x] 2.9.3 — `due_count(user_id, kb_id, today)`.

- [x] **2.10 — Implement `mindforge/infrastructure/persistence/read_models.py`**
  - [x] 2.10.1 — `upsert_lesson_projection(kb_id, lesson_id, data)` — UPSERT
    into `lesson_projections`.
  - [x] 2.10.2 — `list_lessons(kb_id)` — return projections for lesson list
    endpoint.

- [x] **2.11 — Write integration tests for persistence layer**
  - [x] 2.11.1 — Test document CRUD: save, get_by_id, dedup check, list.
  - [x] 2.11.2 — Test artifact checkpoint save/load round-trip.
  - [x] 2.11.3 — Test interaction redaction in `list_for_user`.
  - [x] 2.11.4 — Test identity repo: create_user_and_link, find_user_id, link.
  - [x] 2.11.5 — Test study progress SM-2 update cycle.
  - [x] 2.11.6 — Test lesson projection upsert/list.

### Completion Checklist

- [x] `load_settings()` loads and validates all `.env` variables.
- [x] `alembic upgrade head` creates the full schema.
- [x] All repository implementations pass integration tests with real PostgreSQL.
- [x] Redaction policy enforced in `InteractionStore.list_for_user()`.

> **Completed:** 2026-04-12

---

## [x] Phase 3 — AI Gateway

**Goal:** Implement the LiteLLM-backed AI Gateway adapter with retry, circuit
breaker, cost tracking, deadline profiles, and fallback chains.

### Tasks

- [x] **3.1 — Implement `mindforge/infrastructure/ai/gateway.py`**
  - [x] 3.1.1 — Implement `LiteLLMGateway` class fulfilling `AIGateway` protocol.
    Constructor accepts: `default_model`, `model_map: dict[str, str]`,
    `fallback_models: list[str]`, `timeout_seconds`, `max_retries`,
    `tracer: LangfuseAdapter | None`.
  - [x] 3.1.2 — Implement `complete(model, messages, temperature, response_format,
    deadline)` — resolve logical model name via `model_map`, call
    `litellm.acompletion(...)`, wrap result in `CompletionResult`.  Track
    `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd` (record 0.0
    for local models like Ollama).
  - [x] 3.1.3 — Implement deadline profile enforcement: `INTERACTIVE` = 15s,
    `BATCH` = 180s, `BACKGROUND` = 300s.  Raise `DeadlineExceeded` if total
    time exceeds budget.
  - [x] 3.1.4 — Implement retry with exponential backoff + jitter using
    LiteLLM's built-in retry mechanism, supplemented by a custom wrapper for
    circuit breaker logic.
  - [x] 3.1.5 — Implement circuit breaker: open after 5 consecutive failures,
    half-open after 60s cooldown.  When open, immediately fail to fallback
    model.
  - [x] 3.1.6 — Implement provider fallback chain: on primary failure (after
    retries), try each fallback model in order.
  - [x] 3.1.7 — Record the **actually used model** (not the requested one) in
    `CompletionResult.model` so that `StepFingerprint` reflects fallback usage.
  - [x] 3.1.8 — Implement `Retry-After` header respect for rate-limited
    responses.

- [x] **3.2 — Implement `mindforge/infrastructure/ai/embeddings.py`**
  - [x] 3.2.1 — Implement `embed(model, texts)` method on the gateway (or as a
    separate adapter) — call `litellm.aembedding(...)`, return
    `list[list[float]]`.
  - [x] 3.2.2 — Handle batching: if `texts` exceeds the provider's max batch
    size, split and concatenate.

- [x] **3.3 — Implement `DeadlineExceeded` exception**
  - Define in `mindforge/domain/` (or a shared exceptions module).  Callers
    decide how to handle: degraded response for interactive, retry for batch.

- [x] **3.4 — Implement `StubAIGateway` for tests**
  - In `tests/conftest.py`: a test double returning deterministic responses
    from a preconfigured dict keyed by prompt content or model name.

- [x] **3.5 — Write unit tests for AI Gateway**
  - [x] 3.5.1 — Test logical model name resolution via `model_map`.
  - [x] 3.5.2 — Test `CompletionResult` construction with all fields.
  - [x] 3.5.3 — Test deadline enforcement (mock slow responses).
  - [x] 3.5.4 — Test circuit breaker state transitions.
  - [x] 3.5.5 — Test fallback chain invocation on primary failure.

- [x] **3.6 — Implement `StdoutTracingAdapter` (early observability stub)**
  - [x] 3.6.1 — Create `mindforge/infrastructure/tracing/stdout_adapter.py`
    implementing the same `TracingAdapter` protocol that the full
    `LangfuseAdapter` (Phase 16) will fulfill.  On each `complete()` call,
    log model name, token counts, `cost_usd`, and `latency_ms` to stdout
    using structured logging (`logging.getLogger`).
  - [x] 3.6.2 — Wire into `LiteLLMGateway` as the default tracer when
    `LANGFUSE_PUBLIC_KEY` is not configured.
  - **Rationale:** `CompletionResult` already carries `cost_usd` and
    `latency_ms`.  During Phase 6 agent development, having live cost
    visibility in the terminal is invaluable for catching runaway token
    usage.  The full Langfuse integration (Phase 16) replaces this adapter
    at composition-root level — no code changes needed in the gateway.

### Completion Checklist

- [x] Gateway correctly resolves logical model names to LiteLLM strings.
- [x] Deadline profiles enforce correct timeouts.
- [x] Circuit breaker opens/closes as specified.
- [x] Fallback chain works and records the actually-used model.
- [x] `StubAIGateway` available for all downstream tests.

> **Completed:** 2026-04-14

---

## [x] Phase 4 — Document Parsing and Ingestion

**Goal:** Implement the parser registry, all four document format parsers, the
upload sanitizer, the egress policy, the chunking strategy, and the ingestion
service with deduplication and revision management.

### Tasks

- [x] **4.1 — Implement `mindforge/infrastructure/security/upload_sanitizer.py`**
  - [x] 4.1.1 — Implement `UploadSanitizer` class: sanitize filename (strip
    path components, reject absolute paths, reject drive-qualified paths,
    reject path traversal sequences `..`), validate file extension against
    allowed set, enforce byte size limit per format.
  - [x] 4.1.2 — All filenames, external URLs, and image URLs are untrusted.
    Final writes only inside designated storage directories.

- [x] **4.2 — Implement `mindforge/infrastructure/security/egress_policy.py`**
  - [x] 4.2.1 — Implement `EgressPolicy` class initialized from
    `EgressSettings`.  `validate_url(url)` resolves the hostname, blocks
    private IPs (`10.x`, `172.16-31.x`, `192.168.x`), loopback (`127.x`,
    `::1`), link-local (`169.254.x`), metadata service IPs (`169.254.169.254`),
    blocks non-allowlisted schemes (only `http`/`https` by default), blocks
    non-standard ports if configured.
  - [x] 4.2.2 — Implement `fetch(url)` method: validates URL, follows redirects
    with re-validation at each hop, enforces `max_response_bytes` and
    `timeout_seconds`, sends `User-Agent: MindForge/2.0` header.
  - [x] 4.2.3 — Raise `EgressViolation` on any policy breach.

- [x] **4.3 — Implement `mindforge/infrastructure/parsing/registry.py`**
  - [x] 4.3.1 — Implement `ParserRegistry` class: `register(mime_type, parser)`,
    `get(mime_type) -> DocumentParser` (raises `UnsupportedFormatError`).
  - [x] 4.3.2 — Define `DocumentParser` Protocol: `parse(raw_bytes, filename) ->
    ParsedDocument`.
  - [x] 4.3.3 — Define `ParsedDocument` dataclass: `text_content`, `metadata`,
    `content_blocks`, `embedded_images`.

- [x] **4.4 — Implement format parsers**
  - [x] 4.4.1 — `MarkdownParser` (`markdown_parser.py`): extract frontmatter
    via `python-frontmatter`, text content, first heading, embedded image
    references.  Handle YAML frontmatter fields `lesson_id`, `title`.
  - [x] 4.4.2 — `PdfParser` (`pdf_parser.py`): extract text via PyMuPDF,
    extract PDF metadata `Title`, extract embedded images, enforce page limit.
  - [x] 4.4.3 — `DocxParser` (`docx_parser.py`): extract text via
    `python-docx`, extract document properties, extract embedded images.
  - [x] 4.4.4 — `TxtParser` (`txt_parser.py`): plain text extraction, no
    metadata, no images.

- [x] **4.5 — Implement heading-aware chunking**
  - [x] 4.5.1 — Implement `Chunker` class (in `mindforge/infrastructure/parsing/`
    or `mindforge/application/`): heading-aware splitting as described in
    Section 10.5.  Configurable via `CHUNK_MAX_TOKENS`, `CHUNK_MIN_TOKENS`,
    `CHUNK_OVERLAP_TOKENS`.
  - [x] 4.5.2 — For Markdown: split on `##` and `###` headings → paragraph
    boundaries → sentence boundaries.  Merge small chunks.  Apply overlap.
  - [x] 4.5.3 — For unstructured text: fall back to paragraph-based splitting.
  - [x] 4.5.4 — Each chunk gets deterministic ID: `sha256(lesson_id|position|text)[:16]`.
  - [x] 4.5.5 — Each chunk carries `heading_context` (breadcrumb of heading
    hierarchy above it).

- [x] **4.6 — Implement `mindforge/application/ingestion.py`**
  - [x] 4.6.1 — Implement `IngestionService` class with constructor accepting
    `DocumentRepository`, `DocumentSanitizer`, `DocumentParserRegistry`,
    `PipelineTaskStore`, `EventPublisher`.
  - [x] 4.6.2 — Implement `ingest(raw_bytes, filename, knowledge_base_id,
    upload_source, uploaded_by)` method executing the 13-step transaction
    from Section 10.1: sanitize filename → validate size/format → compute
    content hash → dedup check → pending task limit check
    (`MAX_PENDING_TASKS_PER_USER`, reject with 429) → parse → resolve
    lesson identity → deactivate previous revision → INSERT document →
    INSERT pipeline_task → INSERT outbox event → COMMIT.
  - [x] 4.6.3 — All steps within a single PostgreSQL transaction.
  - [x] 4.6.4 — Return `IngestionResult` with `document_id`, `task_id`,
    `lesson_id`, `revision`.

- [x] **4.7 — Implement size and cost guards (Section 10.7)**
  - [x] 4.7.1 — Byte size limit per format (configurable, default 10 MB).
  - [x] 4.7.2 — Estimated token limit: character count × factor, reject
    if exceeded.
  - [x] 4.7.3 — PDF page limit (configurable).

- [x] **4.8 — Write unit tests for parsing and ingestion**
  - [x] 4.8.1 — Tests for `UploadSanitizer`: path traversal, absolute paths,
    drive-qualified paths, valid filenames.
  - [x] 4.8.2 — Tests for `EgressPolicy`: private IPs, loopback, link-local,
    metadata service, allowed schemes, redirect re-validation.
  - [x] 4.8.2a — **Security invariant test:** Verify all outbound fetches
    (article fetcher, image URLs) go through `EgressPolicy` — no direct
    `httpx.get()` or similar calls bypass the policy.  This is a build-time
    guarantee, not deferred to Phase 18.
  - [x] 4.8.3 — Tests for each parser with sample documents.
  - [x] 4.8.4 — Tests for chunking: heading-aware splitting, overlap,
    merge small chunks, deterministic IDs, heading context.
  - [x] 4.8.5 — Tests for `LessonIdentity` resolution through the parsers
    (frontmatter, PDF metadata, filename).
  - [x] 4.8.6 — Tests for `IngestionService`: dedup rejection, revision
    creation, pending task limit, full transactional flow.

### Completion Checklist

- [x] All four parsers extract text and metadata correctly.
- [x] Chunker produces deterministic, heading-aware chunks with overlap.
- [x] Ingestion flow handles dedup, revision, task submission in one transaction.
- [x] Security guards reject path traversal, SSRF, and oversized uploads.
- [x] All outbound fetches are verified to go through `EgressPolicy`.

---

## [x] Phase 5 — Agent Framework and Pipeline Orchestration

**Goal:** Implement the agent registry, orchestration graph, pipeline
orchestrator with DAG-aware checkpointing and fingerprint invalidation, and
the pipeline worker process.

### Tasks

- [x] **5.1 — Implement `AgentRegistry`**
  - [x] 5.1.1 — In `mindforge/agents/__init__.py` or a dedicated module:
    `AgentRegistry` class with `register(agent)`, `get(name)`, `all()` methods.
    Open/Closed — adding an agent never modifies the orchestrator.

- [x] **5.2 — Implement `OrchestrationGraph`**
  - [x] 5.2.1 — Define `GraphNode` dataclass: `agent_name`, `output_key`,
    `dependencies: list[str]` (names of upstream nodes).
  - [x] 5.2.2 — Implement `OrchestrationGraph` class: holds a list of
    `GraphNode`s, provides `topological_order()` method (Kahn's algorithm or
    DFS), `dependencies(step_name) -> list[str]`.
  - [x] 5.2.3 — Define the default pipeline graph matching the DAG in
    Section 9.4: `DocumentParser` → `RelevanceGuard` → (`ImageAnalyzer` ||
    `Preprocessor`) → `ArticleFetcher` → `Summarizer` →
    (`FlashcardGenerator` || `ConceptMapper`) → `Validation` →
    `GraphIndexer` → `ReadModelPublisher`.

- [x] **5.3 — Implement `mindforge/application/pipeline.py`**
  - [x] 5.3.1 — Implement `PipelineOrchestrator` class (Section 9.5):
    constructor accepts `AgentRegistry`, `OrchestrationGraph`,
    `ArtifactRepository`, `EventPublisher`, `InteractionStore`.
  - [x] 5.3.2 — Implement `run(document_id, artifact, context, force=False)`:
    iterate topological order, for each step: check fingerprint → execute or
    skip → flush checkpoint → publish `PipelineStepCompleted` event → record
    interaction turn.
  - [x] 5.3.3 — Implement `_compute_fingerprint(step, context)`: build
    `StepFingerprint` from upstream artifact fields hash, prompt version,
    model ID, agent version.
  - [x] 5.3.4 — Implement checkpoint skip logic: skip only if (a) output field
    is populated AND (b) stored fingerprint matches current fingerprint.
    `force=True` bypasses all checkpoints.
  - [x] 5.3.5 — Implement `invalidated_steps(graph, changed_step)`: return all
    downstream dependents via DAG traversal.
  - [x] 5.3.6 — Implement transactional flush: after each LLM-producing step,
    save artifact checkpoint AND outbox event in the **same** database
    transaction.

- [x] **5.4 — Implement `mindforge/cli/pipeline_runner.py`**
  - [x] 5.4.1 — Implement `PipelineWorker` class (Section 11.5): `worker_id`,
    `db_engine`, `orchestrator`, `event_publisher`, `max_concurrent`.
  - [x] 5.4.2 — Implement `run_forever()`: poll `pipeline_tasks` WHERE
    status='pending' with `FOR UPDATE SKIP LOCKED`, claim and execute.
  - [x] 5.4.3 — Implement `claim_task()`: atomic claim via
    `SELECT ... FOR UPDATE SKIP LOCKED`.
  - [x] 5.4.4 — Implement `execute_task(task)`: load document, load/create
    artifact, build `AgentContext`, run orchestrator, update task status
    (done/failed).
  - [x] 5.4.5 — Implement stale task recovery on startup: reclaim tasks where
    `status='running'` AND `claimed_at` older than
    `PIPELINE_TASK_STALE_THRESHOLD_MINUTES`.  Mark as failed after 3 reclaim
    attempts.
  - [x] 5.4.6 — Implement `shutdown(timeout_seconds)`: graceful drain on
    SIGTERM.
  - [x] 5.4.7 — Implement `main()` entry point: composition root wiring all
    dependencies (settings, DB, gateway, registry, graph, repos, publisher).

- [x] **5.5 — Write unit tests for orchestration**
  - [x] 5.5.1 — Test topological ordering of the default graph.
  - [x] 5.5.2 — Test fingerprint computation and comparison.
  - [x] 5.5.3 — Test checkpoint skip logic (fingerprint match vs. mismatch).
  - [x] 5.5.4 — Test DAG-aware invalidation cascade.
  - [x] 5.5.5 — Test `force=True` bypasses all checkpoints.
  - [x] 5.5.6 — Test pipeline worker claim/execute/stale-recovery flow (with
    mock DB).

### Completion Checklist

- [x] Orchestrator executes the agent graph in correct topological order.
- [x] Checkpoint skip works when fingerprint matches; invalidation cascades.
- [x] Pipeline worker claims tasks, executes, and handles stale recovery.
- [x] `mindforge-pipeline` entry point is callable.

> **Completed:** 2026-04-15

---

## [x] Phase 6 — Concrete Processing Agents

**Goal:** Implement all processing agents listed in Section 9.3.  Each agent
implements the `Agent` protocol, declares `__version__`, and is registered in
the `AgentRegistry`.

### Tasks

- [x] **6.1 — Implement prompt templates**
  - [x] 6.1.1 — `mindforge/infrastructure/ai/prompts/preprocessor.py`: system
    prompt for content cleaning (remove headers/footers, TOC, boilerplate).
    Version-tagged string constant.
  - [x] 6.1.2 — `prompts/image_analyzer.py`: system prompt for vision model
    to describe images/diagrams in educational context.
  - [x] 6.1.3 — `prompts/summarizer.py`: produce structured summary with
    `key_concepts` (list of `{name, definition}`), `key_facts` (list of
    factual statements), `section_summaries`.
  - [x] 6.1.4 — `prompts/flashcard_gen.py`: generate flashcards of types
    BASIC, CLOZE, REVERSE from summary.
  - [x] 6.1.5 — `prompts/concept_mapper.py`: generate concept map with
    `concepts` (list of `{key, name, definition}`) and `relations` (list of
    `{source_key, target_key, label, description}`).
  - [x] 6.1.6 — `prompts/quiz_generator.py`: generate quiz question from
    concept neighborhood context.
  - [x] 6.1.7 — `prompts/quiz_evaluator.py`: evaluate answer against reference
    answer and grounding context.

- [x] **6.2 — Implement `mindforge/agents/preprocessor.py`**
  - [x] 6.2.1 — `PreprocessorAgent` with `__version__ = "1.0.0"`,
    model tier SMALL.
  - [x] 6.2.2 — Takes `original_content` from artifact, produces
    `cleaned_content`.  Remove noise sections, normalize formatting.

- [x] **6.3 — Implement `mindforge/agents/image_analyzer.py`**
  - [x] 6.3.1 — `ImageAnalyzerAgent` with `__version__ = "1.0.0"`,
    model tier VISION.
  - [x] 6.3.2 — Takes `embedded_images` from parsed document, produces
    `image_descriptions: list[ImageDescription]`.

- [x] **6.4 — Implement `mindforge/agents/relevance_guard.py`**
  - [x] 6.4.1 — `RelevanceGuardAgent` with `__version__ = "1.0.0"`,
    model tier SMALL.
  - [x] 6.4.2 — Extract existing concepts from KB graph (via
    `context.retrieval`).  Compare document content against KB profile.  For
    empty KBs (first document), always accept.  Below threshold → reject.
  - [x] 6.4.3 — Produces `validation_result` with relevance score and
    accept/reject decision.

- [x] **6.5 — Implement `mindforge/agents/article_fetcher.py`**
  - [x] 6.5.1 — `ArticleFetcherAgent` with `__version__ = "1.0.0"`,
    model tier SMALL.
  - [x] 6.5.2 — Extract Markdown links from `cleaned_content` (exclude code
    blocks and image URLs).
  - [x] 6.5.3 — Classify each URL using LLM (SMALL): `article | api_docs |
    video | social | irrelevant`.
  - [x] 6.5.4 — Fetch `article` and `api_docs` URLs via `EgressPolicy.fetch()`.
    HTTP timeout 10s, max body 1 MB.
  - [x] 6.5.5 — Produce `fetched_articles: list[FetchedArticle]`.  Cache by
    URL hash.

- [x] **6.6 — Implement `mindforge/agents/summarizer.py`**
  - [x] 6.6.1 — `SummarizerAgent` with `__version__ = "1.0.0"`,
    model tier LARGE.
  - [x] 6.6.2 — Input: `cleaned_content` + `image_descriptions` +
    `fetched_articles` (ok status only) + prior concepts from graph context
    (injected via `context.metadata` by the orchestrator).
  - [x] 6.6.3 — Produce `summary: SummaryData` with `key_concepts`,
    `key_facts`, `section_summaries`.
  - [x] 6.6.4 — Use `response_format` for structured JSON output.

- [x] **6.7 — Implement `mindforge/agents/flashcard_generator.py`**
  - [x] 6.7.1 — `FlashcardGeneratorAgent` with `__version__ = "1.0.0"`,
    model tier LARGE.
  - [x] 6.7.2 — Input: `summary`, `cleaned_content`.
  - [x] 6.7.3 — Produce `flashcards: list[FlashcardData]` with deterministic
    `card_id` using `sha256(kb_id|lesson_id|card_type|front|back)[:16]`.
  - [x] 6.7.4 — Generate a mix of BASIC, CLOZE, and REVERSE card types.

- [x] **6.8 — Implement `mindforge/agents/concept_mapper.py`**
  - [x] 6.8.1 — `ConceptMapperAgent` with `__version__ = "1.0.0"`,
    model tier LARGE.
  - [x] 6.8.2 — Input: `summary`, `cleaned_content`.
  - [x] 6.8.3 — Produce `concept_map: ConceptMapData` with concepts
    (key, name, definition, normalized_key via `dedupe_key()`) and relations
    (source_key, target_key, label, description).

- [x] **6.9 — Implement `mindforge/agents/quiz_generator.py`**
  - [x] 6.9.1 — `QuizGeneratorAgent` with `__version__ = "1.0.0"`,
    model tier LARGE.
  - [x] 6.9.2 — Used at quiz runtime (not in the pipeline).  Input:
    concept neighborhood context from Graph RAG.  Produces a quiz question
    with reference answer.

- [x] **6.10 — Implement `mindforge/agents/quiz_evaluator.py`**
  - [x] 6.10.1 — `QuizEvaluatorAgent` with `__version__ = "1.0.0"`,
    model tier LARGE.
  - [x] 6.10.2 — Evaluates user answer against stored `reference_answer` and
    `grounding_context`.  Reuses the stored reference answer — never
    regenerates.
  - [x] 6.10.3 — Returns score, feedback, and detailed explanation.

- [x] **6.11 — Register all agents in `AgentRegistry`**
  - In the pipeline worker's composition root and other surfaces that need
    agents.

- [x] **6.12 — Write unit tests for agents**
  - [x] 6.12.1 — Test each agent's prompt assembly (correct input fields used).
  - [x] 6.12.2 — Test response parsing (JSON → domain objects).
  - [x] 6.12.3 — Test error handling (malformed LLM output → graceful failure).
  - [x] 6.12.4 — Test flashcard ID determinism.
  - [x] 6.12.5 — Test article fetcher URL extraction and classification.

### Completion Checklist

- [x] All 8 pipeline agents + 2 quiz agents implemented and registered.
- [x] Each agent declares `__version__`.
- [x] All agents pass unit tests with `StubAIGateway`.

> **Completed:** 2026-04-15

---

## [x] Phase 7 — Neo4j Graph Layer

> **Completed:** 2026-04-15

**Goal:** Implement the Neo4j graph adapter, indexer, retrieval port, and
Cypher queries for concept graph management, Graph RAG, and weak concept
detection.

### Tasks

- [x] **7.1 — Implement `mindforge/infrastructure/graph/neo4j_context.py`**
  - [x] 7.1.1 — `Neo4jContext` class: create and manage `AsyncDriver` from
    `neo4j` Python driver.  Accept `neo4j_uri`, `neo4j_password`,
    `neo4j_database`.  Provide `session()` context manager and `close()`.

- [x] **7.2 — Implement `mindforge/infrastructure/graph/cypher_queries.py`**
  - [x] 7.2.1 — Named Cypher query constants for all graph operations:
    `MERGE_KNOWLEDGE_BASE`, `MERGE_LESSON`, `MERGE_CONCEPT`,
    `MERGE_FACT`, `MERGE_CHUNK`, `CREATE_ASSERTS_CONCEPT`,
    `CREATE_ASSERTS_RELATION`, `DELETE_LESSON_ENTITIES` (the cleanup query
    from Section 7.2), `DELETE_ORPHANED_CONCEPTS`,
    `REBUILD_RELATES_TO_EDGES`, `RETRIEVE_CONCEPT_NEIGHBORHOOD`
    (Section 7.2 — the Cypher from Graph RAG), `FIND_WEAK_CONCEPTS`
    (the quiz targeting query), `FULLTEXT_SEARCH`, `VECTOR_SEARCH`.
  - [x] 7.2.2 — All write queries use `UNWIND` batches.
  - [x] 7.2.3 — All queries filter by `kb_id` for knowledge base isolation.

- [x] **7.3 — Implement `mindforge/infrastructure/graph/neo4j_indexer.py`**
  - [x] 7.3.1 — `Neo4jGraphIndexer` fulfilling `GraphIndexer` protocol.
  - [x] 7.3.2 — `index_lesson(kb_id, lesson_id, artifact)`: execute the
    lesson revision lifecycle from Section 7.2 — (1) delete old lesson
    entities, (2) clean up orphaned concepts, (3) MERGE new lesson +
    concepts + facts + chunks + relations via UNWIND batches, (4) rebuild
    `RELATES_TO` derived edges, (5) set embeddings on chunks.
  - [x] 7.3.3 — Deterministic node IDs: `Fact.id = sha256(lesson_id|text)[:16]`,
    `Chunk.id = sha256(lesson_id|position|text)[:16]`.
  - [x] 7.3.4 — Concept normalization via `dedupe_key()` function:
    consistent `normalized_key` used across all write paths.

- [x] **7.4 — Implement `mindforge/infrastructure/graph/neo4j_retrieval.py`**
  - [x] 7.4.1 — `Neo4jRetrievalAdapter` fulfilling `RetrievalPort` protocol.
  - [x] 7.4.2 — `retrieve(query, kb_id, ...)`: hybrid retrieval —
    (1) extract concept mentions from query (keyword/NER matching),
    (2) for each matched concept: `retrieve_concept_neighborhood()`,
    (3) if no concepts matched: fall back to full-text → vector similarity,
    (4) assemble context from neighborhoods + supplementary chunks.
  - [x] 7.4.3 — `retrieve_concept_neighborhood(concept_key, kb_id, depth=2)`:
    execute the Cypher query from Section 7.2, return `ConceptNeighborhood`.
  - [x] 7.4.4 — `find_weak_concepts(user_id, kb_id, limit=5)`: execute
    the Graph-Based Quiz Question Selection query from Section 7.2 — concepts
    with low `ease_factor` and high graph degree.
  - [x] 7.4.5 — `get_concepts(kb_id)`, `get_lesson_concepts(kb_id, lesson_id)`.

- [x] **7.5 — Create Neo4j indexes and constraints**
  - [x] 7.5.1 — Create uniqueness constraints on `Lesson.id + kb_id`,
    `Concept.key + kb_id`, deterministic node IDs.
  - [x] 7.5.2 — Create full-text index on `Chunk.text`, `Fact.text`.
  - [x] 7.5.3 — Create vector index on `Chunk.embedding` (Neo4j 5.x vector
    index).

- [x] **7.6 — Implement `StubRetrievalAdapter` for tests**
  - In `tests/conftest.py`: returns preconfigured concept neighborhoods and
    weak concepts.

- [x] **7.7 — Write integration tests for graph layer**
  - [x] 7.7.1 — Test lesson indexing: concepts, facts, chunks created with
    correct IDs.
  - [x] 7.7.2 — Test lesson revision cleanup: old entities deleted, orphaned
    concepts removed.
  - [x] 7.7.3 — Test concept neighborhood retrieval: correct graph traversal.
  - [x] 7.7.4 — Test weak concept detection query.
  - [x] 7.7.5 — Test MERGE idempotency: re-index same data → no duplicates.

### Completion Checklist

- [x] Graph indexer writes correct nodes/edges with UNWIND batches.
- [x] Lesson revision cleanup removes stale data.
- [x] Retrieval follows graph-first → full-text → vector priority.
- [x] All graph queries scoped to `kb_id`.

---

## [x] Phase 8 — Event System

**Goal:** Implement the transactional outbox, outbox relay, durable consumers
(Graph Indexer, Audit Logger), and ephemeral subscriber infrastructure.

### Tasks

- [x] **8.1 — Implement `mindforge/infrastructure/events/outbox_publisher.py`**
  - [x] 8.1.1 — `OutboxEventPublisher` fulfilling `EventPublisher` protocol.
  - [x] 8.1.2 — `publish_in_tx(event, connection)`: INSERT into `outbox_events`
    within the caller's in-flight transaction.  Generate `event_id`, serialize
    event via `to_dict()`, store as JSONB `payload`.
  - [x] 8.1.3 — After transaction commit (at the call site), issue
    `pg_notify('outbox')` for fast relay wake.

- [x] **8.2 — Implement `mindforge/infrastructure/events/outbox_relay.py`**
  - [x] 8.2.1 — `OutboxRelay` class: poll `outbox_events WHERE NOT published
    ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED`.
  - [x] 8.2.2 — For each row: build envelope `{event_id, event_type, payload,
    created_at}`, publish to Redis Pub/Sub channel `events:{event_type}`,
    then UPDATE `published=TRUE, published_at=now()`.
  - [x] 8.2.3 — Listen for `pg_notify('outbox')` for immediate wake; fall back
    to polling with configurable interval (default 1s).
  - [x] 8.2.4 — `start()` and `stop()` lifecycle methods for integration with
    API lifespan.

- [x] **8.3 — Implement `mindforge/infrastructure/events/durable_consumer.py`**
  - [x] 8.3.1 — `DurableEventConsumer` abstract base class: poll
    `outbox_events WHERE sequence_num > cursor ORDER BY sequence_num LIMIT 100`,
    call `handle()` for each event, advance cursor in `consumer_cursors` table.
  - [x] 8.3.2 — `GraphIndexerConsumer(DurableEventConsumer)`: on
    `ProcessingCompleted` events, load artifact from PostgreSQL and call
    `Neo4jGraphIndexer.index_lesson()`.
  - [x] 8.3.3 — `AuditLoggerConsumer(DurableEventConsumer)`: record relevant
    events in `interaction_turns`.
  - [x] 8.3.4 — Both consumers handle events idempotently (keyed by `event_id`).

- [x] **8.4 — Implement outbox retention**
  - [x] 8.4.1 — Background task (in pipeline worker or standalone cron):
    `DELETE FROM outbox_events WHERE published = TRUE AND published_at <
    now() - interval '7 days'`.  Never delete unpublished events.

- [x] **8.5 — Write tests for event system**
  - [x] 8.5.1 — Test outbox publisher writes event within caller's transaction.
  - [x] 8.5.2 — Test outbox relay publishes and marks events as delivered.
  - [x] 8.5.3 — Test durable consumer advances cursor correctly.
  - [x] 8.5.4 — Test idempotency: same event delivered twice → no duplicate
    processing.
  - [x] 8.5.5 — Test relay with `FOR UPDATE SKIP LOCKED` prevents
    double-publishing.

### Completion Checklist

- [x] Events are written in the same transaction as state changes.
- [x] Relay publishes envelopes to Redis Pub/Sub.
- [x] Durable consumers process events with at-least-once delivery.
- [x] No event is lost on crash; subscribers are idempotent.

> **Completed:** 2026-04-18

---

## [x] Phase 9 — API Layer (FastAPI)

**Goal:** Implement the FastAPI application factory, composition root, auth
system (Discord OAuth + email/password + JWT), all routers, middleware, and
SPA serving.

### Tasks

- [x] **9.1 — Implement `mindforge/api/main.py`**
  - [x] 9.1.1 — `lifespan()` async context manager implementing the full
    composition root from Section 11.2: load settings → validate → create
    DB engine → run migrations (with advisory lock) → create Neo4j context →
    create AI Gateway → connect Redis (with fallback warning) → create
    outbox publisher → start outbox relay (if Redis) → create all
    repositories → create quiz session store (Redis or PG fallback) →
    create ingestion service → wire onto `app.state`.
  - [x] 9.1.2 — `create_app()`: FastAPI instance with lifespan, include all
    routers, add middleware.
  - [x] 9.1.3 — `run()` function for `mindforge-api` entry point: call
    `uvicorn.run(app, host="0.0.0.0", port=8080)`.

- [x] **9.2 — Implement `mindforge/api/deps.py`**
  - [x] 9.2.1 — FastAPI `Depends()` providers for `get_settings()`,
    `get_db_engine()`, `get_gateway()`, `get_doc_repo()`,
    `get_artifact_repo()`, `get_retrieval()`, `get_quiz_sessions()`,
    `get_event_publisher()`, `get_interaction_store()`,
    `get_study_progress()`, `get_ingestion()`, `get_current_user()`.
  - All providers read from `request.app.state` — no module globals.

- [x] **9.3 — Implement `mindforge/api/auth.py`**
  - [x] 9.3.1 — Define `AuthProvider` Protocol: `name` property,
    `get_authorization_url(state)`, `exchange_code(code) -> UserInfo`.
  - [x] 9.3.2 — Implement `DiscordAuthProvider`: OAuth 2.0 flow with Discord
    API.  Validate `state` on every callback (CSRF protection).
  - [x] 9.3.3 — Implement `BasicAuthProvider`: `register(email, password,
    display_name)` — hash with bcrypt (cost ≥ 12), `authenticate(email,
    password)` — verify hash.
  - [x] 9.3.4 — Implement JWT issuing: access token (configurable TTL, default
    60 min) + refresh token (30 days) stored in `HttpOnly`, `Secure`,
    `SameSite=Lax` cookies.  `Secure` flag configurable for local dev.
  - [x] 9.3.5 — Implement auto-refresh: if access token expires within 5 min,
    issue new one in response `Set-Cookie`.
  - [x] 9.3.6 — Implement refresh token rotation: each use issues new refresh
    token and invalidates the old one.
  - [x] 9.3.7 — Implement account linking flow: logged-in user can link
    additional providers; reject if `(provider, external_id)` already linked
    to a different user.
  - [x] 9.3.8 — Implement `IdentityResolver` shared between API, Discord, and
    Slack: resolve external platform ID to internal UUID; auto-provision user
    on first contact.
  - [x] 9.3.9 — Rate-limit registration endpoint.

- [x] **9.4 — Implement `mindforge/api/schemas.py`**
  - [x] 9.4.1 — Pydantic request/response models for all endpoints.  Must stay
    in sync with Angular `api.models.ts` (Phase 12).
  - [x] 9.4.2 — Ensure no `reference_answer`, `grounding_context`,
    `raw_prompt`, `raw_completion` fields in any user-facing schema.

- [x] **9.5 — Implement `mindforge/api/middleware.py`**
  - [x] 9.5.1 — CORS middleware: configurable origins.
  - [x] 9.5.2 — Rate limiting middleware.
  - [x] 9.5.3 — Request ID middleware: generate and propagate request ID.
  - [x] 9.5.4 — Request size limiter.

- [x] **9.6 — Implement routers**
  - [x] 9.6.1 — `routers/health.py`: `GET /api/health` — DB connectivity
    check, optional Neo4j/Redis checks.
  - [x] 9.6.2 — `routers/auth.py`: `GET /login/{provider}`,
    `GET /callback/{provider}`, `GET /link/{provider}`, `POST /register`,
    `POST /login`, `GET /me`, `POST /logout`.
  - [x] 9.6.3 — `routers/knowledge_bases.py`: CRUD on `/api/knowledge-bases`.
    Scoped to `current_user`.
  - [x] 9.6.4 — `routers/documents.py`: upload (`POST`, return 202 with
    `task_id`), list, get, reprocess.  Scoped to KB.
  - [x] 9.6.5 — `routers/concepts.py`: `GET /api/knowledge-bases/{kb_id}/concepts`
    — return concept graph data for Cytoscape.
  - [x] 9.6.6 — `routers/quiz.py`: start session, submit answer, get results.
    Server-authoritative — never return `grounding_context` or
    `reference_answer`.
  - [x] 9.6.7 — `routers/flashcards.py`: due cards, review submission, all
    cards.
  - [x] 9.6.8 — `routers/search.py`: `POST /api/knowledge-bases/{kb_id}/search`.
  - [x] 9.6.9 — `routers/chat.py`: start session, send message, list sessions.
    No grounding/prompt data in response.
  - [x] 9.6.10 — `routers/events.py`: SSE stream
    `GET /api/knowledge-bases/{kb_id}/events`.  Subscribe to Redis Pub/Sub;
    fall back to polling `outbox_events` when Redis unavailable (2s interval).
  - [x] 9.6.11 — `routers/tasks.py`: pipeline task status polling.
  - [x] 9.6.12 — `routers/interactions.py`: user's own interaction history
    (redacted).
  - [x] 9.6.13 — `routers/admin.py`: system metrics, unredacted interactions
    (admin-only).

- [x] **9.7 — Implement SPA serving**
  - [x] 9.7.1 — Mount `frontend/dist/frontend/browser` as static files.
  - [x] 9.7.2 — Catch-all route returns `index.html` for Angular client-side
    routing.

- [x] **9.8 — Write API integration tests**
  - [x] 9.8.1 — Test auth flows: registration, login, OAuth callback, JWT
    issuance, refresh.
  - [x] 9.8.2 — Test KB CRUD with user scoping.
  - [x] 9.8.3 — Test document upload returns 202 and creates pipeline task.
  - [x] 9.8.4 — Test quiz answer submission → no sensitive fields in response.
  - [x] 9.8.5 — Test data isolation: user A cannot access user B's data.
  - [x] 9.8.6 — Test SSE event stream.
  - [x] 9.8.7 — Test rate limiting on auth endpoints.

### Completion Checklist

- [x] All routers functional with auth enforcement.
- [x] Composition root wires all dependencies correctly.
- [x] No business logic in routers — all delegated to application services.
- [x] Quiz responses contain no sensitive fields.
- [x] `mindforge-api` entry point starts Uvicorn correctly.

---

## [x] Phase 10 — Quiz and Flashcard Services

**Goal:** Implement the Quiz Service (session management, question generation
via Graph RAG, answer evaluation, SR integration) and Flashcard Service
(card catalog, spaced repetition scheduling with SM-2).

### Tasks

- [x] **10.1 — Implement `mindforge/application/quiz.py`**
  - [x] 10.1.1 — `QuizService` class: constructor accepts `AIGateway`,
    `RetrievalPort`, `QuizSessionStore`, `StudyProgressStore`,
    `InteractionStore`.
  - [x] 10.1.2 — `start_session(user_id, kb_id, topic)`:
    (1) query `find_weak_concepts(user_id, kb_id)` for target concepts,
    (2) for each concept: `retrieve_concept_neighborhood()` for grounding
    context, (3) call `QuizGeneratorAgent` to produce question + reference
    answer, (4) store session in `QuizSessionStore` (Redis or PG),
    (5) publish `QuizSessionStarted` event, (6) return question (no
    reference answer, no grounding context).
  - [x] 10.1.3 — `submit_answer(session_id, question_id, user_answer)`:
    (1) load session from `QuizSessionStore`, (2) validate `question_id`
    matches current question, (3) call `QuizEvaluatorAgent` with stored
    `reference_answer` and `grounding_context` (reuse, never regenerate),
    (4) update SR state via `StudyProgressStore.save_review()`,
    (5) record interaction turn in `InteractionStore`,
    (6) publish `QuizAnswerEvaluated` event,
    (7) return evaluation result (score, feedback — no reference answer).
  - [x] 10.1.4 — Session TTL: `QUIZ_SESSION_TTL_SECONDS` (default 1800).

- [x] **10.2 — Implement `QuizSessionStore` implementations**
  - [x] 10.2.1 — `RedisQuizSessionStore`: store as JSON hash in Redis with
    TTL.  Key format: `quiz:{session_id}`.
  - [x] 10.2.2 — `PostgresQuizSessionStore`: fallback when Redis absent.  Same
    protocol, higher latency.  Store in a dedicated table or temporary rows.

- [x] **10.3 — Implement SM-2 spaced repetition algorithm**
  - [x] 10.3.1 — Pure Python SM-2 implementation (in domain or application
    layer): given `ease_factor`, `interval`, `repetitions`, and a `rating`
    (0-5), compute new `ease_factor`, `interval`, `repetitions`,
    `next_review` date.
  - [x] 10.3.2 — Rating mapping: quiz scores map to SM-2 ratings.

- [x] **10.4 — Implement `mindforge/application/flashcards.py`**
  - [x] 10.4.1 — `FlashcardService` class: constructor accepts
    `ArtifactRepository`, `StudyProgressStore`.
  - [x] 10.4.2 — `get_due_cards(user_id, kb_id)`: query `StudyProgressStore`
    for cards where `next_review <= today`, join with flashcard data from
    artifacts.
  - [x] 10.4.3 — `review_card(user_id, kb_id, card_id, result)`: apply SM-2,
    save updated progress.  Record `ReviewRecorded` event.
  - [x] 10.4.4 — `list_all_cards(kb_id, lesson_id=None)`: catalog view.
  - [x] 10.4.5 — `due_count(user_id, kb_id)`: summary for UI.

- [x] **10.5 — Write unit tests for quiz and flashcard services**
  - [x] 10.5.1 — Test SM-2 calculations: various rating inputs, edge cases.
  - [x] 10.5.2 — Test quiz session lifecycle: start → answer → evaluation.
  - [x] 10.5.3 — Test that reference answer is reused, not regenerated.
  - [x] 10.5.4 — Test flashcard due date calculations.
  - [x] 10.5.5 — Test quiz session TTL behavior.
  - [x] 10.5.6 — **Security invariant test:** Verify quiz answer responses
    never contain `grounding_context`, `reference_answer`, `raw_prompt`, or
    `raw_completion`.  Verify answers are bound to server-side session and
    `question_id`.  This is a build-time guarantee, not deferred to Phase 18.

### Completion Checklist

- [x] Quiz sessions use Graph RAG for question targeting.
- [x] Reference answers are stored and reused.
- [x] SM-2 algorithm produces correct scheduling.
- [x] Both Redis and PostgreSQL session stores work.
- [x] Quiz responses verified to contain no sensitive fields.

> **Completed:** 2026-04-18

---

## [x] Phase 11 — Search and Conversational RAG

**Goal:** Implement the Search Service and Chat Service (conversational RAG
with knowledge base).

### Tasks

- [x] **11.1 — Implement `mindforge/application/search.py`**
  - [x] 11.1.1 — `SearchService` class: constructor accepts `RetrievalPort`,
    `AIGateway`, `InteractionStore`.
  - [x] 11.1.2 — `search(query, kb_id, user_id)`: call
    `RetrievalPort.retrieve(query, kb_id)` with the graph-first →
    full-text → vector priority order.  Optionally rerank results using
    LLM (INTERACTIVE deadline).  Record interaction turn.  Return
    `SearchResult` (no raw prompts or grounding snippets to client).

- [x] **11.2 — Implement `mindforge/application/chat.py`**
  - [x] 11.2.1 — `ChatService` class: constructor accepts `AIGateway`,
    `RetrievalPort`, `InteractionStore`, Redis client (optional).
  - [x] 11.2.2 — `start_session(user_id, kb_id)`: create `ChatSession`,
    store in Redis (or in-memory), return `session_id`.
  - [x] 11.2.3 — `send_message(session_id, message)`:
    (1) load chat history (last N turns),
    (2) extract concept mentions from user message (keyword/NER),
    (3) for each concept: `retrieve_concept_neighborhood()`,
    (4) if no concepts matched: fall back to `retrieve()`,
    (5) assemble prompt: system prompt ("Answer using ONLY provided context")
    + context (concept neighborhoods + facts + related concepts) + history
    (summarized if beyond token budget) + user message,
    (6) LLM completion (INTERACTIVE deadline),
    (7) store turn in session and in `interaction_turns`,
    (8) return answer + source concept keys (no context/prompt leaked).
  - [x] 11.2.4 — Session stored in Redis with TTL or in-memory if Redis absent.
    Not persisted to PostgreSQL.  Interaction metadata IS recorded for audit.
  - [x] 11.2.5 — `list_sessions(user_id, kb_id)`: list active chat sessions.

- [x] **11.3 — Implement `mindforge/application/knowledge_base.py`**
  - [x] 11.3.1 — `KnowledgeBaseService`: CRUD for knowledge bases, scoped to
    user.  `create`, `get`, `list_for_user`, `update`, `delete`.

- [x] **11.4 — Write unit tests**
  - [x] 11.4.1 — Test search with mock retrieval: graph-first priority.
  - [x] 11.4.2 — Test chat message flow: concept extraction → retrieval →
    prompt assembly → response.
  - [x] 11.4.3 — Test chat history sliding window.
  - [x] 11.4.4 — Test KB service user scoping.
  - [x] 11.4.5 — **Security invariant test:** Verify semantic cache keys
    include `kb_id` to prevent cross-KB data leakage.  This is a build-time
    guarantee, not deferred to Phase 18.

### Completion Checklist

- [x] Search uses retrieval priority order: graph → full-text → vector.
- [x] Chat uses Graph RAG per-turn with concept neighborhoods.
- [x] No grounding context or prompts leaked to the client.
- [x] Chat sessions are ephemeral (Redis/memory); audit data persisted.
- [x] Semantic cache keys verified to include `kb_id`.

> **Completed:** 2026-04-19

---

## [x] Phase 12 — Angular Frontend

> **Completed:** 2026-04-19

**Goal:** Create the Angular SPA with standalone components, lazy-loaded
routing, auth integration, and all user-facing pages.

### Tasks

- [x] **12.0 — Generate TypeScript API contracts (entry gate)**
  - [x] 12.0.1 — Generate `frontend/src/app/core/models/api.models.ts` from
    FastAPI's `/openapi.json` schema.  Use `openapi-typescript` or a similar
    code generator to produce TypeScript interfaces for all Pydantic
    request/response models defined in `mindforge/api/schemas.py` (Phase 9).
  - [x] 12.0.2 — If code generation is impractical, manually write the
    interfaces with a verified 1:1 mapping to the Pydantic schemas.  Every
    field name, type, and optionality must match.
  - [x] 12.0.3 — Add a CI check or test (e.g., `openapi-typescript --check`)
    that fails if `api.models.ts` drifts from the OpenAPI spec.
  - **Rationale:** This task is a prerequisite for all component and service
    implementation below.  Without it, frontend code is built on assumptions
    about API responses, and Phase 19 task 19.1.1 would discover
    mismatches instead of confirming correctness.

- [x] **12.1 — Initialize Angular project**
  - [x] 12.1.1 — `ng new frontend` with Angular 19+ standalone configuration.
  - [x] 12.1.2 — Configure `angular.json` for build output to
    `frontend/dist/frontend/browser`.

- [x] **12.2 — Implement core services**
  - [x] 12.2.1 — `core/models/api.models.ts`: TypeScript interfaces matching
    `mindforge/api/schemas.py`.  Keep in sync.
  - [x] 12.2.2 — `core/services/auth.service.ts`: login (OAuth redirect +
    email/password), logout, user state management, token refresh handling.
  - [x] 12.2.3 — `core/services/api.service.ts`: base HTTP client with error
    handling.
  - [x] 12.2.4 — `core/services/knowledge-base.service.ts`: KB CRUD operations.
  - [x] 12.2.5 — `core/services/document.service.ts`: upload, list, status.
  - [x] 12.2.6 — `core/services/concept.service.ts`: fetch concept graph.
  - [x] 12.2.7 — `core/services/quiz.service.ts`: session management, answer
    submission.
  - [x] 12.2.8 — `core/services/flashcard.service.ts`: due cards, review.
  - [x] 12.2.9 — `core/services/search.service.ts`: knowledge queries.
  - [x] 12.2.10 — `core/services/chat.service.ts`: `sendMessage()`,
    `listSessions()`.
  - [x] 12.2.11 — `core/services/event.service.ts`: SSE subscription via
    `EventSource`, real-time notifications.
  - [x] 12.2.12 — `core/services/task.service.ts`: pipeline task status.

- [x] **12.3 — Implement interceptors and guards**
  - [x] 12.3.1 — `core/interceptors/auth.interceptor.ts`: attach auth cookies
    (automatic with `withCredentials`), handle 401 → redirect to login.
  - [x] 12.3.2 — `core/guards/auth.guard.ts`: protect routes requiring login.

- [x] **12.4 — Implement routes (`app.routes.ts`)**
  - [x] 12.4.1 — Lazy-loaded route structure matching Section 12.2:
    `/` (dashboard), `/login`, `/knowledge-bases`, `/kb/:kbId/documents`,
    `/kb/:kbId/concepts`, `/kb/:kbId/quiz`, `/kb/:kbId/flashcards`,
    `/kb/:kbId/search`, `/kb/:kbId/chat`.

- [x] **12.5 — Implement pages**
  - [x] 12.5.1 — `pages/login/`: auth provider selection + email/password
    registration form.
  - [x] 12.5.2 — `pages/dashboard/`: lesson list, stats, recent activity.
    Uses SSE for real-time updates.
  - [x] 12.5.3 — `pages/upload/`: drag-and-drop file upload in
    `documents` page.  Show progress via SSE events.
  - [x] 12.5.4 — `pages/concept-map/`: Cytoscape.js graph visualization of
    concepts and relationships fetched from `/api/.../concepts`.
  - [x] 12.5.5 — `pages/quiz/`: interactive quiz interface — display question,
    accept answer, show graded feedback.
  - [x] 12.5.6 — `pages/flashcards/`: spaced repetition review interface —
    show card front, reveal back, submit rating.
  - [x] 12.5.7 — `pages/search/`: knowledge search interface with results.
  - [x] 12.5.8 — Chat page (`/kb/:kbId/chat`): conversational RAG interface
    with message input, response display, and source concept indicators.

- [x] **12.6 — Write frontend tests**
  - [x] 12.6.1 — Service tests: verify HTTP calls and response mapping.
  - [x] 12.6.2 — Component tests: rendering, user interaction.
  - [x] 12.6.3 — Guard tests: auth required enforcement.

- [x] **12.7 — Prompt internationalization (i18n)**

  **Backend tasks:**
  - [x] 12.7.1 — Add `prompt_locale: str = "pl"` field to the `KnowledgeBase`
    domain model (`mindforge/domain/models.py`) and to the SQLAlchemy ORM model
    (`mindforge/infrastructure/persistence/models.py`).
  - [x] 12.7.2 — Write a database migration (`migrations/versions/`) that adds
    the `prompt_locale` column to the `knowledge_bases` table with a default
    of `'pl'`.
  - [x] 12.7.3 — Update `ProcessingSettings` (`mindforge/domain/models.py` or
    wherever it lives) to include `prompt_locale: str = "pl"`.  The pipeline
    worker reads `kb.prompt_locale` and passes it through `ProcessingSettings →
    AgentContext`.
  - [x] 12.7.4 — Update `load_prompt()` in
    `mindforge/infrastructure/ai/prompts/__init__.py` to accept a `locale`
    parameter and resolve locale-suffixed files with fallback to `pl` (see
    ADR-18 and architecture Section 9.7).
  - [x] 12.7.5 — Rename all existing `.md` prompt files to the `.pl.md`
    convention (e.g., `summarizer_system.md` → `summarizer_system.pl.md`).
    Update each prompt module to call `load_prompt("summarizer_system.md",
    locale)` using the new signature.
  - [x] 12.7.6 — Update the `prompt_version` / `VERSION` string in each prompt
    module to encode locale (e.g., `f"1.0.0+{locale}"`), so that switching
    locale automatically invalidates `StepFingerprint` checkpoints.
  - [x] 12.7.7 — Add `prompt_locale` to the `KnowledgeBase` CRUD schemas in
    `mindforge/api/schemas.py` (request bodies for create/update and the
    response model) and keep `frontend/src/app/core/models/api.models.ts` in
    sync.

  **Frontend tasks:**
  - [x] 12.7.8 — Add a locale selector (dropdown: Polish / English) to the KB
    settings / create form in the Angular SPA.  Bind to the `prompt_locale`
    field via `KnowledgeBaseService`.
  - [x] 12.7.9 — Display the current prompt locale on the KB detail/settings
    page.  Show a warning that changing the locale will trigger full pipeline
    re-processing for all documents in that KB.

### Completion Checklist

- [x] `npm start` serves SPA on `:4200` with proxy to API `:8080`.
- [x] `npm run build` produces output in `frontend/dist/frontend/browser`.
- [x] All routes navigable; lazy loading works.
- [x] API models match backend schemas.
- [x] SSE events update UI in real time.

---

## [ ] Phase 13 — Docker and Deployment

**Goal:** Complete Docker multi-stage build, Docker Compose orchestration,
and deployment documentation.

### Completion Checklist

- [ ] `docker build` creates multi-stage image.
- [ ] `docker compose up` starts all services.
- [ ] All health checks passing.

---

## [ ] Phase 14 — Slack Bot

**Goal:** Implement the Slack bot using Slack Bolt (async mode) with quiz,
search, upload handlers, identity resolution, and workspace security.

> **Implementation note:** The Slack bot shares ~95% of its logic with the
> Discord bot (Phase 13): the same `IdentityResolver`, application services,
> auth enforcement patterns, and interaction flows.  Only the Bolt-specific
> adapter layer (slash commands, interactive messages, Socket Mode transport)
> is new.  Expect implementation effort to be 20–30% of Phase 13, not
> comparable in scope.

### Tasks

- [ ] **14.1 — Implement `mindforge/slack/app.py`**
  - [ ] 14.1.1 — Bolt app setup with Socket Mode (default) and HTTP mode
    support.  Composition root: same pattern as Discord — load settings,
    wire dependencies, register handlers.
  - [ ] 14.1.2 — `main()` entry point for `mindforge-slack`.

- [ ] **14.2 — Implement `mindforge/slack/auth.py`**
  - [ ] 14.2.1 — Workspace allowlist: verify `team_id` against
    `SLACK_ALLOWED_WORKSPACES`.
  - [ ] 14.2.2 — Signing secret validation: handled by Bolt automatically.
  - [ ] 14.2.3 — User mapping: Slack user IDs resolved to internal UUIDs via
    `IdentityResolver` (provider='slack').

- [ ] **14.3 — Implement handlers**
  - [ ] 14.3.1 — `handlers/quiz.py`: `/quiz` slash command, interactive messages.
    Resolve Slack user → internal UUID, resolve KB, delegate to `QuizService`.
  - [ ] 14.3.2 — `handlers/search.py`: `/search` slash command.
  - [ ] 14.3.3 — `handlers/upload.py`: file upload event handler.
  - [ ] 14.3.4 — `handlers/notifications.py`: SR reminders via DM.

- [ ] **14.4 — Write tests for Slack bot**
  - [ ] 14.4.1 — Test workspace allowlist enforcement.
  - [ ] 14.4.2 — Test identity resolution for Slack users.
  - [ ] 14.4.3 — Test slash command handling.

### Completion Checklist

- [ ] Bot connects via Socket Mode and responds to commands.
- [ ] Workspace allowlists enforced.
- [ ] Identity resolution works.
- [ ] `mindforge-slack` entry point is callable.

---

## [ ] Phase 15 — CLI Entry Points

**Goal:** Implement all remaining CLI entry points: quiz runner, backfill tool,
and startup scripts.

### Tasks

- [ ] **15.1 — Implement `mindforge/cli/quiz_runner.py`**
  - [ ] 15.1.1 — `main()`: composition root (same as API minus HTTP), interactive
    loop: prompt for topic → `QuizService.start_session()` → display
    question → accept answer → display evaluation.
  - [ ] 15.1.2 — `ensure_cli_user(db_engine)`: create or find a CLI user.

- [ ] **15.2 — Implement `mindforge/cli/backfill.py`**
  - [ ] 15.2.1 — `main()`: composition root, subcommands for reindex
    (rebuild Neo4j from PostgreSQL artifacts), reprocess (re-run pipeline
    with `force=True`), rebuild-projections (refresh `lesson_projections`).

- [ ] **15.3 — Create startup scripts**
  - [ ] 15.3.1 — `scripts/start-dev.sh` / `scripts/start-dev.bat`: activate
    venv, set development env vars, start API with `--reload`.
  - [ ] 15.3.2 — `scripts/start-api.sh` / `scripts/start-api.bat`: production
    API start.
  - [ ] 15.3.3 — `scripts/start-discord.sh` / `scripts/start-discord.bat`.
  - [ ] 15.3.4 — `scripts/migrate.py`: programmatic migration runner.
  - [ ] 15.3.5 — `scripts/STARTUP_GUIDE.md`: document all startup modes.

### Completion Checklist

- [ ] All six `mindforge-*` entry points functional.
- [ ] Backfill tool can rebuild Neo4j from PostgreSQL.
- [ ] Scripts work on both Windows and Linux.

---

## [ ] Phase 16 — Observability and Tracing

**Goal:** Implement Langfuse integration, tracing spans for all meaningful
operations, cost tracking, and quality evaluations.

### Tasks

- [ ] **16.1 — Implement `mindforge/infrastructure/tracing/langfuse_adapter.py`**
  - [ ] 16.1.1 — `LangfuseAdapter` class: initialize Langfuse SDK at
    composition root only (never on import).
  - [ ] 16.1.2 — `trace(name, metadata)` context manager → `TracingContext`.
  - [ ] 16.1.3 — `report_generation(ctx, result)`: log CompletionResult with
    token counts, cost, model.
  - [ ] 16.1.4 — `report_score(ctx, name, value)`: record quality evaluation.

- [ ] **16.2 — Instrument the AI Gateway**
  - [ ] 16.2.1 — Every `complete()` and `embed()` call creates a tracing span
    with model, tokens, cost, latency.

- [ ] **16.3 — Instrument the pipeline**
  - [ ] 16.3.1 — Create a parent trace per document (`document-ingest-{id}`).
  - [ ] 16.3.2 — Create child spans for each agent step.
  - [ ] 16.3.3 — Create child spans for graph indexing, read model publishing.

- [ ] **16.4 — Implement deterministic quality evaluations**
  - [ ] 16.4.1 — Concept coverage: compare generated concepts against document
    content.
  - [ ] 16.4.2 — Content grounding: verify summary facts trace to source text.
  - [ ] 16.4.3 — Flashcard balance: check distribution across card types.
  - [ ] 16.4.4 — Map connectivity: verify concept map is connected.
  - Run inline on every pipeline execution.

- [ ] **16.5 — Implement cost aggregation**
  - [ ] 16.5.1 — Record cost per interaction turn.
  - [ ] 16.5.2 — Admin dashboard data: cost per user, per KB, per day.

### Completion Checklist

- [ ] All LLM calls produce Langfuse traces.
- [ ] Pipeline produces hierarchical trace spans.
- [ ] Cost is tracked per agent step and per interaction.
- [ ] Deterministic evals run on every pipeline execution.

---

## [ ] Phase 17 — Security Hardening (Penetration Testing and Regression)

**Goal:** Whole-system penetration testing, security regression test suite, and
production configuration review.  This phase does NOT introduce security
invariants for the first time — each feature phase already contains its own
security verification tests (EgressPolicy in Phase 4, quiz integrity in
Phase 10, semantic cache isolation in Phase 11, auth in Phase 9, bot
allowlists in Phase 13/14).  Phase 18 validates the system as a whole and
catches cross-cutting issues that per-phase tests cannot.

### Tasks

- [ ] **17.1 — Penetration test checklist**
  - [ ] 17.1.1 — OWASP Top 10 review against the running application:
    injection, broken auth, sensitive data exposure, XXE, broken access
    control, security misconfiguration, XSS, insecure deserialization,
    insufficient logging, SSRF.
  - [ ] 17.1.2 — Attempt path traversal, SSRF, cross-user access, session
    hijacking, JWT manipulation, OAuth state bypass, prompt injection, and
    upload-based attacks against the full deployed stack (Docker Compose).
  - [ ] 17.1.3 — Verify LLM prompt safety: user input never interpolated
    into prompts without context framing; output filtered before client
    delivery.
  - [ ] 17.1.4 — Verify data isolation end-to-end: user A cannot reach
    user B's KBs or artifacts through any combination of API, Discord,
    Slack, and CLI surfaces.

- [ ] **17.2 — Security regression test suite**
  - Create `tests/security/` as a dedicated test directory that aggregates
    cross-cutting security scenarios into a single runnable suite:
  - [ ] 17.2.1 — Upload with path traversal → rejected.
  - [ ] 17.2.2 — Quiz answer response → no sensitive fields.
  - [ ] 17.2.3 — Discord interaction from non-owner → rejected.
  - [ ] 17.2.4 — OAuth callback without valid `state` → rejected.
  - [ ] 17.2.5 — Outbound fetch to private IP → blocked.
  - [ ] 17.2.6 — Cross-user data access → empty results.
  - [ ] 17.2.7 — Semantic cache cross-KB poisoning → isolated.
  - [ ] 17.2.8 — JWT with tampered claims → rejected.
  - [ ] 17.2.9 — Expired refresh token reuse → rejected.
  - [ ] 17.2.10 — Slack request with invalid signing secret → rejected.
  - [ ] 17.2.11 — Adversarial LLM instructions embedded in document content
    (prompt injection via RAG context) — verify the chat system prompt's
    "Answer using ONLY provided context" framing prevents instruction
    leakage to the model and that the response does not follow injected
    commands.
  - [ ] 17.2.12 — Semantic cache key omits `kb_id` in `Neo4jRetrievalAdapter`
    (if a cache layer is added) — verify that cross-KB cache poisoning is
    structurally impossible at the adapter level, not just at the service
    layer.

- [ ] **17.3 — Production configuration review**
  - [ ] 17.3.1 — Verify `Secure` flag is ON for JWT cookies in production
    config.
  - [ ] 17.3.2 — Verify CORS origins are explicitly allowlisted (no `*`).
  - [ ] 17.3.3 — Verify bcrypt cost ≥ 12 in production settings.
  - [ ] 17.3.4 — Verify rate limiters are active on registration, login,
    and upload endpoints.
  - [ ] 17.3.5 — Verify Docker Compose does not expose internal ports
    (PostgreSQL, Neo4j, Redis) to the host in production profiles.
  - [ ] 17.3.6 — Verify environment secrets are not baked into the Docker
    image.

### Completion Checklist

- [ ] Penetration test checklist completed against the running stack.
- [ ] Dedicated security regression test suite passes (`tests/security/`).
- [ ] Production configuration reviewed and hardened.

---

## [ ] Phase 18 — End-to-End Testing and Quality Gates

**Goal:** Implement the full test pyramid, contract tests, LLM quality
evaluations, and verify the complete data flow from upload to quiz.

### Tasks

- [ ] **18.1 — Implement contract tests**
  - [ ] 18.1.1 — Verify API response schemas match `api.models.ts` TypeScript
    interfaces.

- [ ] **18.2 — Implement idempotency tests**
  - [ ] 18.2.1 — Submit same content twice → no duplicate processing.
  - [ ] 18.2.2 — Pipeline interrupted and resumed → checkpoint works, no
    duplicate LLM calls.
  - [ ] 18.2.3 — Re-index to Neo4j → no duplicate nodes.

- [ ] **18.3 — Implement cost regression tests**
  - [ ] 18.3.1 — Reference answer reused during evaluation (no extra LLM call).
  - [ ] 18.3.2 — Summarizer context bounded (not entire knowledge index).
  - [ ] 18.3.3 — Deterministic operations don't trigger LLM calls.

- [ ] **18.4 — Implement E2E scenarios**
  - [ ] 18.4.1 — Full flow: upload document → pipeline processes →
    artifact created → graph indexed → lesson projection updated →
    quiz session started → answer evaluated → SR state updated.
  - [ ] 18.4.2 — Full flow: upload → search → results returned.
  - [ ] 18.4.3 — Full flow: upload → chat → conversational response.

- [ ] **18.5 — Set up LLM quality evaluations (offline)**
  - [ ] 18.5.1 — Dataset of test documents with expected outputs.
  - [ ] 18.5.2 — Summary coherence evaluation (LLM-as-judge).
  - [ ] 18.5.3 — Quiz question quality evaluation.
  - [ ] 18.5.4 — Retrieval relevance evaluation (embedding distance).

- [ ] **18.6 — Redis-absent verification**
  - [ ] 18.6.1 — Verify system starts correctly without Redis.
  - [ ] 18.6.2 — Verify startup warning is emitted.
  - [ ] 18.6.3 — Verify quiz sessions fall back to PostgreSQL.
  - [ ] 18.6.4 — Verify SSE falls back to outbox polling.
  - [ ] 18.6.5 — **Multi-worker session isolation note:** When Redis is absent
    and multiple Uvicorn workers are running, each worker holds a separate
    `_InMemorySessionCache`; chat sessions created on worker A are not
    visible on worker B.  Verify that `compose.yml` and
    `scripts/STARTUP_GUIDE.md` document that Redis is **required** in
    multi-worker deployments, and that the `api` service defaults to a
    single worker when Redis is absent.

- [ ] **18.7 — Prompt locale end-to-end verification**
  - [ ] 18.7.1 — Create a KB with `prompt_locale = "pl"`, upload a document,
    and verify the pipeline processes it using Polish prompt templates
    (check `StepFingerprint` encodes `+pl`).
  - [ ] 18.7.2 — Switch the KB's `prompt_locale` to `"en"`, trigger
    reprocessing, and verify: (a) all step fingerprints are invalidated,
    (b) pipeline re-runs using English templates, (c) new fingerprints encode
    `+en`.
  - [ ] 18.7.3 — Verify that requesting a locale without a corresponding
    `.{locale}.md` file falls back to `.pl.md` without error.

### Completion Checklist

- [ ] All test layers pass: unit, integration, contract, E2E.
- [ ] LLM quality evaluations produce baseline scores.
- [ ] System fully functional with and without Redis.
- [ ] Idempotency and cost regression tests pass.
- [ ] Prompt locale switching invalidates checkpoints and reruns pipeline.

---

## Dependency Graph

The following shows which phases depend on which.  A phase cannot start until
all its prerequisites are complete.

```
Phase 0: Scaffolding
    │
    ▼
Phase 1: Domain Layer
    │
    ├──────────────┬──────────────┐
    ▼              ▼              ▼
Phase 2:       Phase 3:       (independent)
Infra          AI Gateway
Foundation
    │              │
    ├──────────────┘
    ▼
Phase 4: Parsing & Ingestion
    │
    ▼
Phase 5: Agent Framework & Pipeline
    │
    ├──────────────┐
    ▼              ▼
Phase 6:       Phase 7:
Agents         Neo4j Graph
    │              │
    ├──────────────┘
    ▼
Phase 8: Event System
    │
    ▼
Phase 9: API Layer ──────────────────────────────────────────┐
    │                                                         │
    ├──────────────┬──────────────┐                           │
    ▼              ▼              ▼                           ▼
Phase 10:      Phase 11:      Phase 12:                  Phase 15:
Quiz &         Search &       Angular                    CLI
Flashcards     Chat           Frontend                   Entry Points
    │              │              │                           │
    ├──────────────┴──────────────┤                           │
    │                             │                           │
    ▼                             ▼                           │
Phase 13:                     Phase 14:                      │
Discord Bot                   Slack Bot                      │
    │                             │                           │
    └──────────────┬──────────────┘                           │
                   │                                          │
                   ├──────────────────────────────────────────┘
                   ▼
              Phase 16: Observability
                   │
                   ▼
              Phase 17: Docker & Deployment
                   │
                   ▼
              Phase 18: Security Hardening
                   │
                   ▼
              Phase 19: E2E Testing & Quality Gates
```

**Notes:**
- Phase 2 and Phase 3 can proceed in parallel after Phase 1.
- Phase 6 and Phase 7 can proceed in parallel after Phase 5.
- Phases 10, 11, 12, 13, 14, 15 can proceed in partial parallel after Phase 9.
- Phase 16 (Observability) can start partially alongside earlier phases by
  wiring the `LangfuseAdapter` stub and adding tracing progressively.



