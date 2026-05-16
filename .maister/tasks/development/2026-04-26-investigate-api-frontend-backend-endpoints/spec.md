# Specification: Fix Broken API Integration (Frontend ↔ Backend)

## Goal

Three confirmed URL mismatches and one missing backend route are causing silent failures
in the flashcard review, due-count, and lessons flows. Additionally, three missing
frontend services (InteractionsService, AdminService, auth-refresh interceptor) and an
absent Playwright E2E setup must be added to complete the API integration layer.

---

## User Stories

- As a learner, I want flashcard reviews to be recorded so that my spaced-repetition
  schedule advances correctly.
- As a learner, I want to see the due-card count badge so that I know when to study.
- As a learner, I want to browse lessons inside a knowledge base so that I can navigate
  my content.
- As a user, I want my session refreshed automatically on 401 so that I am not
  redirected to the login page mid-session when a valid refresh token exists.
- As a developer, I want Playwright E2E tests so that regressions in critical flows are
  caught automatically.

---

## Core Requirements

1. `FlashcardService.reviewCard()` must include `card_id` as a path segment.
2. `FlashcardService.getDueCount()` must use `/due/count`, not `/due-count`.
3. `GET /api/knowledge-bases/{kb_id}/lessons` must exist and return `list[LessonResponse]`.
4. `InteractionsService` with `list()` method must be created.
5. `AdminService` with `getMetrics()` and `getInteractions()` methods must be created.
6. An auth-refresh HTTP interceptor must silently retry requests after a successful
   `POST /api/auth/refresh`, with loop-protection.
7. Playwright (`@playwright/test`) E2E harness must be configured in `frontend/`.

---

## Reusable Components

### Existing Code to Leverage

| Asset | Path | Usage |
|-------|------|-------|
| `ApiService` | `frontend/src/app/core/services/api.service.ts` | Base HTTP wrapper — all new services delegate to it |
| `authInterceptor` | `frontend/src/app/core/interceptors/auth.interceptor.ts` | Reference for `HttpInterceptorFn` signature and `withCredentials` pattern |
| `FlashcardService` | `frontend/src/app/core/services/flashcard.service.ts` | Lines 26 and 31 — two one-line URL fixes in place |
| `InteractionResponse` | `frontend/src/app/core/models/api.models.ts` | Already declared — import directly |
| `SystemMetricsResponse` | `frontend/src/app/core/models/api.models.ts` | Already declared — import directly |
| `PostgresReadModelRepository.list_lessons()` | `mindforge/infrastructure/persistence/read_models.py` | Returns `list[dict]` keyed `lesson_id, title, flashcard_count, concept_count, processed_at` |
| `LessonResponse` schema | `mindforge/api/schemas.py` (line ~378) | Already declared — import in router |
| `get_kb_repo` dependency | `mindforge/api/deps.py` | Copy pattern to create `get_read_model_repo` |
| Existing router handlers | `mindforge/api/routers/knowledge_bases.py` | Follow handler signature pattern (Annotated deps, UUID path param, 404 guard) |
| `appConfig` providers array | `frontend/src/app/app.config.ts` | Register new interceptor alongside `authInterceptor` |

### New Components Required

| Component | Reason new code is needed |
|-----------|--------------------------|
| `get_read_model_repo` dependency provider in `deps.py` | No provider for `PostgresReadModelRepository` currently exists in `deps.py` |
| `GET /{kb_id}/lessons` route handler in `knowledge_bases.py` | Route is absent; 404 on every frontend call |
| `frontend/src/app/core/services/interactions.service.ts` | File does not exist; `GET /api/interactions` is uncovered |
| `frontend/src/app/core/services/admin.service.ts` | File does not exist; admin endpoints are uncovered |
| `frontend/src/app/core/interceptors/auth-refresh.interceptor.ts` | No refresh logic exists; current interceptor only redirects on 401 |
| `frontend/playwright.config.ts` | Not present; `@playwright/test` not yet in `package.json` |
| `frontend/e2e/*.spec.ts` | E2E test directory and tests do not exist |

---

## Technical Approach

### Bug 1 — FlashcardService.reviewCard() URL (1-line fix)

**File**: `frontend/src/app/core/services/flashcard.service.ts`

Change line 26 from:
```
return this.api.post<void>(`/api/knowledge-bases/${kbId}/flashcards/review`, req);
```
to:
```
return this.api.post<void>(`/api/knowledge-bases/${kbId}/flashcards/${req.card_id}/review`, req);
```

`ReviewRequest.card_id: string` is already present in the argument; no interface changes needed.

### Bug 2 — FlashcardService.getDueCount() URL (1-line fix)

**File**: `frontend/src/app/core/services/flashcard.service.ts`

Change line 31 from:
```
return this.api.get<DueCountResponse>(`/api/knowledge-bases/${kbId}/flashcards/due-count`);
```
to:
```
return this.api.get<DueCountResponse>(`/api/knowledge-bases/${kbId}/flashcards/due/count`);
```

### Bug 3 — Missing GET /lessons backend route

**Step 1 — Add `get_read_model_repo` to `mindforge/api/deps.py`**

Add import at the top:
```python
from mindforge.infrastructure.persistence.read_models import PostgresReadModelRepository
```

Add provider function after `get_kb_repo`:
```python
def get_read_model_repo(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return PostgresReadModelRepository(session)
```

**Step 2 — Add route handler to `mindforge/api/routers/knowledge_bases.py`**

Add import:
```python
from mindforge.api.deps import ..., get_read_model_repo
from mindforge.api.schemas import ..., LessonResponse
from mindforge.infrastructure.persistence.read_models import PostgresReadModelRepository
```

Add handler after `get_knowledge_base`:
```python
@router.get("/{kb_id}/lessons", response_model=list[LessonResponse])
async def list_lessons(
    kb_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    kb_repo: Annotated[PostgresKnowledgeBaseRepository, Depends(get_kb_repo)],
    read_repo: Annotated[PostgresReadModelRepository, Depends(get_read_model_repo)],
) -> list[LessonResponse]:
    # Verify ownership
    kb = await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")
    rows = await read_repo.list_lessons(kb_id)
    return [
        LessonResponse(
            lesson_id=row["lesson_id"],
            title=row["title"],
            document_count=1,           # 1:1 lesson:document enforced by PK
            flashcard_count=row["flashcard_count"],
            concept_count=row["concept_count"],
            last_processed_at=row.get("processed_at"),
        )
        for row in rows
    ]
```

**Route ordering note**: Place this handler BEFORE `@router.get("/{kb_id}")` (the single-KB getter) to avoid FastAPI matching `lessons` as a `kb_id` UUID — though FastAPI will reject a non-UUID string anyway, explicit ordering is cleaner.

### Feature 1 — InteractionsService

**File to create**: `frontend/src/app/core/services/interactions.service.ts`

```typescript
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type { InteractionResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class InteractionsService {
  private readonly api = inject(ApiService);

  list(): Observable<InteractionResponse[]> {
    return this.api.get<InteractionResponse[]>('/api/interactions');
  }
}
```

`withCredentials` is handled globally by `authInterceptor`.

### Feature 2 — AdminService

**File to create**: `frontend/src/app/core/services/admin.service.ts`

```typescript
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type { SystemMetricsResponse, InteractionResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly api = inject(ApiService);

  getMetrics(): Observable<SystemMetricsResponse> {
    return this.api.get<SystemMetricsResponse>('/api/admin/metrics');
  }

  getInteractions(): Observable<InteractionResponse[]> {
    return this.api.get<InteractionResponse[]>('/api/admin/interactions');
  }
}
```

### Feature 3 — Auth Auto-Refresh Interceptor

**File to create**: `frontend/src/app/core/interceptors/auth-refresh.interceptor.ts`

Logic:
1. Pass the request through normally.
2. On `HttpErrorResponse` with `status === 401`:
   - If the failing URL contains `/api/auth/refresh` or `/api/auth/login` → do NOT retry (loop-protection).
   - Otherwise: call `POST /api/auth/refresh` (empty body, `withCredentials` added by `authInterceptor`).
   - On refresh success: retry the original request once via `switchMap`.
   - On refresh failure: propagate the 401 unchanged (let `authInterceptor` redirect to login).

```typescript
import { HttpInterceptorFn, HttpRequest, HttpHandlerFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { catchError, switchMap, throwError } from 'rxjs';

const SKIP_REFRESH_URLS = ['/api/auth/refresh', '/api/auth/login', '/api/auth/register'];

export const authRefreshInterceptor: HttpInterceptorFn = (req, next) => {
  const http = inject(HttpClient);

  return next(req).pipe(
    catchError(error => {
      if (
        error.status !== 401 ||
        SKIP_REFRESH_URLS.some(url => req.url.includes(url))
      ) {
        return throwError(() => error);
      }
      return http.post('/api/auth/refresh', {}, { withCredentials: true }).pipe(
        switchMap(() => next(req)),
        catchError(() => throwError(() => error)),
      );
    }),
  );
};
```

**Registration** — modify `frontend/src/app/app.config.ts`:

```typescript
import { authInterceptor } from './core/interceptors/auth.interceptor';
import { authRefreshInterceptor } from './core/interceptors/auth-refresh.interceptor';

// in providers:
provideHttpClient(withInterceptors([authInterceptor, authRefreshInterceptor]), withFetch()),
```

Interceptor order: `authInterceptor` runs first (attaches `withCredentials`), then
`authRefreshInterceptor` handles 401s on the outbound response. The `authInterceptor`'s
own 401 redirect will only fire when the refresh also fails.

### Feature 4 — Playwright E2E Setup

**Install** (add to `frontend/package.json` `devDependencies`):
```
"@playwright/test": "^1.44.0"
```

**Config file** — `frontend/playwright.config.ts`:
```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:4200',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
```

**Test directory**: `frontend/e2e/` — create the following spec files:

| File | Scenarios |
|------|-----------|
| `e2e/auth.spec.ts` | Login success, login failure (wrong password), register flow |
| `e2e/knowledge-base.spec.ts` | Create KB, list KBs, navigate to KB detail |
| `e2e/flashcards.spec.ts` | View due cards, submit review (verifies correct URL in network log), due count badge |
| `e2e/lessons.spec.ts` | Navigate to lessons tab, verify lesson list renders |

---

## Implementation Guidance

### Testing Approach

Each change group below has 2–8 dedicated tests. Do not run the entire test suite after
each change — run only the tests for the group being worked on.

| Group | Tests to run |
|-------|-------------|
| Bug 1 (reviewCard URL) | `frontend/src/tests/flashcard.service.tdd-red.spec.ts` (must turn green) |
| Bug 2 (getDueCount URL) | Add test in `frontend/src/tests/flashcard.service.tdd-red.spec.ts` for due-count URL |
| Bug 3 (lessons route) | `tests/unit/api/test_lessons_tdd_red.py` (must turn green) + 2 additional unit tests |
| InteractionsService | New `frontend/src/tests/interactions.service.spec.ts` — 2 tests (list success, list error) |
| AdminService | New `frontend/src/tests/admin.service.spec.ts` — 4 tests (getMetrics success/error, getInteractions success/error) |
| Auth refresh interceptor | New `frontend/src/tests/auth-refresh.interceptor.spec.ts` — 5 tests (non-401 pass-through, 401 refresh success retry, 401 on /refresh no-retry, 401 on /login no-retry, refresh failure propagates) |
| Playwright setup | `frontend/e2e/auth.spec.ts` smoke test — 1 passing login test confirms harness works |

### Standards Compliance

- **Angular services**: All services follow `@Injectable({ providedIn: 'root' })` +
  `inject()` pattern (`api.service.ts` is canonical reference).
- **HTTP interceptors**: Functional interceptor (`HttpInterceptorFn`) pattern as in
  `auth.interceptor.ts`; no class-based interceptors.
- **Backend router**: Follow existing handler signatures in `knowledge_bases.py` —
  `Annotated[T, Depends(...)]`, UUID path params, 404 HTTPException for missing resources.
- **Dependency providers**: Follow `get_kb_repo` pattern in `deps.py` for new
  `get_read_model_repo`.
- **Security**: Refresh endpoint call uses `withCredentials: true` (HttpOnly cookie);
  no token stored in JS memory. Loop-protection via URL skip-list.

---

## Out of Scope

- New UI pages or component changes (flashcards.ts, knowledge-base detail component, etc.)
- Changes to domain or application layers (`mindforge/domain/`, `mindforge/application/`)
- Database schema changes or new migrations
- OAuth / SSO changes
- Chat, search, quiz, or concept features
- Backend refresh token implementation (assumed already working; interceptor only calls it)

---

## Success Criteria

| Criterion | Verification |
|-----------|-------------|
| `flashcard.service.tdd-red.spec.ts` passes | `ng test --watch=false` — reviewCard test green |
| `test_lessons_tdd_red.py` passes | `pytest tests/unit/api/test_lessons_tdd_red.py` exits 0 |
| `GET /api/knowledge-bases/{kb_id}/lessons` returns 200 + `[]` for valid KB | Manual curl or integration test |
| Due-count badge shows correct number in UI | E2E flashcards.spec.ts |
| `InteractionsService.list()` calls `GET /api/interactions` | Unit test — HttpTestingController |
| `AdminService.getMetrics()` calls `GET /api/admin/metrics` | Unit test — HttpTestingController |
| `AdminService.getInteractions()` calls `GET /api/admin/interactions` | Unit test — HttpTestingController |
| Auth refresh interceptor retries once on 401 and does not loop | Unit test — 5 interceptor tests |
| Playwright smoke test `e2e/auth.spec.ts` passes against dev server | `npx playwright test` |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Auth interceptor infinite loop | Low | High | URL skip-list for `/api/auth/refresh`, `/login`, `/register`; single-retry by design |
| `list_lessons` route matching conflict (`lessons` vs UUID `{kb_id}`) | Low | Medium | FastAPI rejects non-UUID strings before reaching handler; explicit route ordering as described |
| `document_count=1` hardcoded assumption breaks in future | Low | Low | Documented in code comment; 1:1 lesson:document PK enforces this invariant today |
| `@playwright/test` version conflict with existing devDependencies | Low | Low | Pin to `^1.44.0`; no Angular/Vitest peer dep conflicts expected |
| Refresh token endpoint doesn't exist yet | Medium | High | Verify `/api/auth/refresh` handler exists before enabling interceptor; interceptor degrades gracefully (falls through to redirect) if endpoint absent |
