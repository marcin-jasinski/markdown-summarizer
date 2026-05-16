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
16. [Phase 14 — Discord Bot](#phase-14--discord-bot)
17. [Phase 15 — Slack Bot](#phase-15--slack-bot)
18. [Phase 16 — CLI Entry Points](#phase-16--cli-entry-points)
19. [Phase 17 — Observability and Tracing](#phase-17--observability-and-tracing)
20. [Phase 18 — Security Hardening (Penetration Testing and Regression)](#phase-18--security-hardening-penetration-testing-and-regression)
21. [Phase 19 — End-to-End Testing and Quality Gates](#phase-19--end-to-end-testing-and-quality-gates)
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
- [x] **2.2 — Implement `mindforge/infrastructure/db.py`**
- [x] **2.3 — Set up Alembic and create initial migration**
- [x] **2.4 — Implement `mindforge/infrastructure/persistence/models.py`**
- [x] **2.5 — Implement `mindforge/infrastructure/persistence/document_repo.py`**
- [x] **2.6 — Implement `mindforge/infrastructure/persistence/artifact_repo.py`**
- [x] **2.7 — Implement `mindforge/infrastructure/persistence/interaction_repo.py`**
- [x] **2.8 — Implement `mindforge/infrastructure/persistence/identity_repo.py`**
- [x] **2.9 — Implement `mindforge/infrastructure/persistence/study_progress_repo.py`**
- [x] **2.10 — Implement `mindforge/infrastructure/persistence/read_models.py`**
- [x] **2.11 — Write integration tests for persistence layer**

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
- [x] **3.2 — Implement `mindforge/infrastructure/ai/embeddings.py`**
- [x] **3.3 — Implement `DeadlineExceeded` exception**
- [x] **3.4 — Implement `StubAIGateway` for tests**
- [x] **3.5 — Write unit tests for AI Gateway**
- [x] **3.6 — Implement `StdoutTracingAdapter` (early observability stub)**

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
- [x] **4.2 — Implement `mindforge/infrastructure/security/egress_policy.py`**
- [x] **4.3 — Implement `mindforge/infrastructure/parsing/registry.py`**
- [x] **4.4 — Implement format parsers**
- [x] **4.5 — Implement heading-aware chunking**
- [x] **4.6 — Implement `mindforge/application/ingestion.py`**
- [x] **4.7 — Implement size and cost guards (Section 10.7)**
- [x] **4.8 — Write unit tests for parsing and ingestion**

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
- [x] **5.2 — Implement `OrchestrationGraph`**
- [x] **5.3 — Implement `mindforge/application/pipeline.py`**
- [x] **5.4 — Implement `mindforge/cli/pipeline_runner.py`**
- [x] **5.5 — Write unit tests for orchestration**

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
- [x] **6.2 — Implement `mindforge/agents/preprocessor.py`**
- [x] **6.3 — Implement `mindforge/agents/image_analyzer.py`**
- [x] **6.4 — Implement `mindforge/agents/relevance_guard.py`**
- [x] **6.5 — Implement `mindforge/agents/article_fetcher.py`**
- [x] **6.6 — Implement `mindforge/agents/summarizer.py`**
- [x] **6.7 — Implement `mindforge/agents/flashcard_generator.py`**
- [x] **6.8 — Implement `mindforge/agents/concept_mapper.py`**
- [x] **6.9 — Implement `mindforge/agents/quiz_generator.py`**
- [x] **6.10 — Implement `mindforge/agents/quiz_evaluator.py`**
- [x] **6.11 — Register all agents in `AgentRegistry`**
- [x] **6.12 — Write unit tests for agents**

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
- [x] **7.2 — Implement `mindforge/infrastructure/graph/cypher_queries.py`**
- [x] **7.3 — Implement `mindforge/infrastructure/graph/neo4j_indexer.py`**
- [x] **7.4 — Implement `mindforge/infrastructure/graph/neo4j_retrieval.py`**
- [x] **7.5 — Create Neo4j indexes and constraints**
- [x] **7.6 — Implement `StubRetrievalAdapter` for tests**
- [x] **7.7 — Write integration tests for graph layer**

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
- [x] **8.2 — Implement `mindforge/infrastructure/events/outbox_relay.py`**
- [x] **8.3 — Implement `mindforge/infrastructure/events/durable_consumer.py`**
- [x] **8.4 — Implement outbox retention**
- [x] **8.5 — Write tests for event system**

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
- [x] **9.2 — Implement `mindforge/api/deps.py`**
- [x] **9.3 — Implement `mindforge/api/auth.py`**
- [x] **9.4 — Implement `mindforge/api/schemas.py`**
- [x] **9.5 — Implement `mindforge/api/middleware.py`**
- [x] **9.6 — Implement routers**
- [x] **9.7 — Implement SPA serving**
- [x] **9.8 — Write API integration tests**

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
- [x] **10.2 — Implement `QuizSessionStore` implementations**
- [x] **10.3 — Implement SM-2 spaced repetition algorithm**
- [x] **10.4 — Implement `mindforge/application/flashcards.py`**
- [x] **10.5 — Write unit tests for quiz and flashcard services**

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
- [x] **11.2 — Implement `mindforge/application/chat.py`**
- [x] **11.3 — Implement `mindforge/application/knowledge_base.py`**
- [x] **11.4 — Write unit tests**

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

## [ ] Phase 14 — Discord Bot

**Goal:** Implement the Discord bot with quiz, search, upload cogs, identity
resolution, and auth enforcement.

### Tasks

- [ ] **14.1 — Implement `mindforge/discord/bot.py`**
  - [ ] 14.1.1 — Composition root: load settings, create DB engine, create
    gateway, create repositories, create application services (same instances
    as API uses), create `IdentityResolver`, load cogs.
  - [ ] 14.1.2 — `main()` entry point for `mindforge-discord`.

- [ ] **14.2 — Implement `mindforge/discord/auth.py`**
  - [ ] 14.2.1 — Allowlist enforcement: guild IDs, role IDs, user IDs loaded
    lazily after `load_dotenv()`.
  - [ ] 14.2.2 — Interaction ownership: every view, modal, and button callback
    validates invoking user matches session owner.

- [ ] **14.3 — Implement cogs**
  - [ ] 14.3.1 — `cogs/quiz.py`: `/quiz start`, `/quiz answer` commands.
    Resolve Discord user → internal UUID via `IdentityResolver`.  Resolve KB
    by name or interactive picker.  Delegate to `QuizService`.
  - [ ] 14.3.2 — `cogs/search.py`: `/search` command.  Delegate to
    `SearchService`.
  - [ ] 14.3.3 — `cogs/upload.py`: upload attachment as document.  Delegate to
    `IngestionService`.
  - [ ] 14.3.4 — `cogs/notifications.py`: per-user SR reminders via DM (not
    channel-wide).

- [ ] **14.4 — Write tests for Discord bot**
  - [ ] 14.4.1 — Test identity resolution: first contact auto-provisions user.
  - [ ] 14.4.2 — Test allowlist enforcement.
  - [ ] 14.4.3 — Test interaction ownership validation.

### Completion Checklist

- [ ] Bot connects and responds to slash commands.
- [ ] Identity resolution works for new and existing users.
- [ ] Auth enforced on all interactions.
- [ ] `mindforge-discord` entry point is callable.

---

## [ ] Phase 15 — Slack Bot

**Goal:** Implement the Slack bot using Slack Bolt (async mode) with quiz,
search, upload handlers, identity resolution, and workspace security.

### Completion Checklist

- [ ] Bot connects via Socket Mode and responds to commands.
- [ ] Workspace allowlists enforced.
- [ ] Identity resolution works.
- [ ] `mindforge-slack` entry point is callable.

---

## [ ] Phase 16 — CLI Entry Points

**Goal:** Implement all remaining CLI entry points: quiz runner, backfill tool,
and startup scripts.

### Completion Checklist

- [ ] All six `mindforge-*` entry points functional.
- [ ] Backfill tool can rebuild Neo4j from PostgreSQL.
- [ ] Scripts work on both Windows and Linux.

---

## [ ] Phase 17 — Observability and Tracing

**Goal:** Implement Langfuse integration, tracing spans for all meaningful
operations, cost tracking, and quality evaluations.

### Completion Checklist

- [ ] Langfuse integration traces pipeline and API operations.
- [ ] Cost tracking per operation.
- [ ] Quality evaluations deterministic and inline.

---

## [ ] Phase 18 — Security Hardening (Penetration Testing and Regression)

**Goal:** Penetration testing, security audit, and regression fix.

### Completion Checklist

- [ ] All build-time security invariants verified.
- [ ] No new vulnerabilities introduced.

---

## [ ] Phase 19 — End-to-End Testing and Quality Gates

**Goal:** Full E2E test suite and quality gates.

### Completion Checklist

- [ ] E2E tests cover user journeys.
- [ ] Quality gates pass before production.
