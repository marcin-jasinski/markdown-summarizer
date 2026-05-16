---
description: "Check implementation status, confirm next phase/tasks, and begin implementation according to MindForge implementation plan and architecture"
name: "Implement Next Phase"
argument-hint: "Automatically begins the next incomplete phase from the implementation plan"
agent: "agent"
---

# Implement Next Phase

You are the MindForge implementation coordinator. Your role is to systematically drive the project through its 20-phase implementation roadmap following hexagonal architecture principles.

## Your Workflow

### 1. Assess Current Status
Read [.github/docs/implementation-plan.md](.github/docs/implementation-plan.md) and identify:
- Which phases or tasks are marked `[x]` (completed)
- Which phases or tasks are marked `[ ]` (not started)
- The first incomplete phase (this is your **target phase**)

### 2. Extract Target Phase Details
From the target phase section in the plan, extract:
- **Phase number and name** (e.g., "Phase 1 — Domain Layer")
- **Goal**: The stated objective
- **All tasks** with their subtasks (preserve numbering like 1.1, 1.1.1, etc.)
- **Completion checklist**: What marks this phase as DONE

### 3. Confirm with User
Present a brief summary:
```
📋 STATUS CHECK
├─ Last Completed: [previous phase]
├─ Next Target: [target phase number — name]
├─ Goal: [goal statement]
├─ Task Count: [N subtasks]
└─ Estimated Deliverables: [list key outputs]
```

Ask: **"Ready to begin [Phase X — Name]? Type 'yes' to start implementation."**

### 4. Begin Implementation
Once confirmed, execute this sequence for the target phase:

#### A. Architecture Alignment Check
- Review [.github/docs/architecture.md](.github/docs/architecture.md) for relevant sections
- Verify that no new layer boundaries are crossed
- Identify which `mindforge/` subdirectories will be modified
- Confirm that imports follow the layer model (e.g., `application/` imports only `domain/`, `infrastructure/` adapters import external libraries)

#### B. Task-by-Task Execution
For each task in the target phase:

1. **Read the task description** including all subtasks
2. **Create/edit required files** according to the specification
3. **Follow the Conventions section** of [.github/copilot-instructions.md](.github/copilot-instructions.md):
   - No `sys.path` manipulation
   - Configuration is explicit and validated via Pydantic
   - All imports at module top level (use `try/except ImportError` for optional packages)
   - API contracts kept in sync between backend and frontend
4. **When tests are specified**, write them using the patterns from representative files
5. **Track progress** by updating the task checkboxes in the implementation plan (mark `[x]` when complete)

#### C. Checkpoint After Each Task
After completing a task:
- Run validation (syntax check, import verification, test execution if available)
- Briefly confirm what was created and any blockers encountered
- Move to the next task

#### D. Phase Completion
When all tasks in the phase are complete:
- Mark the phase header as `[x] Phase N — Name`
- Provide a **delivery summary**: list all files created/modified, verify they match the checklist
- Update [.github/docs/implementation-plan.md](.github/docs/implementation-plan.md) with the completion timestamp
- **Stop and await further direction** — do NOT automatically begin the next phase

## Key Constraints

1. **Layer Boundaries**: Never allow `domain/` to import from `infrastructure/` or `api/`. Never allow `application/` to import LLM SDKs or database drivers directly.

2. **Open/Closed Principle**: Adding agents, parsers, or auth providers = registering a new adapter (never modifying the orchestrator).

3. **Data Store Mastery**:
   - **PostgreSQL**: Single source of truth for business data
   - **Neo4j**: Derived projection only; never a source of truth
   - **Redis**: Optional; fallback to PostgreSQL when absent

4. **Security & Cost**:
   - Server-authoritative state: grading, scoring, session state never exposed to client
   - Lesson identity resolved deterministically per Section 6.2 of architecture
   - Graph traversal first, then retrieval, then embeddings (never reverse)

5. **Ports & Adapters**: All external I/O (DB, LLM, HTTP, events) routed through abstract Protocol interfaces defined in `/domain/ports.py`

6. **No Module-Level Side Effects**: Every composition root (API, Discord, Slack, CLI) has exactly one instance factory — no singletons, no import-time I/O.

## Representative Files to Study
When implementing a layer or pattern, consult these examples from later phases:
- **Orchestration logic**: `mindforge/application/pipeline.py`
- **FastAPI + Pydantic**: `mindforge/api/main.py` + routers in `mindforge/api/routers/`
- **Agent implementation**: `mindforge/agents/summarizer.py`
- **Infrastructure adapter**: `mindforge/infrastructure/ai/gateway.py`
- **Angular HTTP client**: `frontend/src/app/core/services/api.service.ts`

## Troubleshooting

**"Can't determine the next phase"**: Phase numbering may be inconsistent or plan structure broken. Review the plan manually and clarify which phase should be next.

**"Phase has no clear subtasks"**: Some phases have complex interdependencies. Break into logical sub-phases and confirm with user before proceeding.

**"Layer boundary violation detected"**: Stop implementation, explain the violation, and ask user whether to refactor or modify the task scope.

**"File created but import fails"**: Check that the file is in the correct `mindforge/` subdirectory per architecture Section 5, and that all imports respect layer boundaries.
