# Hexagonal Architecture Standards

MindForge follows strict Hexagonal Architecture (Ports and Adapters). These standards are non-negotiable — deviations corrupt the architecture.

## Layer Boundaries

Dependencies always point inward: adapters → application → domain. Never cross layer boundaries.

| Layer | Path | Allowed Imports |
|---|---|---|
| Domain | `mindforge/domain/` | Python stdlib only; zero I/O, zero framework imports |
| Application | `mindforge/application/` | `mindforge.domain.*` only |
| Infrastructure | `mindforge/infrastructure/` | `mindforge.domain.*`, `mindforge.application.*`, any third-party |
| Agents | `mindforge/agents/` | `mindforge.domain.*`, `mindforge.infrastructure.ai.*` |
| Adapters | `mindforge/api/`, `mindforge/discord/`, `mindforge/slack/`, `mindforge/cli/` | All layers (thin; no business logic) |

```python
# NEVER in mindforge/domain/
from sqlalchemy import ...  # ❌ framework import
import httpx               # ❌ I/O import

# NEVER in mindforge/application/
from litellm import ...    # ❌ LLM SDK
from sqlalchemy import ... # ❌ database driver
```

## Composition Root

Each runtime surface has **exactly one** composition root — no module-level singletons, no import-time side effects.

Composition roots:
- `mindforge/api/main.py` → `lifespan()` function
- `mindforge/discord/bot.py`
- `mindforge/slack/app.py`
- `mindforge/cli/pipeline_runner.py`

```python
# CORRECT: all wiring in lifespan()
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db_engine = create_async_engine(settings.database_url)
    gateway = LiteLLMGateway(settings)
    # ... wire everything here

# NEVER: module-level singletons
db_engine = create_async_engine(...)  # ❌ module-level
```

## Open/Closed Principle

Adding a new AI agent, document format parser, or auth provider means registering a new adapter — **never** modifying the orchestrator, `ParserRegistry`, or auth framework.

```python
# CORRECT: register new format
registry.register("application/epub", EpubParser())

# NEVER: add new format by modifying IngestionService.ingest()
```

## Data Store Roles

- **PostgreSQL**: Single source of truth for all business data. All writes go here first.
- **Neo4j**: Derived read projection only. Rebuilt from PostgreSQL via outbox events. Never write business data here as authoritative state.
- **Redis**: Optional. When absent: quiz sessions fall back to PostgreSQL, SSE falls back to outbox polling, semantic cache disabled. Always emit startup warning when Redis is absent.

## Pipeline Idempotency

Every pipeline step must:
1. Check if a matching `StepFingerprint` already exists for the current inputs
2. Skip execution and return cached output if fingerprint matches
3. Checkpoint output + fingerprint to `document_artifacts` after execution
4. Publish domain event to outbox in the **same database transaction** as the checkpoint

```python
# CORRECT: checkpoint + publish in same transaction
async with session.begin():
    artifact_repo.save_checkpoint(artifact, session)
    event_publisher.publish_in_tx(event, session)

# NEVER: publish event outside transaction
```

## Retrieval Cost Discipline

Order: **graph traversal first → full-text/lexical second → vector embeddings last**.

Always reuse the stored `reference_answer` from `DocumentArtifact` during quiz grading — never regenerate it.

## Agent Communication

Agents **never call each other directly**. All inter-agent data flows through the shared `DocumentArtifact` in `AgentContext`. The pipeline orchestrator (`mindforge/application/pipeline.py`) is the single coordination point.

```python
# NEVER
class SummarizerAgent:
    async def execute(self, ctx: AgentContext) -> AgentResult:
        flashcard_result = await self.flashcard_agent.execute(ctx)  # ❌

# CORRECT: orchestrator injects shared artifact
```

## Transactional Outbox

All domain events are propagated via the transactional outbox pattern. State changes and their events are committed in the same database transaction — guaranteeing at-least-once delivery without distributed transactions.

All event subscribers must be **idempotent** (keyed by `event_id`) because an event may be delivered more than once after relay crash recovery.
