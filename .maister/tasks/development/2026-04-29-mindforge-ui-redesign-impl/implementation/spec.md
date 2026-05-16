# Specification: MindForge UI Redesign

## Goal

Replace Angular Material 3 with Angular CDK + Tailwind CSS v4 across all 9 application screens, introduce a custom `--mf-*` design token system, add dark mode, add a collapsible sidebar with a gamification footer, replace Material Icons with Lucide, and expose a new `GET /api/v1/users/me/stats` backend stub endpoint.

---

## User Stories

- As a user, I want a modern, clean interface so that I can focus on learning without visual clutter.
- As a user, I want a collapsible sidebar so that I can maximize screen real estate on smaller displays.
- As a user, I want a dark mode that respects my OS preference and persists across sessions.
- As a user, I can see my streak and due-today flashcard count in the sidebar footer at a glance.
- As a developer, I want a reusable `mf-*` component library so that all screens share a consistent look and feel without duplicating styles.

---

## Core Requirements

Requirements are organized by Functional Requirement group (FR-1 through FR-9) as established in `analysis/requirements.md`.

### FR-1: Foundation — Build & Design System

1. Install `tailwindcss`, `@tailwindcss/postcss` as npm dev dependencies in `frontend/`.
2. Install `lucide-angular` as an npm dependency in `frontend/`.
3. Create `frontend/postcss.config.js` that registers `@tailwindcss/postcss` plugin with Tailwind Preflight **disabled** during the incremental migration phase.
4. Update `frontend/angular.json`: add `"postcss.config.js"` to the `postcssConfiguration` field of the `build` architect target, and ensure `styles.scss` is listed in `styles`.
5. Create `frontend/src/app/core/styles/design-tokens.css` with the complete `--mf-*` primitive → semantic → dark-mode override token set (see Design Token Reference below).
6. Update `frontend/src/styles.scss`: add `@import "tailwindcss/theme"` and `@import "tailwindcss/utilities"` at the top (NOT `@import "tailwindcss"` — that includes Preflight/base reset which conflicts with Angular Material on unmigrated screens), import `./app/core/styles/design-tokens.css`, add `@theme { … }` block mapping `--mf-*` tokens to Tailwind theme keys, and add the Inter font-family reset. Keep the existing `@include mat.theme()` until FR-9 (removal phase).
7. Update `frontend/src/index.html`: add `<link rel="preconnect">` for `fonts.googleapis.com` and `fonts.gstatic.com`, add the Inter variable font `<link>`, and remove the Material Icons `<link>` (once all `<mat-icon>` usages are eliminated in FR-7).

### FR-2: Core Services & Utilities

8. Create `frontend/src/app/core/services/theme.service.ts` — `providedIn: 'root'`, reads `localStorage('mf-theme')` and `prefers-color-scheme` on construction, exposes `isDark = signal(false)`, calls `document.documentElement.setAttribute('data-theme', …)` and persists to localStorage. `toggle()` flips the current value.
9. Register ThemeService initialization via `APP_INITIALIZER` in `frontend/src/app/app.config.ts` so dark mode applies on every route including Login before the shell renders.
10. Create `frontend/src/app/core/services/mf-snackbar.service.ts` — `providedIn: 'root'`, creates a fixed-position DOM container on first call, appends toast elements, auto-dismisses after 4000 ms, exposes `show(message: string, type: 'success' | 'error' | 'info')`.
11. Add `UserStatsResponse` interface to `frontend/src/app/core/models/api.models.ts`: `{ streak_days: number; due_today: number }`.
12. Add `getMyStats(): Observable<UserStatsResponse>` method to `frontend/src/app/core/services/api.service.ts` calling `GET /api/v1/users/me/stats`.

### FR-3: Backend Endpoint

13. Create `mindforge/api/routers/users.py` with a single route `GET /me/stats` protected by `get_current_user` dependency, returning `UserStatsResponse(streak_days=0, due_today=0)`.
14. Add `class UserStatsResponse(BaseModel): streak_days: int = 0; due_today: int = 0` to `mindforge/api/schemas.py`.
15. Register the new router in `mindforge/api/main.py` with `prefix="/api/v1/users"` alongside existing routers.

### FR-4: mf-* Component Library

All 8 components live in `frontend/src/app/core/components/`. Every component must use `ChangeDetectionStrategy.OnPush`, `inject()` for DI, Angular signals where stateful, `@if`/`@for` control flow, and `takeUntilDestroyed()` for subscriptions. No Angular Material imports.

16. **`mf-button`** — directive-based on `<button>` element; inputs: `variant: 'primary' | 'secondary' | 'ghost' | 'danger' | 'icon'` (default `'primary'`), `size: 'sm' | 'md' | 'lg'` (default `'md'`), `disabled: boolean`, `loading: boolean`. Renders a spinner overlay when `loading=true`. All variant/size/state classes from design spec applied via host bindings.
17. **`mf-card`** — standalone component with `<ng-content>` for default, header, footer, and actions named slots; inputs: `variant: 'default' | 'elevated' | 'flat'` (default `'default'`), `hoverable: boolean` (default `false`), `padding: 'sm' | 'md' | 'lg'` (default `'md'`). Uses `--mf-surface-1`, `--mf-radius-lg`, `--mf-shadow-md`.
18. **`mf-input`** — standalone component wrapping a labelled `<input>`; inputs: `label: string`, `placeholder: string`, `type: string`, `value = model<string>('')` (two-way), `disabled: boolean`, `error: string`, `helperText: string`. Supports `iconLeft` and `iconRight` content slots via `<ng-content select="[slot=iconLeft]">`.
19. **`mf-chip`** — standalone component; inputs: `variant: 'default' | 'active' | 'removable' | 'subtle' | 'status'`, `size: 'sm' | 'md'`, `color` (for status variant: `'correct' | 'incorrect' | 'pending' | 'processing'`); output: `removed = output<void>()`. Keyboard accessible: Enter/Space toggles active, Delete/Backspace emits removed on removable chips.
20. **`mf-skeleton`** — standalone component; inputs: `height: string | number`, `width: string | number`, `variant: 'rect' | 'circle' | 'text'`. Applies `skeleton-shimmer` CSS animation using `--mf-surface-3` / `--mf-border` gradient. No JS logic needed.
21. **`mf-dialog`** — standalone component opened via Angular CDK `Dialog` service; wraps `MfDialogComponent` with a header (title + close button), scrollable content slot, and actions slot. Inputs: `title: string`, `disableClose: boolean`. Backdrop: `rgba(0,0,0,0.4) blur(4px)`. Enter animation: `scale(0.95) opacity(0)` → `scale(1) opacity(1)` 200 ms.
22. **`mf-progress`** — standalone component; inputs: `value: number` (0–100), `indeterminate: boolean`, `color: 'primary' | 'success' | 'danger'`. 6 px height, `--mf-radius-full` corners. Indeterminate renders a left-to-right sweep CSS animation.
23. **`MfSnackbarService`** — service (not a component); see FR-2 item 10. Replaces all `MatSnackBar` usages. No component creation needed separately.

### FR-5: Shell Redesign

24. Refactor `frontend/src/app/shell/shell.ts` to split into three sub-components: `ToolbarComponent`, `SidebarComponent`, and the existing `ShellComponent` as layout host.
25. **Toolbar** (`frontend/src/app/shell/toolbar/toolbar.component.ts`): 56 px height, `surface-1` background, `border-b border-[--mf-border]`. Left: hamburger/arrow icon toggle (`lucide-angular` `MenuIcon` / `ArrowLeftIcon`) that emits `sidebarToggle`. Center-left: breadcrumb `text-sm font-medium text-[--mf-text-secondary]`. Right: theme toggle button (`SunIcon` / `MoonIcon`) calling `ThemeService.toggle()`, user avatar (32×32 px circle with initials) + dropdown (profile name, logout).
26. **Sidebar** (`frontend/src/app/shell/sidebar/sidebar.component.ts`): 240 px expanded / 64 px collapsed; `surface-3` background; `border-r border-[--mf-border]`; CSS `transition: width var(--mf-transition-normal)`. State in `sidebarCollapsed = signal(…)` initialized from `localStorage('mf-sidebar-collapsed')`. On change, persists value. Nav sections: GLOBAL (Dashboard, Knowledge Bases), KB context block (Quiz, Flashcards, Documents, Concepts), VISUALISE (Search, Chat). Section labels hidden when collapsed. Nav items: 36 px height, `--mf-radius-md` corners, Lucide icon + label. Active item: `bg-[--mf-primary-subtle] text-[--mf-primary]`. Collapsed: icon only, CDK Tooltip shows label on hover.
27. **Gamification footer** inside `SidebarComponent`: fetches `GET /api/v1/users/me/stats` on init via `ApiService.getMyStats()`; displays `🔥 streak_days days` (amber) and `📚 due_today due` (secondary). Shows `—` while loading or on error. Clicking navigates to KB flashcards if `kbId` in route params, otherwise to `/knowledge-bases`. Footer collapses to icon-only when sidebar is collapsed.
28. **Mobile responsive** (< 768 px): sidebar `position: fixed; z-index: 50; transform: translateX(-100%)` when closed; when opened, overlay mode. Use existing `BreakpointObserver` in `shell.ts` (already imported from `@angular/cdk/layout`) — do not add another breakpoint service.
29. **Tablet** (768–1024 px): sidebar collapsed by default (64 px). **Desktop** (> 1024 px): sidebar expanded by default (240 px).

### FR-6: Cross-Cutting Services Migration

30. Replace all **9** `MatSnackBar` usages with `MfSnackbarService` calls across: `login.ts`, `dashboard.ts`, `kb-create-dialog.ts`, `flashcards.ts`, `quiz.ts`, `concept-map.ts`, `chat.ts`, `documents.ts`, and `knowledge-bases.ts`. The last two were identified in the codebase analysis but were mistakenly omitted from initial counts — both must be migrated in this cross-cutting phase.
31. Migrate `kb-create-dialog.ts` from `MatDialog` to `mf-dialog` (CDK `Dialog`-backed), updating the template to use `mf-button` and `mf-input` inside the dialog wrapper.

### FR-7: Screen Redesigns (9 screens)

All screens: remove `mat-*` component selectors, remove `MatXModule` imports, import `mf-*` components, apply Tailwind utilities using `--mf-*` tokens, use Lucide icons. Preserve ALL Polish language strings verbatim.

32. **Login** — Split-hero layout: `<div class="flex min-h-screen">`. Left 50%: `bg-[--mf-primary]` hero panel with MindForge wordmark (Inter 700 white), subtitle, SVG decoration (hidden on mobile via `hidden md:flex`). Right 50%: `surface-1` auth panel, centered `max-w-[400px]`. Auth card: Discord OAuth button (`bg-[#5865F2]`), divider, segmented tab toggle `@if (isLogin())` signal, `mf-input` fields, `mf-button` primary full-width submit with loading state.
33. **Dashboard / Knowledge Bases** (`/knowledge-bases`) — page header with `text-2xl font-bold` + `mf-button` primary "New Knowledge Base". Grid: `grid gap-4 grid-cols-[repeat(auto-fill,minmax(280px,1fr))]`. KB card: `mf-card hoverable` with `border-t-4 border-t-[--mf-primary]`, 40 px icon circle (`bg-[--mf-primary-subtle]`), KB name `font-semibold`, doc count chip, 2-line description clamp, divider, ghost icon buttons (Documents, Quiz, Chat). Loading: 3 `mf-skeleton` cards. Empty state: centered SVG, heading, CTA.
34. **Knowledge-Bases** screen (screen 9) — same grid layout as Dashboard; "Create KB" button opens `mf-dialog` (using migrated `kb-create-dialog`).
35. **Documents** — page header + "Upload Document" `mf-button`. Dashed upload zone (hover: `border-[--mf-primary] bg-[--mf-primary-subtle]`). `<table class="w-full">` with `border-collapse`; header row `bg-[--mf-surface-3] text-xs uppercase tracking-widest`; data rows with `mf-chip` status badges (pending/processing/done/failed), format chip, date, action icon button. Loading: 4 `mf-skeleton` rows. No `mat-table` or `MatTableModule`.
36. **Quiz** — `max-w-[680px] mx-auto py-8 px-4`. Idle state: centered SVG + heading + `mf-button`. Loading state: `mf-skeleton` card `h-40 rounded-xl`. Question state: `mf-card p-6` with lesson label, `text-xl font-medium` question text, `mf-input` textarea `min-h-[120px]`, right-aligned "Submit" `mf-button` (disabled when empty). Evaluated state: score badge (color-coded by score ≥4/3/2/≤1), feedback text, `border-l-4` answer quote block, [Next Question] primary + [Done] ghost buttons.
37. **Flashcards** — `max-w-[600px] mx-auto py-8 px-4`. Progress row: "Card N / total" `text-sm text-secondary` + `mf-progress` bar. Flip card: **preserve existing 3D CSS animation verbatim** (`transform: rotateY(180deg)`, `transition: 0.55s cubic-bezier(.4,0,.2,1)`, `transform-style: preserve-3d`, `backface-visibility: hidden`). Restyle card surfaces only: front = `surface-1 border border-[--mf-border]`, back = `bg-[--mf-primary-subtle] border border-primary/20`. Both: `min-h-[280px] p-8 rounded-[--mf-radius-xl]`. Rating buttons (Again/Hard/Good/Easy) fade in after flip; pill shape, color-coded. End state: 🎉 heading + "Back to Knowledge Bases" ghost button.
38. **Search** — `mf-input` with search icon prefix + "Search" `mf-button`. Filter row of removable `mf-chip` components. Results: `flex flex-col gap-3 mt-6`, each row = `mf-card p-4` with lesson_id chip + match-score chip + snippet with `<strong>` highlights.
39. **Chat** — `flex flex-col h-[calc(100vh-var(--mf-toolbar-height))] max-w-[800px] mx-auto w-full px-4`. User bubble: `align-self: flex-end; bg-[--mf-primary] text-white; border-radius: 18px 18px 4px 18px`. Assistant bubble: `align-self: flex-start; bg-[--mf-surface-3]; border-radius: 18px 18px 18px 4px`. Source chips below assistant messages. Typing indicator: 3 dots staggered scale animation. Sticky input bar: `mf-input` textarea (auto-grow, max 4 rows) + send icon button.
40. **Concept Map** — Replace hardcoded Cytoscape dark stylesheet with `lightStylesheet` (white nodes, `#C7D2FE` borders, `#CBD5E1` edges, Inter font). Canvas background: `var(--mf-surface-2)`. Floating toolbar: `position: absolute; top: 12px; left: 50%; transform: translateX(-50%)` — Zoom in/out/fit/reset `mf-button icon ghost`. Node detail side panel: `@if (selectedNode())`, width 280 px, `position: absolute; right: 0` with `[@panelSlide]` animation (translateX(100%) → 0 on enter, 200 ms ease-out). Canvas `cy-container.panel-open` shrinks to `width: calc(100% - 280px)`. Dark mode: `effect(() => this.cy.style(themeService.isDark() ? darkStylesheet : lightStylesheet))`.

### FR-8: Dark Mode

41. All `--mf-*` overrides inside `[data-theme="dark"]` in `design-tokens.css` take effect via `ThemeService` setting `data-theme` on `<html>`.
42. `html { transition: background-color 200ms ease, color 200ms ease; }` — **not** `transition: all` (causes layout jank).
43. Cytoscape switches stylesheets reactively via `effect()` as described in FR-7 item 40.

### FR-9: Angular Material Removal

44. After all 9 screens, shell, and cross-cutting migration is complete: first remove all remaining `MatXModule` imports, `MatXComponent` selectors, and `@include mat.theme()` from `styles.scss`. Verify the TypeScript build passes cleanly before the next step.
45. Once the build is clean with zero Material imports: run `npm uninstall @angular/material` in `frontend/`. (**Step order is critical**: uninstalling before removing all imports causes immediate build failure.)
46. Remove any `--mat-sys-*` CSS variable references from all stylesheets.
47. Verify `@angular/cdk` v21.2.7 remains in `package.json` (overlays, focus-trap, a11y, BreakpointObserver are all still used).
48. Remove `provideAnimations()` from `app.config.ts` only if no CDK animations use it — CDK animations require `BrowserAnimationsModule`, verify before removing.

---

## Visual Design

Mockups are in `../../product-design/2026-04-29-mindforge-ui-redesign/analysis/ui-mockups.md` (9 screens: Dashboard/KB Grid, Concept Map, Flashcards, Quiz, Login, Documents, Search, Chat, Knowledge-Bases).

Key layout constants:
- Toolbar: 56 px, `surface-1`, `border-b`
- Sidebar: 240 px expanded / 64 px collapsed, `surface-3`, `border-r`
- Page background: `surface-2` (`#F8F9FA`)
- Cards: `mf-card`, `radius-lg`, `shadow-md`
- Max content widths: Quiz 680 px, Flashcards 600 px, Chat 800 px

The mockup fidelity level is **high-fidelity specification** — layouts, spacing, colors, and typography are all fully specified. Pixel-level accuracy is expected for the component library and shell; screen-level layouts may have minor justified deviations.

---

## Design Token Reference

### Full Token Set (to be placed in `design-tokens.css`)

**Primitives** (`:root`): indigo-50 through indigo-900, amber-50/400/500/600, emerald-500, red-500, orange-500, gray-50/100/200/300/400/500/700/900.

**Semantic tokens** (`:root`):

| Token | Light Value |
|-------|------------|
| `--mf-primary` | `#5B4FE9` |
| `--mf-primary-hover` | `#4338CA` |
| `--mf-primary-subtle` | `#EEF2FF` |
| `--mf-accent` | `#F59E0B` |
| `--mf-surface-1` | `#FFFFFF` |
| `--mf-surface-2` | `#F8F9FA` |
| `--mf-surface-3` | `#F0F2F5` |
| `--mf-text-primary` | `#111827` |
| `--mf-text-secondary` | `#6B7280` |
| `--mf-text-tertiary` | `#9CA3AF` |
| `--mf-text-on-primary` | `#FFFFFF` |
| `--mf-border` | `#E5E7EB` |
| `--mf-border-strong` | `#D1D5DB` |
| `--mf-shadow-sm` | `0 1px 2px 0 rgb(0 0 0 / 0.05)` |
| `--mf-shadow-md` | `0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05)` |
| `--mf-shadow-lg` | `0 10px 15px -3px rgb(0 0 0 / 0.07), 0 4px 6px -4px rgb(0 0 0 / 0.05)` |
| `--mf-shadow-card-hover` | `0 20px 25px -5px rgb(0 0 0 / 0.08), 0 8px 10px -6px rgb(0 0 0 / 0.04)` |
| `--mf-correct` | `#10B981` |
| `--mf-incorrect` | `#EF4444` |
| `--mf-warning` | `#F97316` |
| `--mf-streak-color` | `var(--color-amber-500)` |
| `--mf-radius-sm` | `6px` |
| `--mf-radius-md` | `10px` |
| `--mf-radius-lg` | `16px` |
| `--mf-radius-xl` | `20px` |
| `--mf-radius-full` | `9999px` |
| `--mf-sidebar-width` | `240px` |
| `--mf-sidebar-collapsed` | `64px` |
| `--mf-toolbar-height` | `56px` |
| `--mf-transition-fast` | `150ms ease` |
| `--mf-transition-normal` | `250ms ease` |
| `--mf-transition-slow` | `350ms cubic-bezier(0.4, 0, 0.2, 1)` |

> **Canonical source**: The token values below are authoritative and supersede any conflicting values in `feature-spec.md` or elsewhere. Use these exact hex values in `design-tokens.css`.

**Dark mode overrides** (`[data-theme="dark"]`):

| Token | Dark Value |
|-------|-----------|
| `--mf-surface-1` | `#1C1B23` |
| `--mf-surface-2` | `#16151D` |
| `--mf-surface-3` | `#201F29` |
| `--mf-text-primary` | `#F8FAFC` |
| `--mf-text-secondary` | `#94A3B8` |
| `--mf-text-tertiary` | `#475569` |
| `--mf-border` | `rgba(255, 255, 255, 0.08)` |
| `--mf-primary-subtle` | `rgba(91, 79, 233, 0.15)` |
| `--mf-shadow-sm` | `0 1px 2px rgba(0,0,0,0.4)` |
| `--mf-shadow-md` | `0 2px 8px rgba(0,0,0,0.5)` |
| `--mf-shadow-lg` | `0 8px 24px rgba(0,0,0,0.6)` |
| `--mf-shadow-card-hover` | `0 8px 20px rgba(0,0,0,0.6)` |

**Tailwind `@theme` mapping** in `styles.scss`:
Map `--color-primary`, `--color-surface-1/2/3`, `--color-text`, `--color-text-secondary`, `--color-border`, `--color-correct`, `--color-incorrect`, `--shadow-card`, `--radius-sm/md/lg/xl` to their `--mf-*` equivalents.

---

## Reusable Components

### Existing Code to Leverage

| Asset | File | How to Reuse |
|-------|------|--------------|
| `BreakpointObserver` | `frontend/src/app/shell/shell.ts` (already imported) | Reuse exact import and breakpoint constant (`'(max-width: 768px)'`) for mobile sidebar mode |
| Flashcard 3D CSS animation | `frontend/src/app/pages/flashcards/flashcards.scss` | Copy verbatim into new flashcards component stylesheet — do not rewrite |
| `AuthService` | `frontend/src/app/core/services/auth.service.ts` | Reuse `logout()` and user display name in toolbar avatar dropdown |
| `ApiService` | `frontend/src/app/core/services/api.service.ts` | Add `getMyStats()` method; all existing methods remain untouched |
| `api.models.ts` | `frontend/src/app/core/models/api.models.ts` | Add `UserStatsResponse` interface; all existing interfaces remain |
| `get_current_user` dependency | `mindforge/api/deps.py` | Reuse directly in `users.py` router — same pattern as `auth.py` and `quiz.py` |
| CDK `Dialog` | `@angular/cdk/dialog` (already installed) | Use as the overlay engine for `mf-dialog` |
| `BrowserAnimationsModule` / `provideAnimations` | `app.config.ts` | Keep as-is; required for CDK `@panelSlide` Angular animation trigger |

### New Components Required

| Component | Justification |
|-----------|---------------|
| `mf-button` directive | No generic reusable button abstraction exists; all buttons are bare `<button mat-*>` elements |
| `mf-card` | No standalone card component exists; all cards use inline `mat-card` |
| `mf-input` | Form fields use `MatFormField` + `MatInput` — no standalone equivalent |
| `mf-chip` | Existing chips are `mat-chip-set` elements; no standalone component |
| `mf-skeleton` | No loading placeholder components exist anywhere in the codebase |
| `mf-dialog` | `MatDialog` is the only dialog mechanism; CDK Dialog wrapper needed |
| `mf-progress` | `MatProgressBar` is the only progress component; no standalone |
| `ThemeService` | No dark mode infrastructure exists |
| `MfSnackbarService` | `MatSnackBar` injected directly; no custom service |
| `ToolbarComponent` | Toolbar is inline in `shell.html`; needs extraction into own component |
| `SidebarComponent` | Sidebar is inline in `shell.html`; needs extraction to support collapsed state |
| `NodeDetailPanelComponent` | Concept map has no node detail panel — entirely new UI |
| `mindforge/api/routers/users.py` | No user stats endpoint exists |

---

## Technical Approach

### Build System Integration

Tailwind CSS v4 is integrated via PostCSS (`@tailwindcss/postcss`). `postcss.config.js` is referenced from `angular.json` `build.options.postcssConfiguration`. Tailwind Preflight is **disabled** by using `@import "tailwindcss/utilities"` and `@import "tailwindcss/theme"` separately (without the base/preflight layer), or by configuring `content` without base. This allows Angular Material's global styles to remain active on unmigrated screens during the incremental migration. After FR-9 (Material removal), Preflight can be re-enabled.

### Design Token Architecture

Tokens use a three-layer cascade:
1. **Primitives** in `:root` (raw color values)
2. **Semantic tokens** in `:root` (reference primitives via `var()`)
3. **Dark overrides** in `[data-theme="dark"]` (override only semantic tokens)

Tailwind `@theme` block bridges the custom property system to Tailwind's utility class generation, allowing classes like `bg-primary`, `text-text-secondary`, `shadow-card` in templates.

### Component Library Architecture

All `mf-*` components are standalone Angular 17+ components with no barrel files required — each component exports itself. Components are placed in `frontend/src/app/core/components/<name>/`. No shared `index.ts` file is needed; import paths are direct.

### CSS Coexistence Strategy

During the incremental migration:
- Angular Material injects styles globally via `@include mat.theme()` in `styles.scss`
- Tailwind utilities are added alongside Material styles
- Tailwind Preflight is disabled to prevent conflicts on unmigrated screens
- `mf-*` component classes coexist with `mat-*` classes on the same page during transition

This means partially-migrated screens may have slightly mixed visual states — this is acceptable and expected.

### Shell Architecture

`ShellComponent` remains the route outlet host. It injects `ToolbarComponent` and `SidebarComponent` into its template. The shell owns `sidebarCollapsed` signal and passes it as input to both child components. The sidebar emits `toggle` event which the shell handles.

### Stats Data Flow

`SidebarComponent` → `ApiService.getMyStats()` → `GET /api/v1/users/me/stats` → Python stub returning `{streak_days: 0, due_today: 0}`. The call happens once on sidebar init; no polling. Failed requests silently show `—` values (no error toast, no spinner).

### Concept Map Panel

`ConceptMapComponent` owns `selectedNode = signal<CyNode | null>(null)`. When a Cytoscape `tap` event fires on a node, the signal is set. `@if (selectedNode())` in the template shows the panel. The panel slides in using an Angular `@panelSlide` animation trigger (`translateX(100%) → 0` in 200 ms). The canvas container switches to `width: calc(100% - 280px)` via the `panel-open` CSS class. `cy.resize()` is called after 210 ms to let Cytoscape recalculate the canvas viewport.

---

## Migration Order and Phasing

Phasing follows the gap analysis recommendation: infrastructure and cross-cutting concerns first, then screen-by-screen, then cleanup.

### Phase 0: Infrastructure (FR-1, FR-2, FR-3)
No screen redesign yet. Establishes the foundation.
1. Install npm packages (`tailwindcss`, `@tailwindcss/postcss`, `lucide-angular`)
2. Create `postcss.config.js` (Preflight disabled)
3. Update `angular.json` with PostCSS config path
4. Create `design-tokens.css`
5. Update `styles.scss` (add Tailwind imports + `@theme` block + Inter reset)
6. Update `index.html` (add Inter font links)
7. Create `ThemeService` + register `APP_INITIALIZER` in `app.config.ts`
8. Create `MfSnackbarService`
9. Add `UserStatsResponse` to `api.models.ts` + `getMyStats()` to `ApiService`
10. Create `mindforge/api/routers/users.py` + `UserStatsResponse` in `schemas.py` + register in `main.py`

### Phase 1: Component Library (FR-4)
Build all 8 `mf-*` components. No screen changes yet.
- `mf-button`, `mf-card`, `mf-input`, `mf-chip`, `mf-skeleton`, `mf-dialog`, `mf-progress` (components)
- `MfSnackbarService` (already done in Phase 0)

### Phase 2: Shell Redesign (FR-5)
- Extract `ToolbarComponent` from shell template
- Extract `SidebarComponent` from shell template
- Implement 240px / 64px collapse logic with localStorage persistence
- Add gamification footer to sidebar
- Implement mobile drawer behavior using existing `BreakpointObserver`

### Phase 3: Cross-Cutting Migration (FR-6)
- Migrate all 7 `MatSnackBar` → `MfSnackbarService`
- Migrate `kb-create-dialog.ts` `MatDialog` → `mf-dialog`

### Phase 4: Screen Redesigns (FR-7, FR-8) — in this order
1. Login (low risk — isolated route, no shared state)
2. Dashboard / Knowledge Bases grid
3. Knowledge-Bases (reuses Dashboard KB card pattern)
4. Documents
5. Quiz
6. Flashcards (highest care: preserve 3D animation)
7. Search
8. Chat
9. Concept Map (highest complexity: Cytoscape + new panel)

Dark mode (FR-8) is tested with each screen as it is redesigned — `ThemeService` is already wired from Phase 0.

### Phase 5: Material Removal (FR-9)
- `npm uninstall @angular/material`
- Remove all `MatXModule` imports across all files
- Re-enable Tailwind Preflight in `postcss.config.js`
- Remove `@include mat.theme()` from `styles.scss`
- Remove `--mat-sys-*` references
- Remove Material Icons `<link>` from `index.html` (if not already done in FR-1)

---

## Implementation Guidance

### Testing Approach

Each phase or screen group should have 2–8 focused tests. Do not run the full test suite for each incremental change — run only tests for the affected code.

Recommended test groupings:
1. **Phase 0 (Infrastructure)**: 2–4 tests — `ThemeService` reads OS pref, persists toggle, applies `data-theme` attribute; `UserStatsResponse` model shape
2. **Phase 1 (Component Library)**: 4–8 tests per component — variant classes applied, disabled state, loading state, keyboard events for `mf-chip`, error state for `mf-input`
3. **Phase 2 (Shell)**: 3–5 tests — sidebar collapses/expands, state persisted to localStorage, mobile breakpoint triggers drawer mode
4. **Phase 3 (Cross-cutting)**: 2–3 tests — `MfSnackbarService` shows toast, auto-dismisses, shows correct type classes
5. **Phase 4 (Screens)**: 2–4 tests per screen — component renders, key user action works (submit, flip, etc.), Polish strings present
6. **Phase 5 (FR-9)**: 2–3 tests — no `mat-*` selectors remain, `@angular/cdk` present in lock file

### Standards Compliance

- Follow `ChangeDetectionStrategy.OnPush` on all new components (project standard: all Angular components).
- Use `inject()` DI pattern — no constructor-injected dependencies (project standard).
- Use Angular signals (`signal()`, `computed()`, `effect()`) for local state (project standard).
- Use `@if`/`@for` control flow syntax — not `*ngIf`/`*ngFor` (project standard).
- Use `takeUntilDestroyed()` for all Observable subscriptions in components (project standard).
- No `sys.path` manipulation or module-level singletons in backend (project standard).
- Backend router follows same auth dependency pattern as existing routers (`get_current_user` from `mindforge/api/deps.py`).
- API schema sync: `UserStatsResponse` Pydantic model in `schemas.py` and `UserStatsResponse` TypeScript interface in `api.models.ts` must match exactly.

---

## Constraints and Exclusions

### Hard Constraints (must not violate)

- **Preserve flashcard 3D animation verbatim**: The CSS `transform: rotateY(180deg)`, `transition: 0.55s cubic-bezier(.4,0,.2,1)`, `transform-style: preserve-3d`, `backface-visibility: hidden` in `flashcards.scss` must be copied exactly to the new component. Do not rewrite the animation logic.
- **Preserve ALL Polish language strings**: Every user-visible Polish text string across all screens is preserved unchanged. This is a visual redesign, not a content change.
- **No domain or application layer changes**: `mindforge/domain/`, `mindforge/application/`, and `mindforge/agents/` are off-limits. The only backend change is adding the stub router in `mindforge/api/`.
- **No server-authoritative state bypass**: The stats endpoint returns hardcoded zeros. Do not attempt to query `document_interactions` or flashcard tables — that logic is deferred and out of scope.
- **Angular CDK must remain**: `@angular/cdk` stays in `package.json` after Angular Material is removed.

### Out of Scope

- Real streak/due-today calculation logic (stub returns 0s permanently for this task)
- PWA / offline support
- Logo SVG design (placeholder SVG acceptable; final design deferred to Phase 7 of product design)
- E2E Playwright test updates for new selectors
- Internationalization infrastructure changes
- Any changes to `mindforge/discord/`, `mindforge/slack/`, `mindforge/cli/`
- Accessibility audit beyond WCAG AA compliance for the specified color pairs
- Storybook or component documentation
- Animation on screen transitions (router-level animations)

---

## Files to Create

| File | Purpose |
|------|---------|
| `frontend/postcss.config.js` | PostCSS config with `@tailwindcss/postcss`, Preflight disabled |
| `frontend/src/app/core/styles/design-tokens.css` | Complete `--mf-*` primitive + semantic + dark override token set |
| `frontend/src/app/core/services/theme.service.ts` | Dark mode toggle service, `APP_INITIALIZER` target |
| `frontend/src/app/core/services/mf-snackbar.service.ts` | Toast notification service replacing `MatSnackBar` |
| `frontend/src/app/core/components/button/button.component.ts` | `mf-button` directive/component |
| `frontend/src/app/core/components/button/button.component.scss` | `mf-button` styles |
| `frontend/src/app/core/components/card/card.component.ts` | `mf-card` component |
| `frontend/src/app/core/components/card/card.component.scss` | `mf-card` styles |
| `frontend/src/app/core/components/input/input.component.ts` | `mf-input` component |
| `frontend/src/app/core/components/input/input.component.scss` | `mf-input` styles |
| `frontend/src/app/core/components/chip/chip.component.ts` | `mf-chip` component |
| `frontend/src/app/core/components/chip/chip.component.scss` | `mf-chip` styles |
| `frontend/src/app/core/components/skeleton/skeleton.component.ts` | `mf-skeleton` component |
| `frontend/src/app/core/components/skeleton/skeleton.component.scss` | `mf-skeleton` shimmer animation |
| `frontend/src/app/core/components/dialog/dialog.component.ts` | `mf-dialog` CDK wrapper component |
| `frontend/src/app/core/components/dialog/dialog.component.scss` | `mf-dialog` styles + entry animation |
| `frontend/src/app/core/components/progress/progress.component.ts` | `mf-progress` component |
| `frontend/src/app/core/components/progress/progress.component.scss` | `mf-progress` styles + indeterminate animation |
| `frontend/src/app/shell/toolbar/toolbar.component.ts` | Extracted toolbar component |
| `frontend/src/app/shell/toolbar/toolbar.component.html` | Toolbar template |
| `frontend/src/app/shell/toolbar/toolbar.component.scss` | Toolbar styles |
| `frontend/src/app/shell/sidebar/sidebar.component.ts` | Extracted sidebar component with gamification footer |
| `frontend/src/app/shell/sidebar/sidebar.component.html` | Sidebar template |
| `frontend/src/app/shell/sidebar/sidebar.component.scss` | Sidebar styles including collapse transition |
| `mindforge/api/routers/users.py` | `GET /api/v1/users/me/stats` stub endpoint |

---

## Files to Modify

| File | Changes Needed |
|------|---------------|
| `frontend/package.json` | Add `tailwindcss`, `@tailwindcss/postcss`, `lucide-angular`; remove `@angular/material` in Phase 5 |
| `frontend/angular.json` | Add `postcssConfiguration: "postcss.config.js"` to build architect target |
| `frontend/src/index.html` | Replace Roboto Google Fonts link with Inter variable font links; remove Material Icons link in Phase 5 |
| `frontend/src/styles.scss` | Add `@import "tailwindcss"`, `@import "./app/core/styles/design-tokens.css"`, `@theme { … }`, Inter font reset; remove `@include mat.theme()` in Phase 5 |
| `frontend/src/app/app.config.ts` | Add `APP_INITIALIZER` for `ThemeService` |
| `frontend/src/app/core/models/api.models.ts` | Add `UserStatsResponse` interface |
| `frontend/src/app/core/services/api.service.ts` | Add `getMyStats(): Observable<UserStatsResponse>` method |
| `frontend/src/app/shell/shell.ts` | Refactor to use `ToolbarComponent` + `SidebarComponent`; add `sidebarCollapsed` signal and localStorage persistence |
| `frontend/src/app/shell/shell.html` | Replace inline toolbar/sidenav with `<app-toolbar>` + `<app-sidebar>` |
| `frontend/src/app/shell/shell.scss` | Update layout to flexbox shell; remove Material sidenav overrides |
| `frontend/src/app/pages/login/login.ts` | Remove `MatCardModule`, `MatTabsModule`, `MatFormFieldModule`, `MatInputModule`, `MatButtonModule`, `MatSnackBar`; add `mf-input`, `mf-button`, `MfSnackbarService`; refactor to split-hero layout |
| `frontend/src/app/pages/login/login.html` | Full redesign per FR-7 item 32 |
| `frontend/src/app/pages/login/login.scss` | Replace Material overrides with Tailwind + design tokens |
| `frontend/src/app/pages/knowledge-bases/knowledge-bases.ts` | Remove Material modules; add `mf-*` components; replace MatSnackBar + MatDialog |
| `frontend/src/app/pages/knowledge-bases/knowledge-bases.html` | Full redesign per FR-7 items 33–34 |
| `frontend/src/app/pages/knowledge-bases/knowledge-bases.scss` | New styles |
| `frontend/src/app/pages/knowledge-bases/kb-create-dialog/kb-create-dialog.ts` | Replace `MatDialog` with CDK `Dialog` + `mf-dialog`; replace `MatFormField` with `mf-input`; replace `MatButton` with `mf-button` |
| `frontend/src/app/pages/knowledge-bases/kb-create-dialog/kb-create-dialog.html` | Redesign using `mf-dialog`, `mf-input`, `mf-button` |
| `frontend/src/app/pages/documents/documents.ts` | Remove Material modules; add `mf-*`; replace MatSnackBar |
| `frontend/src/app/pages/documents/documents.html` | Redesign per FR-7 item 35 |
| `frontend/src/app/pages/documents/documents.scss` | New styles |
| `frontend/src/app/pages/quiz/quiz.ts` | Remove Material modules; add `mf-*`; replace MatSnackBar |
| `frontend/src/app/pages/quiz/quiz.html` | Redesign per FR-7 item 36 |
| `frontend/src/app/pages/quiz/quiz.scss` | New styles |
| `frontend/src/app/pages/flashcards/flashcards.ts` | Remove Material modules; add `mf-*`; replace MatSnackBar |
| `frontend/src/app/pages/flashcards/flashcards.html` | Redesign per FR-7 item 37 |
| `frontend/src/app/pages/flashcards/flashcards.scss` | Restyle card surfaces; **preserve 3D animation CSS verbatim** |
| `frontend/src/app/pages/search/search.ts` | Remove Material modules; add `mf-*` |
| `frontend/src/app/pages/search/search.html` | Redesign per FR-7 item 38 |
| `frontend/src/app/pages/search/search.scss` | New styles |
| `frontend/src/app/pages/chat/chat.ts` | Remove Material modules; add `mf-*`; replace MatSnackBar |
| `frontend/src/app/pages/chat/chat.html` | Redesign per FR-7 item 39 |
| `frontend/src/app/pages/chat/chat.scss` | Bubble layout styles |
| `frontend/src/app/pages/concepts/concept-map.ts` | Replace hardcoded Cytoscape stylesheet; add `selectedNode` signal + panel logic; add `@panelSlide` animation; replace MatSnackBar |
| `frontend/src/app/pages/concepts/concept-map.html` | Add floating toolbar, `@if (selectedNode())` side panel |
| `frontend/src/app/pages/concepts/concept-map.scss` | Panel and canvas styles |
| `mindforge/api/schemas.py` | Add `UserStatsResponse` Pydantic model |
| `mindforge/api/main.py` | Import and register `users.router` with `prefix="/api/v1/users"` |

---

## Backend Endpoint Specification

### `GET /api/v1/users/me/stats`

**File**: `mindforge/api/routers/users.py` (new)

**Auth**: `Depends(get_current_user)` — same pattern as `mindforge/api/routers/auth.py`

**Response model**: `UserStatsResponse` from `mindforge/api/schemas.py`

**Implementation**: Stub — return `UserStatsResponse()` (streak_days=0, due_today=0). No database query.

**Registration in `main.py`**:
```python
from mindforge.api.routers import users
app.include_router(users.router, prefix="/api/v1/users")
```

**Pydantic model** in `schemas.py`:
```python
class UserStatsResponse(BaseModel):
    streak_days: int = 0
    due_today: int = 0
```

**Router pattern** (matches existing routers):
```python
router = APIRouter(tags=["users"])

@router.get("/me/stats", response_model=UserStatsResponse)
async def get_my_stats(current_user=Depends(get_current_user)) -> UserStatsResponse:
    return UserStatsResponse()
```

---

## Acceptance Criteria

1. **Build succeeds**: `npm run build` in `frontend/` completes without errors after all phases.
2. **All 9 screens render**: Every route loads without console errors or missing styles.
3. **No Angular Material components in templates**: Zero `mat-*` selectors exist in any `.html` file (verified after Phase 5).
4. **No `--mat-sys-*` references**: Zero occurrences in any CSS/SCSS file (verified after Phase 5).
5. **Dark mode works**: Toggling `ThemeService.toggle()` switches `data-theme` on `<html>`, all `--mf-*` overrides apply, all screens are readable in dark mode.
6. **Dark mode persists**: Refreshing the page restores the last selected theme.
7. **Dark mode respects OS preference on first visit**: No saved preference → reads `prefers-color-scheme`.
8. **Sidebar collapses**: Clicking hamburger collapses sidebar to 64 px icon rail; labels hidden; collapse state persists in localStorage.
9. **Gamification footer**: `/api/v1/users/me/stats` responds 200 with `{streak_days: 0, due_today: 0}`; sidebar footer shows `🔥 0 days  📚 0 due`; shows `—` when request fails.
10. **Flashcard 3D animation preserved**: Card flips with the existing `rotateY(180deg) 0.55s cubic-bezier` animation. Front and back surfaces use new `--mf-*` token colors.
11. **Polish strings unchanged**: All Polish user-facing text is present and unchanged.
12. **Mobile sidebar**: At < 768 px, sidebar is off-screen; hamburger opens it as overlay; clicking outside closes it.
13. **mf-* components pass unit tests**: All 8 component groups have passing unit tests covering variants, states, and keyboard behavior.
14. **Stats endpoint registered**: `GET /api/v1/users/me/stats` returns 200 for an authenticated user; 401 for unauthenticated.
15. **Inter font loads**: Browser DevTools shows `Inter` font applied to `body` and all text elements.
16. **Lucide icons render**: All `<lucide-icon>` elements render without console errors.
17. **WCAG AA contrast**: `--mf-text-primary` on `--mf-surface-1` ≥ 4.5:1 contrast ratio; `--mf-text-on-primary` on `--mf-primary` ≥ 4.5:1.
18. **Concept map node panel**: Clicking a Cytoscape node slides in the right panel; clicking the canvas background closes it; `cy.resize()` is called after panel open/close.
19. **No `@angular/material` in `package.json`** after Phase 5.
20. **`@angular/cdk` remains in `package.json`** after Phase 5.

---

## Known Limitations

- The gamification footer will show `0 days` and `0 due` until the real streak/SRS calculation logic is implemented (deferred, out of scope).
- Tailwind Preflight is disabled during migration, meaning base styles (box-sizing, font smoothing) come from Angular Material's CSS until Phase 5. After Phase 5, Preflight should be re-enabled and the base styles verified.
- The MindForge logo mark SVG is a placeholder (24×24 px indigo spark shape acceptable) — the final icon design is out of scope.
- `provideAnimations()` in `app.config.ts` must remain until Phase 5 removal is verified — CDK animations depend on it.
