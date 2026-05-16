# Documentation Index

**IMPORTANT**: Read this file at the beginning of any development task to understand available documentation and standards.

## Quick Reference

### Project Documentation
Project-level documentation covering vision, goals, architecture, and technology choices. Files will be generated in the project initialization phase.

### Technical Standards
Coding standards, conventions, and best practices organized by domain (global, backend, frontend, testing).

---

## Project Documentation

Located in `.maister/docs/project/`

### Vision (`project/vision.md`)
What MindForge is and why it exists. Covers the core product concept (AI-powered learning platform that transforms uploaded documents into study artifacts), primary user flows, key capabilities (summaries, flashcards, concept maps, quiz engine, knowledge graph), and the guiding design principles. Read this first for product context before feature work.

### Roadmap (`project/roadmap.md`)
Development phase status overview. Documents which phases (0–19) are complete, in-progress, or planned, with brief summaries of what each phase delivers. References the full detail in `project/implementation-plan.md`. Check here to understand where the project stands and what work remains.

### Implementation Plan (`project/implementation-plan.md`)
Complete phase-by-phase breakdown of all development work: phases 0–19, each with detailed task lists, dependencies, completion checklists, and rationale. This is the **source of truth** for structuring development work using `/maister-implement`. Use Maister's implementation-plan-executor to read phases, track checkbox progress, and manage work-logs as you build features.

### Tech Stack (`project/tech-stack.md`)
Technology choices with rationale. Covers backend (Python, FastAPI, PostgreSQL, Neo4j, Redis, LiteLLM), frontend (Angular standalone SPA), infrastructure (Docker, Alembic, Langfuse, MinIO), and the reasoning behind each choice. Read before introducing new dependencies or proposing technology changes.

### Architecture (`project/architecture.md`)
Navigable summary of the hexagonal architecture design — layers, boundaries, composition roots, data flow, and key conventions. The authoritative full-detail reference is `.github/docs/architecture.md`. Read before touching layer boundaries, adding adapters, or working on the pipeline.

---

## Technical Standards

### Global Standards

Located in `.maister/docs/standards/global/`

#### Coding Style (`standards/global/coding-style.md`)
Naming consistency, automatic formatting, descriptive names, focused functions, no dead code, DRY principle.

#### Commenting (`standards/global/commenting.md`)
Let code speak, comment sparingly, no change comments.

#### Conventions (`standards/global/conventions.md`)
Predictable structure, clean version control, environment variables, minimal dependencies, testing standards, feature flags. Also covers: UTF-8 encoding, `npm@11` as the only permitted frontend package manager, LF line endings, and no-trailing-whitespace rules — all enforced via `.editorconfig`.

#### Error Handling (`standards/global/error-handling.md`)
Clear user messages, fail fast, typed exceptions, centralized handling, graceful degradation, retry with backoff, resource cleanup.

#### Minimal Implementation (`standards/global/minimal-implementation.md`)
Build what you need, no future stubs, no speculative abstractions, review before commit, delete exploration artifacts.

#### Validation (`standards/global/validation.md`)
Server-side always, validate early, specific errors, allowlists over blocklists, type and format checks, input sanitization, business rules.

---

### Backend Standards

Located in `.maister/docs/standards/backend/`

#### API Design (`standards/backend/api.md`)
RESTful principles, consistent naming, versioning, plural nouns, limited nesting, query parameters, proper status codes, rate limit headers.

#### Python Conventions (`standards/backend/python-conventions.md`)
MindForge-specific Python conventions: module docstring and `from __future__ import annotations` header, import ordering with `try/except ImportError` guards for optional packages, module-level constants (`_SCREAMING_SNAKE_CASE`), 79-char section dividers, and `log` (not `logger`) naming. Read before writing any new Python module in the `mindforge/` package.

#### Agent Standards (`standards/backend/agents.md`)
Mandatory interface for all AI agents (`__version__`, `PROMPT_VERSION`, `execute()`), `_CAPABILITY` constant placement, version-bump rules (only on logic/prompt changes), model selection by role (`"large"`, `"small"`, `"vision"`) not provider string, and the rule that all LLM calls flow through `AIGateway` — never a provider SDK directly.

#### Models (`standards/backend/models.md`)
Clear naming, timestamps, database constraints, appropriate types, index foreign keys, multi-layer validation, clear relationships, practical normalization.

#### Database Queries (`standards/backend/queries.md`)
Parameterized queries, avoid N+1, select only needed columns, index strategic columns, transactions, query timeouts, cache expensive queries.

#### Database Migrations (`standards/backend/migrations.md`)
Reversible migrations, small and focused, zero-downtime awareness, separate schema and data, careful indexing, descriptive names, version control.

---

### Frontend Standards

Located in `.maister/docs/standards/frontend/`

#### Components (`standards/frontend/components.md`)
Single responsibility, reusability, composability, clear interface, encapsulation, consistent naming, local state, minimal props.

#### Angular Patterns (`standards/frontend/angular-patterns.md`)
Angular 21 patterns for MindForge: standalone components only (no NgModules), `inject()` function for DI (not constructor injection), `signal()` and `computed()` for all component state (no `BehaviorSubject` for local state), `asReadonly()` for service-level shared signals, `HttpClient` via Angular's functional injection in services. Read before creating or modifying any Angular component or service.

#### CSS (`standards/frontend/css.md`)
Consistent methodology, work with the framework, design tokens, minimize custom CSS, production optimization.

#### Accessibility (`standards/frontend/accessibility.md`)
Semantic HTML, keyboard navigation, color contrast (4.5:1), alt text and labels, screen reader testing, ARIA when needed, heading structure, focus management.

#### Responsive Design (`standards/frontend/responsive.md`)
Mobile-first, standard breakpoints, fluid layouts, relative units, cross-device testing, touch-friendly targets (44x44px minimum), content priority.

---

### Architecture Standards

Located in `.maister/docs/standards/architecture/`

#### Hexagonal Architecture (`standards/architecture/hexagonal.md`)
Non-negotiable rules for MindForge's Hexagonal Architecture (Ports and Adapters). Covers layer boundaries and forbidden cross-layer imports, composition root placement, Open/Closed principle for parsers and agents, data store roles (PostgreSQL as source of truth, Neo4j as derived projection, Redis as optional), pipeline idempotency and the transactional checkpoint pattern, retrieval cost discipline (graph first → lexical second → vector last), agent communication rules (no direct agent-to-agent calls), and the transactional outbox guarantee.

---

### Security Standards

Located in `.maister/docs/standards/security/`

#### Web Security (`standards/security/web-security.md`)
MindForge-specific security rules: server-authoritative state (fields forbidden in API responses: `reference_answer`, `grounding_context`, `raw_prompt`, `raw_completion`, `cost`), bcrypt password hashing at cost ≥ 12, JWT in HttpOnly/Secure/SameSite=Lax cookies (never response body), OAuth CSRF via `state` parameter validation, uploaded filename and URL sanitization, and egress policy enforcement. Read before any auth, file upload, or API response work.

---

### Testing Standards

Located in `.maister/docs/standards/testing/`

#### Test Writing (`standards/testing/test-writing.md`)
Test behavior not implementation, clear names, mock external dependencies, fast unit tests, risk-based testing, critical path focus, appropriate depth. Also covers MindForge Python-specific patterns: test folder layout and markers (`unit/`, `integration/`, `e2e/`), no `@pytest.mark.asyncio` needed (`asyncio_mode=auto`), `StubAIGateway` as the LLM test double, `AsyncMock` for async port dependencies, and `_make_*` factory functions for domain objects and services.

---

## How to Use This Documentation

1. **Start Here**: Always read this INDEX.md first to understand what documentation exists
2. **Project Context**: Read relevant project documentation before starting work
3. **Standards**: Reference appropriate standards when writing code
4. **Keep Updated**: Update documentation when making significant changes
5. **Customize**: Adapt all documentation to the project's specific needs

## Updating Documentation

- Project documentation should be updated when goals, tech stack, or architecture changes
- Technical standards should be updated when team conventions evolve
- Always update INDEX.md when adding, removing, or significantly changing documentation
