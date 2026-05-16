# Codebase Analysis Report

**Date**: 2026-04-29
**Task**: MindForge UI Redesign — Angular Material 3 → Angular CDK + Tailwind CSS v4 with custom design tokens
**Description**: Replace Angular Material 3 with Angular CDK + Tailwind CSS v4, add custom `--mf-*` CSS design tokens, replace Roboto with Inter, redesign all 8 screens (Login, Dashboard, Documents, Quiz, Flashcards, Search, Chat, Concept Map), add collapsible sidebar with gamification footer, add dark mode ThemeService, add `GET /api/v1/users/me/stats` backend endpoint.
**Analyzer**: codebase-analyzer skill (3 Explore agents: File Discovery, Code Analysis, Pattern Mining)

---

## Summary

The frontend is a fully standalone Angular 21 application using Angular Material 3 for every component; it must be systematically migrated to Angular CDK + Tailwind CSS v4 with a custom `--mf-*` token layer while preserving all existing signal-based state patterns. The backend requires one new router (`mindforge/api/routers/users.py`) and one new Pydantic schema (`UserStatsResponse`) wired into `main.py`; everything else is a pure frontend change.

---

## Files Identified

### Primary Files — Frontend Core

**`frontend/src/styles.scss`** (≈120 lines)
- Single point of Material 3 theme injection: `@use '@angular/material' as mat` + `@include mat.theme(…)`
- Owns all global utilities (`page-container`, `card-grid`, `status-badge`), scrollbar styles, and the dark color-scheme declaration
- **Full rewrite required**: remove Material theme, add Tailwind v4 `@import "tailwindcss"`, define all `--mf-*` CSS variables, migrate utilities to Tailwind classes

**`frontend/src/index.html`** (16 lines)
- Loads Roboto via Google Fonts and Material Icons via `<link>`
- **Must change**: swap Roboto for Inter font link, remove (or replace) Material Icons link with a suitable icon solution (e.g. keep Material Symbols as web font or bundle SVG icons)

**`frontend/src/app/shell/shell.ts`** (≈90 lines) + **`shell.html`** (≈80 lines) + **`shell.scss`**
- Structural root of the authenticated layout: `mat-sidenav-container`, `mat-sidenav` (256 px), `mat-toolbar`, `mat-nav-list`
- Already uses `BreakpointObserver` from `@angular/cdk/layout` for mobile responsiveness
- Imports: `MatSidenavModule`, `MatToolbarModule`, `MatListModule`, `MatMenuModule`, `MatDividerModule`, `MatIconModule`, `MatButtonModule`, `MatTooltipModule`
- **Full component rewrite**: replace all `mat-*` elements with CDK + Tailwind equivalents, add collapsible behaviour, add gamification footer

**`frontend/src/app/app.routes.ts`** (52 lines)
- No Material imports; uses `loadComponent()` lazy loading with `canActivate: [authGuard]`
- **No change needed** (routing is framework-agnostic)

**`frontend/src/app/app.config.ts`**
- Provides `provideAnimations()`, HTTP client with interceptors, router with `PreloadAllModules`
- **Minor change**: `provideAnimations()` may be dropped or replaced with `provideAnimationsAsync()` once Material is removed; ensure CDK overlay still works

### Primary Files — Page Components (all require Material removal)

| File | Material Modules Used | Complexity |
|------|----------------------|------------|
| `frontend/src/app/pages/login/login.ts` + `.html` + `.scss` | `MatTabsModule`, `MatFormFieldModule`, `MatInputModule`, `MatButtonModule`, `MatIconModule` | Low |
| `frontend/src/app/pages/dashboard/dashboard.ts` + `.html` + `.scss` | `MatCardModule`, `MatButtonModule`, `MatIconModule`, `MatDialogModule`, `MatSnackBar` | Medium |
| `frontend/src/app/pages/dashboard/kb-create-dialog.ts` | `MatDialogModule`, `MatFormFieldModule`, `MatInputModule`, `MatButtonModule`, `MatSelectModule`, `MatSnackBar` | Medium |
| `frontend/src/app/pages/knowledge-bases/knowledge-bases.ts` + `.html` + `.scss` | `MatCardModule`, `MatButtonModule`, `MatIconModule`, `MatChipsModule`, `MatDividerModule` | Low |
| `frontend/src/app/pages/documents/documents.ts` + `.html` + `.scss` | `MatTableModule`, `MatButtonModule`, `MatIconModule`, `MatProgressBarModule`, `MatChipsModule`, `MatTooltipModule` | High |
| `frontend/src/app/pages/quiz/quiz.ts` + `.html` + `.scss` | `MatCardModule`, `MatButtonModule`, `MatIconModule`, `MatProgressBarModule`, `MatSnackBar` | Medium |
| `frontend/src/app/pages/flashcards/flashcards.ts` + `.html` + `.scss` | `MatCardModule`, `MatButtonModule`, `MatIconModule`, `MatProgressBarModule`, `MatSnackBar` | Medium |
| `frontend/src/app/pages/search/search.ts` + `.html` + `.scss` | `MatCardModule`, `MatButtonModule`, `MatIconModule`, `MatFormFieldModule`, `MatInputModule`, `MatChipsModule` | Medium |
| `frontend/src/app/pages/chat/chat.ts` + `.html` + `.scss` | `MatCardModule`, `MatButtonModule`, `MatIconModule`, `MatFormFieldModule`, `MatInputModule`, `MatDividerModule` | Medium |
| `frontend/src/app/pages/concept-map/concept-map.ts` + `.html` + `.scss` | `MatCardModule`, `MatButtonModule`, `MatIconModule`, `MatProgressSpinnerModule`, `MatTooltipModule`, `MatSnackBar`, Cytoscape | High |

### Primary Files — Backend (new)

**`mindforge/api/routers/users.py`** — does not exist yet
- New file: `GET /api/v1/users/me/stats` endpoint
- Needs `get_current_user` dep, DB session, aggregation query

**`mindforge/api/schemas.py`** (≈200+ lines)
- Defines all request/response Pydantic models
- **Add**: `UserStatsResponse` schema (quiz count, flashcard count, documents processed, streak, etc.)
- Currently has `UserResponse` but no stats fields

**`mindforge/api/main.py`**
- Composition root; registers all routers via `app.include_router()`
- **Add**: import and include the new `users` router

### Related Files

**`frontend/src/app/core/services/auth.service.ts`**
- Gold-standard service: private `_state` signal + `asReadonly()` + Observable pipe pattern
- `ThemeService` must follow the same structure exactly
- Will need a `stats()` signal added or a separate `UserStatsService`

**`frontend/src/app/core/models/api.models.ts`**
- TypeScript mirror of `schemas.py`; must stay in sync
- **Add**: `UserStatsResponse` interface

**`frontend/src/app/core/services/api.service.ts`**
- Generic HTTP client wrapping Angular `HttpClient`; all services call through it
- No changes needed unless new stats service is added (which uses it)

**`frontend/angular.json`**
- `styles: ["src/styles.scss"]`, `inlineStyleLanguage: "scss"`
- **Add**: Tailwind PostCSS plugin configuration (or use `@tailwindcss/postcss` in a `postcss.config.js`)

**`frontend/package.json`**
- `@angular/cdk ^21.2.7` already installed; `@angular/material ^21.2.7` installed; Tailwind absent
- **Add**: `tailwindcss`, `@tailwindcss/postcss` (v4 approach)

**`frontend/src/app/pages/concept-map/concept-map.ts`**
- Cytoscape stylesheet uses hardcoded `#7c3aed` (violet) and `#4c1d95` (dark-violet)
- These must be replaced with `--mf-*` CSS variable values read at runtime so dark/light mode works

---

## Current Functionality

### Material 3 Theme Architecture

The entire application is styled through Angular Material 3's CSS custom properties (`--mat-sys-*`). The theme is declared once in `styles.scss`:

```scss
@use '@angular/material' as mat;
html {
  @include mat.theme({
    color: { theme-type: dark, primary: mat.$violet-palette, tertiary: mat.$cyan-palette },
    typography: Roboto,
    density: 0,
  });
}
```

Every component inherits color, typography, and elevation from these generated tokens. Body background is `var(--mat-sys-surface)`, text is `var(--mat-sys-on-surface)`.

### Shell Layout

- `mat-sidenav-container` fills the viewport; `mat-sidenav` is 256 px wide
- Desktop: `mode="side"`, always open; Mobile (CDK Breakpoints.XSmall/Small): `mode="over"`, closes on navigation
- Signals: `isMobile`, `sidenavOpen`, `currentKbId` (extracted from URL via Router events)
- No gamification footer exists currently

### Page-Level Patterns

All pages follow an identical structure:
1. Standalone component, `ChangeDetectionStrategy.OnPush`
2. `inject()` for all dependencies (no constructor params)
3. `signal()` + `computed()` + `asReadonly()` for state
4. `@if`/`@for` control flow (Angular 17+ syntax, not `*ngIf`/`*ngFor`)
5. `takeUntilDestroyed()` for any observable subscriptions
6. `MatSnackBar` injected for notifications (must be replaced with CDK overlay or custom toast)

### Key Specialised Components

- **Flashcards**: CSS `rotateY(180deg)` flip animation with `backface-visibility: hidden`; `currentCard` computed signal tracks progress
- **Concept Map**: Cytoscape.js with `@ViewChild` container, COSE layout, hardcoded violet/dark-violet palette, initialised in `ngAfterViewInit`
- **Documents**: uses `MatTableModule` — highest complexity single-component migration (table, sorting, pagination)
- **Chat**: role-based bubble styling already present in SCSS

### No ThemeService

No `ThemeService` exists. The only theming is the static Material 3 dark theme. Dark/light toggle requires a new service that sets a `data-theme` attribute (or class) on `<html>` and switches the `--mf-*` token values.

---

## Dependencies

### Imports (What This Depends On)

**Frontend**
- `@angular/material`: every page component (14 distinct Mat modules in use across all pages + shell)
- `@angular/cdk/layout`: `BreakpointObserver` — already in use in shell (must keep)
- `@angular/cdk/overlay`, `@angular/cdk/portal`: will be needed to replace `MatDialog` and `MatSnackBar`
- `cytoscape`: Concept Map (version-pinned, no change needed)
- Google Fonts CDN: Roboto (must swap to Inter)

**Backend**
- `mindforge/api/deps.py`: `get_current_user`, `get_db_session`
- `mindforge/infrastructure/persistence/`: user/document/quiz/flashcard models needed for stats aggregation
- `mindforge/domain/models.py`: `User` entity

### Consumers (What Depends On This)

**Material-related**
- `shell.ts`: consumes 8 Material modules — highest coupling in the shell layer
- `kb-create-dialog.ts`: inline template + styles tightly coupled to `mat-dialog-*`, `mat-form-field`
- All 9 page components: import 3–7 Material modules each

**Auth**
- `auth.service.ts` → `GET /api/auth/me` (existing, no change)
- New stats endpoint → `GET /api/v1/users/me/stats` (new dependency for ThemeService or dashboard)

**Consumer Count**: 11 TypeScript files directly import Material modules (shell + 9 pages + dialog)
**Impact Scope**: High — the entire frontend UI layer changes

---

## Test Coverage

### Test Files

- `frontend/src/tests/api.service.spec.ts`: tests generic HTTP layer
- `frontend/src/tests/auth.service.spec.ts`: tests auth state management
- `frontend/src/tests/auth.guard.spec.ts`: tests route guard
- `frontend/src/tests/flashcard.service.tdd-red.spec.ts`: TDD red-phase stub for flashcard service
- `frontend/src/app/app.spec.ts`: smoke test for root component
- `frontend/e2e/`: Playwright e2e specs — `auth.spec.ts`, `flashcards.spec.ts`, `knowledge-bases.spec.ts`, `api-smoke.spec.ts`
- `tests/unit/`, `tests/integration/`: Python backend tests

### Coverage Assessment

- **Component tests**: 0 dedicated unit tests for page components — no coverage to break during migration
- **Service tests**: thin coverage of auth and API services; stats service will need new tests
- **E2e tests**: cover critical flows (auth, flashcards, KB management) — will exercise the redesigned UI and catch regressions
- **Gaps**: No snapshot or visual regression tests; no tests for ThemeService (will need to be written TDD)
- **Test count relevant to migration**: ~5 frontend unit tests + 4 e2e specs

---

## Coding Patterns

### Naming Conventions

- **Components**: `PascalCase` class + `app-` selector prefix (e.g. `AppShellComponent`, `app-shell`)
- **Services**: `camelCase` filename + `Service` suffix; `providedIn: 'root'`
- **Files**: `kebab-case` (e.g. `knowledge-base.service.ts`, `concept-map.ts`)
- **Signals**: private `_name` signal + `readonly name = _name.asReadonly()` for public API
- **CSS classes**: `kebab-case`; BEM-lite (`.sidenav-logo`, `.nav-active`)

### Architecture Patterns

- **Style**: Standalone components only; no NgModules
- **DI**: `inject()` function everywhere — no constructor injection
- **State management**: Angular signals (`signal()`, `computed()`, `effect()`)
- **Subscriptions**: always `takeUntilDestroyed()` — never manual `unsubscribe()`
- **Control flow**: `@if` / `@for` / `@switch` (Angular 17+ built-in)
- **Lazy loading**: all routes use `loadComponent()` — no eager loading
- **Change detection**: `OnPush` on every component

### CSS Conventions

- Global utilities in `styles.scss`; component-specific in `.scss` sidecar
- Currently uses `--mat-sys-*` tokens throughout
- Target: `--mf-surface`, `--mf-on-surface`, `--mf-primary`, `--mf-on-primary`, etc.
- Tailwind v4 utility classes preferred over custom SCSS for layout; custom SCSS only for complex animations (flashcard flip, Cytoscape colours)

---

## Complexity Assessment

| Factor | Value | Level |
|--------|-------|-------|
| File count (primary changes) | 32 files | High |
| Material module usages | 14 distinct modules, 70+ import statements | High |
| Consumers of shell | Every authenticated route (9 routes) | High |
| Existing test coverage | ~5 frontend unit tests, 4 e2e specs | Low |
| Backend new code | 1 router + 1 schema + 1 model + 1 `main.py` line | Low |
| Cytoscape coupling | Hardcoded hex colours, `ngAfterViewInit` init | Medium |
| Dialog system | 1 dialog component tightly coupled to `MatDialog` API | Medium |
| Animation complexity | Flashcard 3D flip (pure CSS, framework-agnostic) | Low |

### Overall: **Complex**

The migration touches every authenticated UI component. The `@angular/material` dependency must be fully removed (or kept as dev-only) to achieve the design goal — partial migration leaves conflicting CSS custom properties. The replacement CDK Dialog/Overlay API is structurally different from `MatDialog`, requiring a CDK-specific dialog wrapper. The absence of component tests means regressions will surface only in e2e tests.

---

## Key Findings

### Strengths

- **CDK already installed** (`^21.2.7`): overlay, portal, layout, a11y modules available immediately
- **Signal-first codebase**: no RxJS state to reason about in components; `OnPush` already enforced everywhere — Tailwind rendering will be efficient
- **No NgModules**: standalone components are fully self-contained; imports list is the complete dependency declaration, making Material module removal surgical
- **`BreakpointObserver` already in shell**: responsive logic doesn't need rewriting, only the template
- **Lazy-loaded routes**: each page component can be migrated and tested independently
- **Robust auth layer**: `AuthService` pattern is the exact template for `ThemeService`

### Concerns

- **`MatSnackBar` used in 7 of 10 components**: requires a CDK overlay replacement (`CdkOverlay` + custom toast component) before any page can drop Material entirely
- **`MatDialog` / `MatDialogRef`**: `KbCreateDialogComponent` uses `MatDialogRef` API directly — must be replaced with `CdkDialog` from `@angular/cdk/dialog`
- **`MatTableModule`** in Documents: most complex Material widget; no direct CDK equivalent; must be built with plain HTML `<table>` + Tailwind
- **Cytoscape hardcoded colours**: won't pick up `--mf-*` tokens automatically; need runtime CSS variable reading (`getComputedStyle`)
- **Zero component tests**: regressions have no fast feedback loop; e2e tests will be the only safety net
- **Material Icons CDN dependency**: removing Material doesn't remove the icon font; icon strategy must be decided (keep web font vs. tree-shakeable SVG library)
- **Tailwind PostCSS configuration**: Angular's esbuild-based builder requires explicit `postcss.config.js`; this must be verified against `angular.json` build options

### Opportunities

- **Custom `--mf-*` tokens** enable dark/light switching without framework overhead (pure CSS `prefers-color-scheme` + JS class toggle)
- **Gamification footer** in the sidebar is a new feature that can be built cleanly with the new shell rewrite — no migration debt
- **`UserStatsResponse`** backend endpoint is low-risk (read-only aggregation) and can be delivered in parallel with frontend work
- **Remove `@angular/material` from `dependencies`** after migration — significant bundle size reduction (Material CSS alone is 50–200 kB compressed)

---

## Impact Assessment

### Files Requiring Changes

**Frontend — Full rewrite**
- `frontend/src/styles.scss` — theme system replacement
- `frontend/src/index.html` — font swap
- `frontend/src/app/shell/shell.ts` + `shell.html` + `shell.scss` — sidebar redesign

**Frontend — Component migration (remove Mat imports, replace templates)**
- `frontend/src/app/pages/login/login.ts` + `.html` + `.scss`
- `frontend/src/app/pages/dashboard/dashboard.ts` + `.html` + `.scss`
- `frontend/src/app/pages/dashboard/kb-create-dialog.ts`
- `frontend/src/app/pages/knowledge-bases/knowledge-bases.ts` + `.html` + `.scss`
- `frontend/src/app/pages/documents/documents.ts` + `.html` + `.scss`
- `frontend/src/app/pages/quiz/quiz.ts` + `.html` + `.scss`
- `frontend/src/app/pages/flashcards/flashcards.ts` + `.html` + `.scss`
- `frontend/src/app/pages/search/search.ts` + `.html` + `.scss`
- `frontend/src/app/pages/chat/chat.ts` + `.html` + `.scss`
- `frontend/src/app/pages/concept-map/concept-map.ts` + `.html` + `.scss`

**Frontend — New files**
- `frontend/src/app/core/services/theme.service.ts` — dark/light ThemeService
- `frontend/postcss.config.js` (or `tailwind.config.js`) — Tailwind v4 build config

**Frontend — Minor additions**
- `frontend/package.json` — add `tailwindcss`, `@tailwindcss/postcss`
- `frontend/src/app/core/models/api.models.ts` — add `UserStatsResponse` interface
- `frontend/src/app/app.config.ts` — verify animation provider after Material removal

**Backend — New**
- `mindforge/api/routers/users.py` — new router with `GET /api/v1/users/me/stats`
- `mindforge/api/schemas.py` — add `UserStatsResponse`
- `mindforge/api/main.py` — include `users` router

**Backend — No changes needed**
- All existing routers, services, domain models, infrastructure layer

### Test Updates

- New `frontend/src/tests/theme.service.spec.ts` (TDD)
- E2e specs in `frontend/e2e/` will implicitly validate redesigned screens
- New `tests/unit/api/test_users_router.py` for stats endpoint
- Potentially new integration test verifying stats aggregation SQL

### Risk Level: **Medium-High**

**Primary risk factors:**
1. **`MatSnackBar` breadth** — 7 components use it; must be replaced atomically or all at once via a shared `ToastService` wrapper
2. **No component tests** — any template regression is invisible until e2e
3. **`MatDialog` API incompatibility** — `CdkDialog` has a different injection token and result-handling pattern
4. **Tailwind v4 + Angular esbuild** — v4 uses a new PostCSS-based setup; Angular's esbuild builder requires specific configuration that must be validated before migrating any component
5. **Bundle size regression** if `@angular/material` is not removed from final bundle

**Mitigating factors:**
- CDK already installed; overlay infrastructure exists
- All components are standalone — no shared NgModule to break
- Backend endpoint is isolated and low-risk

---

## Recommendations

### 1. Establish the Tailwind + Token foundation first (blocking for all else)

Before touching any component, complete:
1. `npm install tailwindcss @tailwindcss/postcss` in `frontend/`
2. Create `frontend/postcss.config.js` (verify with `ng serve` that styles compile)
3. Rewrite `styles.scss`: remove `@use '@angular/material'`, add `@import "tailwindcss"`, declare all `--mf-*` tokens for both dark and light themes
4. Update `index.html` (Inter font, keep Material Icons CDN until icon strategy resolved)
5. Verify no visual regression on the shell (baseline screenshot)

### 2. Build shared CDK primitives before page migration

The following CDK wrappers will be consumed by multiple pages — build them first to unblock sequential page migrations:
- **`ToastService`** (wraps `CdkOverlay`) — replaces `MatSnackBar` across 7 components
- **`MfDialogComponent`** (wraps `CdkDialog`) — replaces `MatDialog` for `KbCreateDialogComponent`
- **`ThemeService`** (`core/services/theme.service.ts`) — dark/light toggle via `data-theme` attribute

### 3. Migrate pages in complexity order (low → high)

Recommended order to minimise risk exposure:
1. Login (no dialog, no table, no snack — lowest coupling)
2. Knowledge Bases
3. Search
4. Quiz
5. Flashcards (preserve flip animation SCSS verbatim)
6. Chat
7. Dashboard + KbCreateDialog (dialog requires CDK dialog wrapper)
8. Documents (MatTable replacement — most complex)
9. Shell (last — redesign once all pages are stable)
10. Concept Map (Cytoscape colour binding to `--mf-*` via `getComputedStyle`)

### 4. Backend endpoint in parallel

The `GET /api/v1/users/me/stats` endpoint is independent of all frontend work. Implement it in parallel:
1. Add `UserStatsResponse` to `schemas.py`
2. Create `mindforge/api/routers/users.py` with the endpoint, reusing `get_current_user` and `get_db_session`
3. Aggregate counts from existing PostgreSQL tables (interactions, document_artifacts, flashcards)
4. Register router in `main.py` under prefix `/api/v1/users`
5. Add `UserStatsResponse` to `api.models.ts`

### 5. Remove `@angular/material` only after all pages migrated

Keep `@angular/material` in `package.json` until all components are migrated. Remove it as a final step and run `ng build --configuration production` to confirm no import errors. This is the bundle-size payoff gate.

---

## Next Steps

The orchestrator should invoke the **gap-analyzer** with this report to identify any missing specifications before implementation begins. Key gaps to probe:
- Exact `--mf-*` token palette values (violet → Tailwind `violet-*` mapping)
- Icon strategy decision (keep Material Icons web font vs. Lucide/Heroicons SVG)
- Gamification footer data model (what stats/XP values are displayed, from which source)
- `UserStatsResponse` field specification (which metrics: quiz count, streak days, documents, flashcard mastery %)
- Dark/light mode persistence strategy (localStorage vs. system preference only)
- Cytoscape theme integration approach (CSS variable polling in `ngAfterViewInit` vs. reactive `effect()`)
