# Gap Analysis: Investigate API Frontend-Backend Endpoints

## Summary
- **Risk Level**: Medium-High
- **Estimated Effort**: Medium
- **Detected Characteristics**: has_reproducible_defect, modifies_existing_code, creates_new_entities, involves_data_operations

## Task Characteristics
- Has reproducible defect: yes
- Modifies existing code: yes
- Creates new entities: yes
- Involves data operations: yes
- UI heavy: no

---

## Gaps Identified

### Missing Features

- **`GET /api/knowledge-bases/{kb_id}/lessons` backend route**: No route handler exists in `mindforge/api/routers/knowledge_bases.py`. The frontend `KnowledgeBaseService.listLessons()` calls this URL and always receives 404. The read-model infrastructure (`PostgresReadModelRepository.list_lessons()`, `LessonProjectionModel`) is already implemented and ready to serve the query — only the router endpoint is absent.

- **Playwright E2E infrastructure**: `@playwright/test` is not in `frontend/package.json`. No `playwright.config.ts` exists anywhere in the project. The `tests/e2e/` directory contains only an empty `__init__.py`. Zero E2E test coverage exists for any endpoint.

- **`InteractionsService` Angular service**: `GET /api/interactions` backend route exists and works. No corresponding frontend service file exists (`frontend/src/app/core/services/interactions.service.ts` is absent). `InteractionResponse` / `InteractionTurnResponse` TypeScript interfaces exist in `api.models.ts` (line 295+) and are ready to be consumed.

- **`AdminService` Angular service**: Both `GET /api/admin/metrics` and `GET /api/admin/interactions` backend routes exist. No `frontend/src/app/core/services/admin.service.ts` exists. `SystemMetricsResponse` is defined in `schemas.py` (line 332) but its TypeScript counterpart needs verification in `api.models.ts`.

- **Auto-refresh logic in `AuthService`**: `POST /api/auth/refresh` exists in the backend (`routers/auth.py` line 269), uses HttpOnly `refresh_token` cookie. `AuthService` has no `refresh()` method and no auto-refresh strategy — users are silently logged out when the access token expires.

### Incomplete Features

- **`FlashcardService.reviewCard()`**: Currently calls `POST /api/knowledge-bases/${kbId}/flashcards/review` with `{card_id, rating}` in body. Backend expects `POST /api/knowledge-bases/{kb_id}/flashcards/{card_id}/review` — `card_id` must be a **path parameter**, not just a body field. The `ReviewRequest` schema body also contains `card_id` (schemas.py line 204), creating duplication. The fix only requires correcting the frontend URL; the body payload passes through unchanged. One caller exists: `flashcards.ts` line 68 — it already passes `{ card_id: card.card_id, rating }` so extracting `card_id` from the request body for the URL requires no component change.

### Behavioral Changes Needed

- **`AuthService`**: Needs a `refresh()` method and a strategy that calls it automatically (interceptor-based on 401 is standard for Angular). Currently any token expiry silently fails all API calls.

---

## User Journey Impact Assessment

| Dimension | Current | After | Assessment |
|-----------|---------|-------|------------|
| Reachability (flashcard review) | Broken (404) | Fixed | ✅ |
| Reachability (KB lessons) | Broken (404) | Fixed | ✅ |
| Reachability (interactions) | Backend-only | No UI change (service only) | ⚠️ Neutral |
| Reachability (admin) | Backend-only | No UI change (service only) | ⚠️ Neutral |
| Auth resilience | Silent logout on expiry | Auto-refresh retries | ✅ |
| E2E test coverage | 0% | All endpoints covered | ✅ |

No new UI pages are being created. All new Angular services are library-level (`providedIn: 'root'`) and do not affect existing navigation or flows.

---

## Data Lifecycle Analysis

### Entity: Flashcard Review

| Operation | Backend | UI Component | User Access | Status |
|-----------|---------|--------------|-------------|--------|
| UPDATE (review) | ✅ `POST /{card_id}/review` in flashcards.py | ❌ Missing `card_id` path segment in `reviewCard()` URL | ❌ Always 404 | **BROKEN** |

**Completeness**: 33% (backend exists, URL broken, users cannot submit reviews)
**Root Cause**: `reviewCard(kbId, req)` builds URL without the `card_id` path segment; the path segment must be interpolated from `req.card_id`.

### Entity: Knowledge Base Lessons

| Operation | Backend | UI Component | User Access | Status |
|-----------|---------|--------------|-------------|--------|
| READ | ❌ No route in knowledge_bases.py | ✅ `listLessons()` in knowledge-base.service.ts | ❌ 404 | **ORPHANED** |

**Completeness**: 33% (frontend service + projection table exist, route absent)
**Infrastructure ready**: `PostgresReadModelRepository.list_lessons()` already queries `lesson_projections` table.
**Schema gap**: `LessonResponse` has `document_count: int` field; `LessonProjectionModel` stores `document_id` (FK, 1 document per lesson) but no aggregated `document_count` column. Since the PK is `(kb_id, lesson_id)` and each lesson maps to exactly one document, `document_count` is always 1.

### Entity: User Interactions (READ)

| Operation | Backend | UI Component | User Access | Status |
|-----------|---------|--------------|-------------|--------|
| READ | ✅ `GET /api/interactions` with redaction | ❌ No `InteractionsService` | ❌ N/A | **ORPHANED** |

### Entity: Admin Metrics (READ)

| Operation | Backend | UI Component | User Access | Status |
|-----------|---------|--------------|-------------|--------|
| READ | ✅ `GET /api/admin/metrics` | ❌ No `AdminService` | ❌ N/A | **ORPHANED** |

### Entity: Auth Token Refresh

| Operation | Backend | UI Component | User Access | Status |
|-----------|---------|--------------|-------------|--------|
| REFRESH | ✅ `POST /api/auth/refresh` (cookie-based) | ❌ No `refresh()` in `AuthService` | ❌ No auto-refresh | **ORPHANED** |

---

## Defect Analysis

### Bug 1: FlashcardService.reviewCard() URL mismatch

**Reproduction**:
1. Open a knowledge base with due flashcards
2. Flip a card and submit any rating
3. Network tab shows `POST /api/knowledge-bases/{kb_id}/flashcards/review` → **404**
4. Expected: `POST /api/knowledge-bases/{kb_id}/flashcards/{card_id}/review` → **204**

**Root Cause**: `flashcard.service.ts` line 26 — URL template omits `/${req.card_id}` before `/review`. The `ReviewRequest` schema body includes `card_id` (schemas.py:204), so the component passes it; the service just doesn't use it in the path.

**Fix Location**: `frontend/src/app/core/services/flashcard.service.ts` line 26.

**Regression Risk**: Only one caller — `flashcards.ts:68`. Signature does not need to change (no component update required if `card_id` is extracted from the existing `req` parameter).

### Bug 2: Missing GET /api/knowledge-bases/{kb_id}/lessons

**Reproduction**:
1. Call `KnowledgeBaseService.listLessons(kbId)` from any component or test
2. Network tab shows `GET /api/knowledge-bases/{kb_id}/lessons` → **404**
3. Expected: `200 OK` with `LessonResponse[]`

**Root Cause**: `knowledge_bases.py` router has CRUD routes for `/`, `/{kb_id}` but no `/{kb_id}/lessons` sub-route. The route was never added.

**Fix Location**: `mindforge/api/routers/knowledge_bases.py` — add new endpoint using `PostgresReadModelRepository`.

**Regression Risk**: No existing callers in components (only defined in the service). Zero risk of breaking existing flows. New endpoint only.

---

## Issues Requiring Decisions

### Critical (Must Decide Before Proceeding)

1. **`LessonResponse.document_count` schema mismatch**
   - `LessonProjectionModel` does not have a `document_count` column — it has `document_id` (FK to one document per lesson row).
   - `LessonResponse` in both `schemas.py` and `api.models.ts` declares `document_count: int`.
   - Options:
     - **A** — Hardcode `document_count=1` in the new route handler (canonical: 1 document per lesson per KB, enforced by `(kb_id, lesson_id)` PK)
     - **B** — Add a `COUNT(documents)` JOIN to the query in `PostgresReadModelRepository.list_lessons()`
     - **C** — Remove `document_count` from `LessonResponse` schema + TypeScript model
   - **Recommendation**: Option A — hardcode to 1. Canonical model enforces 1:1 (lesson → document). No migration needed, minimal code change, correct semantics.

2. **Playwright test location**
   - `tests/e2e/` is a Python directory (has `__init__.py`). Playwright TypeScript is the natural choice given the Angular + TypeScript stack.
   - Options:
     - **A** — TypeScript tests in `frontend/` using `@playwright/test` (install there, `playwright.config.ts` at `frontend/`)
     - **B** — Python tests in `tests/e2e/` using the Python `playwright` library
     - **C** — Root-level `playwright.config.ts` with tests in `tests/e2e/` as TypeScript (separate from Angular build)
   - **Recommendation**: Option A — TypeScript in `frontend/`. Consistent with the Angular ecosystem, `@playwright/test` is the canonical choice, and test utilities can share TypeScript types from `api.models.ts`.

### Important (Should Decide)

3. **Auto-refresh strategy for `AuthService`**
   - The backend `POST /api/auth/refresh` uses an HttpOnly cookie (`refresh_token`), so the frontend only needs to POST to it — no token to extract.
   - Options:
     - **A** — HTTP interceptor: catch 401 responses, call `POST /api/auth/refresh`, retry the original request (standard Angular pattern)
     - **B** — Proactive timer: schedule a `setInterval` to call refresh N minutes before expiry
     - **C** — App-init call only: call `refresh` once on `APP_INITIALIZER` to get a fresh token at startup
   - **Default**: Option A (interceptor). Handles expiry transparently, works for all scenarios including tab restores after idle periods. Standard Angular pattern per `auth.interceptor.ts` precedent.

4. **`FlashcardService.reviewCard()` signature**
   - The component (`flashcards.ts:68`) passes `{ card_id: card.card_id, rating }` as the second argument. No signature change is needed if `card_id` is extracted from the `req` body for URL interpolation.
   - Options:
     - **A** — Keep current signature `reviewCard(kbId, req)`, extract `req.card_id` for URL path (no component changes needed)
     - **B** — Refactor to `reviewCard(kbId, cardId, req)`, update `flashcards.ts:68` accordingly
   - **Default**: Option A (zero blast radius — no component change required).

---

## Recommendations

1. Fix `flashcard.service.ts` line 26 first — it's a one-line change with zero component impact.
2. Add `/lessons` route to `knowledge_bases.py` using the existing `PostgresReadModelRepository.list_lessons()`, hardcoding `document_count=1`.
3. Create `InteractionsService`, `AdminService`, and `refresh()` in `AuthService` as thin wrappers — no new infrastructure required.
4. Set up Playwright as TypeScript in `frontend/` — install `@playwright/test`, write `playwright.config.ts`, write tests for all 10 service endpoints.
5. Confirm the `document_count` and Playwright location decisions before writing specs.

---

## Risk Assessment

- **Complexity Risk**: Low — all infrastructure layers exist; only wiring and URL fixes needed.
- **Integration Risk**: Low — no DB schema changes, no new tables. `lesson_projections` table and `PostgresReadModelRepository` are already in place.
- **Regression Risk**: Low — bug fixes are local; new services/routes are additive. Only `flashcards.ts:68` is an indirect callsite, and it requires no change under Option A.
- **Playwright Risk**: Medium — infrastructure must be built from scratch; test coverage for 10+ endpoints across auth, quiz, documents, chat, SSE is non-trivial to write correctly.
