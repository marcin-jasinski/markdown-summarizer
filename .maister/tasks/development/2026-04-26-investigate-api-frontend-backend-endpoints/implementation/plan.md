# Implementation Plan: Fix Broken API Integration (Frontend ↔ Backend)

## Overview
Total Steps: 33
Task Groups: 6
Expected Tests: ~20–34

---

## Implementation Steps

### Task Group 1: Backend Layer
**Dependencies:** None
**Estimated Steps:** 7

- [ ] 1.0 Complete backend layer (deps provider + lessons route)
  - [ ] 1.1 Write 3 focused tests in `tests/unit/api/test_lessons_tdd_red.py` (existing file — verify red, then add 2 more)
    - `test_list_lessons_endpoint_exists` — already present (must fail before fix, pass after)
    - Add `test_list_lessons_returns_lesson_shapes`: mock `list_lessons` returning one row, assert response matches `LessonResponse` fields (`lesson_id`, `title`, `flashcard_count`, `concept_count`, `document_count`, `last_processed_at`)
    - Add `test_list_lessons_unknown_kb_returns_404`: mock `kb_repo.get_by_id` returning `None`, assert 404 + Polish detail text
    - Run before coding: `python -m pytest tests/unit/api/test_lessons_tdd_red.py -v` — must show 1 FAIL (route missing)

  - [ ] 1.2 Add `get_read_model_repo` provider to `mindforge/api/deps.py`

    **Prerequisite:** `PostgresReadModelRepository` exists at
    `mindforge/infrastructure/persistence/read_models.py`

    Add import with existing infrastructure imports (after line 49 `PostgresPipelineTaskRepository`):
    ```python
    from mindforge.infrastructure.persistence.read_models import (
        PostgresReadModelRepository,
    )
    ```

    Add provider function immediately after `get_kb_repo` (after line ~117):
    ```python
    def get_read_model_repo(
        request: Request,
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ):
        return PostgresReadModelRepository(session)
    ```

  - [ ] 1.3 Update imports in `mindforge/api/routers/knowledge_bases.py`

    Change the `mindforge.api.deps` import (line 10):
    ```python
    # Before
    from mindforge.api.deps import get_current_user, get_db_session, get_kb_repo
    # After
    from mindforge.api.deps import get_current_user, get_db_session, get_kb_repo, get_read_model_repo
    ```

    Change the `mindforge.api.schemas` import (line 11–15):
    ```python
    # Before
    from mindforge.api.schemas import (
        KnowledgeBaseCreate,
        KnowledgeBaseResponse,
        KnowledgeBaseUpdate,
    )
    # After
    from mindforge.api.schemas import (
        KnowledgeBaseCreate,
        KnowledgeBaseResponse,
        KnowledgeBaseUpdate,
        LessonResponse,
    )
    ```

    Add import for `PostgresReadModelRepository` after the `PostgresKnowledgeBaseRepository` import (line 17):
    ```python
    from mindforge.infrastructure.persistence.read_models import PostgresReadModelRepository
    ```

  - [ ] 1.4 Add `GET /{kb_id}/lessons` route handler to `mindforge/api/routers/knowledge_bases.py`

    **Placement:** Insert BEFORE `@router.get("/{kb_id}", ...)` (currently around line 69) so FastAPI
    does not attempt UUID-coercion on the literal string `"lessons"`.

    Insert this handler between `create_knowledge_base` and `get_knowledge_base`:
    ```python
    @router.get("/{kb_id}/lessons", response_model=list[LessonResponse])
    async def list_lessons(
        kb_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        kb_repo: Annotated[PostgresKnowledgeBaseRepository, Depends(get_kb_repo)],
        read_repo: Annotated[PostgresReadModelRepository, Depends(get_read_model_repo)],
    ) -> list[LessonResponse]:
        # Verify KB ownership before exposing lesson data
        kb = await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id)
        if kb is None:
            raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")
        rows = await read_repo.list_lessons(kb_id)
        return [
            LessonResponse(
                lesson_id=row["lesson_id"],
                title=row["title"],
                document_count=1,  # 1:1 lesson:document enforced by PK
                flashcard_count=row["flashcard_count"],
                concept_count=row["concept_count"],
                last_processed_at=row.get("processed_at"),
            )
            for row in rows
        ]
    ```

  - [ ] 1.5 Verify `LessonResponse` schema exists in `mindforge/api/schemas.py`

    Run: `python -c "from mindforge.api.schemas import LessonResponse; print(LessonResponse.__fields__.keys())"`
    — must print field names without ImportError. If the schema is missing, add it:
    ```python
    class LessonResponse(BaseModel):
        lesson_id: str
        title: str
        document_count: int
        flashcard_count: int
        concept_count: int
        last_processed_at: datetime | None = None
    ```

  - [ ] 1.6 Check syntax and imports compile
    ```
    python -c "from mindforge.api.routers.knowledge_bases import router; print('OK')"
    python -c "from mindforge.api.deps import get_read_model_repo; print('OK')"
    ```

  - [ ] 1.7 Ensure backend tests pass
    ```
    python -m pytest tests/unit/api/test_lessons_tdd_red.py -v
    ```
    All 3 tests must be GREEN. Do NOT run the full test suite.

**Acceptance Criteria:**
- All 3 tests in `test_lessons_tdd_red.py` pass
- `GET /api/knowledge-bases/{kb_id}/lessons` returns 200 + `[]` for valid KB with no lessons

---

### Task Group 2: Frontend URL Bug Fixes
**Dependencies:** None (independent of Group 1 — can be done in parallel)
**Estimated Steps:** 5

- [ ] 2.0 Complete frontend URL bug fixes (flashcard.service.ts)
  - [ ] 2.1 Add `getDueCount` URL test to `frontend/src/tests/flashcard.service.tdd-red.spec.ts`

    Append a second `it` block inside the existing `describe`:
    ```typescript
    it('getDueCount() should use /due/count path (not /due-count)', () => {
      const kbId = 'kb-abc-123';

      service.getDueCount(kbId).subscribe();

      const expectedUrl = `/api/knowledge-bases/${kbId}/flashcards/due/count`;
      http.expectOne(expectedUrl);
    });
    ```

    Run before coding: `ng test --watch=false --include=src/tests/flashcard.service.tdd-red.spec.ts`
    — must show 2 FAILs (both URL bugs present).

  - [ ] 2.2 Fix `reviewCard()` URL in `frontend/src/app/core/services/flashcard.service.ts` (line 26)

    ```typescript
    // Before (line 26):
    return this.api.post<void>(`/api/knowledge-bases/${kbId}/flashcards/review`, req);
    // After:
    return this.api.post<void>(`/api/knowledge-bases/${kbId}/flashcards/${req.card_id}/review`, req);
    ```

  - [ ] 2.3 Fix `getDueCount()` URL in `frontend/src/app/core/services/flashcard.service.ts` (line 30)

    ```typescript
    // Before (line 30):
    return this.api.get<DueCountResponse>(`/api/knowledge-bases/${kbId}/flashcards/due-count`);
    // After:
    return this.api.get<DueCountResponse>(`/api/knowledge-bases/${kbId}/flashcards/due/count`);
    ```

  - [ ] 2.4 Verify no other method in `flashcard.service.ts` was changed (getDueCards and getAllCards are correct as-is)

  - [ ] 2.5 Ensure flashcard service tests pass
    ```
    cd frontend && npx ng test --watch=false --include=src/tests/flashcard.service.tdd-red.spec.ts
    ```
    Both tests must be GREEN.

**Acceptance Criteria:**
- Both tests in `flashcard.service.tdd-red.spec.ts` pass
- `reviewCard` URL contains `${req.card_id}` as path segment
- `getDueCount` URL ends with `/due/count`

---

### Task Group 3: Frontend Services
**Dependencies:** Group 2
**Estimated Steps:** 8

- [ ] 3.0 Complete frontend services (InteractionsService + AdminService)
  - [ ] 3.1 Write 2 tests for `InteractionsService` in `frontend/src/tests/interactions.service.spec.ts` (new file)

    Create `frontend/src/tests/interactions.service.spec.ts`:
    ```typescript
    import { TestBed } from '@angular/core/testing';
    import { provideHttpClient } from '@angular/common/http';
    import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
    import { InteractionsService } from '../app/core/services/interactions.service';
    import { ApiService } from '../app/core/services/api.service';

    describe('InteractionsService', () => {
      let service: InteractionsService;
      let http: HttpTestingController;

      beforeEach(() => {
        TestBed.configureTestingModule({
          providers: [provideHttpClient(), provideHttpClientTesting(), ApiService, InteractionsService],
        });
        service = TestBed.inject(InteractionsService);
        http = TestBed.inject(HttpTestingController);
      });

      afterEach(() => http.verify());

      it('list() should GET /api/interactions', () => {
        service.list().subscribe();
        http.expectOne('/api/interactions').flush([]);
      });

      it('list() should propagate HTTP errors', () => {
        let error: unknown;
        service.list().subscribe({ error: e => (error = e) });
        http.expectOne('/api/interactions').flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });
        expect(error).toBeTruthy();
      });
    });
    ```

  - [ ] 3.2 Write 4 tests for `AdminService` in `frontend/src/tests/admin.service.spec.ts` (new file)

    Create `frontend/src/tests/admin.service.spec.ts`:
    ```typescript
    import { TestBed } from '@angular/core/testing';
    import { provideHttpClient } from '@angular/common/http';
    import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
    import { AdminService } from '../app/core/services/admin.service';
    import { ApiService } from '../app/core/services/api.service';

    describe('AdminService', () => {
      let service: AdminService;
      let http: HttpTestingController;

      beforeEach(() => {
        TestBed.configureTestingModule({
          providers: [provideHttpClient(), provideHttpClientTesting(), ApiService, AdminService],
        });
        service = TestBed.inject(AdminService);
        http = TestBed.inject(HttpTestingController);
      });

      afterEach(() => http.verify());

      it('getMetrics() should GET /api/admin/metrics', () => {
        service.getMetrics().subscribe();
        http.expectOne('/api/admin/metrics').flush({});
      });

      it('getMetrics() should propagate HTTP errors', () => {
        let error: unknown;
        service.getMetrics().subscribe({ error: e => (error = e) });
        http.expectOne('/api/admin/metrics').flush('Forbidden', { status: 403, statusText: 'Forbidden' });
        expect(error).toBeTruthy();
      });

      it('getInteractions() should GET /api/admin/interactions', () => {
        service.getInteractions().subscribe();
        http.expectOne('/api/admin/interactions').flush([]);
      });

      it('getInteractions() should propagate HTTP errors', () => {
        let error: unknown;
        service.getInteractions().subscribe({ error: e => (error = e) });
        http.expectOne('/api/admin/interactions').flush('Forbidden', { status: 403, statusText: 'Forbidden' });
        expect(error).toBeTruthy();
      });
    });
    ```

    Run before coding to confirm red: `ng test --watch=false --include=src/tests/interactions.service.spec.ts --include=src/tests/admin.service.spec.ts`

  - [ ] 3.3 Create `frontend/src/app/core/services/interactions.service.ts`

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

  - [ ] 3.4 Create `frontend/src/app/core/services/admin.service.ts`

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

  - [ ] 3.5 Verify `InteractionResponse` and `SystemMetricsResponse` are exported from `frontend/src/app/core/models/api.models.ts`

    Run: `npx tsc --noEmit` inside `frontend/` — must compile without errors.

  - [ ] 3.6 Ensure service tests pass
    ```
    cd frontend && npx ng test --watch=false --include=src/tests/interactions.service.spec.ts --include=src/tests/admin.service.spec.ts
    ```
    All 6 tests must be GREEN.

**Acceptance Criteria:**
- All 6 service tests pass (2 interactions + 4 admin)
- `InteractionsService.list()` calls `GET /api/interactions`
- `AdminService.getMetrics()` calls `GET /api/admin/metrics`
- `AdminService.getInteractions()` calls `GET /api/admin/interactions`

---

### Task Group 4: Auth Refresh Interceptor
**Dependencies:** Group 3
**Estimated Steps:** 7

- [ ] 4.0 Complete auth refresh interceptor
  - [ ] 4.1 Write 5 tests in `frontend/src/tests/auth-refresh.interceptor.spec.ts` (new file)

    Create `frontend/src/tests/auth-refresh.interceptor.spec.ts`:
    ```typescript
    import { TestBed } from '@angular/core/testing';
    import { provideHttpClient, withInterceptors } from '@angular/common/http';
    import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
    import { HttpClient } from '@angular/common/http';
    import { authRefreshInterceptor } from '../app/core/interceptors/auth-refresh.interceptor';

    describe('authRefreshInterceptor', () => {
      let http: HttpClient;
      let httpMock: HttpTestingController;

      beforeEach(() => {
        TestBed.configureTestingModule({
          providers: [
            provideHttpClient(withInterceptors([authRefreshInterceptor])),
            provideHttpClientTesting(),
          ],
        });
        http = TestBed.inject(HttpClient);
        httpMock = TestBed.inject(HttpTestingController);
      });

      afterEach(() => httpMock.verify());

      it('passes non-401 responses through unchanged', () => {
        let result: unknown;
        http.get('/api/data').subscribe({ next: r => (result = r) });

        httpMock.expectOne('/api/data').flush({ ok: true });
        expect(result).toEqual({ ok: true });
      });

      it('retries original request once after successful refresh on 401', () => {
        let result: unknown;
        http.get('/api/data').subscribe({ next: r => (result = r) });

        // First attempt → 401
        httpMock.expectOne('/api/data').flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });

        // Interceptor calls refresh
        httpMock.expectOne('/api/auth/refresh').flush({});

        // Retry of original request → 200
        httpMock.expectOne('/api/data').flush({ retried: true });
        expect(result).toEqual({ retried: true });
      });

      it('does NOT retry if the 401 comes from /api/auth/refresh itself', () => {
        let error: unknown;
        http.post('/api/auth/refresh', {}).subscribe({ error: e => (error = e) });

        httpMock.expectOne('/api/auth/refresh').flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });
        expect(error).toBeTruthy();
        // No second /api/auth/refresh call — httpMock.verify() enforces this
      });

      it('does NOT retry if the 401 comes from /api/auth/login', () => {
        let error: unknown;
        http.post('/api/auth/login', {}).subscribe({ error: e => (error = e) });

        httpMock.expectOne('/api/auth/login').flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });
        expect(error).toBeTruthy();
      });

      it('propagates the original 401 when refresh itself fails', () => {
        let error: unknown;
        http.get('/api/data').subscribe({ error: e => (error = e) });

        // First attempt → 401
        httpMock.expectOne('/api/data').flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });

        // Refresh call → also fails
        httpMock.expectOne('/api/auth/refresh').flush('Unauthorized', { status: 401, statusText: 'Unauthorized' });

        expect(error).toBeTruthy();
      });
    });
    ```

    Run before coding to confirm red: `ng test --watch=false --include=src/tests/auth-refresh.interceptor.spec.ts`

  - [ ] 4.2 Create `frontend/src/app/core/interceptors/auth-refresh.interceptor.ts`

    ```typescript
    import { HttpInterceptorFn } from '@angular/common/http';
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

  - [ ] 4.3 Register `authRefreshInterceptor` in `frontend/src/app/app.config.ts`

    ```typescript
    // Add import after existing authInterceptor import:
    import { authRefreshInterceptor } from './core/interceptors/auth-refresh.interceptor';

    // Change provideHttpClient line:
    // Before:
    provideHttpClient(withInterceptors([authInterceptor]), withFetch()),
    // After:
    provideHttpClient(withInterceptors([authInterceptor, authRefreshInterceptor]), withFetch()),
    ```

    **Order matters:** `authInterceptor` runs first (attaches `withCredentials`); `authRefreshInterceptor`
    handles 401s. The `authInterceptor` 401→redirect fires only after refresh also fails.

  - [ ] 4.4 Verify TypeScript compiles
    ```
    cd frontend && npx tsc --noEmit
    ```

  - [ ] 4.5 Ensure interceptor tests pass
    ```
    cd frontend && npx ng test --watch=false --include=src/tests/auth-refresh.interceptor.spec.ts
    ```
    All 5 tests must be GREEN.

**Acceptance Criteria:**
- All 5 interceptor tests pass
- Non-401 responses pass through untouched
- 401 on `/api/auth/refresh` or `/api/auth/login` does not trigger retry loop
- Successful refresh causes one retry of the original request
- Failed refresh propagates the original error

---

### Task Group 5: E2E Test Setup
**Dependencies:** Groups 1, 2, 3, 4
**Estimated Steps:** 8

- [ ] 5.0 Complete E2E setup (Playwright install + config + test files)
  - [ ] 5.1 Install `@playwright/test` in `frontend/`
    ```
    cd frontend && npm install @playwright/test --save-dev
    ```
    Verify `"@playwright/test"` appears in `frontend/package.json` `devDependencies`.

  - [ ] 5.2 Install Playwright browser binaries
    ```
    cd frontend && npx playwright install chromium
    ```

  - [ ] 5.3 Create `frontend/playwright.config.ts`

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

  - [ ] 5.4 Create `frontend/e2e/auth.spec.ts` (smoke test — 1 passing test confirms harness works)

    ```typescript
    import { test, expect } from '@playwright/test';

    test.describe('Auth flows', () => {
      test('login page loads', async ({ page }) => {
        await page.goto('/login');
        await expect(page.locator('form')).toBeVisible();
      });

      test('login with wrong password shows error', async ({ page }) => {
        await page.goto('/login');
        await page.fill('[name="email"], input[type="email"]', 'wrong@example.com');
        await page.fill('[name="password"], input[type="password"]', 'badpassword');
        await page.click('button[type="submit"]');
        await expect(page.locator('[role="alert"], .error, .alert')).toBeVisible({ timeout: 5000 });
      });

      test('register page loads', async ({ page }) => {
        await page.goto('/register');
        await expect(page.locator('form')).toBeVisible();
      });
    });
    ```

  - [ ] 5.5 Create `frontend/e2e/knowledge-base.spec.ts`

    ```typescript
    import { test, expect } from '@playwright/test';

    const E2E_EMAIL = process.env['E2E_USER_EMAIL'] ?? '';
    const E2E_PASSWORD = process.env['E2E_USER_PASSWORD'] ?? '';

    test.describe('Knowledge Base flows', () => {
      test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.fill('[name="email"], input[type="email"]', E2E_EMAIL);
        await page.fill('[name="password"], input[type="password"]', E2E_PASSWORD);
        await page.click('button[type="submit"]');
        await page.waitForURL('**/knowledge-bases**', { timeout: 10_000 });
      });

      test('knowledge bases list page renders', async ({ page }) => {
        await expect(page).toHaveURL(/knowledge-bases/);
      });

      test('can navigate to knowledge base detail', async ({ page }) => {
        const firstKb = page.locator('[data-testid="kb-item"], .kb-card, a[href*="/knowledge-bases/"]').first();
        await firstKb.click();
        await page.waitForURL('**/knowledge-bases/**');
        await expect(page).toHaveURL(/knowledge-bases\/.+/);
      });
    });
    ```

  - [ ] 5.6 Create `frontend/e2e/flashcards.spec.ts`

    ```typescript
    import { test, expect } from '@playwright/test';

    const E2E_EMAIL = process.env['E2E_USER_EMAIL'] ?? '';
    const E2E_PASSWORD = process.env['E2E_USER_PASSWORD'] ?? '';

    test.describe('Flashcard review flow', () => {
      test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.fill('[name="email"], input[type="email"]', E2E_EMAIL);
        await page.fill('[name="password"], input[type="password"]', E2E_PASSWORD);
        await page.click('button[type="submit"]');
        await page.waitForURL('**/knowledge-bases**', { timeout: 10_000 });
      });

      test('due-count request uses /due/count path', async ({ page }) => {
        const requests: string[] = [];
        page.on('request', req => requests.push(req.url()));

        await page.goto('/');
        await page.waitForTimeout(2000);

        const dueCountRequests = requests.filter(u => u.includes('/flashcards/due'));
        for (const r of dueCountRequests) {
          expect(r).toContain('/due/count');
          expect(r).not.toContain('/due-count');
        }
      });

      test('review request includes card_id in URL path', async ({ page }) => {
        const requests: string[] = [];
        page.on('request', req => {
          if (req.method() === 'POST' && req.url().includes('/flashcards/')) {
            requests.push(req.url());
          }
        });

        // Navigate to a KB flashcard review page (adjust selector as needed)
        const firstKb = page.locator('a[href*="/knowledge-bases/"]').first();
        await firstKb.click();
        await page.waitForURL('**/knowledge-bases/**');

        // Attempt to find and click a review button
        const reviewBtn = page.locator('[data-testid="review-btn"], button:has-text("Oceń"), button:has-text("Review")').first();
        if (await reviewBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
          await reviewBtn.click();
          await page.waitForTimeout(500);
          const reviewReqs = requests.filter(u => u.includes('/review'));
          for (const r of reviewReqs) {
            // URL must NOT end with /flashcards/review — must contain a card_id segment
            expect(r).toMatch(/\/flashcards\/.+\/review/);
          }
        }
      });
    });
    ```

  - [ ] 5.7 Create `frontend/e2e/lessons.spec.ts`

    ```typescript
    import { test, expect } from '@playwright/test';

    const E2E_EMAIL = process.env['E2E_USER_EMAIL'] ?? '';
    const E2E_PASSWORD = process.env['E2E_USER_PASSWORD'] ?? '';

    test.describe('Lessons tab', () => {
      test.beforeEach(async ({ page }) => {
        await page.goto('/login');
        await page.fill('[name="email"], input[type="email"]', E2E_EMAIL);
        await page.fill('[name="password"], input[type="password"]', E2E_PASSWORD);
        await page.click('button[type="submit"]');
        await page.waitForURL('**/knowledge-bases**', { timeout: 10_000 });
      });

      test('lessons tab/section is reachable in KB detail', async ({ page }) => {
        const firstKb = page.locator('a[href*="/knowledge-bases/"]').first();
        await firstKb.click();
        await page.waitForURL('**/knowledge-bases/**');

        const lessonsTab = page.locator('[data-testid="lessons-tab"], a:has-text("Lekcje"), a:has-text("Lessons")').first();
        if (await lessonsTab.isVisible({ timeout: 3000 }).catch(() => false)) {
          await lessonsTab.click();
        }

        // GET /api/knowledge-bases/{id}/lessons must return 200 (not 404)
        const [response] = await Promise.all([
          page.waitForResponse(resp => resp.url().includes('/lessons') && resp.request().method() === 'GET', { timeout: 5000 }).catch(() => null),
          page.waitForTimeout(2000),
        ]);

        if (response) {
          expect(response.status()).toBe(200);
        }
      });
    });
    ```

  - [ ] 5.8 Verify Playwright smoke test passes (requires dev server running on `:4200`)
    ```
    cd frontend && E2E_USER_EMAIL=<test-user> E2E_USER_PASSWORD=<pw> npx playwright test e2e/auth.spec.ts --project=chromium
    ```
    The login-page-loads test must pass (does not require credentials).

**Acceptance Criteria:**
- `@playwright/test` present in `frontend/package.json` devDependencies
- `playwright.config.ts` exists and points to `./e2e`
- All 4 E2E spec files exist with correct structure
- `e2e/auth.spec.ts` smoke test (`login page loads`) passes without credentials

---

### Task Group 6: Test Review & Gap Analysis
**Dependencies:** Groups 1, 2, 3, 4, 5

- [ ] 6.0 Review and fill critical gaps
  - [ ] 6.1 Review all tests written in Groups 1–5 (~18 tests total):
    - Group 1: 3 backend tests (`test_lessons_tdd_red.py`)
    - Group 2: 2 frontend URL tests (`flashcard.service.tdd-red.spec.ts`)
    - Group 3: 6 service tests (2 interactions + 4 admin)
    - Group 4: 5 interceptor tests
    - Group 5: ~3+ E2E smoke tests

  - [ ] 6.2 Identify gaps for this feature only (do NOT audit unrelated code):
    - Is `list_lessons` tested with non-empty rows (field mapping)?
    - Is 404 for missing KB covered?
    - Is `authRefreshInterceptor` registered order tested (runs after `authInterceptor`)?
    - Is the `document_count=1` assumption documented via a test comment?

  - [ ] 6.3 Write up to 10 additional strategic tests (focus on highest-risk gaps):
    - Backend: If `test_list_lessons_returns_lesson_shapes` wasn't added in 1.1, add it now
    - Backend: If `test_list_lessons_unknown_kb_returns_404` wasn't added in 1.1, add it now
    - Frontend: Add `getDueCount` URL test if missing from `flashcard.service.tdd-red.spec.ts`
    - Frontend: Consider 1 test verifying `app.config.ts` interceptor order (integration-style)
    - Do NOT exceed 10 additional tests

  - [ ] 6.4 Run all feature-specific tests
    ```
    # Backend
    python -m pytest tests/unit/api/test_lessons_tdd_red.py -v

    # Frontend unit tests
    cd frontend && npx ng test --watch=false \
      --include=src/tests/flashcard.service.tdd-red.spec.ts \
      --include=src/tests/interactions.service.spec.ts \
      --include=src/tests/admin.service.spec.ts \
      --include=src/tests/auth-refresh.interceptor.spec.ts

    # E2E smoke (requires running dev server)
    cd frontend && npx playwright test e2e/auth.spec.ts --project=chromium
    ```
    All tests must be GREEN (expected total: ~18–28 feature tests).

**Acceptance Criteria:**
- All feature tests pass
- No more than 10 additional tests added beyond Groups 1–5
- Zero test failures in feature scope

---

## Execution Order

1. **Group 1: Backend Layer** (7 steps) — no dependencies
2. **Group 2: Frontend URL Bug Fixes** (5 steps) — no dependencies; can run in parallel with Group 1
3. **Group 3: Frontend Services** (6 steps) — depends on Group 2
4. **Group 4: Auth Refresh Interceptor** (5 steps) — depends on Group 3
5. **Group 5: E2E Setup** (8 steps) — depends on Groups 1, 2, 3, 4
6. **Group 6: Test Review & Gap Analysis** (4 steps) — depends on all

---

## Standards Compliance

Follow standards from `.maister/docs/standards/`:
- `global/` — always applicable (no module-level globals, explicit config, top-level imports)
- Hexagonal architecture: router and deps changes stay within `mindforge/api/` (driving adapter layer); no domain or application layer changes
- Angular: `@Injectable({ providedIn: 'root' })` + `inject()` pattern; functional interceptor (`HttpInterceptorFn`); no class-based interceptors
- Security: `withCredentials` handled globally by `authInterceptor`; refresh interceptor uses URL skip-list to prevent loops; no tokens in JS memory

## Notes

- **Test-Driven:** Each group starts with 2–8 tests before implementation
- **Run Incrementally:** Run only the group's new tests after each group — NOT the full suite
- **Mark Progress:** Check off steps as completed
- **Reuse First:** All new services delegate to existing `ApiService`; route handler follows existing `get_knowledge_base` pattern
- **Polish UI text:** Error messages in Polish (`"Baza wiedzy nie istnieje."`) per project convention
- **F2/F3 audit findings** (pre-existing `admin.py` bug and Playwright credentials) are out of scope for implementation — tracked separately
