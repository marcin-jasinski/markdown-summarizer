# MindForge

<div align="center">

**AI-Powered Knowledge Graph & Study Tool**

Transform learning materials into interactive study artifacts with intelligent summarization, flashcard generation, concept mapping, and knowledge graph indexing.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.135%2B-009688)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-15%2B-336791)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[Quick Start](#-quick-start) • [Architecture](#-architecture) • [Features](#-features) • [Documentation](#-documentation)

</div>

---

## 📋 Overview

MindForge is a full-stack AI-powered learning platform built with **hexagonal architecture** (Ports & Adapters). It extracts knowledge from documents (Markdown, PDF, DOCX, TXT), automatically generates study materials, and provides an interactive learning interface through multiple runtime surfaces:

- **Web UI** — Angular SPA with interactive quizzes and knowledge browser
- **FastAPI REST API** — Full programmatic access to all features
- **Discord Bot** — Study and quiz directly from Discord
- **Slack Bot** — Classroom integration for Slack workspaces
- **Quiz CLI** — Terminal-based interactive quizzing
- **Pipeline Runner** — Background document processing with AI orchestration

### 🎯 Key Capabilities

| Capability | Details |
|---|---|
| **Document Processing** | Extract and structure text from Markdown, PDF, DOCX, TXT with metadata preservation |
| **AI-Powered Enrichment** | Generate summaries, flashcards, concept maps, and knowledge graphs via agent orchestration |
| **Knowledge Graph** | Neo4j-backed semantic search with fallback to PostgreSQL full-text retrieval |
| **Interactive Quizzing** | Spaced repetition quiz engine with weak concept detection and scoring |
| **Multi-Channel** | Access knowledge through web UI, REST API, Discord, Slack, or CLI |
| **Provider Agnostic** | Support any LLM via LiteLLM (OpenAI, Anthropic, Ollama, OpenRouter, and more) |
| **Cost-Optimized** | Deterministic logic first, small models second, frontier models last |
| **Observable** | Full distributed tracing with token/cost accounting per operation via Langfuse |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **PostgreSQL 15+** (or Docker Compose)
- **Node.js 20+** (for frontend)
- **Docker & Docker Compose** (optional, for full stack)

### Local Development (5 minutes)

#### 1. Clone & Setup Environment

```bash
git clone https://github.com/yourusername/mindforge.git
cd mindforge

# Copy environment template and configure
cp env.example .env
# Edit .env with your local database URL and LLM API keys
```

#### 2. Create Python Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

#### 3. Initialize Database

```bash
# Run migrations
alembic upgrade head

# Or use the FastAPI server (runs migrations automatically)
python -m uvicorn mindforge.api.main:app --host 0.0.0.0 --port 8080 --reload
```

#### 4. Start Services

In separate terminals:

```bash
# Terminal 1: Backend API
python -m uvicorn mindforge.api.main:app --host 0.0.0.0 --port 8080 --reload

# Terminal 2: Frontend (Angular)
cd frontend
npm install
npm start
# Opens http://localhost:4200

# Terminal 3: Pipeline runner (optional, for document processing)
mindforge-pipeline
```

#### 5. Create User & Upload Document

- Open http://localhost:4200
- Sign up or log in (Discord OAuth or email)
- Create a knowledge base
- Upload a Markdown or PDF document
- Watch the pipeline process it and generate artifacts

### Docker Compose (Full Stack)

```bash
docker-compose up -d
# Services:
#   API: http://localhost:8080
#   SPA: http://localhost:4200
#   PostgreSQL: localhost:5432
#   Neo4j: http://localhost:7474 (user: neo4j, pass: secret)
#   Redis: localhost:6379
```

---

## 🏗️ Architecture

MindForge follows **hexagonal architecture** (Ports and Adapters) with strict layer boundaries:

```
┌─────────────────────────────────────────────────────┐
│            Driving Adapters                          │
│  (HTTP, CLI, Discord, Slack, File Watcher)          │
└───────────────────┬─────────────────────────────────┘
                    │ uses
┌───────────────────▼─────────────────────────────────┐
│            Application Services                      │
│  (Use cases: ingest, quiz, search, flashcards)       │
├─────────────────────────────────────────────────────┤
│            Domain Model                              │
│  (Entities, events, protocols, orchestration)        │
└───────────────────┬─────────────────────────────────┘
                    │ depends on (ports)
┌───────────────────▼─────────────────────────────────┐
│            Driven Adapters                           │
│  (PostgreSQL, Neo4j, LiteLLM, Redis, MinIO, SMTP)   │
└─────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Purpose | Key Modules |
|---|---|---|
| **Domain** | Pure Python, zero I/O. Entities, value objects, domain events, agent protocols, port interfaces. | `mindforge/domain/` |
| **Application** | Use-case orchestration. Imports only `domain/`. No database, HTTP, or LLM SDK. | `mindforge/application/` |
| **Infrastructure** | All I/O: databases, LLM gateway, storage, messaging, security. | `mindforge/infrastructure/` |
| **Adapters** | Thin driving/driven adapters. No business logic. | `mindforge/api/`, `mindforge/discord/`, `mindforge/slack/`, `mindforge/cli/` |

### Key Architectural Decisions

1. **Single Source of Truth**: PostgreSQL is canonical; Neo4j is a derived projection rebuilt from artifacts.
2. **Composition Root**: Each runtime (API, CLI, Discord) has exactly one composition root—no module-level singletons.
3. **Idempotency**: Every pipeline step checkpoints output with a fingerprint; safe to retry.
4. **Cost Discipline**: Graph traversal first → full-text search second → vector embeddings last.
5. **Server Authoritative**: All grading, scoring, and session state computed server-side; sensitive data never sent to browser.

For detailed architecture documentation, see [.github/docs/architecture.md](.github/docs/architecture.md).

---

## 📦 Project Structure

```
mindforge/
├── domain/              # Pure Python, zero I/O
│   ├── agents.py        # Agent protocols and contexts
│   ├── models.py        # Core entities and value objects
│   ├── events.py        # Domain events (pipeline, quiz, etc.)
│   └── ports.py         # Abstract interfaces (repositories, gateways)
├── application/         # Use-case orchestration
│   ├── pipeline.py      # Document processing orchestrator
│   ├── quiz.py          # Quiz service and scoring
│   ├── search.py        # Knowledge search
│   └── flashcards.py    # Flashcard service
├── infrastructure/      # All I/O
│   ├── config.py        # Settings validation (Pydantic)
│   ├── db.py            # PostgreSQL engine and migrations
│   ├── ai/              # LiteLLM gateway and agent implementations
│   ├── graph/           # Neo4j graph adapter
│   ├── cache/           # Redis session store
│   ├── persistence/     # SQLAlchemy repositories
│   └── security/        # Auth, upload sanitization, egress policy
├── agents/              # Stateless AI agent implementations
│   ├── preprocessor.py  # Text normalization
│   ├── summarizer.py    # Extractive & abstractive summaries
│   ├── flashcard_generator.py
│   ├── concept_mapper.py
│   ├── quiz_generator.py
│   └── quiz_evaluator.py
├── api/                 # FastAPI composition root & routers
│   ├── main.py          # Lifespan context, ASGI app factory
│   ├── schemas.py       # Pydantic request/response models
│   └── routers/         # Endpoint handlers (quiz, search, docs, etc.)
├── discord/             # Discord bot adapter
│   ├── bot.py           # Discord.py client setup
│   └── cogs/            # Discord command handlers
├── slack/               # Slack bot adapter
│   ├── app.py           # Slack Bolt setup
│   └── handlers/        # Slack event handlers
└── cli/                 # CLI entry points
    ├── pipeline_runner.py
    ├── quiz_runner.py
    └── backfill.py

frontend/               # Angular SPA (standalone, lazy routes)
├── src/
│   ├── app/
│   │   ├── core/services/   # HTTP clients, auth, state
│   │   ├── core/guards/     # Route protection
│   │   ├── pages/           # Feature components
│   │   └── shell/           # Layout wrapper
│   ├── assets/
│   └── styles/
└── dist/                # Built output (served by FastAPI)

tests/
├── unit/                # No I/O, fast (uses pytest fixtures)
├── integration/         # Real DB, mocked LLM (Testcontainers)
└── e2e/                 # Full stack tests
```

---

## ✨ Features

### 1. Document Ingestion & Processing

Upload documents in multiple formats; the pipeline automatically extracts text, detects metadata, and validates lesson identity.

```bash
mindforge-pipeline
```

**Supported Formats:**
- Markdown (with YAML frontmatter for metadata)
- PDF (text & image extraction)
- DOCX (structured content)
- TXT (plain text)

**Metadata Detection:**
- YAML frontmatter (`lesson_id`, `title`, `topic`)
- PDF metadata (Title, Author)
- Filename-based fallback

### 2. AI-Powered Enrichment

The pipeline orchestrator runs agents in topological order:

1. **Preprocessor** — Normalize text, detect language
2. **Summarizer** — Generate key points and abstractive summary
3. **Concept Mapper** — Extract entities and relationships
4. **Flashcard Generator** — Create study cards (BASIC, CLOZE, REVERSE)
5. **Quiz Generator** — Generate questions with reference answers
6. **Image Analyzer** — OCR and caption extraction (VISION model)

All agents run via the **LiteLLM gateway** with deadline profiles (INTERACTIVE, BATCH, BACKGROUND) for cost optimization.

### 3. Knowledge Graph & Search

- **Neo4j Backend** — Semantic relationships and traversal
- **Full-Text Search** — PostgreSQL lexical + trigram similarity
- **Vector Embeddings** — Optional semantic search (via embedding model)
- **Fallbacks** — Search works even if Neo4j or Redis is unavailable

### 4. Interactive Quizzing

- **Spaced Repetition** — Quiz engine tracks retention and intervals
- **Weak Concept Detection** — Identify topics needing reinforcement
- **Server-Authoritative Grading** — LLM-based answer evaluation; reference answers never sent to client
- **Interaction Audit Trail** — Full history of quiz attempts for analytics

```bash
mindforge-quiz
# Interactive CLI quiz with scoring and feedback
```

### 5. Multi-Channel Access

| Channel | Features |
|---|---|
| **Web UI** | Create knowledge bases, upload docs, browse artifacts, take quizzes |
| **REST API** | Full programmatic access with comprehensive OpenAPI docs |
| **Discord Bot** | `/start-quiz`, `/search`, `/new-kb` commands |
| **Slack Bot** | Thread-based quizzing and classroom integration |
| **Quiz CLI** | Terminal-based spaced repetition study |

### 6. Security & Cost Guardrails

- **Server-Authoritative State** — No sensitive data (answers, grading logic) on client
- **Upload Sanitization** — Filename validation, egress policy enforcement
- **Cost Discipline** — Graph-first retrieval, deterministic logic before LLM calls
- **Rate Limiting** — Per-user and per-service quotas
- **Observability** — Token count tracking and cost attribution via Langfuse

---

## 🔧 Configuration

### Environment Variables

Copy `env.example` to `.env`:

```bash
# Database (REQUIRED)
DATABASE_URL=postgresql+asyncpg://mindforge:secret@localhost:5432/mindforge

# Redis (optional, falls back to PostgreSQL)
REDIS_URL=redis://localhost:6379/0

# Neo4j (optional, graph features disabled if absent)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=secret

# AI Models (REQUIRED: at least one provider API key)
MODEL_SMALL=openai/gpt-4o-mini
MODEL_LARGE=openai/gpt-4o
MODEL_VISION=openai/gpt-4o
MODEL_EMBEDDING=openai/text-embedding-3-small
OPENROUTER_API_KEY=sk-or-...

# Auth (Discord OAuth)
DISCORD_CLIENT_ID=...
DISCORD_CLIENT_SECRET=...
DISCORD_REDIRECT_URI=http://localhost:8080/api/auth/callback/discord

# Features
ENABLE_GRAPH=true
ENABLE_DISCORD_BOT=true
ENABLE_SLACK_BOT=false
```

All settings are **validated once at startup** via Pydantic; never read at request time.

---

## 📚 CLI Entry Points

After `pip install -e .`:

```bash
# REST API server (FastAPI)
mindforge-api

# Document processing pipeline
mindforge-pipeline

# Interactive quiz CLI
mindforge-quiz

# Discord bot
mindforge-discord

# Slack bot
mindforge-slack

# Backfill and reindex operations
mindforge-backfill
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Unit tests (no I/O, fast)
pytest tests/unit/ -v

# Integration tests (real DB, mocked LLM)
pytest tests/integration/ -v

# E2E tests (full stack, requires all services)
pytest tests/e2e/ -v

# Test coverage
pytest --cov=mindforge tests/
```

---

## 📖 API Overview

### Authentication

All endpoints (except `/api/health` and `/api/auth/*`) require a JWT bearer token:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8080/api/knowledge-bases
```

### Key Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/auth/register` | User registration |
| `POST` | `/api/auth/login` | Get JWT token |
| `POST` | `/api/knowledge-bases` | Create a knowledge base |
| `POST` | `/api/knowledge-bases/{kb_id}/documents` | Upload document |
| `GET` | `/api/knowledge-bases/{kb_id}/documents` | List documents |
| `POST` | `/api/knowledge-bases/{kb_id}/search` | Full-text search |
| `POST` | `/api/knowledge-bases/{kb_id}/quiz/start` | Start a quiz session |
| `POST` | `/api/knowledge-bases/{kb_id}/quiz/answer` | Submit quiz answer |
| `GET` | `/api/health` | Health check |
| `GET` | `/openapi.json` | OpenAPI spec |

**Interactive API Docs:** http://localhost:8080/docs (Swagger UI)

---

## 🛠️ Development

### Project Standards

- **No `sys.path` manipulation** — Install as `pip install -e .` and import `mindforge.*`
- **Composition root per surface** — Each runtime (API, CLI, bot) has one place where all dependencies are wired
- **Explicit configuration** — No module-level singletons; settings are validated once and injected
- **Type hints** — All public APIs use type hints; Pylance for verification
- **Docstrings** — Domain and application layers have comprehensive docstrings
- **Idempotency** — Every pipeline step is safe to retry; use fingerprints and checksums

### Code Style

```bash
# Format with ruff
ruff format mindforge tests

# Lint
ruff check mindforge tests

# Type check
pyright mindforge
```

### Adding a New Agent

1. Create `mindforge/agents/my_agent.py` implementing the `Agent` protocol
2. Register in composition root (e.g., `mindforge/api/main.py`)
3. Add to orchestration DAG in `mindforge/application/orchestration.py`
4. Write tests in `tests/unit/agents/`

No modifications to the orchestrator or registry required—the Open/Closed principle is enforced.

### Adding a New API Endpoint

1. Create route in `mindforge/api/routers/` (or extend existing router)
2. Use application service for business logic
3. Validate input with Pydantic schema
4. Return response model (never expose sensitive fields like `reference_answer`)
5. Sync OpenAPI spec: `python scripts/export_openapi.py`

---

## 🚢 Deployment

### Docker Compose

```bash
# Start all services (API, Angular, PostgreSQL, Neo4j, Redis, etc.)
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Single Server

For production, use the multi-stage `Dockerfile`:

```bash
docker build -t mindforge:latest .
docker run -p 8080:8080 \
  -e DATABASE_URL=postgresql+asyncpg://... \
  -e OPENROUTER_API_KEY=... \
  mindforge:latest
```

### Health Checks

```bash
# API health
curl http://localhost:8080/api/health

# With Docker Compose
docker-compose ps
# Healthy if all services show "healthy" or "Up"
```

---

## 📖 Documentation

- **[Architecture Overview](.github/docs/architecture.md)** — System design, layers, and principles
- **[Implementation Plan](.github/docs/implementation-plan.md)** — Feature roadmap and delivery timeline
- **[Security Review](.reviews/mindforge-deep-code-review-2026-04-01.md)** — Security and cost baseline
- **[Frontend README](./frontend/README.md)** — Angular SPA development guide
- **[Copilot Instructions](.github/copilot-instructions.md)** — Guidelines for this workspace

---

## 🤝 Contributing

1. **Read the architecture** — Understand hexagonal architecture and layer boundaries
2. **Follow conventions** — See [.github/copilot-instructions.md](.github/copilot-instructions.md)
3. **Test first** — Write tests for domain and application layers
4. **Use representative files** — Model new code after existing patterns
5. **Preserve polish** — Don't change user-facing content unless intended

---

## 📝 License

[MIT License](LICENSE) — See LICENSE file for details.

---

## 🎓 Learning Resources

### Understanding Hexagonal Architecture

- [Alistair Cockburn's Original Paper](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports & Adapters Pattern](https://en.wikipedia.org/wiki/Hexagonal_architecture)
- [Domain-Driven Design](https://www.domainlanguage.com/ddd/)

### Stack Technologies

- [FastAPI](https://fastapi.tiangolo.com/) — Modern Python web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) — SQL toolkit and ORM
- [Neo4j](https://neo4j.com/) — Graph database
- [LiteLLM](https://litellm.vercel.app/) — LLM gateway
- [Angular](https://angular.io/) — Frontend framework
- [Discord.py](https://discordpy.readthedocs.io/) — Discord bot library
- [Slack Bolt](https://slack.dev/bolt-python/) — Slack bot framework

---

## 🐛 Troubleshooting

### Database Connection Failed

```bash
# Verify PostgreSQL is running
psql -U mindforge -d mindforge -c "SELECT version();"

# Check DATABASE_URL in .env
# Format: postgresql+asyncpg://user:password@host:port/database
```

### Redis Not Available

The system gracefully degrades:
- Quiz sessions fall back to PostgreSQL
- SSE falls back to polling `outbox_events`
- Semantic cache is disabled
- A warning is logged on startup

### LLM API Key Issues

```bash
# Verify key format and provider
# Check OPENROUTER_API_KEY, OPENAI_API_KEY, etc. in .env

# Test connectivity
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/models
```

### Migration Errors

```bash
# Rollback last migration
alembic downgrade -1

# Re-run migrations
alembic upgrade head

# Check migration status
alembic current
```

---

## 📞 Support

- **Issues:** Open a GitHub issue with reproduction steps
- **Discussions:** Use GitHub Discussions for architecture and design questions
- **Security:** Report vulnerabilities to security@mindforge.dev

---

**Built with ❤️ by the MindForge team**
