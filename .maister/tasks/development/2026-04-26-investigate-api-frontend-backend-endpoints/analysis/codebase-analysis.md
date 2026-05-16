# Codebase Analysis Report

**Date**: 2026-04-26
**Task**: Investigate the API between frontend and backend, verify all endpoints work properly via Playwright MCP and browser integration.
**Description**: Investigate the API between frontend and backend API, make sure all endpoints work properly. Start the services, frontend, use Playwright MCP and browser integration. All functions must work.
**Analyzer**: codebase-analyzer skill (3 Explore agents: File Discovery, Code Analysis, Context Discovery)

---

## Summary

The MindForge frontend-backend API surface is largely well-structured, with Pydantic schemas and Angular TypeScript models in sync across 12 routers and ~40 schema classes. However, two confirmed broken endpoints were found: a URL mismatch in `FlashcardService.reviewCard()` that will always produce a 404, and a frontend call to `GET /api/knowledge-bases/{kb_id}/lessons` which has no corresponding backend route. Additionally, there is no E2E or Playwright test infrastructure — it must be created from scratch before any browser-based validation can run.

---

## Files Identified

### Primary Files

**mindforge/api/schemas.py** (435 lines)
- Defines all 40+ Pydantic response/request models
- Single source of truth for the API contract; must stay in sync with `api.models.ts`

**mindforge/api/main.py** (344 lines)
- FastAPI app factory; registers all 12 routers, configures middleware, lifespan

**mindforge/api/auth.py** (407 lines)
- Discord OAuth flow, HTTP Basic Auth, JWTService, CSRF protection

**mindforge/api/deps.py** (376 lines)
- FastAPI dependency injection: `get_current_user`, `get_db_session`, all repository providers

**mindforge/api/middleware.py** (264 lines)
- CORS, rate limiter, request-ID propagation, 20 MB request-size guard

**frontend/src/app/core/models/api.models.ts** (230 lines)
- TypeScript interfaces mirroring all Pydantic schemas
- Must remain in sync with `schemas.py`; current sync appears intact for all domains except the missing `LessonResponse` consumer

**frontend/src/app/core/services/api.service.ts** (42 lines)
- Base HTTP client: `get()`, `post()`, `put()`, `patch()`, `delete()`, `uploadFile()`
- All feature services delegate HTTP through this class

### Related Files

**mindforge/api/routers/auth.py** (302 lines) — 8 auth endpoints; login, register, OAuth, refresh, /me, logout
**mindforge/api/routers/quiz.py** (~120 lines) — quiz start + answer-submission flow
**mindforge/api/routers/documents.py** (159 lines) — multipart upload, list, get, reprocess
**mindforge/api/routers/knowledge_bases.py** (~120 lines) — CRUD + the missing `/lessons` sub-route
**mindforge/api/routers/concepts.py** (~80 lines) — concept graph GET
**mindforge/api/routers/flashcards.py** (~100 lines) — due list, due count, **card-level review** (/{card_id}/review)
**mindforge/api/routers/chat.py** (~150 lines) — chat sessions + messages
**mindforge/api/routers/interactions.py** (~60 lines) — redacted user interaction history
**mindforge/api/routers/tasks.py** (~40 lines) — pipeline task status polling
**mindforge/api/routers/events.py** (~50 lines) — SSE stream per knowledge base
**mindforge/api/routers/health.py** (~40 lines) — `/api/health` liveness probe
**mindforge/api/routers/admin.py** (~80 lines) — metrics + unredacted interactions (admin-only)
**mindforge/api/routers/search.py** — full-text + vector search

**frontend/src/app/core/services/auth.service.ts** — /me, register, login, logout
**frontend/src/app/core/services/quiz.service.ts** — quiz start, submit answer
**frontend/src/app/core/services/document.service.ts** — upload, list, reprocess
**frontend/src/app/core/services/knowledge-base.service.ts** — KB CRUD + broken `/lessons` call
**frontend/src/app/core/services/flashcard.service.ts** — due list, count, **broken review URL**
**frontend/src/app/core/services/chat.service.ts** — sessions, messages
**frontend/src/app/core/services/search.service.ts** — POST /search
**frontend/src/app/core/services/concept.service.ts** — GET /concepts
**frontend/src/app/core/services/task.service.ts** — GET /tasks/{id}
**frontend/src/app/core/services/event.service.ts** — EventSource SSE

**frontend/src/app/core/interceptors/auth.interceptor.ts** (21 lines) — attaches JWT to every request
**frontend/src/app/core/guards/auth.guard.ts** (18 lines) — route-level auth enforcement

---

## Current Functionality

The backend exposes a RESTful API under `/api` via FastAPI, served on port 8080. The Angular SPA (port 4200) proxies all `/api/*` requests to the backend via `frontend/proxy.conf.json`. Authentication uses JWT (issued at login/register/OAuth) propagated by the Angular `AuthInterceptor` and validated by `deps.py`.

### Key Components/Functions

- **JWTService** (`api/auth.py`): Issues and validates JWT access tokens
- **get_current_user** (`api/deps.py`): DI dependency — resolves the authenticated user for every protected route
- **ApiService** (`api.service.ts`): Central Angular HTTP wrapper; all feature services call through it
- **AuthInterceptor** (`auth.interceptor.ts`): Attaches Bearer token from local storage to outgoing requests
- **Pipeline task polling**: Upload → returns `task_id` → frontend polls `GET /api/tasks/{task_id}` until done

### Data Flow

1. User authenticates → POST /api/auth/login → JWT stored in browser
2. AuthInterceptor attaches JWT to subsequent requests
3. Feature requests flow: Angular service → ApiService → `/api/{resource}` → FastAPI router → Application layer → DB/AI
4. Document upload creates an async pipeline task; frontend polls task status via `GET /api/tasks/{task_id}`
5. SSE stream (`GET /api/knowledge-bases/{kb_id}/events`) delivers real-time pipeline notifications

---

## Dependencies

### Backend Imports (What the API Depends On)

- **FastAPI / Pydantic**: routing, request validation, response serialization
- **SQLAlchemy (async)**: DB sessions via `get_db_session` in deps.py
- **mindforge.application.***: all business logic; routers import application services, never domain directly
- **mindforge.infrastructure.config**: Pydantic settings — loaded once at startup
- **mindforge.domain.models**: entity types used in schemas

### Frontend Consumers (What Depends On ApiService)

- **auth.service.ts**: authentication flows
- **knowledge-base.service.ts**: KB management + broken `/lessons` call
- **document.service.ts**: document lifecycle
- **quiz.service.ts**: quiz sessions
- **flashcard.service.ts**: spaced-repetition + broken `/review` URL
- **chat.service.ts**: chat sessions
- **search.service.ts**: search
- **concept.service.ts**: concept graph
- **task.service.ts**: task polling
- **event.service.ts**: SSE

**Consumer Count**: 10 services
**Impact Scope**: High — all major product features route through ApiService

---

## Test Coverage

### Existing Test Files

**Backend unit** (`tests/unit/`):
- `agents/`, `application/`, `domain/`, `events/` — logic-level, no I/O

**Backend integration** (`tests/integration/`):
- `api/test_openapi_drift.py` — confirms schema hasn't drifted; minimal
- `graph/`, `persistence/` — infrastructure-level

**Frontend unit** (`frontend/src/tests/`):
- `api.service.spec.ts` — base HTTP client
- `auth.service.spec.ts` — authentication service
- `auth.guard.spec.ts` — route guard

**E2E**: `tests/e2e/` is **empty**. No Playwright config exists.

### Coverage Assessment

- **Test count**: Unit + integration tests exist for most backend domains; frontend has 3 unit specs
- **Gaps**:
  - Zero E2E or browser integration tests
  - No Playwright setup (`playwright.config.ts` absent, package not in `frontend/package.json`)
  - No API integration test that exercises the full HTTP stack against a running server
  - The two broken endpoints (flashcard review URL, /lessons) are not caught by any existing test

---

## Coding Patterns

### Naming Conventions

- **Backend routers**: snake_case file names matching URL prefix (e.g., `knowledge_bases.py` → `/api/knowledge-bases`)
- **Frontend services**: kebab-case file names, PascalCase class names, camelCase methods
- **Schemas**: `{Entity}{Action}Request` / `{Entity}Response` pattern (e.g., `StartQuizRequest`, `QuizQuestionResponse`)
- **Angular models**: interfaces matching Pydantic schema names in `api.models.ts`

### Architecture Patterns

- **Style**: hexagonal — routers are thin adapters; all logic in `application/`
- **Auth**: JWT bearer, CSRF on mutating requests, optional Discord OAuth
- **Async HTTP (Angular)**: `HttpClient` via `ApiService` wrapper, returning `Observable<T>`
- **SSE**: native `EventSource` in Angular `EventService` (not via `ApiService`)
- **File upload**: `FormData` via `ApiService.uploadFile()`

---

## Complexity Assessment

| Factor | Value | Level |
|--------|-------|-------|
| Routers / endpoint groups | 12 | High |
| Total API endpoints | ~40 | High |
| Frontend services | 10 | High |
| Schema classes | 40+ | High |
| Existing E2E tests | 0 | High risk |
| Confirmed broken endpoints | 2 | High risk |

### Overall: Complex

The API surface is large (40+ endpoints across 12 routers, 10 Angular services), and two confirmed runtime failures exist. Standing up Playwright from scratch adds a non-trivial setup phase before any browser validation can begin.

---

## Key Findings

### Strengths
- Pydantic schemas and TypeScript models are largely in sync — no widespread drift detected
- Proxy config correctly routes `/api/*` from Angular dev server to FastAPI
- CORS allows credentials from localhost:4200 — auth flow should work in dev
- JWT-based auth with interceptor is a clean pattern; all protected routes consistently use `get_current_user`
- Middleware stack (CORS → rate limit → request ID → size limit) is coherent

### Confirmed Bugs (will cause runtime 404/failures)

1. **FlashcardService.reviewCard() URL mismatch** (CRITICAL)
   - Frontend calls: `POST /api/knowledge-bases/{kb_id}/flashcards/review`
   - Backend expects: `POST /api/knowledge-bases/{kb_id}/flashcards/{card_id}/review`
   - Effect: every flashcard review operation returns 404; spaced-repetition is completely broken

2. **Missing `/lessons` backend route** (HIGH)
   - Frontend (KnowledgeBaseService) calls: `GET /api/knowledge-bases/{kb_id}/lessons`
   - Backend: no such route registered on the knowledge_bases or documents router
   - Effect: any UI feature listing lessons returns 404

### Additional Gaps

3. **No token auto-refresh** — `POST /api/auth/refresh` exists on the backend but is never called by the frontend; JWT expiry will force full re-login silently
4. **Admin endpoints unexposed in UI** — `/api/admin/metrics` and admin interactions are backend-only; no frontend feature exists
5. **InteractionsService missing** — `/api/interactions` has no Angular service counterpart
6. **No Playwright/E2E infrastructure** — must be bootstrapped before browser-based validation

### Opportunities
- Add `{card_id}` parameter to flashcard review call to fix the URL mismatch
- Add a `/lessons` endpoint (or determine the correct endpoint name) to fix KB lesson listing
- Implement token refresh interceptor to handle JWT expiry gracefully
- Bootstrap Playwright in `frontend/` for ongoing E2E coverage

---

## Impact Assessment

- **Primary changes needed**:
  - `frontend/src/app/core/services/flashcard.service.ts` — fix review URL to include `{card_id}`
  - `mindforge/api/routers/knowledge_bases.py` — add `/lessons` route, or `frontend/knowledge-base.service.ts` to remove/fix the call
- **Related changes**: `frontend/src/app/core/models/api.models.ts` if new `LessonResponse` schema is added
- **Test updates**: Playwright setup in `frontend/`, E2E test files for auth, KB, documents, quiz, flashcards, chat flows

### Risk Level: Medium-High

Two endpoints are confirmed broken and will produce visible user-facing failures. Playwright must be installed and configured before browser testing can proceed. The rest of the API surface appears structurally sound but is unvalidated end-to-end.

---

## Recommendations

### Fix Broken Endpoints First (before browser testing)

1. **Fix flashcard review URL** in `flashcard.service.ts`:
   - Current: `this.api.post(\`/api/knowledge-bases/${kbId}/flashcards/review\`, payload)`
   - Correct: `this.api.post(\`/api/knowledge-bases/${kbId}/flashcards/${cardId}/review\`, payload)`
   - Ensure `cardId` is passed as a parameter to `reviewCard()`

2. **Resolve `/lessons` 404** — two options:
   - Add a backend route `GET /api/knowledge-bases/{kb_id}/lessons` that queries lessons from documents; or
   - Remove/replace the frontend call if the data is available from another endpoint (e.g., `/documents` with a lesson filter)

### Playwright Setup

3. **Install Playwright** in the frontend project:
   - `npm install --save-dev @playwright/test`
   - Create `frontend/playwright.config.ts` targeting `http://localhost:4200`
   - Create `tests/e2e/` test files for: auth flow, KB create/list, document upload, quiz session, flashcard review, chat session

### Token Refresh

4. **Implement JWT refresh** in Angular:
   - Add a 401-interceptor that calls `POST /api/auth/refresh` when a 401 is received, retries the original request, and redirects to login if refresh fails

### Validation Sequence

Once bugs are fixed and Playwright is configured:
1. Start infrastructure: `docker compose up -d postgres neo4j redis minio mc-init`
2. Start API: `mindforge-api` (port 8080)
3. Start frontend: `cd frontend && npm start` (port 4200)
4. Run Playwright tests against `http://localhost:4200`
5. Verify all 40+ endpoints via automated browser flows

---

## Next Steps

The orchestrator should proceed to the **specification phase** to define the exact fixes for the two broken endpoints and the Playwright setup requirements, followed by an **implementation phase** that repairs the bugs and creates the E2E test scaffold, then a **verification phase** using Playwright MCP against the running services.
