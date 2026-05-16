---
description: "Trigger a thorough code review of the most recently implemented phase, covering security, performance, best practices, and architecture alignment with the MindForge implementation plan."
name: "Review Last Phase"
argument-hint: "Automatically detects and reviews the last completed phase from the implementation plan"
agent: "Code Review"
---

# Review Last Implemented Phase

You are the MindForge code review agent performing a **phase review**. Your
goal is to evaluate the most recently completed implementation phase against
the project's security model, performance constraints, best practices, and
hexagonal architecture rules.

## Workflow

### 1. Identify the Target Phase

Read [.github/docs/implementation-plan.md](.github/docs/implementation-plan.md)
and find the **most recently completed phase**: the last phase whose tasks are
all marked `[x]`. Record its phase number, name, goal, and deliverables.

### 2. Collect Phase Artifacts

For every file created or modified in this phase:

- Use `get_changed_files` or diff tooling to enumerate changes, or infer from
  the task descriptions in the plan which `mindforge/` paths were affected.
- Read changed files and any shared modules they import or are imported by.
- Do **not** limit review to changed hunks only — read the full context of each
  modified module.

### 3. Load Reference Material

Before producing findings, read:

- [.github/copilot-instructions.md](.github/copilot-instructions.md) —
  conventions, layer rules, security policy.
- [.github/docs/architecture.md](.github/docs/architecture.md) —
  hexagonal architecture reference.
- The **Completion checklist** for the target phase in the implementation plan —
  verify that every item is actually satisfied in code.

### 4. Review Dimensions

Evaluate the phase changes against every dimension below. Skip a dimension only
if the phase description explicitly excludes it (e.g., a docs-only phase has no
security surface).

#### 4.1 Architecture and Layer Boundaries

- `domain/` is pure Python: entities, value objects, events, port interfaces.
  No I/O, no framework imports, no infrastructure leakage.
- `application/` imports only `domain/`. No database drivers, HTTP clients, or
  LLM SDK calls.
- `infrastructure/` is the only layer allowed to perform I/O.
- `agents/` agents are stateless and communicate exclusively through
  `DocumentArtifact` / `AgentContext`. No agent-to-agent direct calls.
- Driving adapters (`api/`, `discord/`, `slack/`, `cli/`) are thin: no business
  logic, delegate immediately to application services.
- Each runtime surface has exactly one composition root; no module-level
  singletons or import-time side effects.
- Open/Closed: new agents, parsers, and auth providers must be registered as
  adapters — orchestrator, `ParserRegistry`, and auth framework must not require
  modification.
- No `sys.path` manipulation; all imports as `mindforge.*`.
- Configuration exclusively via `mindforge/infrastructure/config.py` (Pydantic);
  no `os.environ` at request time or module level.
- `mindforge/api/schemas.py` and `frontend/src/app/core/models/api.models.ts`
  stay synchronized.

#### 4.2 Security

Treat any finding here as **Critical** by default.

- `InteractionStore.list_for_user()` strips `reference_answer`,
  `grounding_context`, `raw_prompt`, `raw_completion` at the store level, not
  only in the router.
- Browser-facing quiz payloads must not leak grounding context or reference
  answers. Cross-check `mindforge/api/routers/quiz.py` and
  `mindforge/application/quiz.py`.
- All uploaded filenames, external URLs, and image URLs are treated as
  untrusted; processing must go through
  `mindforge/infrastructure/security/upload_sanitizer.py` and `egress_policy.py`.
  No ad-hoc filesystem or outbound HTTP handling.
- Discord and Slack features enforce channel/user allowlists and interaction
  ownership (`mindforge/discord/auth.py`, `mindforge/slack/auth.py`).
- OAuth `state` parameter is validated; cookies are hardened appropriately for
  the deployment environment.
- No secrets, tokens, or credentials in code or log output.
- OWASP Top-10 surface: injection (SQL, prompt, path, header), broken access
  control, insecure deserialization, and SSRF via user-controlled URLs.

#### 4.3 Performance and Cost

- Retrieval order invariant: graph traversal first → lexical/full-text second →
  vector embeddings last. Introducing embeddings before exhausting cheaper
  options is a cost regression.
- Question grading reuses the stored `reference_answer` from `document_artifacts`.
  Regenerating it per evaluation is a cost regression.
- Summarizer and retrieval context windows are bounded; passing the full
  knowledge index is not acceptable.
- Agent `__version__` is bumped only when agent logic changes, not on unrelated
  refactors, to avoid invalidating unaffected pipeline checkpoints.
- Redis is optional: quiz sessions fall back to PostgreSQL, SSE falls back to
  polling `outbox_events`, semantic cache is disabled. No hard Redis dependency.

#### 4.4 Data Store and Pipeline Integrity

- PostgreSQL (`document_artifacts`) is the single source of truth. Neo4j is a
  derived projection rebuilt from PostgreSQL; it is never the primary write target.
- Every pipeline step checkpoints its output and `StepFingerprint` after
  execution. Outbox patterns must not be bypassed.
- `lesson_id` resolves deterministically (frontmatter `lesson_id:` → `title:`
  slug → PDF `Title` metadata → filename). Falling back to `"unknown"` or any
  placeholder is a defect; the upload must be rejected.
- Neo4j and Langfuse degrade gracefully when unavailable (startup warning is
  acceptable; crash or silent data loss is not).

#### 4.5 Best Practices and Conventions

- All imports at module top level. Optional packages use `try/except ImportError`
  guards; no imports inside functions or conditional scopes.
- No `sys.path` manipulation anywhere in new code.
- No module-level singletons or import-time side effects.
- Polish user-facing strings are preserved unless the phase explicitly changes
  product language.
- Representative file patterns followed: `application/pipeline.py` for
  orchestration, `agents/summarizer.py` for agents,
  `infrastructure/ai/gateway.py` for the LLM gateway,
  `frontend/src/app/core/services/api.service.ts` for Angular HTTP.

#### 4.6 Testing Coverage

- Domain, application, and agent changes have matching unit tests in
  `tests/unit/`.
- Real-DB interactions have integration tests in `tests/integration/`.
- The phase completion checklist explicitly lists test requirements; verify
  each is actually implemented, not just declared.

#### 4.7 Documentation Accuracy

- [.github/copilot-instructions.md](.github/copilot-instructions.md) and
  [.github/docs/architecture.md](.github/docs/architecture.md) are updated if
  architecture, workflow, or Docker behavior materially changed.
- `README.md` and `scripts/STARTUP_GUIDE.md` remain accurate after any runtime
  or entry-point changes.

### 5. Phase Completion Checklist Audit

For every item in the phase's **Completion checklist**, state explicitly:

| Checklist item | Status | Evidence / Finding |
|---|---|---|
| … | PASS / FAIL / PARTIAL | file:line or description |

### 6. Output Format

Produce findings in this order:

1. **Phase Summary** — name, goal, files reviewed.
2. **Findings** (sorted: Critical → High → Medium → Low):
   - Severity
   - Dimension (Architecture / Security / Performance / Data / Best Practices /
     Testing / Docs)
   - File(s) and location
   - Why it is a problem
   - What must change (describe, do not write code)
3. **Completion Checklist Audit** (the table from §5).
4. **Open Questions or Assumptions** — items that could not be verified without
   running the system.
5. **Residual Risk** — any risk that remains even if all findings are resolved.

### 7. Save the Report

After completing the report, save it as a Markdown file:

- **Path:** `reviews/review-last-phase-<YYYY-MM-DD>.md` (use today's date).
- The file must contain the full report output (all sections 1–5) exactly as
  specified above.
- **Do NOT modify any application code, test files, migration files,
  configuration files, or any file outside `reviews/`.** The only write
  operation permitted is creating or overwriting the report file.

## Constraints

- Do not write or suggest replacement code. Describe what must change.
- Do not raise findings for untouched pre-existing code outside the reviewed
  phase scope.
- If a dimension has no relevant changes, mark it "N/A — no changes in scope".
- Security and trust-boundary regressions are always Critical, regardless of
  apparent impact.
- The only file you may create or overwrite is the report file in `reviews/`.
  Never edit source code, tests, or configuration files.
