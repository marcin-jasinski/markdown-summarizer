# Requirements

## Initial Description

Implement the MindForge GUI redesign: replace Angular Material 3 with Angular CDK + Tailwind CSS v4, introduce a custom `--mf-*` design token system, swap Roboto for Inter (from Google Fonts CDN), redesign all 9 screens (Login, Dashboard, Documents, Quiz, Flashcards, Search, Chat, Concept Map, Knowledge-Bases), add collapsible sidebar with gamification footer, add dark mode ThemeService, and add `GET /api/v1/users/me/stats` backend endpoint. Replace Material Icons with Lucide icons. Migration approach: screen-by-screen incremental.

---

## Q&A

### Phase 1 Clarifications
- **Migration approach**: Screen-by-screen incremental (not big-bang)
- **Tailwind setup**: `@tailwindcss/postcss` plugin via `postcss.config.js`
- **Icon set**: Lucide icons (`lucide-angular` package), replacing Material Icons
- **Stats endpoint**: Stub (returns `{streak_days: 0, due_today: 0}`), real logic deferred

### Phase 2 Scope Clarifications
- **CSS coexistence**: Disable Tailwind Preflight during incremental migration
- **MatSnackBar + MatDialog**: Cross-cutting Phase 1 migration — all 7+ usages replaced before screen redesigns
- **Knowledge-Bases screen**: Included as screen 9 (complete migration)
- **Stats router**: New `mindforge/api/routers/users.py`
- **Concept map panel**: Slide-in side panel (280–320px, pushes graph)
- **ThemeService init**: `APP_INITIALIZER` in `app.config.ts` (Login page also gets dark mode)

### Phase 5 Requirements Clarifications
- **Flashcard animation**: Preserve 3D flip CSS exactly (`rotateY 0.55s cubic-bezier, backface-visibility`), only restyle card surfaces
- **Polish UI text**: Keep ALL Polish strings unchanged — visual design change only
- **Mobile responsive**: Yes — sidebar becomes hidden off-screen drawer on mobile (`<768px`), Login hero panel collapses, card grids stack to 1 column

---

## Functional Requirements

### FR-1: Foundation — Build & Design System
1. Install Tailwind CSS v4 via `@tailwindcss/postcss` + `postcss.config.js`
2. Install `lucide-angular` package
3. Create `frontend/src/app/core/styles/design-tokens.css` with full `--mf-*` primitive and semantic tokens
4. Create `frontend/postcss.config.js` with Preflight disabled
5. Update `frontend/angular.json` to add `postcss.config.js` to build config
6. Update `frontend/src/index.html`: swap Roboto → Inter (Google Fonts, variable font), remove Material Icons link
7. Update `frontend/src/styles.scss`: import design tokens, import Tailwind, remove `@include mat.theme()`

### FR-2: Core Services & Utilities
8. Create `ThemeService` at `frontend/src/app/core/services/theme.service.ts` — localStorage + OS preference detection, toggles `[data-theme="dark"]` on `<html>`
9. Register `ThemeService` via `APP_INITIALIZER` in `app.config.ts`
10. Create `MfSnackbarService` at `frontend/src/app/core/services/mf-snackbar.service.ts` — replaces all 7 `MatSnackBar` usages
11. Update `frontend/src/app/core/models/api.models.ts`: add `UserStatsResponse` interface

### FR-3: Backend Endpoint
12. Create `mindforge/api/routers/users.py` with `GET /api/v1/users/me/stats` → `UserStatsResponse { streak_days: 0, due_today: 0 }` (stub)
13. Add `UserStatsResponse` Pydantic model to `mindforge/api/schemas.py`
14. Register stats router in `mindforge/api/main.py`

### FR-4: mf-* Component Library (8 components)
15. `mf-button` — 4 variants: primary, secondary, ghost, danger; size sm/md/lg; loading state; icon slot
16. `mf-card` — wrapper with surface-1, radius-xl, shadow variants; optional header/footer slots
17. `mf-input` — text input with leading/trailing icon slots, error state, label, helper text
18. `mf-chip` — 5 variants: default, active, removable, subtle, status; keyboard accessible
19. `mf-skeleton` — pulse animation placeholder; height/width/variant props
20. `mf-dialog` — CDK OverlayContainer-based; replaces MatDialog in `kb-create-dialog.ts`
21. `mf-progress` — horizontal progress bar using `--mf-primary`; value 0-100; `indeterminate` mode
22. All components: `ChangeDetectionStrategy.OnPush`, `inject()` DI, signals, `@if/@for` control flow

### FR-5: Shell Redesign
23. Toolbar: 56px height, `surface-1`, border-bottom, `[☰]` hamburger, breadcrumb title, `[🌙]` theme toggle, `[A▾]` avatar
24. Sidebar: 240px expanded / 64px icon-only mode; collapse/expand toggle; state persisted in `localStorage("mf-sidebar-collapsed")`; gamification footer showing `streak_days` + `due_today` from stats endpoint
25. Mobile: sidebar off-screen at `<768px` (CDK `BreakpointObserver` already used), overlay mode on open
26. Login hero panel collapses on mobile (hero panel `hidden md:block`)

### FR-6: Cross-Cutting Services Migration (before screen redesigns)
27. Migrate all 7 `MatSnackBar` usages to `MfSnackbarService`
28. Migrate `kb-create-dialog.ts` `MatDialog` usage to `mf-dialog`

### FR-7: Screen Redesigns (9 screens — incremental)
29. **Login**: Split hero layout (40/60 columns, hero hides on mobile); `mf-input`, `mf-button`; tabs replaced with `@if (isLogin())` signal toggle
30. **Dashboard (Knowledge Bases Grid)**: `mf-card` grid auto-fill(280px); KB card with indigo `border-t-4` top accent; quick-action icon buttons
31. **Knowledge-Bases**: Same grid layout as Dashboard; "Create KB" → `mf-dialog`
32. **Documents**: `mf-card` rows (replace `mat-table`); `mf-chip` status badges; `mf-progress` bars
33. **Quiz**: `mf-card` centered max-w-680px; score badge in `--mf-correct` color; answer quote block `border-l-4`
34. **Flashcards**: `mf-card` centered max-w-600px; PRESERVE 3D flip animation CSS; SRS rating buttons (Again/Hard/Good/Easy); `mf-progress` counter bar
35. **Search**: `mf-input` full-width search; removable `mf-chip` filters; `mf-card` result rows with score badge
36. **Chat**: bubble layout (user=indigo right, assistant=white left); `mf-input`+`mf-button` input bar; preserve Polish strings
37. **Concept Map**: Light Cytoscape stylesheet (white/indigo-200 nodes, #CBD5E1 edges); slide-in 280–320px node detail panel (`@panelSlide` animation); panel `@if (selectedNode())`; floating toolbar over canvas

### FR-8: Dark Mode
38. `[data-theme="dark"]` on `<html>` governs all `--mf-*` overrides
39. `ThemeService` toggles dark/light, persists preference, reads `prefers-color-scheme` on first load
40. Dark token overrides cover all `--mf-surface-*`, `--mf-text-*`, `--mf-border`, `--mf-primary-subtle`

### FR-9: Angular Material Removal
41. After all 9 screens and cross-cutting migration is done: remove `@angular/material` from `package.json`
42. Ensure `@angular/cdk` remains (overlays, focus-trap, a11y, BreakpointObserver)
43. Remove any remaining `--mat-sys-*` CSS variable references

---

## Reusability Opportunities

- **Existing CDK BreakpointObserver** in `shell.ts`: reuse for mobile sidebar breakpoint
- **Existing Angular animation patterns** in `flashcards.scss`: preserve verbatim
- **Existing signal + `inject()` patterns** from `auth.service.ts`, `kb-create-dialog.ts`: follow for all new services and components
- **Existing `takeUntilDestroyed()`** in services: follow for HTTP subscriptions in ThemeService

---

## Scope Boundaries

**IN SCOPE**:
- Full Angular Material → CDK + Tailwind CSS v4 migration across 9 screens
- New `--mf-*` design token system with dark mode support
- 8 new shared components + mf-snackbar service
- New shell (toolbar + collapsible sidebar with gamification footer)
- ThemeService with OS preference + localStorage
- Lucide icons replacing Material Icons
- Backend stats endpoint stub (`users.py` router)
- Mobile-responsive layout for sidebar and Login hero

**OUT OF SCOPE**:
- Real streak/due-count calculation logic (stub only)
- New features beyond what's in the product design spec
- Changes to Polish UI text strings
- Backend business logic changes (domain/application layer)
- E2E tests (deferred — existing tests must continue to pass)

---

## Visual Assets

- Product design feature spec: `.maister/tasks/product-design/2026-04-29-mindforge-ui-redesign/analysis/feature-spec.md`
- UI mockups (4 screens from product design): `.maister/tasks/product-design/2026-04-29-mindforge-ui-redesign/analysis/ui-mockups.md`
- UI mockups (9 screens, development phase): `analysis/ui-mockups.md`
- Product brief: `.maister/tasks/product-design/2026-04-29-mindforge-ui-redesign/outputs/product-brief.md`

---

## Technical Considerations

- `@angular/cdk` already installed (v21.2.7) — do NOT reinstall
- Tailwind Preflight must be disabled during incremental migration (both Material + Tailwind active simultaneously)
- Flashcard 3D flip: only surfaces restyled — animation CSS preserved verbatim
- `ChangeDetectionStrategy.OnPush` on ALL new components
- `inject()` for DI — no constructor parameter injection
- Signal-first state management (no BehaviorSubject for UI state)
- `APP_INITIALIZER` for ThemeService to ensure Login page dark mode works
- Stats endpoint in `users.py` router, separate from `auth.py`
- No `sys.path` manipulation, no module-level side effects, no `os.environ` at request time
