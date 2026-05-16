---
description: "Audit MindForge for cost and performance regressions: retrieval ordering, LLM call discipline, context-window bounds, Redis/Neo4j graceful degradation, and PostgreSQL query efficiency. Run after any change to agents, retrieval, quiz, or pipeline."
name: "Performance Audit"
argument-hint: "Optional: a specific surface or module to focus on (e.g., 'retrieval', 'quiz', 'pipeline', 'agents'). Omit to audit all surfaces."
agent: "Code Review"
---

# MindForge Performance and Cost Audit

You are the MindForge performance and cost auditor. Your goal is to identify
violations of the project's **cost discipline rules** and **performance
invariants** — not general profiling. Findings must be concrete, file-level
regressions against the specific rules listed below. Produce a structured
report; skip narrative commentary.

## Setup

Before auditing, read:

- [.github/copilot-instructions.md](.github/copilot-instructions.md) —
  cost guardrails and retrieval ordering rules.
- [.github/docs/architecture.md](.github/docs/architecture.md) — data store
  responsibilities and degradation contracts.

If an argument was provided, restrict the audit to the relevant modules using
the scope table below. Otherwise audit all surfaces.

| Argument | Paths to read |
|---|---|
| `retrieval` | `mindforge/infrastructure/graph/`, `mindforge/application/` (search paths), `mindforge/api/routers/search.py` |
| `quiz` | `mindforge/application/quiz.py`, `mindforge/api/routers/quiz.py`, `mindforge/agents/quiz_evaluator.py`, `mindforge/agents/quiz_generator.py` |
| `pipeline` | `mindforge/application/pipeline.py`, `mindforge/agents/`, `mindforge/infrastructure/ai/gateway.py` |
| `agents` | `mindforge/agents/`, `mindforge/infrastructure/ai/gateway.py`, `mindforge/infrastructure/ai/prompts/` |
| *(all)* | All of the above plus `mindforge/infrastructure/persistence/`, `mindforge/infrastructure/cache/` |

Read **full file contents** for every path in scope — do not limit to diffs.
Also read any module that the in-scope files import from `mindforge/`.

---

## Audit Dimensions

---

### P1 — Retrieval Cost Ordering

**Rule:** Graph traversal must be attempted first. Full-text / lexical search
is the second tier. Vector embedding search is the last resort, used only when
the cheaper tiers return insufficient results. Skipping to vector search is a
cost regression.

For every call site that performs knowledge retrieval:

1. Locate the call chain from the router or application service down to the
   infrastructure retrieval adapter.
2. Verify the ordering: graph query → lexical/full-text query → vector query.
3. Flag any path where:
   - Vector search is invoked unconditionally (not gated on prior-tier results).
   - Vector search is the only retrieval method used.
   - The graph or lexical tier is bypassed entirely without a documented reason.
4. Check `mindforge/infrastructure/graph/neo4j_retrieval.py` and any full-text
   search adapter for whether their results are evaluated before an embedding
   query is made.

---

### P2 — LLM Call Discipline

**Rule:** Each piece of AI-generated content (summary, flashcards, concepts,
quiz questions, reference answer) must be generated exactly once per pipeline
run and stored in `document_artifacts`. Subsequent reads must load from the
stored artifact — never re-invoke the AI gateway.

For each agent in `mindforge/agents/`:

1. Verify that the agent's output is checkpointed to `document_artifacts` via
   `StepFingerprint` after a successful run.
2. Check that the application layer (pipeline orchestrator) reads the
   checkpointed value and skips the agent call when a valid fingerprint exists.
3. Flag any call to `mindforge/infrastructure/ai/gateway.py` (or the LiteLLM
   client directly) that occurs outside of an agent's `run()` method — i.e.,
   ad-hoc LLM calls in routers, application services, or infrastructure
   adapters are regressions.

Specifically for quiz evaluation:
- `mindforge/agents/quiz_evaluator.py` and `mindforge/application/quiz.py`
  must read `reference_answer` from the stored `DocumentArtifact`. Verify this
  path explicitly. Any code path that calls the AI gateway to (re)generate
  `reference_answer` at grading time is a **Critical** cost regression.

---

### P3 — Context Window Bounds

**Rule:** Agent prompts and RAG context assembly must be bounded. Passing an
unbounded knowledge index or full document set to the LLM is not acceptable.

For every agent and every RAG assembly path:

1. Read prompt templates in `mindforge/infrastructure/ai/prompts/` and the
   context-assembly code in the agent or application service.
2. Verify that retrieved context is trimmed or ranked before being inserted
   into a prompt (e.g., top-K chunks, token-budget truncation).
3. Flag any assembly path where the full set of retrieved documents, chunks,
   or artifacts is passed to the gateway without a size limit.
4. Check the summarizer agent (`mindforge/agents/summarizer.py`) and the
   concept mapper (`mindforge/agents/concept_mapper.py`) specifically, as they
   operate on full document content.

---

### P4 — Agent Version and Checkpoint Discipline

**Rule:** `__version__` on each agent class must be bumped only when the
agent's logic changes. An unnecessary bump invalidates all cached pipeline
checkpoints for that agent, forcing expensive re-runs across all documents.
Conversely, failing to bump after a logic change causes stale outputs to be
served from cache.

For every agent in `mindforge/agents/`:

1. Confirm that `__version__` is defined as a class-level attribute.
2. Check the git log or diff context: if the agent file was changed, verify
   that `__version__` was bumped if and only if the agent's prompt, model
   selection, or output schema changed.
3. Flag agents where `__version__` is missing entirely.

---

### P5 — Redis Graceful Degradation

**Rule:** Redis is optional. No critical path may hard-depend on Redis. Quiz
sessions must fall back to PostgreSQL, SSE must fall back to polling
`outbox_events`, and the semantic cache must be silently disabled when Redis
is unavailable.

For each Redis-using path:

1. Read `mindforge/infrastructure/cache/redis_quiz_sessions.py` and the
   session factory / DI wiring that chooses between Redis and PostgreSQL.
2. Verify that a `ConnectionError`, `RedisError`, or missing Redis URL causes
   graceful fallback, not an unhandled exception or silent data loss.
3. Read the SSE event route (`mindforge/api/routers/events.py` or equivalent).
   Verify that the polling fallback is active when Redis pub/sub is unavailable.
4. Flag any code path where a Redis failure raises an HTTP 500 or causes a
   pipeline step to abort.

---

### P6 — Neo4j Graceful Degradation

**Rule:** Neo4j is a derived projection. Its unavailability must never prevent
document ingestion, quiz serving, or API responses from functioning. A startup
warning is acceptable; a crash or silent data corruption is not.

1. Read the Neo4j indexer (`mindforge/infrastructure/graph/neo4j_indexer.py`)
   and the retrieval adapter (`mindforge/infrastructure/graph/neo4j_retrieval.py`).
2. Verify that a `ServiceUnavailable` or connection failure from the Neo4j
   driver is caught and logged as a warning, not re-raised to the caller.
3. Confirm that the retrieval tier falls through to lexical / vector search
   when Neo4j is unreachable, rather than returning an empty result or raising.
4. Verify that the outbox relay does not crash the process when Neo4j is
   temporarily unavailable — it should retry with backoff.

---

### P7 — PostgreSQL Query Efficiency

**Rule:** ORM queries must not produce N+1 patterns. Relationships needed by a
query must be eagerly loaded in the same query, not lazily fetched in a loop.

For every SQLAlchemy query in `mindforge/infrastructure/persistence/`:

1. Look for `for` loops or list comprehensions that access a relationship
   attribute (`artifact.steps`, `document.artifacts`, etc.) on objects loaded
   by a prior query without eager loading (`joinedload`, `selectinload`,
   `contains_eager`).
2. Flag any query that is executed inside a loop over a result set from another
   query (nested query pattern).
3. Check that queries selecting large result sets use pagination (`limit`,
   `offset`, or keyset pagination) rather than loading all rows into memory.

---

## Output Format

### Performance and Cost Audit Report — `<date>`

**Scope:** `<surfaces audited>`

| Dimension | Status | Findings |
|-----------|--------|----------|
| P1 — Retrieval cost ordering | PASS / FAIL | N findings |
| P2 — LLM call discipline | PASS / FAIL | N findings |
| P3 — Context window bounds | PASS / FAIL | N findings |
| P4 — Agent version / checkpoint | PASS / FAIL | N findings |
| P5 — Redis graceful degradation | PASS / FAIL | N findings |
| P6 — Neo4j graceful degradation | PASS / FAIL | N findings |
| P7 — PostgreSQL query efficiency | PASS / FAIL | N findings |

**Overall: PASS / FAIL**

---

### Finding Detail

For each FAIL dimension, list findings as:

```
[P2] mindforge/application/quiz.py:118
     CRITICAL — calls AIGateway.complete() to regenerate reference_answer at
     grading time. Must read from DocumentArtifact.reference_answer instead.

[P1] mindforge/application/pipeline.py:204
     Vector search invoked unconditionally; no graph or lexical tier attempted
     first. Wrap with prior-tier result check.
```

Format: `[Px] file:line`, severity label, one-sentence description.
Sort Critical first, then High, Medium, Low. No suggested code — use the
Bug Fix agent for remediation.

---

### Save the Report

After completing the report, save it as a Markdown file:

- **Path:** `reviews/performance-audit-<YYYY-MM-DD>.md` (use today's date).
- The file must contain the full report (the summary table and all finding
  details) exactly as specified above.
- **Do NOT modify any application code, test files, migration files,
  configuration files, or any file outside `reviews/`.** The only write
  operation permitted is creating or overwriting the report file.
