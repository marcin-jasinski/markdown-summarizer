# MindForge — System Architecture

> **Version:** 2.0 (Greenfield Rewrite)
> **Date:** 2026-04-11
> **Status:** Approved

---

## Table of Contents

1. [Vision and Operating Model](#1-vision-and-operating-model)
2. [Architectural Principles](#2-architectural-principles)
3. [System Overview](#3-system-overview)
4. [Layer Architecture](#4-layer-architecture)
5. [Package Structure](#5-package-structure)
6. [Core Domain Model](#6-core-domain-model)
7. [Data Architecture](#7-data-architecture)
8. [AI Gateway and LLM Integration](#8-ai-gateway-and-llm-integration)
9. [Agent Architecture and Orchestration](#9-agent-architecture-and-orchestration)
10. [Ingestion Pipeline](#10-ingestion-pipeline)
11. [API Layer](#11-api-layer)
12. [Frontend Architecture](#12-frontend-architecture)
13. [Discord Bot](#13-discord-bot)
14. [Quiz CLI](#14-quiz-cli)
15. [Event System](#15-event-system)
16. [Security and Trust Boundaries](#16-security-and-trust-boundaries)
17. [Cost Optimization](#17-cost-optimization)
18. [Observability](#18-observability)
19. [Deployment and Infrastructure](#19-deployment-and-infrastructure)
20. [Testing Strategy](#20-testing-strategy)
21. [Key Architectural Decisions](#21-key-architectural-decisions)

---

## 1. Vision and Operating Model

MindForge transforms learning materials into structured study artifacts and
provides interactive knowledge assessment, all powered by AI agents and a
knowledge graph.  A user uploads a document (Markdown, PDF, DOCX, or TXT), the
system extracts and enriches the content, generates summaries, flashcards, and
concept maps, builds a queryable knowledge graph, and then exposes this knowledge
through a web UI, an interactive quiz engine, and a Discord bot.

### 1.1 Key Product Characteristics

| Characteristic | Decision |
|---|---|
| **User model** | Multi-user, shared instance with user-scoped data isolation |
| **Knowledge bases** | Multiple knowledge bases per user from day one |
| **Content language** | Language-agnostic — detect and process any language |
| **Document formats** | Markdown, PDF, DOCX, TXT |
| **Runtime surfaces** | Processing Pipeline, FastAPI REST API, Angular SPA, Discord Bot, Slack Bot, Quiz CLI |
| **Deployment** | Single server, Docker Compose |
| **Auth** | Discord OAuth + email/password from day one; pluggable provider architecture (Google, GitHub as future additions) |
| **AI providers** | Provider-agnostic via LiteLLM gateway |

### 1.2 Architectural Quality Goals

| Quality | Requirement |
|---|---|
| **Security** | Server-authoritative state; never trust client inputs; defense in depth |
| **Cost efficiency** | Deterministic logic first, small model second, frontier model last |
| **Observability** | Full distributed tracing with token/cost accounting per operation |
| **Extensibility** | Add new agents, providers, document formats, or runtime surfaces without modifying core |
| **Idempotency** | Every ingestion and processing operation is safe to retry |
| **Data integrity** | Single source of truth (PostgreSQL), derived stores (Neo4j) rebuilt from canonical data |

---

## 2. Architectural Principles

The architecture is built on a handful of non-negotiable principles that guide
every design decision.

### 2.1 Hexagonal Architecture (Ports and Adapters)

The domain core has no knowledge of infrastructure.  All external systems
(databases, LLM providers, file systems, HTTP) are reached through abstract
ports, with concrete adapters wired at the composition root.

```
            ┌──────────────────────────────────────────────┐
            │              Driving Adapters                 │
            │  (HTTP handlers, CLI, Discord commands,       │
            │   file watcher, event subscribers)            │
            └──────────────────┬───────────────────────────┘
                               │ uses
            ┌──────────────────▼───────────────────────────┐
            │              Application Services             │
            │  (Use cases: ingest document, run quiz,       │
            │   generate flashcards, search knowledge)      │
            ├──────────────────────────────────────────────┤
            │              Domain Model                     │
            │  (Entities, value objects, domain events,     │
            │   agent protocols, orchestration contracts)    │
            └──────────────────┬───────────────────────────┘
                               │ depends on (ports)
            ┌──────────────────▼───────────────────────────┐
            │              Driven Adapters                  │
            │  (PostgreSQL repo, Neo4j graph, LiteLLM,      │
            │   Redis, S3/MinIO, SMTP)                      │
            └──────────────────────────────────────────────┘
```

### 2.2 Single Responsibility and Dependency Inversion

- Each module, agent, and service has **one reason to change**.
- High-level policy (domain, use cases) never depends on low-level detail
  (database driver, HTTP framework, LLM SDK).
- Dependencies always point inward: adapters → application → domain.

### 2.3 Open/Closed Principle for Agents and Formats

Adding a new AI agent, a new document format parser, or a new authentication
provider must be a matter of **registering a new adapter**, not modifying the
orchestrator, parser registry, or auth framework.

### 2.4 Composition Root

Each runtime surface (API server, CLI pipeline, Discord bot, Slack bot, Quiz CLI) has
exactly **one composition root** that wires all dependencies: settings,
credentials, database connections, AI gateway, event bus, repositories.
No module-level singletons, no import-time side effects, no `sys.path` surgery.

### 2.5 Explicit Over Implicit

- Configuration is loaded once, validated on startup, and injected — never
  read from `os.environ` at request time.
- Feature flags gate function calls, not imports.
- All imports are at module top level; optional packages use `try/except` guards.

---

## 3. System Overview

### 3.1 Runtime Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Runtime Surfaces                                │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌─────────┐ │
│  │ Angular  │  │ FastAPI  │  │ Discord  │  │  Slack   │  │ Quiz CLI  │  │ Pipeline│ │
│  │ SPA      │  │ API      │  │ Bot      │  │  Bot     │  │           │  │ Runner  │ │
│  │ (:4200)  │  │ (:8080)  │  │          │  │          │  │           │  │         │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └────┬────┘ │
│       │              │              │              │              │              │      │
│       └──────────────┴──────┬───────┴──────────────┴──────────────┴──────────────┘      │
│                             │                                            │
│                    ┌────────▼─────────┐                                  │
│                    │  Application     │                                  │
│                    │  Services Layer  │                                  │
│                    └────────┬─────────┘                                  │
│                             │                                            │
│           ┌─────────────────┼─────────────────────┐                     │
│           │                 │                     │                     │
│  ┌────────▼──────┐ ┌───────▼───────┐ ┌───────────▼────────┐            │
│  │  AI Gateway   │ │  Event Bus    │ │   Agent            │            │
│  │  (LiteLLM)    │ │               │ │   Orchestrator     │            │
│  └───────┬───────┘ └───────────────┘ └────────────────────┘            │
│          │                                                              │
└──────────┼──────────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────────────┐
│                      Infrastructure Layer                               │
│                                                                         │
│  ┌────────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐ │
│  │ PostgreSQL │  │ Neo4j   │  │ Redis   │  │ Langfuse │  │ MinIO/S3 │ │
│  │ (canonical │  │ (graph  │  │ (cache, │  │ (traces, │  │ (media   │ │
│  │  store)    │  │  query) │  │  pubsub)│  │  evals)  │  │  assets) │ │
│  └────────────┘  └─────────┘  └─────────┘  └──────────┘  └──────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow Summary

```
Document Upload (API / Discord / File Watcher)
    │
    ▼
[Ingestion Service] ── compute content hash, deduplicate, store in PostgreSQL
    │
    ▼
[Task Queue] ── submit pipeline task, track status
    │
    ▼
[Agent Orchestrator] ── execute processing graph (parse → analyze → enrich → generate)
    │  publishes domain events at each step
    ▼
[Canonical Artifact] ── persisted in PostgreSQL (document_artifacts)
    │
    ├──▶ [Neo4j Projection] ── concepts, facts, chunks, relationships, embeddings
    ├──▶ [Read Models] ── lesson projections, flashcard catalogs, concept maps
    └──▶ [Event: ProcessingComplete]
              │
              ├──▶ [SSE/WebSocket] ── notify Angular SPA
    ├──▶ [Discord Notification] ── notify subscribed users
    └──▶ [Slack Notification] ── notify subscribed users
Knowledge Retrieval (Quiz / Search / Concept Map)
    │
    ▼
[Retrieval Port] ── graph-first, lexical fallback, embedding last
    │
    ▼
[AI Gateway] ── generate question / evaluate answer / semantic search
    │
    ▼
[Response] ── server-authoritative, no grounding context exposed to client
```

---

## 4. Layer Architecture

### 4.1 Domain Layer (`mindforge/domain/`)

Pure Python.  No framework imports, no I/O, no side effects.

Contains:
- **Entities**: `Document`, `KnowledgeBase`, `Interaction`, `User`
- **Value Objects**: `LessonIdentity`, `ContentHash`, `FlashcardId`, `ConceptKey`
- **Domain Events**: `DocumentIngested`, `PipelineStepCompleted`, `GraphUpdated`
- **Agent Protocols**: `Agent`, `AgentCapability`, `AgentContext`
- **Service Interfaces (Ports)**: `DocumentRepository`, `RetrievalPort`,
  `AIGateway`, `StudyProgressStore`, `EventPublisher`, `InteractionStore`

### 4.2 Application Layer (`mindforge/application/`)

Use-case orchestration.  Depends only on the domain layer.

Contains:
- **Ingestion Service**: document validation, deduplication, storage, task submission
- **Pipeline Orchestrator**: agent graph execution with checkpointing
- **Quiz Service**: question generation, answer evaluation, session management
- **Chat Service**: conversational RAG with Graph context and history
- **Search Service**: retrieval dispatch, result ranking
- **Flashcard Service**: card catalog, spaced repetition scheduling
- **Knowledge Base Service**: CRUD for knowledge bases, user-scoped access

### 4.3 Infrastructure Layer (`mindforge/infrastructure/`)

Adapters implementing domain ports.

Contains:
- **Persistence**: PostgreSQL repositories (SQLAlchemy or asyncpg), Neo4j graph adapter
- **AI**: LiteLLM gateway adapter, embedding adapter
- **Cache**: Redis adapter for sessions, pub/sub, semantic cache
- **Storage**: MinIO/S3 adapter for media assets
- **Parsing**: document format parsers (Markdown, PDF, DOCX, TXT)
- **Tracing**: Langfuse adapter

### 4.4 Presentation Layer

Driving adapters that translate external inputs into application service calls.

- **`mindforge/api/`**: FastAPI routers, schemas, middleware, auth
- **`mindforge/discord/`**: Discord bot commands and cogs
- **`mindforge/slack/`**: Slack bot event handlers and commands
- **`mindforge/cli/`**: CLI entry points (pipeline runner, quiz, backfill)
- **`frontend/`**: Angular SPA (separate build)

---

## 5. Package Structure

```
mindforge/
├── pyproject.toml                      # PEP 621 project metadata, entry points
├── compose.yml                         # Docker Compose orchestration
├── Dockerfile                          # Multi-stage build (Node + Python)
├── env.example                         # Template for .env
│
├── mindforge/                          # Installable Python package
│   ├── __init__.py
│   │
│   ├── domain/                         # Domain layer — pure Python, no I/O
│   │   ├── __init__.py
│   │   ├── models.py                   # Entities, value objects, enums
│   │   ├── events.py                   # Domain event definitions
│   │   ├── agents.py                   # Agent protocols and capability declarations
│   │   └── ports.py                    # Abstract interfaces (repository, gateway, etc.)
│   │
│   ├── application/                    # Application services — use-case orchestration
│   │   ├── __init__.py
│   │   ├── ingestion.py                # Document ingestion and deduplication
│   │   ├── pipeline.py                 # Agent orchestrator with checkpointing
│   │   ├── quiz.py                     # Quiz generation and evaluation
│   │   ├── search.py                   # Knowledge retrieval
│   │   ├── flashcards.py               # Flashcard catalog and spaced repetition
│   │   ├── knowledge_base.py           # Knowledge base management
│   │   ├── chat.py                     # Conversational RAG (chat with KB)
│   │   └── interactions.py             # Interaction tracking and audit
│   │
│   ├── infrastructure/                 # Driven adapters — all I/O lives here
│   │   ├── __init__.py
│   │   ├── config.py                   # Settings, credentials, feature flags
│   │   ├── db.py                       # Database engine, session factory
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── models.py              # SQLAlchemy ORM models
│   │   │   ├── document_repo.py       # DocumentRepository implementation
│   │   │   ├── artifact_repo.py       # ArtifactRepository implementation
│   │   │   ├── interaction_repo.py    # InteractionStore implementation
│   │   │   ├── identity_repo.py      # ExternalIdentityRepository implementation
│   │   │   ├── study_progress_repo.py # StudyProgressStore implementation
│   │   │   └── read_models.py         # Materialized read-model projections
│   │   ├── graph/
│   │   │   ├── __init__.py
│   │   │   ├── neo4j_context.py       # Database-bound session factory
│   │   │   ├── neo4j_retrieval.py     # RetrievalPort implementation
│   │   │   ├── neo4j_indexer.py       # Graph projection writer (UNWIND batches)
│   │   │   └── cypher_queries.py      # Named Cypher query constants
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── gateway.py             # AIGateway implementation (wraps LiteLLM)
│   │   │   ├── embeddings.py          # Embedding adapter
│   │   │   └── prompts/               # Prompt templates (versioned, externalized, i18n)
│   │   │       ├── __init__.py        # load_prompt(filename, locale) loader
│   │   │       ├── summarizer.py
│   │   │       ├── flashcard_gen.py
│   │   │       ├── concept_mapper.py
│   │   │       ├── quiz_generator.py
│   │   │       ├── quiz_evaluator.py
│   │   │       ├── preprocessor.py
│   │   │       ├── image_analyzer.py
│   │   │       ├── article_fetcher.py
│   │   │       ├── chat.py
│   │   │       ├── summarizer_system.pl.md    # Polish (default locale)
│   │   │       ├── summarizer_system.en.md    # English
│   │   │       └── ...                        # one .pl.md + .en.md per template
│   │   ├── parsing/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py            # Format parser registry (Open/Closed)
│   │   │   ├── markdown_parser.py
│   │   │   ├── pdf_parser.py
│   │   │   ├── docx_parser.py
│   │   │   └── txt_parser.py
│   │   ├── cache/
│   │   │   ├── __init__.py
│   │   │   ├── redis_adapter.py       # Redis client wrapper
│   │   │   └── semantic_cache.py      # LLM response semantic cache
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   └── object_store.py        # MinIO/S3 adapter for media assets
│   │   ├── tracing/
│   │   │   ├── __init__.py
│   │   │   └── langfuse_adapter.py    # Tracing, cost, eval reporting
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── outbox_publisher.py    # OutboxEventPublisher (writes to outbox_events)
│   │   │   ├── outbox_relay.py        # OutboxRelay (outbox → Redis Pub/Sub)
│   │   │   └── durable_consumer.py    # DurableEventConsumer base + concrete consumers
│   │   └── security/
│   │       ├── __init__.py
│   │       ├── egress_policy.py       # SSRF protection, URL validation
│   │       └── upload_sanitizer.py    # Filename sanitization, size limits
│   │
│   ├── agents/                         # AI agent implementations
│   │   ├── __init__.py
│   │   ├── preprocessor.py            # Content cleaning and section removal
│   │   ├── image_analyzer.py          # Vision model image description
│   │   ├── summarizer.py              # Structured summary generation
│   │   ├── flashcard_generator.py     # Flashcard generation
│   │   ├── concept_mapper.py          # Concept map generation
│   │   ├── quiz_generator.py          # Quiz question generation
│   │   ├── quiz_evaluator.py          # Answer evaluation
│   │   ├── relevance_guard.py         # Content relevance validation
│   │   └── article_fetcher.py         # Link classification and article fetch
│   │
│   ├── api/                            # FastAPI presentation layer
│   │   ├── __init__.py
│   │   ├── main.py                    # App factory, lifespan, composition root
│   │   ├── deps.py                    # Dependency injection providers
│   │   ├── auth.py                    # Multi-provider OAuth + JWT
│   │   ├── schemas.py                 # Pydantic request/response models
│   │   ├── middleware.py              # CORS, rate limiting, request ID
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── health.py
│   │       ├── auth.py
│   │       ├── knowledge_bases.py
│   │       ├── documents.py
│   │       ├── concepts.py
│   │       ├── quiz.py
│   │       ├── flashcards.py
│   │       ├── search.py
│   │       ├── chat.py                # Conversational RAG routes
│   │       ├── tasks.py
│   │       ├── interactions.py
│   │       ├── events.py              # SSE/WebSocket event stream
│   │       └── admin.py
│   │
│   ├── discord/                        # Discord bot presentation layer
│   │   ├── __init__.py
│   │   ├── bot.py                     # Bot setup, composition root
│   │   ├── auth.py                    # Allowlist, interaction ownership
│   │   └── cogs/
│   │       ├── __init__.py
│   │       ├── quiz.py
│   │       ├── search.py
│   │       ├── upload.py
│   │       └── notifications.py
│   │
│   ├── slack/                          # Slack bot presentation layer
│   │   ├── __init__.py
│   │   ├── app.py                     # Bolt app setup, composition root
│   │   ├── auth.py                    # Workspace/channel allowlists
│   │   └── handlers/
│   │       ├── __init__.py
│   │       ├── quiz.py
│   │       ├── search.py
│   │       ├── upload.py
│   │       └── notifications.py
│   │
│   └── cli/                            # CLI entry points
│       ├── __init__.py
│       ├── pipeline_runner.py         # mindforge-pipeline
│       ├── quiz_runner.py             # mindforge-quiz
│       └── backfill.py                # mindforge-backfill
│
├── frontend/                           # Angular SPA (separate build)
│   ├── angular.json
│   ├── package.json
│   └── src/
│       └── app/
│           ├── core/
│           │   ├── guards/
│           │   ├── interceptors/
│           │   ├── models/
│           │   └── services/
│           └── pages/
│               ├── dashboard/
│               ├── concept-map/
│               ├── quiz/
│               ├── flashcards/
│               ├── search/
│               ├── upload/
│               └── login/
│
├── tests/
│   ├── conftest.py                    # Shared fixtures, stubs, factory functions
│   ├── unit/                          # No I/O, no network, fast
│   │   ├── domain/
│   │   ├── application/
│   │   └── agents/
│   ├── integration/                   # Real DB, mocked LLM
│   │   ├── persistence/
│   │   ├── graph/
│   │   └── api/
│   └── e2e/                           # Full stack, real services
│
├── scripts/
│   ├── start-dev.sh / .bat
│   ├── start-api.sh / .bat
│   ├── start-discord.sh / .bat
│   ├── migrate.py                     # Database migrations runner
│   └── STARTUP_GUIDE.md
│
├── migrations/                         # Alembic or raw SQL migrations
│   └── versions/
│
└── docker/
    └── ...
```

### 5.1 Entry Points (pyproject.toml)

```toml
[project]
name = "mindforge"
requires-python = ">=3.12"

[project.scripts]
mindforge-pipeline = "mindforge.cli.pipeline_runner:main"
mindforge-quiz     = "mindforge.cli.quiz_runner:main"
mindforge-backfill = "mindforge.cli.backfill:main"
mindforge-discord  = "mindforge.discord.bot:main"
mindforge-slack    = "mindforge.slack.app:main"
mindforge-api      = "mindforge.api.main:run"
```

All entry points use the installed package.  No `sys.path` manipulation.
Local development uses `pip install -e .`

---

## 6. Core Domain Model

### 6.1 Entity Relationship Overview

```
User ──────────────── owns ──────────── KnowledgeBase
                                             │
                                             │ contains
                                             ▼
                                        Document
                                             │
                                             │ produces
                                             ▼
                                      DocumentArtifact
                                       ╱    │    ╲
                                      ╱     │     ╲
                                Summary  Flashcards  ConceptMap
                                             │
                                             │ indexed in
                                             ▼
                                    Neo4j Graph Projection
                                    (Concepts, Facts, Chunks,
                                     Relationships, Embeddings)
```

### 6.2 Core Entities

#### Document

The canonical representation of an uploaded learning material.

```python
@dataclass
class Document:
    document_id: UUID
    knowledge_base_id: UUID
    lesson_identity: LessonIdentity
    content_hash: ContentHash          # SHA-256 of original bytes
    source_filename: str
    mime_type: str
    original_content: str              # raw text (extracted from PDF/DOCX if needed)
    content_blocks: list[ContentBlock] # multimodal-ready structured content
    upload_source: UploadSource        # API, DISCORD, FILE_WATCHER
    uploaded_by: UUID | None           # internal user UUID
    status: DocumentStatus             # PENDING, PROCESSING, DONE, FAILED
    created_at: datetime
    updated_at: datetime
```

#### LessonIdentity

Immutable, explicit, resolved once at intake.

```python
@dataclass(frozen=True)
class LessonIdentity:
    lesson_id: str            # canonical primary key — always present
    title: str                # extracted from frontmatter or first heading
```

**Resolution Algorithm:**

The ingestion service resolves `lesson_id` using a deterministic decision tree.
Each step is tried in order; the first match wins.

```
Step 1: Frontmatter `lesson_id:` field
        → Use verbatim (after validation: lowercase, max 80 chars, [a-z0-9-_])

Step 2: Frontmatter `title:` field
        → Slugify: lowercase, replace spaces/special chars with dashes,
          collapse consecutive dashes, strip leading/trailing dashes,
          truncate at 80 characters
        Example: "Sieci neuronowe — wprowadzenie" → "sieci-neuronowe-wprowadzenie"

Step 3: PDF metadata `Title` field (for PDF uploads)
        → Same slugify rules as Step 2

Step 4: Filename without extension
        → Sanitize: lowercase, replace spaces with dashes, strip non-alphanumeric
          except dashes and underscores, truncate at 80 characters
        Example: "S02E05_Attention Mechanism.md" → "s02e05_attention-mechanism"

Step 5: None of the above produced a valid identifier
        → REJECT the upload with error:
          "Nie można ustalić identyfikatora lekcji. Dodaj pole 'lesson_id:'
           lub 'title:' do frontmatter dokumentu, albo zmień nazwę pliku."
```

**Validation rules** (applied to all steps):
- Max length: 80 characters
- Allowed characters: `[a-z0-9\-_]`
- Must not be empty after sanitization
- Must not collide with reserved names: `__init__`, `index`, `default`

**`title` resolution** (for display purposes, independent of `lesson_id`):
1. Frontmatter `title:` field → use verbatim
2. First `# Heading` in Markdown content
3. PDF metadata `Title`
4. Filename without extension (unsanitized, for readability)

If no stable identifier can be produced, the upload is **rejected** — never
processed with a placeholder like `"unknown"`.

#### ContentHash

```python
@dataclass(frozen=True)
class ContentHash:
    sha256: str   # hex digest of original document bytes

    @staticmethod
    def compute(raw_bytes: bytes) -> "ContentHash":
        return ContentHash(sha256=hashlib.sha256(raw_bytes).hexdigest())
```

Content hash is the **deduplication key** across all ingestion surfaces.

#### KnowledgeBase

```python
@dataclass
class KnowledgeBase:
    kb_id: UUID
    owner_id: str             # user ID
    name: str
    description: str
    created_at: datetime
    document_count: int       # derived/cached
```

Each knowledge base isolates its documents, artifacts, concepts, and graph
subgraph.  The relevance guard (Section 10.3) validates new documents against
the target knowledge base, not globally.

#### DocumentArtifact

The canonical structured output of the processing pipeline.

```python
@dataclass
class DocumentArtifact:
    document_id: UUID
    version: int
    lesson_identity: LessonIdentity
    cleaned_content: str
    image_descriptions: list[ImageDescription]
    summary: SummaryData | None
    flashcards: list[FlashcardData]
    concept_map: ConceptMapData | None
    fetched_articles: list[FetchedArticle]
    validation_result: ValidationResult | None
    step_fingerprints: dict[str, StepCheckpoint]  # per-step invalidation metadata
    completed_step: str | None        # last successfully completed pipeline step
    created_at: datetime
```

#### FlashcardData

Cards have **deterministic, content-based IDs** scoped to their knowledge base
— not list-index-based.

```python
@dataclass
class FlashcardData:
    card_id: str              # sha256(kb_id|lesson_id|card_type|front|back)[:16]
    front: str
    back: str
    card_type: CardType       # BASIC, CLOZE, REVERSE
    tags: list[str]
    kb_id: UUID
    lesson_id: str
```

Reprocessing a document preserves card identity as long as content is unchanged.
Spaced repetition progress is keyed by `(user_id, kb_id, card_id)`.  The `kb_id`
prefix in the hash ensures that identical card content in different knowledge
bases produces distinct `card_id` values — preventing cross-KB SR state
collisions.

#### ContentBlock (Multimodal-Ready)

```python
@dataclass
class ContentBlock:
    block_type: BlockType     # TEXT, IMAGE, CODE, AUDIO, VIDEO
    content: str | None       # text content or transcript
    media_ref: str | None     # object storage key for binary assets
    media_type: str | None    # MIME type
    metadata: dict            # block-specific (dimensions, duration, alt text)
    position: int             # ordering within the document
```

Initial implementation only produces `TEXT` and `IMAGE` blocks.  The schema
accommodates future modalities without migration.

### 6.3 Domain Events

All events are immutable value objects published after state-changing operations.

```python
@dataclass(frozen=True)
class DocumentIngested(DomainEvent):
    document_id: UUID
    knowledge_base_id: UUID
    lesson_id: str
    content_hash: str
    timestamp: datetime

@dataclass(frozen=True)
class PipelineStepCompleted(DomainEvent):
    document_id: UUID
    step_name: str
    artifact_version: int
    timestamp: datetime

@dataclass(frozen=True)
class ProcessingCompleted(DomainEvent):
    document_id: UUID
    lesson_id: str
    knowledge_base_id: UUID
    timestamp: datetime

@dataclass(frozen=True)
class ProcessingFailed(DomainEvent):
    document_id: UUID
    step_name: str
    error: str
    timestamp: datetime

@dataclass(frozen=True)
class GraphProjectionUpdated(DomainEvent):
    knowledge_base_id: UUID
    lesson_id: str
    concepts_added: int
    facts_added: int
    timestamp: datetime
```

### 6.4 Port Interfaces

The domain defines abstract interfaces.  Infrastructure provides implementations.

```python
class DocumentRepository(Protocol):
    async def save(self, document: Document, connection: AsyncConnection) -> None: ...
    async def get_by_id(self, document_id: UUID) -> Document | None: ...
    async def get_by_content_hash(self, kb_id: UUID, hash: ContentHash) -> Document | None: ...
    async def update_status(self, document_id: UUID, status: DocumentStatus) -> None: ...
    async def list_by_knowledge_base(self, kb_id: UUID, ...) -> list[Document]: ...

class ArtifactRepository(Protocol):
    async def save_checkpoint(self, artifact: DocumentArtifact, connection: AsyncConnection) -> None: ...
    async def load_latest(self, document_id: UUID) -> DocumentArtifact | None: ...
    async def count_flashcards(self, kb_id: UUID, lesson_id: str) -> int: ...

class RetrievalPort(Protocol):
    async def retrieve(self, query: str, kb_id: UUID, *,
                       max_results: int = 10,
                       query_embedding: list[float] | None = None) -> RetrievalResult: ...
    async def retrieve_concept_neighborhood(
        self, concept_key: str, kb_id: UUID, *, depth: int = 2
    ) -> ConceptNeighborhood: ...
    async def find_weak_concepts(
        self, user_id: UUID, kb_id: UUID, *, limit: int = 5
    ) -> list[WeakConcept]: ...
    async def get_concepts(self, kb_id: UUID) -> list[ConceptNode]: ...
    async def get_lesson_concepts(self, kb_id: UUID, lesson_id: str) -> list[ConceptNode]: ...

class AIGateway(Protocol):
    async def complete(self, *, model: str, messages: list[dict],
                       temperature: float = 0.0,
                       response_format: dict | None = None) -> CompletionResult: ...
    async def embed(self, *, model: str, texts: list[str]) -> list[list[float]]: ...

class StudyProgressStore(Protocol):
    async def get_due_cards(self, user_id: UUID, kb_id: UUID, today: date) -> list[CardState]: ...
    async def save_review(self, user_id: UUID, kb_id: UUID, card_id: str, result: ReviewResult) -> None: ...
    async def due_count(self, user_id: UUID, kb_id: UUID, today: date) -> int: ...

@dataclass
class ReviewResult:
    rating: int                # SM-2 rating (0-5)
    quality_flag: Literal["ok", "bad_content", "too_easy", "unclear"] | None = None
    # quality_flag is optional user feedback on the flashcard itself.
    # Stored in study_progress.quality_flags (append-only JSONB array).
    # Used for: Langfuse eval reporting, prompt tuning analytics.
    # Does NOT affect SM-2 scheduling — only the rating does.

class EventPublisher(Protocol):
    async def publish_in_tx(self, event: DomainEvent, connection: AsyncConnection) -> None: ...

class InteractionStore(Protocol):
    async def create_interaction(self, interaction: Interaction) -> None: ...
    async def add_turn(self, turn: InteractionTurn) -> None: ...
    async def get_interaction(self, interaction_id: UUID) -> Interaction | None: ...
    async def list_for_user(self, user_id: UUID, **filters) -> list[Interaction]: ...
        # Returns REDACTED turns — strips reference_answer, grounding_context,
        # raw_prompt, raw_completion, cost from output_data.
    async def list_unredacted(self, **filters) -> list[Interaction]: ...
        # Admin-only: returns full output_data including sensitive fields.

class ExternalIdentityRepository(Protocol):
    async def find_user_id(self, provider: str, external_id: str) -> UUID | None: ...
    async def link(self, user_id: UUID, provider: str, external_id: str,
                   email: str | None = None, metadata: dict | None = None) -> None: ...
    async def create_user_and_link(self, provider: str, external_id: str,
                                   display_name: str, **kwargs) -> UUID: ...
        # Atomically creates a user row and an external_identity row.
        # Returns the new internal user_id.
```

---

## 7. Data Architecture

### 7.1 PostgreSQL — Canonical Store (System of Record)

PostgreSQL is the single source of truth for all business data.

#### Schema Overview

```sql
-- ============================================================
-- Identity and Access
-- ============================================================
CREATE TABLE users (
    user_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name  TEXT NOT NULL,
    email         TEXT,
    password_hash TEXT,                         -- bcrypt; NULL for OAuth users
    avatar_url    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

-- External identity federation: allows one user to link multiple providers
CREATE TABLE external_identities (
    identity_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider      TEXT NOT NULL,                -- 'discord', 'google', 'github', 'slack'
    external_id   TEXT NOT NULL,                -- provider-scoped user ID
    email         TEXT,                         -- email from provider (may differ from users.email)
    metadata      JSONB NOT NULL DEFAULT '{}',  -- avatar, display name from provider
    linked_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, external_id)              -- one account per provider ID
);

-- ============================================================
-- Knowledge Bases
-- ============================================================
CREATE TABLE knowledge_bases (
    kb_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id      UUID NOT NULL REFERENCES users(user_id),
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, name)
);

-- ============================================================
-- Documents and Artifacts
-- ============================================================
CREATE TABLE documents (
    document_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id           UUID NOT NULL REFERENCES knowledge_bases(kb_id),
    lesson_id       TEXT NOT NULL,              -- stable logical lesson identifier
    revision        INT NOT NULL DEFAULT 1,     -- monotonically increasing per (kb_id, lesson_id)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,  -- only one active revision per lesson
    content_sha256  CHAR(64) NOT NULL,
    source_filename TEXT NOT NULL,
    mime_type       TEXT NOT NULL,
    original_content TEXT NOT NULL,             -- see Design Decision below
    upload_source   TEXT NOT NULL,              -- 'api', 'discord', 'file_watcher'
    uploaded_by     UUID REFERENCES users(user_id),
    status          TEXT NOT NULL DEFAULT 'pending',
    current_task_id UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (kb_id, lesson_id, revision),
    UNIQUE (kb_id, content_sha256)
);
-- Only one active revision per logical lesson within a KB:
CREATE UNIQUE INDEX uq_active_lesson
    ON documents (kb_id, lesson_id) WHERE is_active = TRUE;

> **Design Decision — `original_content` in PostgreSQL, not MinIO:**
> For 1–5 users the largest realistic document corpus is hundreds of lessons,
> each up to ~10 MB of text.  PostgreSQL `TEXT` stores this inline with TOAST
> compression and keeps querying trivial (`SELECT original_content WHERE ...`).
> Moving content to MinIO would add a second I/O hop on every pipeline rerun,
> require presigned-URL management, and complicate transactional guarantees
> (document row + blob must stay in sync).  If the user base grows past ~50
> concurrent heavy uploaders, revisit with an ADR to externalise content to
> object storage and replace the column with a `content_object_key TEXT`
> reference.

CREATE TABLE document_artifacts (
    document_id     UUID NOT NULL REFERENCES documents(document_id),
    version         INT NOT NULL,
    artifact_json   JSONB NOT NULL,
    summary_json    JSONB,
    flashcards_json JSONB,
    concept_map_json JSONB,
    validation_json JSONB,
    fingerprints_json JSONB NOT NULL DEFAULT '{}',  -- per-step fingerprints for invalidation
    completed_step  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, version)
);

-- ============================================================
-- Content Blocks (Multimodal)
-- ============================================================
CREATE TABLE document_content_blocks (
    block_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES documents(document_id),
    block_type   TEXT NOT NULL,                 -- 'text', 'image', 'code', 'audio', 'video'
    text_content TEXT,
    media_ref    TEXT,                          -- object storage key
    mime_type    TEXT,
    metadata     JSONB NOT NULL DEFAULT '{}',
    position     INT NOT NULL
);

CREATE TABLE media_assets (
    asset_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES documents(document_id),
    mime_type    TEXT NOT NULL,
    storage_key  TEXT NOT NULL,                 -- MinIO/S3 key
    size_bytes   BIGINT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Spaced Repetition Progress (user-scoped)
-- ============================================================
CREATE TABLE study_progress (
    user_id      UUID NOT NULL REFERENCES users(user_id),
    kb_id        UUID NOT NULL REFERENCES knowledge_bases(kb_id),
    card_id      CHAR(16) NOT NULL,            -- deterministic hash from FlashcardData (includes kb_id)
    ease_factor  REAL NOT NULL DEFAULT 2.5,
    interval     INT NOT NULL DEFAULT 0,
    repetitions  INT NOT NULL DEFAULT 0,
    next_review  DATE NOT NULL DEFAULT CURRENT_DATE,
    last_review  TIMESTAMPTZ,
    PRIMARY KEY (user_id, kb_id, card_id)
);

-- ============================================================
-- Interactions and Audit Trail
-- ============================================================
CREATE TABLE interactions (
    interaction_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_interaction_id UUID REFERENCES interactions(interaction_id),
    interaction_type      TEXT NOT NULL,        -- 'quiz_session', 'search', 'pipeline_run', 'agent_call'
    user_id               UUID REFERENCES users(user_id),
    kb_id                 UUID REFERENCES knowledge_bases(kb_id),
    status                TEXT NOT NULL DEFAULT 'active',
    context               JSONB NOT NULL DEFAULT '{}',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at          TIMESTAMPTZ
);

CREATE TABLE interaction_turns (
    turn_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL REFERENCES interactions(interaction_id),
    actor_type     TEXT NOT NULL,               -- 'user', 'agent', 'system'
    actor_id       TEXT NOT NULL,
    action         TEXT NOT NULL,               -- 'question', 'answer', 'evaluate', 'generate', 'retrieve'
    input_data     JSONB NOT NULL DEFAULT '{}',
    output_data    JSONB NOT NULL DEFAULT '{}',
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms    INT,
    cost           NUMERIC(10,6)
);

-- Interactions design notes:
--   • interaction_turns are append-only; never modified after creation.
--   • The user-facing interactions endpoint (GET /api/interactions) returns only
--     the authenticated user's own interactions and applies the redaction policy
--     below before serialization.
--
-- REDACTION POLICY FOR USER-FACING API:
--   The following fields are STRIPPED from output_data before API exposure to
--   prevent leaking quiz grounding context or reference answers:
--     - output_data.reference_answer
--     - output_data.grounding_context
--     - output_data.raw_prompt
--     - output_data.raw_completion
--   The cost field is also hidden from non-admin users.
--
--   Redaction is enforced by the InteractionStore.list_for_user() method, not
--   by the API router (defense in depth: the store never returns unredacted data
--   for user-facing queries).
--
--   Admin-only endpoints (GET /api/admin/interactions) return unredacted data.

-- ============================================================
-- Pipeline Tasks
-- ============================================================
CREATE TABLE pipeline_tasks (
    task_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES documents(document_id),
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending, running, done, failed
    worker_id    TEXT,                              -- which worker claimed this task
    claimed_at   TIMESTAMPTZ,                      -- when the worker claimed it (staleness detection)
    error        TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- ============================================================
-- Transactional Outbox (guarantees at-least-once event delivery)
-- ============================================================
CREATE TABLE outbox_events (
    event_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_num BIGSERIAL NOT NULL UNIQUE,     -- monotonic ordering for cursor-based consumption
    event_type   TEXT NOT NULL,                 -- e.g. 'DocumentIngested', 'PipelineStepCompleted'
    payload      JSONB NOT NULL,
    published    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);
CREATE INDEX ix_outbox_unpublished ON outbox_events (created_at) WHERE NOT published;

CREATE TABLE consumer_cursors (
    consumer_name   TEXT PRIMARY KEY,
    last_sequence   BIGINT NOT NULL,            -- last processed sequence_num
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Read Model Projections (materialized for fast API queries)
-- ============================================================
CREATE TABLE lesson_projections (
    kb_id              UUID NOT NULL REFERENCES knowledge_bases(kb_id),
    lesson_id          TEXT NOT NULL,
    document_id        UUID NOT NULL REFERENCES documents(document_id),
    title              TEXT NOT NULL,
    flashcard_count    INT NOT NULL DEFAULT 0,
    concept_count      INT NOT NULL DEFAULT 0,
    processed_at       TIMESTAMPTZ,
    summary_excerpt    TEXT,
    PRIMARY KEY (kb_id, lesson_id)
);
```

#### Key Design Decisions

1. **Content hash uniqueness is scoped to knowledge base** — the same document
   content can exist in different knowledge bases intentionally.
2. **Lesson revision model** — `lesson_id` is a stable, logical identifier.
   Uploading new content for the same `lesson_id` creates a new document row
   with an incremented `revision` number.  The previous document is deactivated
   (`is_active = FALSE`).  Only the active revision is served by read-model
   queries and the pipeline.
3. **Artifact versioning** — every pipeline run creates a new version.
   Checkpointing writes to the current version; a full reprocess bumps the
   version.
4. **Read model projections** — `lesson_projections` is updated by the pipeline
   after artifact flush, eliminating N+1 queries from the lessons list endpoint.
5. **Interactions are append-only** — turns are never modified after creation.
   This supports audit and compliance requirements.

### 7.2 Neo4j — Derived Graph (Query Store)

Neo4j is a **derived projection** rebuilt from canonical PostgreSQL data.  It is
not a source of truth.  Loss of the Neo4j graph is recoverable by re-indexing
from artifacts.

#### Graph Schema

```
(:KnowledgeBase {id, name})

(:Lesson {id, kb_id, title})
    -[:BELONGS_TO]->(:KnowledgeBase)

(:Concept {key, name, primary_definition, normalized_key})
    -[:IN_KNOWLEDGE_BASE]->(:KnowledgeBase)

(:Lesson)-[:ASSERTS_CONCEPT {definition, confidence}]->(:Concept)

(:Fact {id, text, lesson_id})
(:Lesson)-[:HAS_FACT]->(:Fact)

(:Chunk {id, text, position, lesson_id, embedding})
(:Lesson)-[:HAS_CHUNK]->(:Chunk)
(:Chunk)-[:MENTIONS]->(:Concept)

(:RelationAssertion {id, source_key, target_key, label, description, lesson_id})
(:Lesson)-[:ASSERTS_RELATION]->(:RelationAssertion)

-- Derived projection edges (rebuilt from assertions):
(:Concept)-[:RELATES_TO {label, support_count, source_lessons}]->(:Concept)
```

#### Key Design Decisions

1. **Knowledge base isolation** — every graph node carries `kb_id`.  Queries
   always filter by knowledge base.
2. **Lesson-owned assertions vs. global projection** — lesson-specific
   definitions and relationships are stored as `ASSERTS_CONCEPT` relations and
   `RelationAssertion` nodes.  The global `Concept.primary_definition` and
   `RELATES_TO` edges are **derived** by aggregation.
3. **Deterministic node IDs** — `Fact.id` uses `sha256(lesson_id|text)[:16]`.
   `Chunk.id` uses `sha256(lesson_id|position|text)[:16]`.  This makes all
   MERGE operations idempotent.
4. **UNWIND batches** — all writes use UNWIND to minimize round-trips.
5. **Concept normalization** — consistent `normalized_key` via a shared
   `dedupe_key()` function used across all write paths.
6. **Embedding storage** — chunk embeddings stored as node properties for
   vector similarity search (Neo4j 5.x vector indexes).

#### Lesson Revision Lifecycle in Neo4j

When a lesson receives a new revision (`ProcessingCompleted` event for a new
`document_id` with the same `lesson_id`), the `GraphIndexerConsumer` must clean
up the previous graph state before writing the new one.  Without cleanup, stale
concepts, facts, and chunks accumulate and degrade retrieval quality.

**Required procedure:**

```cypher
// Step 1: Delete old lesson node and all lesson-owned entities
//         (Facts, Chunks, RelationAssertions are lesson-scoped)
MATCH (l:Lesson {id: $lesson_id, kb_id: $kb_id})
OPTIONAL MATCH (l)-[:HAS_FACT]->(f:Fact)
OPTIONAL MATCH (l)-[:HAS_CHUNK]->(ch:Chunk)
OPTIONAL MATCH (l)-[:ASSERTS_RELATION]->(ra:RelationAssertion)
DETACH DELETE f, ch, ra, l

// Step 2: Clean up orphaned concepts (no remaining ASSERTS_CONCEPT edges)
MATCH (c:Concept)-[:IN_KNOWLEDGE_BASE]->(kb:KnowledgeBase {id: $kb_id})
WHERE NOT EXISTS { MATCH ()-[:ASSERTS_CONCEPT]->(c) }
DETACH DELETE c

// Step 3: Rebuild RELATES_TO edges from remaining assertions
//         (aggregation query over all RelationAssertions in this KB)
// ... standard projection rebuild ...

// Step 4: MERGE new lesson data (normal write path — idempotent via UNWIND)
```

**Ordering guarantee:** The cleanup and write happen within the same
`GraphIndexerConsumer.handle()` call, which processes events sequentially
per consumer.  No concurrent write can interleave between cleanup and rebuild.

#### Retrieval Strategy (Priority Order)

1. **Graph traversal** — concept matching, relationship navigation
2. **Full-text / lexical search** — Neo4j full-text indexes
3. **Vector similarity** — embedding-based search as a last resort

This ordering minimizes cost (no embedding computation for graph-answerable
queries) and maximizes precision (graph structure carries more semantic signal
than raw similarity).

#### Graph RAG: Concept Neighborhood Retrieval

Standard Vector RAG sends "top N most similar chunks" to the LLM.  MindForge
uses **Graph RAG** — retrieval that exploits the knowledge graph structure to
build a smaller, more precise context.

The `retrieve_concept_neighborhood()` method on `RetrievalPort` traverses the
graph from a target concept outward:

```cypher
// For a given concept: its definition, supporting facts, and
// definitions of related concepts (up to depth 2)
MATCH (c:Concept {key: $concept_key})-[:IN_KNOWLEDGE_BASE]->(kb {id: $kb_id})
OPTIONAL MATCH (c)<-[ac:ASSERTS_CONCEPT]-(l:Lesson)
OPTIONAL MATCH (l)-[:HAS_FACT]->(f:Fact)
OPTIONAL MATCH (c)-[:RELATES_TO*1..2]-(neighbor:Concept)
  -[:IN_KNOWLEDGE_BASE]->(kb)
OPTIONAL MATCH (neighbor)<-[nac:ASSERTS_CONCEPT]-(nl:Lesson)
RETURN c.name, c.primary_definition,
       collect(DISTINCT f.text) as facts,
       collect(DISTINCT {name: neighbor.name, definition: nac.definition}) as neighbors
```

**Why this is better than vector search:**  Instead of sending the LLM "3 most
similar text chunks" (which may overlap or miss context), Graph RAG sends
"definition of concept X + facts that support it + related concepts with their
definitions."  This is:
- **Smaller** (less tokens → lower cost)
- **More precise** (structured knowledge instead of raw text)
- **Graph-aware** (captures relationships that chunk similarity misses)

The `retrieve()` method for general queries uses a hybrid approach:
1. Extract concept mentions from the query (keyword/NER matching)
2. For each matched concept: `retrieve_concept_neighborhood()`
3. If no concepts matched: fall back to full-text → vector similarity
4. Assemble context from neighborhoods + any supplementary chunks

```python
@dataclass
class ConceptNeighborhood:
    concept: ConceptNode
    definition: str
    supporting_facts: list[str]
    related_concepts: list[RelatedConceptSummary]  # name + definition + relation label
    source_lessons: list[str]                       # lesson_ids that assert this concept
```

#### Graph-Based Quiz Question Selection

The knowledge graph enables **intelligent quiz question targeting** — the
primary justification for Neo4j in MindForge.  Instead of random topic
selection, the quiz service queries the graph for concepts the user knows
least and that are most central to the knowledge base.

```cypher
// Find concepts the user struggles with (low ease_factor)
// that are well-connected in the graph (high degree = important)
MATCH (c:Concept)-[:IN_KNOWLEDGE_BASE]->(kb:KnowledgeBase {id: $kb_id})
OPTIONAL MATCH (c)<-[r:REVIEWED]-(u:User {id: $user_id})
WITH c,
     coalesce(r.ease_factor, 2.5) as ease,
     coalesce(r.last_review, date('1970-01-01')) as last_reviewed,
     count{ (c)-[:RELATES_TO]-() } as degree
WHERE ease < 2.3 OR r IS NULL    // struggling or never reviewed
RETURN c.key, c.name, c.primary_definition, ease, degree
ORDER BY ease ASC, degree DESC   // weakest first, most connected first
LIMIT $limit
```

The `find_weak_concepts()` method on `RetrievalPort` encapsulates this query.
The quiz service uses the result to:
1. Pick target concepts for question generation
2. Retrieve concept neighborhoods as grounding context
3. Generate questions that target specific knowledge gaps

This creates a feedback loop: quiz → evaluation → SR update → graph query
picks different concepts next time.  The user always gets questions on their
weakest, most important topics.

```python
@dataclass
class WeakConcept:
    concept_key: str
    concept_name: str
    definition: str
    ease_factor: float        # from spaced repetition (2.5 = never reviewed)
    graph_degree: int         # number of RELATES_TO edges (centrality proxy)
    last_reviewed: date | None
```

### 7.3 Redis — Cache and Coordination

| Use Case | Format | TTL | Without Redis |
|---|---|---|---|
| Quiz sessions | JSON hash per `session_id` | 30 min | PostgreSQL-backed (same contract, higher latency) |
| Semantic cache (LLM responses) | JSON with embedding key | 24 hours | Disabled (cache miss = fresh LLM call) |
| Outbox relay broadcast | Pub/Sub channels | N/A | Relay skipped; durable consumers poll outbox directly |
| SSE event delivery | Pub/Sub → SSE | N/A | SSE handler polls outbox_events directly |
| Rate limiting counters | INCR with EXPIRE | Per window | PostgreSQL advisory locks or in-process (single API) |

**Degradation model (no Redis):**

Redis is **not required** but strongly recommended for production.  When Redis
is unavailable, the system maintains **full semantic correctness** with degraded
performance:

1. **Quiz sessions** fall back to `PostgresQuizSessionStore` — same
   `QuizSessionStore` protocol, higher per-request latency (~5ms vs ~1ms).
2. **Outbox relay** does not start (no Pub/Sub target).  Ephemeral consumers
   (SSE, notifications) degrade to polling `outbox_events` directly with
   bounded delay.
3. **Durable consumers** (Graph Indexer, Audit Logger) are unaffected — they
   always poll PostgreSQL, never Redis.
4. **Semantic cache** is disabled — every LLM call goes to the provider.
   Cost increases but correctness is preserved.
5. **Cross-process propagation** works via PostgreSQL polling instead of
   Pub/Sub.  Latency increases from ~10ms to ~poll_interval.

A loud startup warning is emitted when Redis is absent:
```
WARNING: Redis not configured.  Quiz sessions use PostgreSQL fallback.
         SSE delivery latency degraded to poll interval.
         Semantic cache disabled.  See docs for full implications.
```

### 7.4 MinIO/S3 — Media Asset Storage

Binary assets (images extracted from documents, uploaded media) are stored in
object storage, not in PostgreSQL.  The `media_assets` table holds metadata and
the storage key; the asset itself lives in MinIO.

Bucket structure:
```
mindforge-assets/
  {kb_id}/{document_id}/{asset_id}.{ext}
```

---

## 8. AI Gateway and LLM Integration

### 8.1 Architecture

All LLM interactions flow through a single `AIGateway` abstraction backed by
LiteLLM.  No application code ever calls a provider SDK directly.

```
┌─────────────────────────────────────────────────┐
│              Application Code                    │
│  (Agents, Quiz Service, Search Service)          │
└──────────────────┬──────────────────────────────┘
                   │  uses AIGateway port
┌──────────────────▼──────────────────────────────┐
│              AI Gateway (LiteLLMGateway)         │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │  Unified Interface                         │  │
│  │  complete() → CompletionResult             │  │
│  │  embed()    → list[list[float]]            │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Retry /  │  │ Cost     │  │ Tracing      │   │
│  │ Circuit  │  │ Tracking │  │ (Langfuse)   │   │
│  │ Breaker  │  │          │  │              │   │
│  └──────────┘  └──────────┘  └──────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │  LiteLLM Router                          │    │
│  │  model → provider mapping + fallbacks    │    │
│  └──────────┬───────────────────────────────┘    │
└─────────────┼────────────────────────────────────┘
              │
   ┌──────────▼──────────┐
   │  LLM Providers      │
   │  OpenAI │ Anthropic  │
   │  Google │ OpenRouter │
   │  Ollama │ vLLM       │
   │  Any OpenAI-compat.  │
   └─────────────────────┘
```

### 8.2 Gateway Contract

```python
@dataclass(frozen=True)
class CompletionResult:
    content: str
    input_tokens: int
    output_tokens: int
    model: str
    provider: str
    latency_ms: float
    cost_usd: float | None

class LiteLLMGateway:
    """AIGateway implementation wrapping LiteLLM."""

    def __init__(
        self,
        default_model: str,
        model_map: dict[str, str],       # logical name → LiteLLM model string
        fallback_models: list[str],
        timeout_seconds: int = 180,
        max_retries: int = 3,
        tracer: LangfuseAdapter | None = None,
    ) -> None: ...

    async def complete(self, *, model: str, messages: list[dict],
                       temperature: float = 0.0,
                       response_format: dict | None = None) -> CompletionResult: ...

    async def embed(self, *, model: str, texts: list[str]) -> list[list[float]]: ...
```

### 8.3 Model Routing

The gateway uses **logical model names** mapped to provider-specific identifiers
in configuration:

```env
# Cloud providers (direct)
MODEL_SMALL=openai/gpt-4o-mini
MODEL_LARGE=openai/gpt-4o
MODEL_VISION=openai/gpt-4o
MODEL_EMBEDDING=openai/text-embedding-3-small
MODEL_FALLBACK=anthropic/claude-3-haiku-20240307

# Cloud providers via OpenRouter (single API key, 200+ models)
# MODEL_SMALL=openrouter/openai/gpt-4o-mini
# MODEL_LARGE=openrouter/anthropic/claude-3.5-sonnet
# MODEL_VISION=openrouter/openai/gpt-4o
# MODEL_FALLBACK=openrouter/meta-llama/llama-3.1-70b-instruct
# OPENROUTER_API_KEY=sk-or-...

# Local model examples (via Ollama, vLLM, or any OpenAI-compatible server)
# MODEL_SMALL=ollama/llama3.1
# MODEL_LARGE=ollama/llama3.1:70b
# MODEL_EMBEDDING=ollama/nomic-embed-text
```

Agents request models by role (`small`, `large`, `vision`), not by provider
string.  Changing a provider means changing configuration, not code.

### 8.4 OpenRouter and Local Model Support

LiteLLM natively supports **OpenRouter** (a cloud aggregator providing 200+
models through a single API key) and **local/self-hosted models**, making
MindForge fully operational with any combination of cloud, aggregated, and
local providers:

| Provider | LiteLLM Prefix | Use Case |
|---|---|---|
| OpenRouter | `openrouter/` | Cloud aggregator — 200+ models via single API key |
| Ollama | `ollama/` | Local inference via `ollama serve` |
| vLLM | `hosted_vllm/` | High-throughput local/remote serving |
| llama.cpp server | `openai/` + `api_base` | Lightweight local inference |
| LM Studio | `openai/` + `api_base` | Desktop GUI for local models |
| Any OpenAI-compatible API | `openai/` + `api_base` | Self-hosted or corporate proxies |

Configuration for local models:

```env
# Point LiteLLM to a local Ollama instance
MODEL_SMALL=ollama/llama3.1
MODEL_LARGE=ollama/llama3.1:70b
MODEL_VISION=ollama/llava
MODEL_EMBEDDING=ollama/nomic-embed-text
OLLAMA_API_BASE=http://localhost:11434

# Or point to any OpenAI-compatible local server
# MODEL_SMALL=openai/local-model
# OPENAI_API_BASE=http://localhost:8000/v1
# OPENAI_API_KEY=not-needed
```

The gateway adapter handles provider-specific quirks (e.g., Ollama does not
return cost data) transparently.  Cost tracking records `cost_usd=0` for local
models.

### 8.4 Resilience

| Mechanism | Implementation |
|---|---|
| **Retry with exponential backoff + jitter** | LiteLLM built-in + custom wrapper |
| **Circuit breaker** | Open after 5 consecutive failures; half-open after 60s cooldown |
| **Provider fallback** | Configurable chain: primary → fallback → degraded response |
| **Timeout** | Per-call timeout governed by deadline profile (see below) |
| **Rate limit handling** | Respect `Retry-After` headers; backpressure to callers |

> **Fingerprint invariant**: When a fallback model serves a pipeline step, the
> `model_id` in `StepFingerprint` reflects the **actually used model**, not the
> originally requested one.  This means a step processed by a fallback model
> produces a different fingerprint and will NOT be treated as a cache hit for
> the primary model's fingerprint.  This is intentional — different models may
> produce different outputs.  On the next pipeline run, if the primary model is
> back, the step will rerun and overwrite the fallback result.

#### Per-Path Latency Budgets

Not all paths have the same time sensitivity.  The gateway enforces
**deadline profiles** that match the caller's context:

| Path | Example Endpoint | Total Deadline | Per-LLM-Call Timeout | Notes |
|---|---|---|---|---|
| **Interactive quiz** | `POST .../quiz/{id}/answer` | 15 s | 12 s | Single LLM call (evaluation) |
| **Interactive search** | `POST .../search` | 15 s | 12 s | Retrieval + optional rerank |
| **Pipeline step (batch)** | Worker: summarizer | 180 s | 120 s | Long-form generation |
| **Pipeline step (vision)** | Worker: image_analyzer | 180 s | 120 s | Vision model may be slow |
| **Flashcard review** | `POST .../flashcards/review` | 5 s | — | No LLM call (pure SR math) |
| **SSE / events** | `GET .../events` | ∞ (streaming) | — | Keep-alive every 30 s |

The `AIGateway` accepts a `deadline_profile: DeadlineProfile` parameter
that the calling code provides based on its context:

```python
class DeadlineProfile(str, Enum):
    INTERACTIVE = "interactive"       # 15s total budget
    BATCH = "batch"                   # 180s total budget
    BACKGROUND = "background"         # 300s total budget (reindex, backfill)

class AIGateway(Protocol):
    async def complete(self, *, model: str, messages: list[dict],
                       temperature: float = 0.0,
                       response_format: dict | None = None,
                       deadline: DeadlineProfile = DeadlineProfile.BATCH,
                       ) -> CompletionResult: ...
```

API routers inject `DeadlineProfile.INTERACTIVE`; pipeline agents use
`DeadlineProfile.BATCH` by default.  If the total deadline is exceeded, the
gateway raises `DeadlineExceeded` and the caller decides how to handle it
(return a degraded response for interactive, retry later for batch).

### 8.5 Async-Only

The gateway is **async-only** (`httpx.AsyncClient` under LiteLLM's async API).
CLI entry points that need synchronous calls use `asyncio.run()` at the
outermost level.  No sync HTTP calls ever block an async event loop.

### 8.6 Client Never Talks to Models

The API does **not** expose a generic chat or completion endpoint.  Every
client-to-model interaction goes through a **purpose-built endpoint** with a
fixed input/output schema:

- `POST /api/knowledge-bases/{kb_id}/quiz/{session_id}/answer` — evaluates an answer
- `POST /api/knowledge-bases/{kb_id}/search` — performs a knowledge search
- `POST /api/knowledge-bases/{kb_id}/documents` — triggers ingestion (which may use LLMs internally)

All interactive endpoints are scoped to a knowledge base.  The browser never
knows which model is used or what the raw prompt looks like.

---

## 9. Agent Architecture and Orchestration

### 9.1 Agent Protocol

Every processing agent implements a common protocol:

```python
class Agent(Protocol):
    """Contract for all AI-powered processing agents."""

    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> AgentCapability: ...

    async def execute(self, context: AgentContext) -> AgentResult: ...

@dataclass(frozen=True)
class AgentCapability:
    name: str
    description: str
    input_types: list[str]             # what the agent expects in context
    output_types: list[str]            # what the agent produces
    required_model_tier: ModelTier     # SMALL, LARGE, VISION
    estimated_cost_tier: CostTier     # LOW, MEDIUM, HIGH

@dataclass
class AgentContext:
    document_id: UUID
    knowledge_base_id: UUID
    artifact: DocumentArtifact         # mutable — agents enrich it in place
    gateway: AIGateway
    retrieval: RetrievalPort | None
    settings: ProcessingSettings
    tracer: TracingContext
    metadata: dict                     # step-specific parameters

@dataclass
class AgentResult:
    success: bool
    output_key: str                    # which artifact field was set
    tokens_used: int
    cost_usd: float
    duration_ms: float
    error: str | None = None
```

### 9.2 Agent Registry (Open/Closed)

Agents are registered in a registry; adding a new agent requires no modification
to the orchestrator.

```python
class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Agent:
        return self._agents[name]

    def all(self) -> list[Agent]:
        return list(self._agents.values())
```

### 9.3 Concrete Agents

| Agent | Responsibility | Model Tier | Idempotent |
|---|---|---|---|
| `DocumentParser` | Extract text, metadata, images from uploaded file | None (deterministic) | Yes |
| `ImageAnalyzer` | Describe images/diagrams with vision model | VISION | Yes |
| `Preprocessor` | Clean content, remove noise sections | SMALL | Yes |
| `ArticleFetcher` | Classify links, fetch external content | SMALL | Yes (cached) |
| `Summarizer` | Generate structured summary with key concepts and facts | LARGE | Yes |
| `FlashcardGenerator` | Generate study flashcards | LARGE | Yes |
| `ConceptMapper` | Generate concept relationship map | LARGE | Yes |
| `RelevanceGuard` | Validate content relevance against knowledge base | SMALL | Yes |
| `QuizGenerator` | Generate quiz questions from retrieval context | LARGE | Yes |
| `QuizEvaluator` | Evaluate user answers against reference | LARGE | No (per-interaction) |

### 9.4 Orchestration Model

The pipeline is a **declarative agent graph**, not a hard-coded sequential
function.  Each node in the graph is an agent; edges represent data dependencies.

```
                    ┌──────────────┐
                    │ DocumentParser│
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │RelevanceGuard│ ──── reject if irrelevant
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼─────┐ ┌───▼───────┐    │
       │ImageAnalyzer│ │Preprocessor│    │
       └──────┬──────┘ └───┬───────┘    │
              │            │            │
              └─────┬──────┘            │
                    │                   │
             ┌──────▼───────┐    ┌──────▼───────┐
             │ArticleFetcher│    │ (parallel     │
             └──────┬───────┘    │  branch join) │
                    │            └───────────────┘
                    │
             ┌──────▼───────┐
             │  Summarizer  │
             └──────┬───────┘
                    │
         ┌─────────┼──────────┐
         │                    │
  ┌──────▼──────────┐  ┌─────▼────────┐
  │FlashcardGenerator│  │ConceptMapper │
  └─────────────────┘  └──────────────┘
         │                    │
         └────────┬───────────┘
                  │
           ┌──────▼───────┐
           │  Validation  │ (deterministic)
           └──────┬───────┘
                  │
           ┌──────▼───────┐
           │ GraphIndexer  │
           └──────┬───────┘
                  │
           ┌──────▼───────┐
           │  ReadModel    │ (update lesson_projections)
           │  Publisher    │
           └──────────────┘
```

### 9.5 Orchestrator Implementation

```python
class PipelineOrchestrator:
    """Executes a declarative agent graph with checkpointing."""

    def __init__(
        self,
        agent_registry: AgentRegistry,
        graph: OrchestrationGraph,
        artifact_repo: ArtifactRepository,
        event_bus: EventPublisher,
        interaction_store: InteractionStore,
    ) -> None: ...

    async def run(
        self,
        document_id: UUID,
        artifact: DocumentArtifact,
        context: AgentContext,
        *,
        force: bool = False,
    ) -> DocumentArtifact:
        """Execute the processing graph.

        For each step:
        1. Check if the output is already present (checkpoint skip).
        2. Execute the agent.
        3. Flush artifact checkpoint to the repository.
        4. Publish PipelineStepCompleted event.
        5. Record interaction turn for audit.
        """
        ...
```

**Checkpointing contract:**  A step is skippable if and only if (a) the
corresponding artifact field is already non-None (or non-empty list), AND (b)
the **step fingerprint** matches.  The `force=True` flag bypasses checkpoints
and reprocesses from scratch.per-agent semver (e.g. "1.0.0"), NOT global git hash

    def compute(self) -> str:
        return sha256(f"{self.input_hash}|{self.prompt_version}|{self.model_id}|{self.agent_version}").hexdigest()[:16]

# Each agent declares its own version — changed ONLY when agent logic changes:
#   class SummarizerAgent(Agent):
#       __version__ = "1.0.0"
# This prevents unrelated code changes from invalidating all checkpoints.
Each checkpoint records a **step fingerprint** — a hash of the inputs that
produced the output.  If any input changes, the checkpoint is invalidated
even though the output field is populated.

```python
@dataclass(frozen=True)
class StepFingerprint:
    input_hash: str          # sha256 of step inputs (upstream artifact fields)
    prompt_version: str      # version tag of the prompt template used
    model_id: str            # logical model name (e.g. "large")
    agent_version: str       # per-agent semver (e.g. "1.0.0"), NOT global git hash

    def compute(self) -> str:
        return sha256(f"{self.input_hash}|{self.prompt_version}|{self.model_id}|{self.agent_version}").hexdigest()[:16]

# Each agent declares its own version — changed ONLY when agent logic changes:
#   class SummarizerAgent(Agent):
#       __version__ = "1.0.0"
# This prevents unrelated code changes from invalidating all checkpoints.
```

The artifact stores per-step fingerprints alongside outputs:

```python
@dataclass
class StepCheckpoint:
    output_key: str           # which artifact field this step produced
    fingerprint: str          # StepFingerprint.compute() at time of execution
    completed_at: datetime
```

#### DAG-Aware Invalidation

Because the graph is a DAG, invalidating a step **cascades to its dependents**.
If the Summarizer's fingerprint changes (e.g., new prompt version), the
FlashcardGenerator and ConceptMapper outputs are also invalidated because
they depend on the summary:

```python
def invalidated_steps(graph: OrchestrationGraph, changed_step: str) -> set[str]:
    """Return all steps that need re-execution when changed_step is invalidated."""
    result = {changed_step}
    for step in graph.topological_order():
        if any(dep in result for dep in graph.dependencies(step)):
            result.add(step)
    return result
```

After each LLM-producing step, the artifact and its fingerprint are flushed
to the database:

```python
async def _execute_step(self, step: GraphNode, context: AgentContext) -> None:
    agent = self.agent_registry.get(step.agent_name)

    # Compute current fingerprint
    current_fp = self._compute_fingerprint(step, context)

    # Checkpoint check: skip only if output exists AND fingerprint matches
    stored_fp = self._get_stored_fingerprint(context.artifact, step.output_key)
    if (not context.force
            and self._step_already_done(context.artifact, step.output_key)
            and stored_fp == current_fp):
        log.info("Step %s — checkpoint valid (fp=%s), skipping", step.name, current_fp)
        return

    # Execute
    result = await agent.execute(context)

    # Record fingerprint
    context.artifact.step_fingerprints[step.output_key] = StepCheckpoint(
        output_key=step.output_key,
        fingerprint=current_fp,
        completed_at=utcnow(),
    )

    # Persist checkpoint + outbox event in the SAME transaction
    async with self.db_engine.begin() as conn:
        await self.artifact_repo.save_checkpoint(context.artifact, conn)
        await self.event_publisher.publish_in_tx(PipelineStepCompleted(
            document_id=context.document_id,
            step_name=step.name,
            artifact_version=context.artifact.version,
            timestamp=utcnow(),
        ), connection=conn)
```

This ensures that:
- Changing a prompt template invalidates all steps using that prompt and their
  dependents.
- Changing a model mapping invalidates affected steps.
- Upstream data changes (e.g., re-cleaned content) cascade through the graph.
- Unchanged steps are legitimately skipped, reducing cost on recovery.

### 9.6 Agent-to-Agent Communication

Agents do **not** communicate directly.  All inter-agent data flows through
the shared `DocumentArtifact` object and the `AgentContext`.  The orchestrator
controls what data each agent sees and in what order.

For agents that need retrieval context (e.g., `Summarizer` needs known concepts
from the graph), the orchestrator queries the `RetrievalPort` and injects the
result into `AgentContext.metadata` before calling the agent.

This is the **Mediator pattern** — the orchestrator is the single point of
coordination.  Agents remain stateless and independently testable.

### 9.7 Prompt Internationalization

MindForge prompt templates support multiple locales so that agent instructions
(system prompts, few-shot examples, output schemas) can be delivered in the
language that best matches the user's knowledge base.  Polish (`pl`) is the
default locale; English (`en`) is the first additional locale.

#### File Naming Convention

Prompt files follow the pattern `{name}_{locale}.md`, e.g.:

```
prompts/
├── summarizer_system.pl.md      # Polish (default)
├── summarizer_system.en.md      # English
├── summarizer_user.pl.md
├── summarizer_user.en.md
└── ...                          # one .pl.md + .en.md per template
```

Locale-neutral variants (files without a locale suffix) are not used — every
template must have at least a `.pl.md` baseline.

#### `load_prompt()` Locale Resolution

```python
# mindforge/infrastructure/ai/prompts/__init__.py
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent
_DEFAULT_LOCALE = "pl"

def load_prompt(filename: str, locale: str = _DEFAULT_LOCALE) -> str:
    """Load a prompt template for the requested locale.

    Resolution order:
      1. {stem}_{locale}{suffix}   — exact locale match
      2. {stem}_{DEFAULT_LOCALE}{suffix} — fallback to Polish

    Raises FileNotFoundError if neither file exists.
    """
    p = Path(filename)
    stem, suffix = p.stem, p.suffix or ".md"
    # Strip any existing locale suffix from the stem before resolving
    for candidate in (f"{stem}.{locale}{suffix}", f"{stem}.{_DEFAULT_LOCALE}{suffix}"):
        path = _PROMPTS_DIR / candidate
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        f"No prompt file found for '{filename}' in locale '{locale}' "
        f"or fallback locale '{_DEFAULT_LOCALE}'"
    )
```

Prompt modules pass `locale` through from the call site:

```python
# mindforge/infrastructure/ai/prompts/summarizer.py
from mindforge.infrastructure.ai.prompts import load_prompt

def get_system_prompt(locale: str = "pl") -> str:
    return load_prompt("summarizer_system.md", locale)

def get_user_template(locale: str = "pl") -> str:
    return load_prompt("summarizer_user.md", locale)
```

#### Locale in `ProcessingSettings` and `AgentContext`

`ProcessingSettings` (domain layer) carries a `prompt_locale` field:

```python
@dataclass(frozen=True)
class ProcessingSettings:
    model_size: Literal["small", "large"] = "large"
    max_flashcards: int = 20
    max_concepts: int = 50
    prompt_locale: str = "pl"          # ← new field; default Polish
```

The orchestrator injects `ProcessingSettings` into `AgentContext`, so every
agent automatically receives the correct locale without per-agent changes.
Agents call `get_system_prompt(context.settings.prompt_locale)` to obtain the
locale-specific template.

#### Checkpoint Invalidation

The `StepFingerprint` already hashes `prompt_version`.  Because changing a
locale loads a different file, prompt modules must encode the locale in the
version string they expose:

```python
VERSION = f"1.0.0+{locale}"   # e.g. "1.0.0+pl", "1.0.0+en"
```

This ensures that switching a knowledge base from `pl` to `en` automatically
invalidates all cached pipeline steps for that KB and triggers full
re-processing under the new locale — no manual cache flush required.

#### Per-Knowledge-Base Locale

`KnowledgeBase` stores the user's locale preference:

```python
@dataclass
class KnowledgeBase:
    kb_id: UUID
    owner_id: UUID
    name: str
    prompt_locale: str = "pl"   # ← persisted, user-configurable
    created_at: datetime
    updated_at: datetime
```

When the pipeline worker starts a task for a KB, it reads `kb.prompt_locale`
and passes it through `ProcessingSettings → AgentContext`.  The Angular
settings page (Phase 12) exposes a locale selector for this field.

---

## 10. Ingestion Pipeline

### 10.1 Ingestion Service

A single service handles document intake for all surfaces (API upload, Discord
upload, file watcher).  It enforces deduplication, validation, and task
submission.

```python
class IngestionService:
    """Unified document intake for all surfaces."""

    def __init__(
        self,
        doc_repo: DocumentRepository,
        sanitizer: UploadSanitizer,
        parsers: ParserRegistry,
        event_publisher: OutboxEventPublisher,
    ) -> None: ...

    async def ingest(
        self,
        raw_bytes: bytes,
        filename: str,
        knowledge_base_id: UUID,
        upload_source: UploadSource,
        uploaded_by: UUID | None = None,
    ) -> IngestionResult:
        """
        In a single transaction:
        1. Sanitize filename.
        2. Validate file size and format.
        3. Compute content hash.
        4. Reject if content hash already exists in this KB (dedup).
        5. Check per-user pending task limit (MAX_PENDING_TASKS_PER_USER).
           Reject with 429 if exceeded: "Masz X zadań w kolejce, poczekaj."
        6. Parse document to extract text and metadata.
        7. Resolve lesson identity (lesson_id) — see Section 6.2.
        8. If existing active document for this lesson_id in KB:
           a. Mark it is_active=FALSE.
           b. Compute new revision = prev.revision + 1.
        9. Store new document (is_active=TRUE).
        10. Insert pipeline_task row (status=pending).
        11. Insert outbox event (DocumentIngested).
        12. COMMIT.
        13. Return IngestionResult with document_id and task_id.
        """
        ...
```

### 10.2 Deduplication and Revision Rules

`lesson_id` is a **stable logical identifier** for a lesson.  Uploading new
content for the same `lesson_id` within a KB creates a **new revision** (a new
`document_id` with `revision = prev + 1`).  The old revision is deactivated
(`is_active = FALSE`).  History is preserved — old revisions remain in the
database for audit and rollback.

**Ingestion flow for revisions:**
1. Resolve `lesson_id` from filename / metadata.
2. Check `content_sha256` — identical content is always rejected (dedup).
3. Query `documents WHERE kb_id = ? AND lesson_id = ? AND is_active = TRUE`.
4. If a previous active document exists:
   a. Set `is_active = FALSE` on the previous document.
   b. Insert new document with `revision = prev.revision + 1, is_active = TRUE`.
5. If no previous document: insert with `revision = 1, is_active = TRUE`.
6. Submit pipeline task for the new document.

All steps above execute within a single transaction.

| Scenario | Behavior |
|---|---|
| Same content hash, same KB | Reject — no-op, content already processed |
| Same lesson_id, different content, same KB | Create new revision, deactivate previous |
| Same content hash, different KB | Allow — KBs are independent |
| Same filename, different content | Accept as new document (identity is content-based, not name-based) |
| No resolvable lesson identity | Reject upload with clear error |

### 10.3 Relevance Guard

After initial parsing and before expensive LLM processing, the
`RelevanceGuard` agent validates that the document content is thematically
consistent with the target knowledge base.

```python
class RelevanceGuard(Agent):
    """Validates content relevance against knowledge base."""

    async def execute(self, context: AgentContext) -> AgentResult:
        # 1. Extract existing concepts from the KB graph
        # 2. Compare document content (keywords, embeddings) against KB profile
        # 3. If similarity below threshold → flag or reject
        # 4. For empty KBs (first document) → always accept
        ...
```

This prevents a cooking recipe from being accidentally processed into an AI
agents knowledge base.

### 10.4 Document Format Parsing

A **parser registry** implements Open/Closed: adding a new format means
registering a new parser, not modifying the ingestion service.

```python
class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, DocumentParser] = {}

    def register(self, mime_type: str, parser: DocumentParser) -> None:
        self._parsers[mime_type] = parser

    def get(self, mime_type: str) -> DocumentParser:
        parser = self._parsers.get(mime_type)
        if parser is None:
            raise UnsupportedFormatError(mime_type)
        return parser

class DocumentParser(Protocol):
    def parse(self, raw_bytes: bytes, filename: str) -> ParsedDocument: ...

@dataclass
class ParsedDocument:
    text_content: str
    metadata: dict                     # frontmatter, PDF metadata, etc.
    content_blocks: list[ContentBlock]
    embedded_images: list[bytes]       # extracted images for analysis
```

Initial parsers: `MarkdownParser`, `PdfParser`, `DocxParser`, `TxtParser`.

### 10.5 Chunking Strategy

After parsing and before embedding/indexing, document text is split into chunks
for storage in Neo4j and for retrieval context assembly.  Chunking quality
directly affects RAG performance — it is a non-trivial design decision.

**Strategy: Heading-Aware Chunking with Overlap**

For Markdown and structured documents, the chunker uses headings as natural
split points:

```
1. Split on ## and ### headings → each heading starts a new chunk
2. If chunk > MAX_CHUNK_TOKENS → split further on paragraph boundaries (\n\n)
3. If sub-chunk still > MAX_CHUNK_TOKENS → split on sentence boundaries
4. If chunk < MIN_CHUNK_TOKENS → merge with the next chunk
5. Apply OVERLAP_TOKENS between adjacent chunks (contextual continuity)
```

For unstructured text (TXT, extracted PDF without headings), fall back to
paragraph-based splitting with overlap.

**Configuration:**

```env
CHUNK_MAX_TOKENS=500
CHUNK_MIN_TOKENS=100
CHUNK_OVERLAP_TOKENS=100
```

**Chunk identity:**  Each chunk gets a deterministic ID:
`sha256(lesson_id|position|text)[:16]`.  This makes Neo4j `MERGE` idempotent
and preserves chunk identity across reprocesses if content is unchanged.

**Chunk metadata** stored in Neo4j:
- `position`: ordering within the document
- `heading_context`: the heading hierarchy above this chunk (e.g., "## Neural
  Networks > ### Backpropagation") — used to enrich retrieval context
- `embedding`: vector from the embedding model (for vector similarity fallback)

See ADR-15 for the rationale behind heading-aware over fixed-size chunking.

### 10.6 Article Fetcher

The `ArticleFetcher` agent extracts external URLs from the cleaned document
text (Markdown links), classifies each link (article, API docs, video, social,
irrelevant), and fetches content for article-class links.  Fetched content is
stored in `DocumentArtifact.fetched_articles` and appended to the summariser
input — giving the LLM extra context from referenced sources.

**URL Source:** Markdown links (`[text](url)`) found in `cleaned_content` after
the `Preprocessor` step.  Inline code blocks and image URLs are excluded.

**Classification (LLM-based, SMALL tier):** Each URL is classified as
`article | api_docs | video | social | irrelevant`.  Only `article` and
`api_docs` classes are fetched.

**Fetching:**
- Respects egress policy (see Section 13.3) — private IPs, localhost, and
  non-allowlisted schemes are blocked via `EgressPolicy.validate_url()`.
- HTTP timeout: 10 s per request.  Max response body: 1 MB.
- User-Agent header identifies the bot (`MindForge/2.0`).
- Results cached by URL hash — repeated pipeline runs do not re-fetch.

**Output:**
```python
@dataclass
class FetchedArticle:
    url: str
    title: str | None
    content: str           # extracted article text (HTML→text via readability)
    fetch_status: Literal["ok", "blocked", "timeout", "error"]
```

Articles with `fetch_status != "ok"` are excluded from summariser input but
kept in the artifact for traceability.

### 10.7 Size and Cost Guards

Before any LLM call:
- **Byte size limit**: configurable per format (e.g., 10 MB for PDF)
- **Estimated token limit**: character count × factor; reject documents that
  would exceed the context window budget
- **Page limit**: for PDF, configurable maximum pages

### 10.8 End-to-End Ingestion Sequence

The diagram below traces a single document from upload to fully indexed state.
Columns are system components; the flow shows the exact order of operations,
transaction boundaries, and async handoffs.

```
┌────────┐  ┌───────────┐  ┌──────────┐  ┌─────────────┐  ┌────────────┐  ┌────────┐
│ Client │  │  API/Bot  │  │ Ingestion│  │  Pipeline  │  │ PostgreSQL │  │ Neo4j  │
│        │  │  Router   │  │ Service  │  │  Worker    │  │            │  │        │
└────┬───┘  └─────┬─────┘  └────┬─────┘  └──────┬──────┘  └─────┬──────┘  └───┬────┘
     │          │            │              │              │           │
     │─POST /upload─▶│            │              │              │           │
     │          │──ingest()─▶│              │              │           │
     │          │            │              │              │           │
     │          │     ┌──────┴───TX BEGIN─────────▶│           │
     │          │     │ 1. sanitize filename       │              │           │
     │          │     │ 2. validate size/format     │              │           │
     │          │     │ 3. compute content_sha256   │              │           │
     │          │     │ 4. dedup check────────────▶│  SELECT ... │           │
     │          │     │ 5. pending task limit─────▶│  COUNT(*)   │           │
     │          │     │ 6. parse → text+metadata    │              │           │
     │          │     │ 7. resolve lesson_id       │              │           │
     │          │     │ 8. deactivate prev rev────▶│  UPDATE     │           │
     │          │     │ 9. INSERT document───────▶│  INSERT     │           │
     │          │     │10. INSERT pipeline_task───▶│  INSERT     │           │
     │          │     │11. INSERT outbox_event───▶│  INSERT     │           │
     │          │     │12. pg_notify('outbox')───▶│  NOTIFY     │           │
     │          │     └──────TX COMMIT─────────▶│              │           │
     │          │            │              │              │           │
     │◀─202 {task_id}│            │              │              │           │
     │          │            │              │              │           │
     │   ┌──SSE: subscribe(task_id)───▶│              │           │
     │   │      │            │              │              │           │
     │   │      │            │  ┌──poll pending─▶│  SELECT     │           │
     │   │      │            │  │ claim task──▶│  FOR UPDATE │           │
     │   │      │            │  │ status=running▶│  SKIP LOCKED│           │
     │   │      │            │  │            │              │           │
     │   │      │            │  │ ┌──AGENT GRAPH────────────────┐│           │
     │   │      │            │  │ │ DocumentParser (deterministic)  ││           │
     │   │      │            │  │ │ RelevanceGuard (LLM─SMALL)     ││           │
     │   │      │            │  │ │ ImageAnalyzer  (LLM─VISION)    ││           │
     │   │      │            │  │ │ Preprocessor   (LLM─SMALL)     ││           │
     │   │      │            │  │ │ ArticleFetcher (LLM+HTTP)      ││           │
     │   │      │            │  │ │ Chunker        (deterministic)  ││           │
     │   │      │            │  │ │ Summarizer     (LLM─LARGE)     ││           │
     │   │      │            │  │ │ FlashcardGen   (LLM─LARGE)     ││           │
     │   │      │            │  │ │ ConceptMapper  (LLM─LARGE)     ││           │
     │   │      │            │  │ │ Validation     (deterministic)  ││           │
     │   │      │            │  │ └─────────────────────────────────┘│           │
     │   │      │            │  │            │              │           │
     │   │      │            │  │ ┌─CHECKPOINT per step─▶│ UPDATE    │           │
     │   │      │            │  │ │ artifact_json               │           │
     │   │      │            │  │ │ fingerprints_json            │           │
     │   │      │            │  │ │ completed_step               │           │
     │   │      │            │  │ └──────────────────▶│ outbox_event│           │
     │   │      │            │  │            │              │           │
     │   │◀─event: StepCompleted◀────SSE via Redis◀──relay◀──────│           │
     │   │      │            │  │            │              │           │
     │   │      │            │  │ ┌─GRAPH INDEX─────────────────────▶│
     │   │      │            │  │ │ DETACH DELETE old lesson   │  MERGE   │
     │   │      │            │  │ │ MERGE concepts + chunks    │  UNWIND  │
     │   │      │            │  │ │ CREATE RELATES_TO edges    │  CREATE  │
     │   │      │            │  │ │ SET embeddings on chunks   │  SET     │
     │   │      │            │  │ └─────────────────────────────◀────────┘
     │   │      │            │  │            │              │           │
     │   │      │            │  │ ┌─READ MODEL──▶│ UPSERT     │           │
     │   │      │            │  │ │ lesson_projections         │           │
     │   │      │            │  │ └────────────▶│              │           │
     │   │      │            │  │            │              │           │
     │   │      │            │  │ status=done▶│ UPDATE task │           │
     │   │      │            │  │ outbox:Done▶│ INSERT event│           │
     │   │      │            │  └─────COMMIT─▶│              │           │
     │   │      │            │              │              │           │
     │   │◀─event: ProcessingCompleted◀─relay◀─────────────┘           │
     │   └──▶│            │              │              │           │
     │          │            │              │              │           │
```

**Key observations:**
- Everything from step 1–12 in the upload is a **single PostgreSQL transaction**.
  If any step fails, nothing is persisted.
- The pipeline worker is a **separate OS process** that polls `pipeline_tasks`.
  There is an async handoff between the API response (202) and agent execution.
- Each agent step checkpoints to `document_artifacts` independently.  A crash
  mid-pipeline resumes from the last completed step, not from scratch.
- Graph indexing into Neo4j happens **after** all agents complete.  Neo4j is
  eventually consistent with PostgreSQL — the outbox ensures it catches up.
- The client receives progress via SSE events relayed through Redis Pub/Sub.
  If Redis is down, the SSE handler falls back to polling `outbox_events`.

---

## 11. API Layer

### 11.1 Design Principles

1. **Thin routers**: HTTP handlers do only validation, auth, and delegation to
   application services.  No business logic in route handlers.
2. **Dependency injection**: All services, repositories, and configuration
   injected via FastAPI's `Depends()` system — never imported as module globals.
3. **Async-only handlers**: All route handlers are `async def`.  No sync
   blocking inside the event loop.
4. **Server-authoritative state**: The server owns all grading, scoring, and
   access decisions.  Client payloads never contain reference answers, grounding
   context, or security-critical state.

### 11.2 Composition Root (`api/main.py`)

The API process is concerned with HTTP request handling **only**.  It does not
execute pipeline tasks.  Pipeline work is owned exclusively by the dedicated
worker process (see Section 11.5).

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────
    settings = load_settings()
    credentials = load_credentials()
    auth_settings = load_auth_settings()
    egress_settings = load_egress_settings()

    # Validate all config on startup — fail fast
    validate_settings(settings, credentials, auth_settings)

    # Database
    db_engine = create_async_engine(settings.database_url)
    async with db_engine.begin() as conn:
        # Advisory lock prevents concurrent migration runs (e.g. multiple workers)
        await conn.execute(text("SELECT pg_advisory_lock(42)"))
        await run_migrations(conn)
        await conn.execute(text("SELECT pg_advisory_unlock(42)"))

    # Neo4j
    neo4j_ctx = Neo4jContext(settings.neo4j_uri, credentials.neo4j_password,
                             settings.neo4j_database) if settings.enable_graph else None

    # AI Gateway (for quiz evaluation, search — NOT for pipeline)
    gateway = LiteLLMGateway(
        default_model=settings.model_large,
        model_map=settings.model_map,
        fallback_models=settings.fallback_models,
        tracer=langfuse_adapter,
    )

    # Redis (recommended for production; PostgreSQL fallbacks if absent)
    redis = await connect_redis(settings.redis_url) if settings.redis_url else None
    if not redis:
        log.warning("Redis not configured — using PostgreSQL fallbacks (see Section 7.3)")

    # Outbox-backed event publisher (always uses PostgreSQL outbox_events)
    event_publisher = OutboxEventPublisher(db_engine)

    # Outbox relay: polls outbox table → Redis Pub/Sub (when Redis available).
    # When Redis is absent, ephemeral consumers degrade to outbox polling.
    outbox_relay = OutboxRelay(db_engine, redis) if redis else None
    if outbox_relay:
        await outbox_relay.start()

    # Repositories
    doc_repo = PostgresDocumentRepository(db_engine)
    artifact_repo = PostgresArtifactRepository(db_engine)
    interaction_store = PostgresInteractionStore(db_engine)
    study_progress = PostgresStudyProgressStore(db_engine)
    retrieval = Neo4jRetrievalAdapter(neo4j_ctx) if neo4j_ctx else None

    # Quiz session store (Redis preferred, PostgreSQL fallback)
    quiz_sessions = RedisQuizSessionStore(redis) if redis else PostgresQuizSessionStore(db_engine)

    # Ingestion service (submits tasks to DB — worker picks them up)
    ingestion = IngestionService(doc_repo, event_publisher, ...)

    # Wire everything onto app.state
    app.state.settings = settings
    app.state.gateway = gateway
    app.state.doc_repo = doc_repo
    app.state.artifact_repo = artifact_repo
    app.state.retrieval = retrieval
    app.state.quiz_sessions = quiz_sessions
    app.state.event_publisher = event_publisher
    app.state.interaction_store = interaction_store
    app.state.study_progress = study_progress
    app.state.ingestion = ingestion

    yield

    # ── Shutdown ─────────────────────────────────────
    if outbox_relay:
        await outbox_relay.stop()
    if neo4j_ctx:
        await neo4j_ctx.close()
    if redis:
        await redis.close()
    await db_engine.dispose()
```

### 11.3 Router Map

| Router | Prefix | Key Endpoints |
|---|---|---|
| `health` | `/api` | `GET /health` |
| `auth` | `/api/auth` | `GET /login/{provider}`, `GET /callback/{provider}`, `GET /link/{provider}`, `POST /register`, `POST /login`, `GET /me`, `POST /logout` |
| `knowledge_bases` | `/api/knowledge-bases` | CRUD on knowledge bases |
| `documents` | `/api/knowledge-bases/{kb_id}/documents` | Upload, list, get, reprocess |
| `concepts` | `/api/knowledge-bases/{kb_id}/concepts` | Concept graph for Cytoscape |
| `quiz` | `/api/knowledge-bases/{kb_id}/quiz` | Start session, submit answer, get results |
| `flashcards` | `/api/knowledge-bases/{kb_id}/flashcards` | Due cards, review, all cards |
| `search` | `/api/knowledge-bases/{kb_id}/search` | Knowledge search |
| `chat` | `/api/knowledge-bases/{kb_id}/chat` | Conversational RAG: start session, send message, list sessions |
| `events` | `/api/knowledge-bases/{kb_id}/events` | SSE stream for real-time updates |
| `tasks` | `/api/tasks` | Pipeline task status |
| `interactions` | `/api/interactions` | User's own interaction history (redacted) |
| `admin` | `/api/admin` | System metrics, service health |

### 11.4 Authentication Architecture

Multi-provider authentication with pluggable identity providers.  Supports both
OAuth 2.0 flows and built-in email/password registration.

#### OAuth Flow

```
User → GET /api/auth/login/discord → Redirect to Discord OAuth
                                   → Callback → Validate state
                                   → Look up external_identities by (provider, external_id)
                                   → If found: load existing user
                                   → If not found:
                                       • If JWT present: link new identity to current user
                                       • Else: create new user + external_identity
                                   → Issue JWT in HttpOnly cookie
                                   → Redirect to SPA
```

#### Email/Password Flow

```
User → POST /api/auth/register   → Validate input, hash password (bcrypt)
                                 → Create user in DB (no external_identity row)
                                 → Issue JWT in HttpOnly cookie
                                 → Return user info

User → POST /api/auth/login      → Validate credentials against hash
                                 → Issue JWT in HttpOnly cookie
                                 → Return user info
```

#### Account Linking

Once additional providers are enabled (Google, GitHub — post-launch), a
logged-in user can link them to their account:

```
User (authenticated) → GET /api/auth/link/google → OAuth flow
                                                 → Callback validates state
                                                 → INSERT external_identity for user
                                                 → Return to SPA settings page
```

Linking enforces that the `(provider, external_id)` pair is not already
associated with a different user.  If it is, the request is rejected with
a clear error.

#### Provider Protocol

```python
class AuthProvider(Protocol):
    """Pluggable identity provider."""
    @property
    def name(self) -> str: ...
    def get_authorization_url(self, state: str) -> str: ...
    async def exchange_code(self, code: str) -> UserInfo: ...

class DiscordAuthProvider(AuthProvider): ...

# Future providers (not day-1 scope):
# class GoogleAuthProvider(AuthProvider): ...
# class GitHubAuthProvider(AuthProvider): ...

class BasicAuthProvider:
    """Email/password provider — not OAuth-based, separate interface."""
    async def register(self, email: str, password: str, display_name: str) -> UserInfo: ...
    async def authenticate(self, email: str, password: str) -> UserInfo: ...
```

**Security invariants:**
- OAuth `state` is validated on every callback (CSRF protection).
- Passwords hashed with bcrypt (cost factor ≥ 12); plaintext never stored or logged.
- JWT stored in `HttpOnly`, `Secure`, `SameSite=Lax` cookie.
- `Secure` flag is configurable for local development (`AUTH_SECURE_COOKIES=false`).
- All auth settings loaded and validated at startup — never read from `os.environ`
  at request time.
- Registration rate-limited to prevent abuse.

**JWT Token Lifecycle:**
- Access token TTL: `JWT_ACCESS_TOKEN_TTL_MINUTES=60` (configurable)
- Refresh token: separate `HttpOnly` cookie, TTL 30 days
- Auto-refresh: if access token expires within 5 minutes, API issues a new
  access token in the response `Set-Cookie` header (transparent to SPA)
- Refresh token expiry → SPA receives `401` → redirect to `/login`
- Refresh token rotation: each use issues a new refresh token and invalidates
  the old one (prevents replay after theft)

### 11.5 Pipeline Task Ownership

Pipeline execution is **not** performed by the API process.  The API is the
task **submitter**; the dedicated pipeline worker (`mindforge-pipeline`) is the
sole task **executor**.

```
┌──────────────────────────────────────────────────────────────────┐
│  API Process                                                      │
│  1. Accept upload                                                 │
│  2. Store document in PostgreSQL                                  │
│  3. Insert row into pipeline_tasks (status=pending)               │
│  4. Insert outbox event (DocumentIngested)                        │
│  5. COMMIT transaction                                            │
│  6. Return 202 Accepted with task_id                              │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Pipeline Worker Process (separate OS process / container)         │
│  1. On startup: claim any stale running tasks (crash recovery)    │
│  2. Poll pipeline_tasks WHERE status='pending' with FOR UPDATE    │
│     SKIP LOCKED                                                   │
│  3. Set status=running, worker_id=self                            │
│  4. Execute agent graph with checkpointing                        │
│  5. On completion: set status=done, insert outbox events          │
│  6. On failure: set status=failed, record error                   │
│  7. Repeat                                                        │
└──────────────────────────────────────────────────────────────────┘
```

**Key invariants:**
- The `pipeline_tasks` table is the coordination primitive.  `FOR UPDATE SKIP
  LOCKED` prevents double-claiming.
- `worker_id` and `claimed_at` columns identify which worker owns a task and
  enable stale-task recovery on startup.
- The API never imports the orchestrator or agent code — only the ingestion
  service and the repository layer.
- Multiple pipeline workers can run concurrently (horizontal scaling) as long
  as they share the same PostgreSQL instance.

```python
class PipelineWorker:
    """Dedicated task executor — runs as a separate process."""

    def __init__(
        self,
        worker_id: str,
        db_engine: AsyncEngine,
        orchestrator: PipelineOrchestrator,
        event_publisher: OutboxEventPublisher,
        max_concurrent: int = 2,
    ) -> None: ...

    async def run_forever(self) -> None:
        """Poll for pending tasks and execute them."""
        # 1. Recover stale tasks (worker_id=self, status=running, claimed_at old)
        # 2. Poll loop with configurable interval
        ...

    async def claim_task(self) -> PipelineTask | None:
        """Atomically claim a pending task using SELECT ... FOR UPDATE SKIP LOCKED."""
        ...

    async def execute_task(self, task: PipelineTask) -> None:
        """Run the orchestrator, update task status on completion or failure."""
        ...

    async def shutdown(self, timeout_seconds: int = 300) -> None:
        """Drain running tasks gracefully on SIGTERM."""
        ...
```

Tasks that survive process restarts are recovered from their last checkpoint
(the artifact's `completed_step` field).  The worker detects stale tasks by
comparing `claimed_at` against `PIPELINE_TASK_STALE_THRESHOLD_MINUTES` (default
30 min).  Tasks exceeding the threshold are reclaimed by any available worker.
If a task is reclaimed more than 3 times, it is marked `status=failed` with
`error="exceeded max reclaim attempts"`.

### 11.6 SPA Serving

FastAPI serves the built Angular SPA from `frontend/dist/frontend/browser`.
All non-API routes fall through to `index.html` for client-side routing.

### 11.7 Conversational RAG (Chat with Knowledge Base)

MindForge is a **Graph RAG application** — beyond quizzes and flashcards, users
can converse with their knowledge base.  The chat endpoint uses the concept
graph to build precise context for each turn.

#### Chat Flow

```
User → POST /api/knowledge-bases/{kb_id}/chat
       { "session_id": "...", "message": "Wyjaśnij różnicę między LSTM a GRU" }

Server:
  1. Load chat session history (last N turns)
  2. Extract concept mentions from user message (keyword/NER)
  3. For each concept: retrieve_concept_neighborhood(concept_key, kb_id)
  4. If no concepts matched: fall back to retrieve(query, kb_id)
  5. Assemble prompt:
     - System: "You are a study assistant. Answer using ONLY the provided context."
     - Context: concept neighborhoods + supporting facts + related concepts
     - History: last N turns (summarized if beyond token budget)
     - User message
  6. LLM completion → answer
  7. Store turn in interaction_turns (server-side)
  8. Return answer (no context/prompt leaked to client)

← { "answer": "...", "source_concepts": ["lstm", "gru", "recurrent-networks"] }
```

#### Chat Session Model

```python
@dataclass
class ChatSession:
    session_id: UUID
    user_id: UUID
    kb_id: UUID
    turns: list[ChatTurn]        # append-only history
    created_at: datetime

@dataclass
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str
    source_concepts: list[str]   # concept keys used to build context (assistant only)
    timestamp: datetime
```

**Storage:** Chat conversation history is **session-scoped and ephemeral** —
stored in Redis (`chat:{session_id}` key, TTL = `QUIZ_SESSION_TTL_SECONDS`)
or in-memory if Redis is absent.  It is **not** persisted to PostgreSQL.
The `ChatSession` dataclass above is the in-process representation; it is
serialized to Redis JSON and deserialized on each turn.

Individual chat interactions *are* recorded in the `interactions` /
`interaction_turns` tables (`interaction_type = 'chat_session'`) for audit and
Langfuse cost attribution — but only metadata and the assistant message, not
the full conversation context.  The security contract is identical to quiz: no
grounding context, no raw prompts, no concept neighborhoods are returned to
the client — only the answer text and the list of concept keys that informed it.

#### Why Graph RAG, Not Vector RAG

| Aspect | Vector RAG | Graph RAG (MindForge) |
|---|---|---|
| Context | Top-N similar chunks (may overlap) | Concept definition + facts + neighbors |
| Precision | Depends on embedding quality | Structured, deterministic |
| Cost | Large context windows | Smaller, targeted context |
| Multi-hop | Single-step retrieval | Graph traversal captures relationships |
| Transparency | "Here are 3 chunks" | "I used concept X and its relation to Y" |

#### Frontend Route

```
/kb/:kbId/chat          → Conversational RAG interface
```

Added to `ChatService` in Angular:

```typescript
// frontend/src/app/core/services/chat.service.ts
sendMessage(kbId: string, sessionId: string, message: string): Observable<ChatResponse>;
listSessions(kbId: string): Observable<ChatSession[]>;
```

---

## 12. Frontend Architecture

### 12.1 Technology

| Aspect | Choice |
|---|---|
| Framework | Angular 19+ (standalone components, signals) |
| Routing | Lazy-loaded routes per page |
| HTTP | `HttpClient` with auth interceptor |
| State | Component-local + service-based reactive state |
| Graph visualization | Cytoscape.js |
| Real-time updates | EventSource (SSE) |

### 12.2 Route Structure

```
/                      → Dashboard (lesson list, stats, recent activity)
/login                 → Auth provider selection + email/password registration
/knowledge-bases       → KB list and management
/kb/:kbId/documents    → Document list and upload
/kb/:kbId/concepts     → Concept map visualization
/kb/:kbId/quiz         → Interactive quiz
/kb/:kbId/flashcards   → Flashcard review (spaced repetition)
/kb/:kbId/search       → Knowledge search
/kb/:kbId/chat         → Conversational RAG interface
```

### 12.3 Core Services

| Service | Responsibility |
|---|---|
| `AuthService` | Login, logout, token refresh, user state |
| `KnowledgeBaseService` | KB CRUD |
| `DocumentService` | Upload, list, status polling |
| `ConceptService` | Fetch concept graph for Cytoscape |
| `QuizService` | Session management, answer submission |
| `FlashcardService` | Due cards, review submissions |
| `SearchService` | Knowledge queries |
| `ChatService` | Conversational RAG session management, message sending |
| `EventService` | SSE subscription, real-time notifications |
| `TaskService` | Pipeline task status polling |

### 12.4 Security Contract

The SPA **never** receives:
- Quiz grounding context or reference answers
- Raw LLM prompts or completions
- Internal document IDs that bypass knowledge-base scoping
- Admin-only service metrics (without admin role)

All sensitive operations are server-authoritative.  The SPA sends intents
(e.g., "submit this answer"); the server decides the outcome.

---

## 13. Discord Bot

### 13.1 Structure

```
mindforge/discord/
├── bot.py              # Composition root, lifecycle, cog loading
├── auth.py             # Allowlist enforcement, interaction ownership
└── cogs/
    ├── quiz.py         # /quiz start, /quiz answer
    ├── search.py       # /search query
    ├── upload.py       # Upload attachment as document
    └── notifications.py # Per-user SR reminders (DM)
```

### 13.2 Shared Logic

Cogs are thin.  They delegate to the same application services used by the API.
**Bot adapters always resolve the platform-specific user ID to an internal UUID
via `IdentityResolver` before calling any application service.**

```python
class IdentityResolver:
    """Resolves external platform IDs to internal user UUIDs."""

    def __init__(self, identity_repo: ExternalIdentityRepository) -> None: ...

    async def resolve(self, provider: str, external_id: str) -> UUID:
        """Look up external_identities → return internal user_id.
        Creates a user + identity row on first contact (auto-provisioning)."""
        ...

class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.quiz_service = bot.quiz_service       # same instance as API uses
        self.kb_service = bot.kb_service
        self.identity = bot.identity_resolver       # IdentityResolver
        self.gateway = bot.gateway
        self.retrieval = bot.retrieval

    @app_commands.command()
    async def quiz(self, interaction: Interaction, topic: str, kb: str | None = None):
        # Step 1: resolve external identity → internal UUID
        user_id = await self.identity.resolve("discord", str(interaction.user.id))

        # Step 2: resolve KB
        kb_id = await self._resolve_kb(
            user_id=user_id,
            kb_name=kb,
            interaction=interaction,
        )

        # Step 3: delegate to application service (all args are internal UUIDs)
        session = await self.quiz_service.start_session(
            user_id=user_id,
            kb_id=kb_id,
            topic=topic,
        )
        ...

    async def _resolve_kb(
        self, user_id: UUID, kb_name: str | None, interaction: Interaction
    ) -> UUID:
        """Resolve KB by name or show interactive picker if user has multiple KBs."""
        user_kbs = await self.kb_service.list_for_user(user_id)
        if kb_name:
            return next(kb.kb_id for kb in user_kbs if kb.name == kb_name)
        if len(user_kbs) == 1:
            return user_kbs[0].kb_id
        # Show select menu for multiple KBs
        ...
```

### 13.3 Auth and Interaction Ownership

- **Allowlists**: guild IDs, role IDs, and user IDs loaded lazily after
  `load_dotenv()` — never at import time.
- **Interaction ownership**: every view, modal, and button callback validates
  that the invoking user matches the session owner.
- **No global state leaks**: SR reminders are per-user DMs, not channel-wide
  announcements.

---

## 13a. Slack Bot

### 13a.1 Technology

The Slack integration uses the **Slack Bolt for Python** framework (async mode).
Like the Discord bot, it is a thin presentation layer that delegates to the same
application services.

### 13a.2 Structure

```
mindforge/slack/
├── app.py              # Bolt app setup, composition root, socket-mode listener
├── auth.py             # Workspace/channel allowlists
└── handlers/
    ├── quiz.py         # /quiz slash command, interactive messages
    ├── search.py       # /search slash command
    ├── upload.py       # File upload event handler
    └── notifications.py # SR reminders via DM
```

### 13a.3 Shared Logic

Handlers delegate to application services — identical to the Discord and API
surfaces.  Platform-specific user IDs are resolved to internal UUIDs **before**
any service call (same `IdentityResolver` as Discord):

```python
# mindforge/slack/handlers/quiz.py
async def handle_quiz_command(ack, say, command, context):
    await ack()
    identity: IdentityResolver = context["identity_resolver"]

    # Resolve Slack user → internal UUID
    user_id = await identity.resolve("slack", command["user_id"])

    # Resolve KB: parse from command text or show interactive picker
    kb_id = await resolve_kb_for_user(
        user_id=user_id,
        kb_service=context["kb_service"],
        kb_name=parse_kb_flag(command["text"]),
        say=say,
    )
    topic = parse_topic(command["text"])
    session = await context["quiz_service"].start_session(
        user_id=user_id,
        kb_id=kb_id,
        topic=topic,
    )
    await say(blocks=format_quiz_question(session.current_question))
```

### 13a.4 Auth and Security

- **Workspace allowlists**: Only configured Slack workspaces can interact.
- **Signing secret validation**: All incoming requests verified via Slack's
  signing secret (handled by Bolt automatically).
- **User mapping**: Slack user IDs are resolved to internal UUIDs via
  `external_identities(provider='slack', external_id=...)`.  The
  `IdentityResolver` auto-provisions a user + identity row on first contact.

### 13a.5 Connection Mode

The bot uses **Socket Mode** by default (no public endpoint required).  HTTP
mode with request verification is supported for production deployments behind a
load balancer.

---

## 14. Quiz CLI

A thin command-line interface that uses the same `QuizService` as the API and
Discord bot.

```python
# mindforge/cli/quiz_runner.py
async def main():
    settings = load_settings()
    credentials = load_credentials()
    # Wire dependencies (same as API composition root, minus HTTP)
    gateway = LiteLLMGateway(...)
    retrieval = Neo4jRetrievalAdapter(...)
    quiz_service = QuizService(gateway=gateway, retrieval=retrieval, ...)

    # Interactive loop
    topic = input("Topic: ")
    cli_user_id = await ensure_cli_user(db_engine)
    session = await quiz_service.start_session(user_id=cli_user_id, kb_id=..., topic=topic)
    ...
```

---

## 15. Event System

### 15.1 Transactional Outbox Pattern

Events are propagated through a **transactional outbox** — state changes and
their events are committed in the same database transaction, guaranteeing
at-least-once delivery without distributed transactions.

```
┌───────────────────────────────────────────────────────────────┐
│  Write Path (API / Pipeline Worker)                            │
│                                                                │
│  BEGIN TRANSACTION                                             │
│    INSERT/UPDATE domain tables (documents, artifacts, ...)     │
│    INSERT INTO outbox_events (event_type, payload)             │
│  COMMIT                                                        │
│  pg_notify('outbox')                                           │
└───────────────────────────────────────────────────────────────┘
         │
         │ (polled by)
         ▼
┌───────────────────────────────────────────────────────────────┐
│  Outbox Relay                                                  │
│                                                                │
│  1. SELECT * FROM outbox_events WHERE NOT published            │
│     ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED       │
│  2. For each row:                                              │
│     a. Build envelope: {event_id, event_type, payload, ts}     │
│     b. Publish envelope to Redis Pub/Sub                       │
│  3. UPDATE outbox_events SET published=TRUE, published_at=now()│
│  4. Sleep or pg_notify wake                                    │
└───────────────────────────────────────────────────────────────┘
         │
         │ Redis Pub/Sub (envelope with event_id)
         ▼
┌───────────────────────────────────────────────────────────────┐
│  Subscribers                                                   │
│                                                                │
│  ┌── Ephemeral (tolerate redelivery, no persistence needed) ──┐│
│  │  • SSE Handler → push to connected browsers                ││
│  │  • Task Status Updater → update pipeline_tasks table       ││
│  │  • Notification Handler → Discord/Slack DM                 ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                │
│  ┌── Durable (must not miss events) ─────────────────────────┐│
│  │  • Graph Indexer → poll outbox_events directly, maintain   ││
│  │    own cursor (sequence_num)                               ││
│  │  • Audit Logger → poll outbox_events directly, maintain    ││
│  │    own cursor                                              ││
│  └────────────────────────────────────────────────────────────┘│
└───────────────────────────────────────────────────────────────┘
```

**Key invariants:**
- An event is **never published without a committed state change** (no phantom
  events).
- An event may be delivered more than once after relay crash recovery — all
  subscribers must be **idempotent** (keyed by `event_id`).
- The relay publishes an **envelope** containing `event_id`, not just the
  payload.  Redis subscribers extract `event_id` for deduplication.
- **Durable consumers** (Graph Indexer, Audit Logger) do **not** depend on
  Redis Pub/Sub.  They poll `outbox_events` directly using a stored cursor,
  ensuring no events are missed during their downtime.
- Ephemeral consumers (SSE, notifications) subscribe to Redis Pub/Sub for
  low-latency delivery.  Missed events during downtime are acceptable because
  they are either presentation-only or backed by a separate query.
- **SSE fallback**: when Redis is unavailable or when the relay marks an event
  as published but Redis did not receive it (crash between `PUBLISH` and
  `UPDATE`), the SSE handler degrades to polling `outbox_events` directly with
  a 2-second interval.  This ensures the user always sees processing completion
  — at worst with a 2-second delay instead of real-time.
- The relay polls with `FOR UPDATE SKIP LOCKED`, so multiple API instances can
  run a relay without double-publishing.
- For fast propagation, the writer issues `pg_notify('outbox')` after commit
  so the relay wakes immediately instead of waiting for the next poll cycle.

#### Durable Consumer Pattern

```python
class DurableEventConsumer(ABC):
    """Base class for consumers with at-least-once delivery and idempotent handlers."""

    def __init__(self, db_engine: AsyncEngine, consumer_name: str) -> None:
        self.db_engine = db_engine
        self.consumer_name = consumer_name

    async def run_forever(self, poll_interval: float = 2.0) -> None:
        while True:
            async with self.db_engine.begin() as conn:
                cursor_seq = await self._get_cursor(conn)
                rows = await conn.execute(text(
                    "SELECT * FROM outbox_events "
                    "WHERE sequence_num > :cursor_seq "
                    "ORDER BY sequence_num LIMIT 100"
                ), {"cursor_seq": cursor_seq})
                for row in rows:
                    await self.handle(row.event_type, row.payload, row.event_id)
                    await self._advance_cursor(conn, row.sequence_num)
            await asyncio.sleep(poll_interval)

    @abstractmethod
    async def handle(self, event_type: str, payload: dict, event_id: UUID) -> None: ...

class GraphIndexerConsumer(DurableEventConsumer):
    """Rebuilds Neo4j projection on ProcessingCompleted events."""
    ...

class AuditLoggerConsumer(DurableEventConsumer):
    """Records interaction turns for every relevant event."""
    ...
```

Cursor state is stored in a small `consumer_cursors` table:

```sql
CREATE TABLE consumer_cursors (
    consumer_name   TEXT PRIMARY KEY,
    last_sequence   BIGINT NOT NULL,            -- last processed sequence_num
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### Transactional Contract

The `OutboxEventPublisher` accepts a **connection** (the caller's in-flight
transaction) — it does not create its own transaction.  This ensures the event
and the state change commit or roll back together:

```python
class OutboxEventPublisher:
    """Writes domain events into the outbox_events table within the caller's transaction."""

    async def publish_in_tx(
        self,
        event: DomainEvent,
        connection: AsyncConnection,
    ) -> None:
        event_id = uuid4()
        await connection.execute(
            text("INSERT INTO outbox_events (event_id, event_type, payload) "
                 "VALUES (:id, :type, :payload)"),
            {"id": event_id, "type": type(event).__name__,
             "payload": json.dumps({"event_id": str(event_id), **event.to_dict()})},
        )
```

The `EventPublisher` port reflects the transactional requirement:

```python
class EventPublisher(Protocol):
    async def publish_in_tx(self, event: DomainEvent, connection: AsyncConnection) -> None: ...
```

Callers **must** pass their in-flight `connection`:

```python
# In IngestionService.ingest() — within a single transaction:
async with self.db_engine.begin() as conn:
    await self.doc_repo.save(document, conn)
    await conn.execute(text("INSERT INTO pipeline_tasks ..."))
    await self.event_publisher.publish_in_tx(
        DocumentIngested(document_id=document.document_id, ...),
        connection=conn,
    )
    # All three writes commit atomically or roll back together.
```

```python
class OutboxRelay:
    """Polls outbox_events, publishes envelopes to Redis Pub/Sub, marks as delivered."""

    def __init__(self, db_engine: AsyncEngine, redis: Redis) -> None: ...

    async def run_forever(self, poll_interval: float = 1.0) -> None:
        while True:
            async with self.db_engine.begin() as conn:
                rows = await conn.execute(text(
                    "SELECT * FROM outbox_events WHERE NOT published "
                    "ORDER BY created_at LIMIT 100 FOR UPDATE SKIP LOCKED"
                ))
                for row in rows:
                    # Publish envelope WITH event_id so consumers can deduplicate
                    envelope = json.dumps({
                        "event_id": str(row.event_id),
                        "event_type": row.event_type,
                        "payload": row.payload,
                        "created_at": row.created_at.isoformat(),
                    })
                    await self.redis.publish(f"events:{row.event_type}", envelope)
                    await conn.execute(text(
                        "UPDATE outbox_events SET published=TRUE, published_at=now() "
                        "WHERE event_id = :id"
                    ), {"id": row.event_id})
            await asyncio.sleep(poll_interval)
```

#### Outbox Retention

The `outbox_events` table grows with every domain event.  A background cron job
(or scheduled asyncio task in the pipeline worker) prunes delivered events:

```sql
DELETE FROM outbox_events
WHERE published = TRUE
  AND published_at < now() - interval '7 days';
```

Run daily.  Unpublished events are **never** deleted — the relay will keep
retrying them.  At typical 1–5 user load (~100 events/day), the table stays
under 1 000 rows between prunes.

### 15.2 Event Catalog

| Event | Producer | Consumers |
|---|---|---|
| `DocumentIngested` | Ingestion Service | Notification Handler, Audit Logger |
| `PipelineStepCompleted` | Pipeline Worker | SSE Handler, Task Status Updater |
| `ProcessingCompleted` | Pipeline Worker | Graph Indexer, SSE Handler, Notification Handler |
| `ProcessingFailed` | Pipeline Worker | SSE Handler, Task Status Updater, Notification Handler |
| `QuizSessionStarted` | Quiz Service | Audit Logger |
| `QuizAnswerEvaluated` | Quiz Service | SSE Handler, Audit Logger |
| `ReviewRecorded` | SR Engine | Audit Logger |

### 15.3 Client Event Stream

```
GET /api/knowledge-bases/{kb_id}/events
Accept: text/event-stream

event: pipeline_step_completed
data: {"document_id": "...", "step": "summarizer", "artifact_version": 2}

event: processing_completed
data: {"document_id": "...", "lesson_id": "..."}

event: task_status_changed
data: {"task_id": "...", "status": "done"}
```

The client subscribes via `EventSource` and updates the UI in real time.
Tasks survive browser tab closure — the client reconnects and catches up from
the task status endpoint.

---

## 16. Security and Trust Boundaries

### 16.1 Defense in Depth Model

```
┌─────────────────────────────────────────────────────────────┐
│                     Untrusted Zone                          │
│  Browser, Discord client, uploaded files, external URLs     │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Perimeter Guards                           │
│  Auth middleware, CORS, rate limiter, request size limiter   │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Input Validation                           │
│  Schema validation (Pydantic), upload sanitizer,             │
│  filename sanitizer, content type validation                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Application Logic                          │
│  Server-authoritative decisions, user-scoped data access,    │
│  knowledge base isolation                                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Egress Controls                            │
│  SSRF policy, URL validation, private network blocking,      │
│  redirect validation, protocol allowlist                     │
└─────────────────────────────────────────────────────────────┘
```

### 16.2 Security Invariants

| Category | Invariant |
|---|---|
| **Upload Safety** | Filenames sanitized; path traversal rejected; absolute paths rejected; drive-qualified paths rejected; final write only inside designated storage |
| **SSRF Protection** | All outbound fetches go through `EgressPolicy`; private, loopback, link-local and metadata-service addresses blocked; redirects revalidated; protocol/port allowlists enforced |
| **Quiz Integrity** | Browser never receives `grounding_context` or `reference_answer`; answers bound to server-side session and `question_id` |
| **Data Isolation** | All queries scoped by `kb_id` and `user_id`; no cross-knowledge-base data leakage |
| **Auth** | OAuth `state` validated; passwords hashed with bcrypt (cost ≥ 12); JWT in `HttpOnly`/`Secure` cookie; registration rate-limited; settings validated at startup |
| **Discord** | Guild/role/user allowlists enforced; interaction ownership verified on every callback |
| **Slack** | Workspace allowlists enforced; signing secret validated on every request; Socket Mode token secured |
| **LLM Prompt Safety** | User input never interpolated into prompts without context framing; output filtered before client delivery |

### 16.3 Egress Policy

The `EgressPolicy` is an **instance-based object** configured from
`EgressSettings` at startup — not module-level globals:

```python
@dataclass(frozen=True)
class EgressSettings:
    allow_private_networks: bool = False
    allow_nonstandard_ports: bool = False
    allowed_protocols: frozenset[str] = frozenset({"http", "https"})
    max_response_bytes: int = 10_000_000
    timeout_seconds: float = 30.0

class EgressPolicy:
    def __init__(self, settings: EgressSettings) -> None: ...

    def validate_url(self, url: str) -> ValidatedURL:
        """Raises EgressViolation if URL violates policy."""
        ...

    async def fetch(self, url: str) -> FetchResult:
        """Fetch URL with full policy enforcement including redirect checks."""
        ...
```

---

## 17. Cost Optimization

### 17.1 Cost-Aware Model Routing

```
┌──────────────────────────────────────────────────────────┐
│                  Complexity Router                         │
├────────────────┬────────────────┬─────────────────────────┤
│  Deterministic │  Small Model   │   Large Model           │
│  (regex, rules,│  (GPT-4o-mini, │  (GPT-4o, Claude 3.5   │
│   lookup)      │   Haiku)       │   Sonnet)               │
│  $0            │  ~$0.001/call  │  ~$0.03/call            │
├────────────────┼────────────────┼─────────────────────────┤
│  • Parsing     │  • Preprocessor│  • Summarizer           │
│  • Validation  │  • Link class. │  • Flashcard generator  │
│  • Rendering   │  • Relevance   │  • Concept mapper       │
│  • Dedup check │    guard       │  • Quiz evaluator       │
│  • Identity    │  • Article     │                         │
│    resolution  │    extraction  │                         │
└────────────────┴────────────────┴─────────────────────────┘
```

### 17.2 Caching Strategy

| Cache Layer | What | Where | TTL |
|---|---|---|---|
| **Semantic cache** | LLM responses for near-duplicate queries | Redis | 24h |
| **Article cache** | Fetched article content | PostgreSQL | 7 days |
| **Link classification** | URL → relevant/irrelevant | PostgreSQL | 7 days |
| **Embedding cache** | Text → vector | PostgreSQL / graph | Permanent until reindex |
| **Read model cache** | Lesson projections | PostgreSQL | Updated on artifact flush |
| **Graph query cache** | Concept lists, retrieval results | Redis | 5 min |

#### Semantic Cache Scoping

The semantic cache key **must** include `kb_id` to prevent cross-knowledge-base
data leakage.  Without scoping, User A could receive a cached LLM response
generated from User B's knowledge base context.

```python
def semantic_cache_key(model: str, kb_id: UUID, normalized_query: str) -> str:
    """Cache key includes model and knowledge base — never just the query."""
    return sha256(f"{model}:{kb_id}:{normalized_query}").hexdigest()
```

**Why `kb_id` but not `user_id`?**  Knowledge bases are user-scoped
(`kb.owner_id = user_id`).  The retrieval context used to build the LLM prompt
is determined by the KB, not the user directly.  If shared KBs are introduced
in the future, `kb_id` still provides correct isolation — all users querying
the same KB *should* get the same cached answer for the same query.

Cache invalidation: entries for a given `kb_id` are invalidated when
`ProcessingCompleted` fires for that KB (new or updated content may change
retrieval results).

### 17.3 Token Budget Management

```python
@dataclass
class TokenBudget:
    max_input_tokens: int
    max_output_tokens: int
    reserved_for_system: int

    @property
    def available_for_context(self) -> int:
        return self.max_input_tokens - self.reserved_for_system

def build_prompt_within_budget(
    system_prompt: str,
    user_query: str,
    context_chunks: list[str],
    budget: TokenBudget,
) -> list[dict]:
    """Assemble prompt, prioritizing chunks by relevance,
    truncating to fit the token budget."""
    ...
```

### 17.4 Cost Tracking

Every `CompletionResult` from the AI Gateway includes `cost_usd`.  This cost
is:
- Recorded in the interaction turn (`interaction_turns.cost`)
- Reported to Langfuse per trace
- Aggregated in the admin dashboard per user, per knowledge base, per day

### 17.5 Reuse Over Regeneration

- **Reference answers** generated during quiz question creation are stored in
  the session and reused for evaluation — never regenerated.
- **Prior concept context** for the summarizer comes from a bounded Neo4j query
  (max N concepts), not from the entire knowledge index.
- **Deterministic operations first**: parsing, validation, rendering, dedup
  checks never call the LLM.

---

## 18. Observability

### 18.1 Tracing Architecture

Every meaningful operation produces a trace with typed spans:

```
Trace: document-ingest-{document_id}
├─ Span: ingestion.validate       (5ms)
├─ Span: ingestion.deduplicate    (2ms)
├─ Span: ingestion.store          (15ms)
└─ Span: pipeline.run
   ├─ Span: agent.document_parser    (50ms)
   ├─ Span: agent.relevance_guard    (200ms)
   │  └─ Span: llm.complete          (180ms)  ← model=small, tokens_in=500, tokens_out=50, $0.0002
   ├─ Span: agent.image_analyzer     (1500ms)
   │  └─ Span: llm.complete          (1400ms) ← model=vision, tokens_in=1000, tokens_out=200
   ├─ Span: agent.preprocessor       (300ms)
   │  └─ Span: llm.complete          (280ms)  ← model=small
   ├─ Span: agent.article_fetcher    (2000ms)
   │  ├─ Span: egress.fetch          (500ms)
   │  ├─ Span: egress.fetch          (800ms)
   │  └─ Span: llm.complete          (600ms)  ← model=small, cache=HIT
   ├─ Span: agent.summarizer         (3000ms)
   │  └─ Span: llm.complete          (2800ms) ← model=large, tokens_in=4000, tokens_out=2000, $0.024
   ├─ Span: agent.flashcard_gen      (2500ms)
   │  └─ Span: llm.complete          (2300ms) ← model=large
   ├─ Span: agent.concept_mapper     (2000ms)
   │  └─ Span: llm.complete          (1800ms) ← model=large
   ├─ Span: validation.deterministic (10ms)
   ├─ Span: graph.index_lesson       (200ms)
   │  ├─ Span: neo4j.batch_concepts  (50ms)
   │  ├─ Span: neo4j.batch_facts     (30ms)
   │  └─ Span: neo4j.batch_chunks    (100ms)
   └─ Span: read_model.publish       (20ms)
```

### 18.2 Metrics

| Metric | Source | Purpose |
|---|---|---|
| Token usage per agent | AI Gateway | Cost attribution |
| Cost per document | Aggregated from all agents | Budget monitoring |
| Latency per pipeline step | Tracing | Performance baseline |
| Cache hit rate | Semantic cache, article cache | Cost efficiency |
| Error rate per agent | Agent results | Reliability |
| Queue depth | Task manager | Capacity planning |
| Active quiz sessions | Session store | Load monitoring |
| Concept count per KB | Neo4j | Knowledge growth |

### 18.3 Langfuse Integration

The `LangfuseAdapter` wraps the Langfuse Python SDK:

```python
class LangfuseAdapter:
    def __init__(self, settings: TracingSettings) -> None: ...

    @contextmanager
    def trace(self, name: str, metadata: dict) -> TracingContext: ...

    def report_generation(self, ctx: TracingContext, result: CompletionResult) -> None: ...

    def report_score(self, ctx: TracingContext, name: str, value: float) -> None: ...
```

Initialization happens **explicitly** at the composition root — never as a
side-effect of importing a module.

### 18.4 Quality Evaluation

| Eval | Type | Frequency |
|---|---|---|
| Concept coverage | Deterministic | Every pipeline run |
| Content grounding | Deterministic | Every pipeline run |
| Flashcard balance (types) | Deterministic | Every pipeline run |
| Map connectivity | Deterministic | Every pipeline run |
| Summary coherence | LLM-as-judge | Sampled / offline |
| Quiz question quality | LLM-as-judge | Sampled / offline |
| Retrieval relevance | Embedding distance | Per search query |

Deterministic evals run inline.  LLM-as-judge evals run offline or on a sample
to avoid cost explosion.

---

## 19. Deployment and Infrastructure

### 19.1 Docker Compose Topology

```yaml
# compose.yml
services:
  # ── Application ──────────────────────────────
  api:
    build: .
    command: mindforge-api
    ports: ["8080:8080"]
    depends_on:
      postgres: { condition: service_healthy }
      neo4j: { condition: service_healthy }
    profiles: [app, gui]

  pipeline:
    build: .
    command: mindforge-pipeline --watch
    depends_on:
      postgres: { condition: service_healthy }
    profiles: [app]
    # Pipeline worker is a SEPARATE process from the API.
    # It polls pipeline_tasks in PostgreSQL and executes the agent graph.
    # Multiple replicas can run concurrently (FOR UPDATE SKIP LOCKED).
    # The API never executes pipeline code — it only inserts task rows.

  quiz-agent:
    build: .
    command: mindforge-quiz
    depends_on:
      neo4j: { condition: service_healthy }
    profiles: [quiz]

  discord-bot:
    build: .
    command: mindforge-discord
    depends_on:
      postgres: { condition: service_healthy }
      neo4j: { condition: service_healthy }
    profiles: [discord]

  slack-bot:
    build: .
    command: mindforge-slack
    depends_on:
      postgres: { condition: service_healthy }
      neo4j: { condition: service_healthy }
    profiles: [slack]

  # ── Infrastructure ───────────────────────────
  postgres:
    image: postgres:16-alpine
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: ...
    profiles: [app, gui, quiz, discord]

  neo4j:
    image: neo4j:5-community
    volumes: [neo4jdata:/data]
    healthcheck: ...
    profiles: [app, gui, quiz, discord, graph]

  redis:
    image: redis:7-alpine
    healthcheck: ...
    profiles: [app, gui, discord]

  minio:
    image: minio/minio
    volumes: [miniodata:/data]
    profiles: [app, gui]

  # ── Observability ────────────────────────────
  langfuse-web: ...
  langfuse-worker: ...
  langfuse-postgres: ...
  langfuse-clickhouse: ...
  langfuse-redis: ...
  langfuse-minio: ...

volumes:
  pgdata:
  neo4jdata:
  miniodata:
```

### 19.2 Compose Profiles

| Profile | Services |
|---|---|
| `app` | api, pipeline, postgres, neo4j, redis, minio |
| `gui` | api, postgres, neo4j, redis, minio (no pipeline watcher) |
| `quiz` | quiz-agent, neo4j |
| `discord` | discord-bot, postgres, neo4j, redis |
| `slack` | slack-bot, postgres, neo4j, redis |
| `graph` | neo4j (standalone) |
| `observability` | langfuse-web, langfuse-worker, langfuse-postgres, langfuse-clickhouse, langfuse-redis, langfuse-minio |

### 19.3 Dockerfile (Multi-Stage)

```dockerfile
# Stage 1: Build Angular SPA
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.13-slim AS runtime
WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY mindforge/ ./mindforge/
COPY --from=frontend-build /app/frontend/dist/frontend/browser ./frontend/dist/frontend/browser
RUN pip install --no-cache-dir -e .

# Entry point selected by compose command
ENTRYPOINT ["python", "-m"]
```

### 19.4 Database Migrations

Alembic manages PostgreSQL schema migrations.  Every schema change is a
versioned migration.  `mindforge-api` runs pending migrations on startup
(inside the lifespan).

```
migrations/
├── alembic.ini
├── env.py
└── versions/
    ├── 001_initial_schema.py
    ├── 002_add_knowledge_bases.py
    └── ...
```

---

## 20. Testing Strategy

### 20.1 Test Pyramid

```
              ╱  E2E Scenarios  ╲            ← Real services, real LLM (sampled)
             ╱   Integration     ╲           ← Real DB, mocked LLM, real Neo4j
            ╱    Unit Tests       ╲          ← No I/O, no network, fast
           ╱     Contract Tests    ╲         ← API schema validation
          ╱      LLM Evals (offline)╲        ← Quality benchmarks on datasets
         ╱___________________________╲
```

### 20.2 Testing Layers

| Layer | What | How | Speed |
|---|---|---|---|
| **Domain unit tests** | Models, value objects, identity resolution, validation | Pure Python, no mocks needed | < 1ms |
| **Application unit tests** | Service logic, orchestration, event handling | Mock ports/adapters | < 10ms |
| **Agent unit tests** | Prompt assembly, response parsing, tool logic | Mock AI Gateway | < 10ms |
| **Integration tests** | Repository ↔ PostgreSQL, adapter ↔ Neo4j | Testcontainers or fixtures | < 1s |
| **API integration tests** | Full request cycle through FastAPI | `httpx.AsyncClient` + test DB | < 1s |
| **Contract tests** | API response schemas match frontend models | Schema validation | < 100ms |
| **LLM evals** | Summary quality, flashcard quality, quiz quality | Real LLM calls, dataset-based | Minutes (offline) |
| **E2E scenarios** | Upload → process → quiz → review | Full stack | Minutes (sampled) |
| **Security tests** | Upload traversal, SSRF, quiz state leaks, auth | Guided test cases | < 1s |

### 20.3 Key Test Categories

**Idempotency tests:**
- Submit same content twice → no duplicate processing
- Pipeline interrupted and resumed → checkpoint works, no duplicate LLM calls
- Re-index to Neo4j → no duplicate nodes (MERGE idempotency)

**Data isolation tests:**
- User A cannot see User B's knowledge bases, documents, or quiz sessions
- Cross-KB queries return empty results

**Security regression tests:**
- Upload with path traversal → rejected
- Quiz answer response → no `grounding_context` or `reference_answer`
- Discord interaction from non-owner → rejected
- OAuth callback without valid `state` → rejected
- Outbound fetch to private IP → blocked

**Cost regression tests:**
- Reference answer reused during evaluation (no extra LLM call)
- Summarizer context bounded (not entire knowledge index)
- Deterministic operations don't trigger LLM calls

### 20.4 Test Infrastructure

```python
# tests/conftest.py

@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        database_url="postgresql+asyncpg://...",
        enable_graph=False,
        model_map={"small": "test/mock", "large": "test/mock"},
        ...
    )

@pytest.fixture
def mock_gateway() -> AIGateway:
    """Returns a gateway stub that returns deterministic responses."""
    return StubAIGateway(responses={...})

@pytest.fixture
def stub_retrieval() -> RetrievalPort:
    """Returns a retrieval stub with fixture data."""
    return StubRetrievalAdapter(concepts=[...], chunks=[...])
```

---

## 21. Key Architectural Decisions

### ADR-01: PostgreSQL as Single Source of Truth

**Context:** The old system scattered state across `state/artifacts/*.json`,
`state/knowledge_index.json`, `state/processed.json`, `state/sr_state.json`,
and multiple output directories.  This caused race conditions, data divergence,
and made backups impossible.

**Decision:** PostgreSQL is the single canonical store.  Neo4j is a derived
query index.  Filesystem is used only for transient temp files during parsing.

**Consequences:** Requires database migrations, adds operational dependency on
PostgreSQL, but eliminates all filesystem concurrency issues and enables
transactional consistency.

### ADR-02: LiteLLM as AI Gateway

**Context:** The old system was hard-coupled to a single OpenAI-compatible
endpoint.  Switching providers required modifying the client class.

**Decision:** All LLM calls go through a `LiteLLMGateway` adapter implementing
the `AIGateway` port.  Model references use logical names mapped in
configuration.  This includes full support for local models via Ollama, vLLM,
or any OpenAI-compatible server — MindForge can operate entirely without
cloud API keys.

**Consequences:** Provider changes require only configuration changes.  LiteLLM
adds a dependency but reduces custom provider code to zero.  Local model support
is first-class: the same gateway handles cloud and local providers transparently,
with cost tracking gracefully recording zero cost for local inference.

### ADR-03: Multi-Knowledge-Base from Day One

**Context:** The old system assumed one global knowledge base.  Phase 12 of the
implementation plan called for adding multi-KB later, but retrofitting data
isolation into an existing schema is risky.

**Decision:** Every document, artifact, concept, and quiz session is scoped to a
`KnowledgeBase` entity from the start.  Neo4j nodes carry `kb_id`.

**Consequences:** Initial complexity is slightly higher, but avoids a risky
migration later.  The relevance guard operates per-KB.

### ADR-04: Declarative Agent Orchestration

**Context:** The old pipeline was a 16-step sequential function with interleaved
I/O, feature-flag-guarded lazy imports, and no checkpointing.  Adding or
reordering steps required editing the monolith.

**Decision:** Pipeline steps are agents registered in a registry.  The
orchestrator executes a declarative graph with automatic checkpointing.
Adding a new agent means registering it and adding a node to the graph.

**Consequences:** The orchestrator is more complex than a linear function, but
agents are independently testable, reorderable, and the pipeline survives
interruptions.

### ADR-05: Content-Hash Deduplication

**Context:** The old system prevented duplicate processing by filename only.
The same content uploaded under different names was processed twice.  The same
content uploaded by different surfaces collided unpredictably.

**Decision:** `content_sha256` is the deduplication key, scoped per knowledge
base.  Lesson identity is resolved from metadata, not filename conventions.

**Consequences:** Upload surfaces must compute the hash before queueing.  The
`"unknown"` sentinel is eliminated.  Uploads without resolvable identity are
rejected.

### ADR-06: Server-Authoritative Quiz State

**Context:** Quiz grounding context and reference answers must never reach the
browser.  The old system encoded this correctly but without a clear architectural
boundary.

**Decision:** Quiz sessions live server-side behind a `QuizSessionStore`
protocol with two implementations: `RedisQuizSessionStore` (preferred, ~1ms
latency) and `PostgresQuizSessionStore` (fallback when Redis absent, ~5ms).
The API returns only question text and metadata.  Reference answers are generated
once, stored in the session, and reused during evaluation.

**Consequences:** Both stores implement the same protocol — the rest of the
system is unaware of the backing store.  The PostgreSQL fallback ensures that
local development without Redis preserves full quiz semantics.  All grading is
server-side.

### ADR-07: Async-Only in HTTP and Bot Contexts

**Context:** The old system used synchronous `requests` calls inside async
handlers, blocking the event loop for up to 180 seconds per LLM call.

**Decision:** All I/O in FastAPI handlers and Discord cog handlers is async.
The AI Gateway uses `httpx.AsyncClient` via LiteLLM's async API.  CLI entry
points use `asyncio.run()` at the top level.

**Consequences:** No sync HTTP calls in production paths.  Libraries that are
sync-only (e.g., some Langfuse SDK calls) are wrapped in `asyncio.to_thread()`.

### ADR-08: Installable Python Package

**Context:** The old system used `sys.path` manipulation in multiple entry
points, causing import order bugs and invisible packaging problems.

**Decision:** MindForge is an installable package (`pyproject.toml` with
`[project.scripts]`).  All imports use standard package resolution.

**Consequences:** Local development uses `pip install -e .`.  Docker image
installs the package.  No `sys.path` surgery in production code.

### ADR-09: Event-Driven Communication

**Context:** The old system had no event propagation.  State changes were
invisible to other surfaces.

**Decision:** Domain events are written to a transactional outbox table in the
same DB transaction as the state change.  An OutboxRelay publishes events to
Redis Pub/Sub.  The API streams events to browsers via SSE.  The pipeline
emits events after each step.

**Consequences:** At-least-once delivery guarantee.  Real-time progress tracking,
decoupled notifications, and cross-process event propagation.  Subscribers must
be idempotent.  See also ADR-12.

### ADR-10: Multimodal-Ready Data Structures

**Context:** The current data model is text-only.  Adding image, audio, or video
support later would require breaking schema migrations.

**Decision:** The `ContentBlock` model and the database schema support multiple
modalities from the start.  Initial implementation only produces `TEXT` and
`IMAGE` blocks.

**Consequences:** Slightly more complex schema, but future modalities are
additive (new block types, new parsers) rather than structural changes.

### ADR-11: Dedicated Pipeline Worker

**Context:** Early drafts had the API process executing pipeline tasks in-process
via an async task manager.  This coupled the API's lifecycle with long-running
LLM processing, made scaling difficult, and risked request-processing starvation.

**Decision:** The API only *submits* tasks to `pipeline_tasks` in PostgreSQL.  A
separate worker process (`mindforge-pipeline`) polls for pending tasks using
`SELECT ... FOR UPDATE SKIP LOCKED` and executes the agent graph.

**Consequences:** API scales independently from the pipeline.  Multiple workers
can run concurrently for horizontal scaling.  Crash recovery uses existing
checkpoints and stale-task detection.  Adds operational complexity (separate
process/container to manage).

### ADR-12: Transactional Outbox for Events

**Context:** Publishing events via an in-process EventBus creates a gap between
the database commit and the event publish.  A crash between the two produces
phantom states (data committed, event lost) or phantom events (event published,
transaction rolled back).

**Decision:** Events are written to an `outbox_events` table in the same
transaction as the state change.  An `OutboxRelay` process polls the outbox and
publishes to Redis Pub/Sub.  Subscribers are idempotent (keyed by `event_id`).

**Consequences:** At-least-once delivery guarantee.  No lost events on crash.
Subscribers must tolerate duplicates.  Adds a relay polling loop (latency ≈ poll
interval, mitigated by `pg_notify`).

### ADR-13: Step Fingerprint Checkpoint Invalidation

**Context:** Naive checkpointing (skip if artifact field is non-empty) silently
serves stale results when a prompt template, model mapping, or upstream step
changes.

**Decision:** Each pipeline step records a `StepFingerprint` hash combining
input content hash, prompt template version, model identifier, and agent code
version.  A checkpoint is valid only if the stored fingerprint matches the
current one.  Invalidation cascades through the DAG.

**Consequences:** Prompt or model changes automatically trigger re-processing.
Unchanged steps are legitimately skipped.  Adds fingerprint computation overhead
(negligible vs. LLM latency).

### ADR-14: Identity Federation via External Identities

**Context:** The earlier model used a single `auth_provider` field on the users
table, making it impossible for one user to link multiple providers (e.g.,
log in via Discord and later also via Google).

**Decision:** A separate `external_identities` table maps `(provider,
external_id)` pairs to an internal `user_id` (UUID).  The users table no longer
has an `auth_provider` column.  Account linking is an explicit user action.

**Consequences:** Users can authenticate via any linked provider.  The internal
`user_id` is stable and provider-independent.  Requires a linking flow and
conflict detection when the same external identity is already linked to a
different user.

### ADR-15: Heading-Aware Chunking

**Context:** Naïve fixed-size chunking splits text mid-paragraph and loses
structural context (which section a chunk belongs to).  This degrades retrieval
relevance for both vector similarity and Graph RAG.

**Decision:** Use heading-aware chunking (Section 10.5): split on Markdown
headings, then subdivide oversized sections with overlap.  Each chunk carries
a `heading_path` breadcrumb (e.g. `["3. Sorting", "3.1 Quicksort"]`).
Configurable limits: `CHUNK_MAX_TOKENS=500`, `CHUNK_OVERLAP_TOKENS=100`.

**Consequences:** Retrieval gets section context for free.  Chunks align with
author-intended boundaries.  Slightly more complex parser but deterministic
and testable.  PDF/DOCX inputs require heading extraction in pre-processing.

### ADR-16: Graph RAG as Primary Retrieval Strategy

**Context:** Pure vector similarity retrieval has no awareness of concept
relationships.  For a learning platform the connections *between* concepts
(prerequisites, related topics) are as important as the content itself.

**Decision:** Neo4j concept graph is the **primary retrieval path** — not a
derived projection.  Retrieval queries expand concept neighborhoods via Cypher
before (optionally) falling back to vector similarity.  Quiz question selection
also leverages graph structure to target weak spots.  See Sections 7.2 and 11.7.

**Consequences:** Neo4j becomes a hard dependency (not optional).  Graph quality
depends on concept mapper accuracy.  The combination of graph structure + vector
similarity gives higher-quality context than either approach alone.

### ADR-17: Conversational RAG for Knowledge Base Chat

**Context:** Users want to interact with their processed knowledge base beyond
quizzes and flashcards — asking follow-up questions, exploring connections,
and getting explanations in conversational form.

**Decision:** Add a chat endpoint (`/api/kb/{kb_id}/chat`) that uses Graph RAG
per-turn retrieval with sliding-window conversation history (last 10 turns).
The system prompt grounds the model strictly in the user's knowledge base.
Security: no grounding snippets are leaked to the client; only the assistant
message is returned.

**Consequences:** Adds a new application service (`ChatService`) and router.
Requires turn-level Langfuse tracing for cost attribution.  Conversation history
is session-scoped (in-memory or Redis), not persisted to PostgreSQL.

### ADR-18: Locale-Aware Prompt Templates

**Context:** All LLM prompt templates were written in Polish, matching the
product's primary user base.  As MindForge grows, users may want agents to
reason and output in their preferred language (e.g., English) while keeping
the underlying knowledge base content in any language.

**Decision:** Prompt templates are stored as locale-suffixed Markdown files
(`{name}_{locale}.md`).  The default locale is Polish (`pl`).  The
`load_prompt(filename, locale)` helper resolves the requested locale first and
falls back to `pl` if no match is found.  `ProcessingSettings.prompt_locale`
carries the locale through the agent graph; `KnowledgeBase.prompt_locale`
persists the user's preference.  Locale is encoded into the `StepFingerprint`
via the prompt version string, so a locale change automatically invalidates
all affected pipeline checkpoints and triggers re-processing.

**Consequences:** Every prompt module must implement locale-aware loading.
Prompt files must have at least a `.pl.md` baseline.  Adding a new locale
means adding new `.{locale}.md` files — no code changes required.  Pipeline
re-runs triggered by locale changes carry the same cost as any other full
re-process; users should be informed before switching KB locale.

---

## Appendix A: Technology Stack Summary

| Component | Technology | Purpose |
|---|---|---|
| Language | Python 3.12+ | Backend, agents, CLI |
| Web framework | FastAPI | REST API, SSE, SPA serving |
| Frontend | Angular 19+ | SPA |
| AI Gateway | LiteLLM | Provider abstraction |
| Canonical DB | PostgreSQL 16 | Source of truth |
| Graph DB | Neo4j 5 Community | Concept graph, retrieval |
| Cache / Sessions | Redis 7 | Quiz sessions, semantic cache, pub/sub |
| Object Storage | MinIO | Media assets |
| Observability | Langfuse | Traces, cost, evals |
| Containerization | Docker, Docker Compose | Deployment |
| Graph Visualization | Cytoscape.js | Concept map in SPA |
| Chat Platforms | discord.py, slack-bolt | Discord and Slack bot surfaces |
| Document Parsing | python-frontmatter, PyMuPDF, python-docx | Multi-format ingestion |
| ORM / DB Toolkit | SQLAlchemy 2.0 (async) + Alembic | PostgreSQL access, migrations |
| Spaced Repetition | SM-2 algorithm | Flashcard scheduling |

## Appendix B: Configuration Reference

All settings are loaded once at startup from `.env` / environment variables.
No setting is ever read from `os.environ` at request time.

```env
# ── Database ────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://mindforge:secret@localhost:5432/mindforge
REDIS_URL=redis://localhost:6379/0

# ── Neo4j ───────────────────────────────────────
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=secret
NEO4J_DATABASE=neo4j

# ── AI Models ───────────────────────────────────
MODEL_SMALL=openai/gpt-4o-mini
MODEL_LARGE=openai/gpt-4o
MODEL_VISION=openai/gpt-4o
MODEL_EMBEDDING=openai/text-embedding-3-small
MODEL_FALLBACK=anthropic/claude-3-haiku-20240307
OPENROUTER_API_KEY=sk-or-...

# ── Local Models (uncomment to use instead of cloud) ──
# MODEL_SMALL=ollama/llama3.1
# MODEL_LARGE=ollama/llama3.1:70b
# MODEL_VISION=ollama/llava
# MODEL_EMBEDDING=ollama/nomic-embed-text
# OLLAMA_API_BASE=http://localhost:11434

# ── Auth (OAuth providers) ──────────────────────
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=http://localhost:8080/api/auth/callback/discord
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

# ── Auth (Basic / email+password) ───────────────
ENABLE_BASIC_AUTH=true
BCRYPT_COST_FACTOR=12

# ── Auth (JWT & Cookies) ────────────────────────
JWT_SECRET=...
JWT_ACCESS_TOKEN_TTL_MINUTES=60
JWT_REFRESH_TOKEN_TTL_DAYS=30
AUTH_SECURE_COOKIES=false

# ── Slack Bot ───────────────────────────────────
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...              # required for Socket Mode
SLACK_SIGNING_SECRET=...
SLACK_ALLOWED_WORKSPACES=T00000001,T00000002

# ── Object Storage ──────────────────────────────
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=mindforge-assets

# ── Feature Flags ───────────────────────────────
ENABLE_GRAPH=true
ENABLE_IMAGE_ANALYSIS=true
ENABLE_FLASHCARDS=true
ENABLE_DIAGRAMS=true
ENABLE_TRACING=true
ENABLE_EMBEDDINGS=true
ENABLE_RELEVANCE_GUARD=true

# ── Limits ──────────────────────────────────────
MAX_DOCUMENT_SIZE_MB=10
MAX_CONCURRENT_PIPELINES=2
MAX_PENDING_TASKS_PER_USER=10
PIPELINE_TASK_STALE_THRESHOLD_MINUTES=30
QUIZ_SESSION_TTL_SECONDS=1800

# ── Tracing ─────────────────────────────────────
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=http://localhost:3000
```

## Appendix C: No Data Migration

This is a greenfield rewrite.  There is **no migration** of existing data from
the current system.  The old codebase, filesystem state (`state/artifacts/`,
`state/knowledge_index.json`, `state/processed.json`, `state/sr_state.json`),
and any existing Neo4j data are discarded entirely.  The new system starts with
an empty database and a clean schema.
