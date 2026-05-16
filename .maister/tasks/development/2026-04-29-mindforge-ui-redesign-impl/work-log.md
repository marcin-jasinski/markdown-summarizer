# Work Log — MindForge UI Redesign Implementation

## 2026-04-29 — Implementation Started

**Total Step Groups**: 12
**Total Steps**: ~134
**Expected Tests**: 51–71
**Phases**: 0 Infrastructure → 1 Component Library → 2 Shell → 3 Cross-cutting → 4 Screens → 5 Material Removal

**Task Groups**:
- Group 1: Build System Setup (Phase 0)
- Group 2: Design System (Tokens + Styles) (Phase 0)
- Group 3: Core Services + Backend Stub (Phase 0)
- Group 4: Base mf-* Components (Phase 1)
- Group 5: Advanced mf-* Components (Phase 1)
- Group 6: Shell Refactor (Phase 2)
- Group 7: MatSnackBar + MatDialog Migration (Phase 3)
- Group 8: Simple Screens (Login + Knowledge-Bases/Dashboard) (Phase 4)
- Group 9: Medium Screens (Documents + Quiz + Flashcards + Search) (Phase 4)
- Group 10: Complex Screens (Chat + Concept Map) (Phase 4)
- Group 11: Angular Material Removal (Phase 5)
- Group 12: Test Review & Gap Analysis (Post-implementation)

## 2026-04-29 — Group 1 Complete: Build System Setup

**Steps**: 1.1 through 1.6 completed (1.4 = N/A — angular.json auto-discovers postcss.config.js)
**Standards Applied**:
- From plan: standards/global/conventions.md (npm@11), standards/frontend/css.md (Tailwind v4 PostCSS pattern)
- Discovered: standards/frontend/angular-patterns.md (Angular 21 `@angular/build:application` esbuild auto-discovers postcss.config.js — no angular.json change needed)
**Tests**: 3 passed (build-system.spec.ts — Tailwind installed, PostCSS config correct, lucide-angular installed)
**Files Created/Modified**:
- `frontend/src/tests/build-system.spec.ts` (created)
- `frontend/postcss.config.js` (created)
- `frontend/package.json` (tailwindcss, @tailwindcss/postcss, @types/node devDeps; lucide-angular dep)
- `frontend/tsconfig.spec.json` (added "node" to types for Node.js built-ins in tests)
**Notes**: Angular 21's `@angular/build:application` builder auto-discovers `postcss.config.js` — adding `postcssConfiguration` to angular.json would cause a schema validation error. This is correct behavior for Angular 21.

---

## 2026-04-29 — Group 2 Complete: Design System (Tokens + Styles)

**Steps**: 2.1 through 2.6 all completed
**Standards Applied**:
- standards/frontend/css.md — design tokens in dedicated file, Tailwind as primary utility layer
- standards/global/conventions.md — LF endings, UTF-8 encoding
- Discovered: SCSS `@use` must precede all `@import` rules in Dart Sass — `@use '@angular/material'` hoisted to line 1
**Tests**: 3 passed (design-system.spec.ts — --mf-primary defined, dark mode --mf-surface-1 override, no Preflight import)
**Files Created/Modified**:
- `frontend/src/tests/design-system.spec.ts` (created)
- `frontend/src/app/core/styles/design-tokens.css` (created — full --mf-* token set + dark overrides)
- `frontend/src/styles.scss` (modified — Tailwind theme/utilities imports, @theme block, Inter font reset, existing Material preserved)
- `frontend/src/index.html` (modified — Inter Google Font link added, Roboto + Material Icons preserved)
**Notes**: Sass @import deprecation warnings for tailwindcss/theme and tailwindcss/utilities are non-blocking (warnings, not errors). Will resolve when Material removal enables migration to native CSS @import (Tailwind v4 native CSS). Tailwind utilities confirmed in dist output.

## 2026-04-29 — Group 3 Complete: Core Services + Backend Stub

**Steps**: 3.1 through 3.10 all completed
**Standards Applied**:
- standards/backend/api.md — RESTful prefix, response_model, tags, no layer boundary violations
- standards/frontend/angular-patterns.md — Signal-based ThemeService, inject(DOCUMENT), APP_INITIALIZER
- Discovered: Vitest globals pattern — vi.fn()/vi.spyOn() available without imports (vitest/globals in tsconfig.spec.json); Jasmine APIs (spyOn, toBeTrue) do NOT exist
**Tests**: 4 Angular + 1 Python = 5 passed (core-services.spec.ts, test_users_stats.py)
**Files Created/Modified**:
- `frontend/src/tests/core-services.spec.ts` (created — 4 Angular tests)
- `tests/unit/api/test_users_stats.py` (created — 1 Python test)
- `frontend/src/app/core/services/theme.service.ts` (created — Signal-based, DOCUMENT injection)
- `frontend/src/app/app.config.ts` (modified — APP_INITIALIZER for ThemeService)
- `frontend/src/app/core/services/mf-snackbar.service.ts` (created — DOM toast, DOCUMENT injection)
- `frontend/src/styles.scss` (modified — .mf-toast* CSS + keyframe)
- `frontend/src/app/core/models/api.models.ts` (modified — UserStatsResponse added)
- `frontend/src/app/core/services/api.service.ts` (modified — getMyStats() added)
- `mindforge/api/schemas.py` (modified — UserStatsResponse Pydantic model)
- `mindforge/api/routers/users.py` (created — stub endpoint)
- `mindforge/api/main.py` (modified — users router registered at /api/v1/users)
**Notes**: APP_INITIALIZER factory returns () => {} no-op; ThemeService constructs eagerly via providedIn: 'root', initializer just ensures pre-render instantiation.

---

## 2026-04-29 — Group 4 Complete: Base mf-* Components

**Steps**: 4.1 through 4.11 all completed
**Standards Applied**:
- standards/frontend/angular-patterns.md — standalone:true, input()/model() signals, ChangeDetectionStrategy.OnPush, @if control flow
- standards/frontend/components.md — single responsibility, minimal props, computed() for derived values
**Tests**: 6 passed (base-components.spec.ts — mf-button 3 tests, mf-card 1 test, mf-input 2 tests)
**Files Created**:
- `frontend/src/tests/base-components.spec.ts`
- `frontend/src/app/core/components/button/button.component.ts + .html + .scss`
- `frontend/src/app/core/components/card/card.component.ts + .scss`
- `frontend/src/app/core/components/input/input.component.ts + .html + .scss`
- `frontend/src/app/core/components/skeleton/skeleton.component.ts + .scss`
**Notes**: Angular templates reject TypeScript `as` casts — use `$any($event.target).value` instead of `($event.target as HTMLInputElement).value`. All components use no Angular Material imports.

---

## 2026-04-29 — Group 5 Complete: Advanced mf-* Components

**Steps**: 5.1 through 5.10 all completed
**Standards Applied**:
- standards/frontend/angular-patterns.md — output() API, @HostListener, CDK Dialog (not Material Dialog)
- Discovered: Dialog tests use provideNoopAnimations() to avoid JSDOM animation timing issues
- Discovered: Angular output() tested via OutputEmitterRef.subscribe() (not vi.spyOn)
**Tests**: 6 passed (advanced-components.spec.ts — mf-chip 2, mf-dialog 2, mf-progress 2)
**Files Created**:
- `frontend/src/tests/advanced-components.spec.ts`
- `frontend/src/app/core/components/chip/chip.component.ts + .scss`
- `frontend/src/app/core/components/dialog/dialog.component.ts + .scss`
- `frontend/src/app/core/components/progress/progress.component.ts + .scss`
**Notes**: provideAnimations() already existed in app.config.ts — no change needed. CDK DialogRef injected via inject(), not constructor. Barrel-free: all imports direct by path.

---
## 2026-04-29 — Group 6 Complete: Shell Refactor

**Steps**: 6.1 through 6.13 all completed
**Standards Applied**:
- standards/frontend/angular-patterns.md — signal inputs/outputs, ChangeDetectionStrategy.OnPush, effect() for side effects, takeUntilDestroyed
- Discovered: LucideAngularModule.pick() returns ModuleWithProviders — NOT valid in standalone imports[]. Must use plain LucideAngularModule + provide LUCIDE_ICONS token with LucideIconProvider in providers[]
**Tests**: 5 passed (shell.spec.ts — SidebarComponent 3 tests, ShellComponent 1 test, ToolbarComponent 1 test)
**Files Created**:
- `frontend/src/tests/shell.spec.ts`
- `frontend/src/app/shell/toolbar/toolbar.component.ts + .html + .scss`
- `frontend/src/app/shell/sidebar/sidebar.component.ts + .html + .scss`
**Files Modified**:
- `frontend/src/app/shell/shell.ts` (removed MatSidenavModule/MatToolbarModule, added new components)
- `frontend/src/app/shell/shell.html` (replaced Mat sidenav with mf-shell layout)
- `frontend/src/app/shell/shell.scss` (replaced Mat* overrides with layout styles)
**Notes**: MatSnackBar NOT removed — deferred to Group 7. userName computed from auth.user()?.display_name. LucideAngularModule + LUCIDE_ICONS provider pattern confirmed for Angular 21 standalone components.

---

## 2026-04-29 — Group 7 Complete: MatSnackBar + MatDialog Migration

**Steps**: 7.1 through 7.8 all completed
**Standards Applied**:
- Discovered: CDK DialogRef.closed (Observable) replaces Material MatDialogRef.afterClosed() — different API
- Discovered: concept-map.ts is in pages/concept-map/ not pages/concepts/
- Discovered: kb-create-dialog.ts is in pages/dashboard/ not a separate subdirectory
**Tests**: 4 passed (snackbar-migration.spec.ts)
**Files Modified** (all MatSnackBar removed from page components):
- login.ts, dashboard.ts, knowledge-bases.ts, flashcards.ts, quiz.ts, chat.ts, documents.ts, concept-map.ts
- kb-create-dialog.ts (full migration MatDialog → CDK Dialog, template → mf-dialog + mf-input)
**Files Created**: `frontend/src/tests/snackbar-migration.spec.ts`
**Notes**: kb-create-dialog converted to signal-based form (mf-input uses model() not ControlValueAccessor). Both callers (dashboard.ts + knowledge-bases.ts) updated to CDK Dialog. MatSnackBar grep confirms 0 remaining in pages/.

---

## 2026-04-29 — Group 8 Complete: Simple Screens (Login + Knowledge-Bases)

**Steps**: 8.1 through 8.7 all completed
**Standards Applied**:
- Signal-based forms: isLogin/email/password/isLoading as signal()
- $any($event.target).value pattern for template event casting
- Discovered: App routes use /kb/:kbId/documents format — NOT /documents/:id
**Tests**: 6 passed (simple-screens.spec.ts — Login 3 tests, KnowledgeBases 3 tests)
**Files Created**: `frontend/src/tests/simple-screens.spec.ts`
**Files Modified**:
- login.ts + login.html + login.scss (full redesign, split-hero layout)
- knowledge-bases.ts + knowledge-bases.html + knowledge-bases.scss (full redesign, card grid)
**Notes**: router injected as public readonly in knowledge-bases.ts for template navigation. display_name in register derived from email prefix. Polish strings all preserved.

---

- [x] standards/global/conventions.md — npm@11 confirmed
- [x] standards/frontend/css.md — Tailwind v4 PostCSS pattern

**From INDEX.md**:
- [x] standards/frontend/angular-patterns.md — Angular 21 builder patterns

**Discovered During Execution**:
- [x] tsconfig.spec.json Node.js types issue — @types/node needed for fs/path/url in tests

---
