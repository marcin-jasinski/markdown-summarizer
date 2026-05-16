# Implementation Plan: MindForge UI Redesign

## Overview

| Attribute | Value |
|-----------|-------|
| **Total Task Groups** | 12 (11 implementation + 1 test review) |
| **Phases** | 5 — Infrastructure → Component Library → Shell → Cross-cutting → Screens → Material Removal |
| **Total Implementation Steps** | ~96 |
| **Expected Tests** | 51–71 (41–61 across groups + up to 10 in test review) |
| **Risk Level** | High |
| **Spec source** | `implementation/spec.md` |
| **Mockups source** | `../../product-design/2026-04-29-mindforge-ui-redesign/analysis/ui-mockups.md` |

### Critical Ordering Rules

1. FR-9 step order: remove ALL `MatXModule` imports → verify build → THEN `npm uninstall @angular/material`
2. Tailwind import: use `@import "tailwindcss/theme"` + `@import "tailwindcss/utilities"` (NOT `@import "tailwindcss"`) until Phase 5
3. Flashcard 3D animation CSS must be copied **verbatim** — never rewritten
4. All Polish language strings preserved unchanged across all screen redesigns
5. Backend: only `mindforge/api/` is touched — domain, application, agents are off-limits

---

## Implementation Steps

---

### Phase 0 — Infrastructure (FR-1, FR-2, FR-3)

---

### Task Group 1: Build System Setup
**Phase:** 0
**Dependencies:** None
**Estimated Steps:** 7

- [x] 1.0 Complete build system setup
  - [x] 1.1 Write 3 focused build-system tests
    - Test: `frontend/` builds without errors after Tailwind + PostCSS installation (`ng build --configuration=development` exits 0)
    - Test: `postcss.config.js` is picked up — `bg-primary` Tailwind class appears in compiled CSS output
    - Test: `lucide-angular` LucideAngularModule can be imported without error (compile check)
  - [x] 1.2 Install npm dev dependencies in `frontend/`
    - `npm install --save-dev tailwindcss @tailwindcss/postcss`
    - `npm install lucide-angular`
    - Verify additions in `frontend/package.json`
  - [x] 1.3 Create `frontend/postcss.config.js`
    - Content: `module.exports = { plugins: { '@tailwindcss/postcss': {} } }`
    - ⚠️ **Risk**: do NOT use `{ plugins: ['tailwindcss'] }` — must use `@tailwindcss/postcss` for v4
  - [x] 1.4 Update `frontend/angular.json`
    - **NOTE**: Angular 21 `@angular/build:application` (esbuild) auto-discovers `postcss.config.js` — NO `postcssConfiguration` key needed in angular.json (adding it causes schema validation error). Step completed as N/A.
    - Verify `styles.scss` is listed in `styles` array (it should already be)
  - [x] 1.5 Verify `frontend/` dev build compiles cleanly (`ng build --configuration=development`)
  - [x] 1.6 Ensure build-system tests pass (3 from step 1.1)

**Acceptance Criteria:**
- `frontend/postcss.config.js` exists with `@tailwindcss/postcss` plugin entry
- `frontend/angular.json` has `postcssConfiguration` pointing to it
- `ng build --configuration=development` exits 0
- `lucide-angular` is in `dependencies` (not devDependencies) in `frontend/package.json`

---

### Task Group 2: Design System (Tokens + Styles)
**Phase:** 0
**Dependencies:** Group 1
**Estimated Steps:** 7

- [x] 2.0 Complete design system setup
  - [x] 2.1 Write 3 focused design-system tests
    - Test: `design-tokens.css` defines `--mf-primary: #5B4FE9` in `:root`
    - Test: `[data-theme="dark"]` block in `design-tokens.css` overrides `--mf-surface-1` to `#1C1B23`
    - Test: Angular app renders with `data-theme` attribute on `<html>` after `ThemeService` init (defer if ThemeService not yet created — skip to Group 3 tests)
  - [x] 2.2 Create `frontend/src/app/core/styles/design-tokens.css`
    - Add all primitive color values in `:root` (indigo-50→900, amber, emerald, red, orange, gray palette)
    - Add all semantic tokens (`:root`) — exact values from spec Design Token Reference table:
      - `--mf-primary: #5B4FE9`, `--mf-primary-hover: #4338CA`, `--mf-primary-subtle: #EEF2FF`
      - `--mf-accent: #F59E0B`
      - `--mf-surface-1: #FFFFFF`, `--mf-surface-2: #F8F9FA`, `--mf-surface-3: #F0F2F5`
      - `--mf-text-primary: #111827`, `--mf-text-secondary: #6B7280`, `--mf-text-tertiary: #9CA3AF`, `--mf-text-on-primary: #FFFFFF`
      - `--mf-border: #E5E7EB`, `--mf-border-strong: #D1D5DB`
      - All shadow tokens, color result tokens (correct/incorrect/warning/streak)
      - All radius tokens (sm/md/lg/xl/full)
      - Layout constants: `--mf-sidebar-width: 240px`, `--mf-sidebar-collapsed: 64px`, `--mf-toolbar-height: 56px`
      - Transition tokens (fast/normal/slow)
    - Add `[data-theme="dark"]` block with all dark mode overrides from spec table
    - Add `html { transition: background-color 200ms ease, color 200ms ease; }` — **NOT** `transition: all`
  - [x] 2.3 Update `frontend/src/styles.scss`
    - At the very top (before any existing content):
      - `@import "tailwindcss/theme";` (NOT `@import "tailwindcss"`)
      - `@import "tailwindcss/utilities";`
      - `@import "./app/core/styles/design-tokens.css";`
    - Add `@theme { … }` block mapping `--mf-*` tokens to Tailwind theme keys:
      - `--color-primary: var(--mf-primary)`, `--color-surface-1: var(--mf-surface-1)`, `--color-surface-2: var(--mf-surface-2)`, `--color-surface-3: var(--mf-surface-3)`
      - `--color-text: var(--mf-text-primary)`, `--color-text-secondary: var(--mf-text-secondary)`, `--color-border: var(--mf-border)`
      - `--color-correct: var(--mf-correct)`, `--color-incorrect: var(--mf-incorrect)`
      - `--shadow-card: var(--mf-shadow-md)`, `--shadow-card-hover: var(--mf-shadow-card-hover)`
      - `--radius-sm: var(--mf-radius-sm)`, `--radius-md: var(--mf-radius-md)`, `--radius-lg: var(--mf-radius-lg)`, `--radius-xl: var(--mf-radius-xl)`
    - Add Inter font-family body reset: `body { font-family: 'Inter Variable', 'Inter', sans-serif; }`
    - Keep existing `@include mat.theme()` block — do NOT remove until Phase 5 (Group 11)
  - [x] 2.4 Update `frontend/src/index.html`
    - Add `<link rel="preconnect" href="https://fonts.googleapis.com">` and `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>` in `<head>`
    - Add Inter variable font `<link>` (Google Fonts URL for Inter variable weight)
    - Keep Material Icons `<link>` for now — remove only after all `<mat-icon>` usages are eliminated (Phase 5)
  - [x] 2.5 Run `ng build --configuration=development` — verify Tailwind utility classes are emitted in CSS output
    - ⚠️ **Risk flag**: If `Cannot apply unknown utility class 'bg-primary'`, the `@theme` block tokens are not mapped — check `styles.scss` for syntax errors in `@theme { }` block
  - [x] 2.6 Ensure design-system tests pass (3 from step 2.1)

**Acceptance Criteria:**
- `design-tokens.css` exists with complete token set (primitives, semantic, dark overrides)
- `styles.scss` imports Tailwind theme + utilities (not base/preflight), design-tokens.css, has `@theme` block
- `[data-theme="dark"]` dark mode override values match spec exactly (especially `--mf-surface-1: #1C1B23`)
- `ng build` compiles without Tailwind errors

---

### Task Group 3: Core Services + Backend Stub
**Phase:** 0
**Dependencies:** Group 2
**Estimated Steps:** 10

- [x] 3.0 Complete core services and backend stub
  - [x] 3.1 Write 5 focused services tests
    - Test: `ThemeService` initializes with OS `prefers-color-scheme: dark` → `isDark()` signal is `true`
    - Test: `ThemeService.toggle()` flips `isDark()` and writes `mf-theme` key to `localStorage`
    - Test: `ThemeService` on construction sets `data-theme` attribute on `document.documentElement`
    - Test: `MfSnackbarService.show('msg', 'success')` appends toast element to DOM with success class
    - Test: `GET /api/v1/users/me/stats` returns `{"streak_days": 0, "due_today": 0}` with 200 status (Python unit test)
  - [x] 3.2 Create `frontend/src/app/core/services/theme.service.ts`
    - `providedIn: 'root'`
    - Constructor reads `localStorage.getItem('mf-theme')` first, falls back to `window.matchMedia('(prefers-color-scheme: dark)').matches`
    - `isDark = signal(false)` initialized from above
    - Private `applyTheme()` calls `document.documentElement.setAttribute('data-theme', isDark() ? 'dark' : 'light')` and `localStorage.setItem('mf-theme', isDark() ? 'dark' : 'light')`
    - `toggle()` method: `isDark.update(v => !v)` then `applyTheme()`
    - Call `applyTheme()` at end of constructor to hydrate on load
    - Use `inject()` for `DOCUMENT` token (not `document` directly) for testability
  - [x] 3.3 Register `ThemeService` as `APP_INITIALIZER` in `frontend/src/app/app.config.ts`
    - Add `{ provide: APP_INITIALIZER, useFactory: (t: ThemeService) => () => {}, deps: [ThemeService], multi: true }` to providers
    - This forces ThemeService construction before first route render, applying dark mode to Login page
  - [x] 3.4 Create `frontend/src/app/core/services/mf-snackbar.service.ts`
    - `providedIn: 'root'`
    - `private container: HTMLElement | null = null`
    - `private ensureContainer()`: creates `div` with fixed position CSS (bottom-right corner, z-index 9999), appends to `document.body`, stores reference
    - `show(message: string, type: 'success' | 'error' | 'info')`: calls `ensureContainer()`, creates toast `div` with `mf-toast mf-toast-${type}` classes, sets `textContent`, appends to container, calls `setTimeout(() => toast.remove(), 4000)`
    - Use `inject(DOCUMENT)` for DOM access
  - [x] 3.5 Add `UserStatsResponse` interface to `frontend/src/app/core/models/api.models.ts`
    - `export interface UserStatsResponse { streak_days: number; due_today: number; }`
    - Add immediately after the last existing interface — do NOT modify any other interface
  - [x] 3.6 Add `getMyStats()` method to `frontend/src/app/core/services/api.service.ts`
    - `getMyStats(): Observable<UserStatsResponse> { return this.http.get<UserStatsResponse>('/api/v1/users/me/stats'); }`
    - Import `UserStatsResponse` from `api.models.ts`
    - All existing methods remain unchanged
  - [x] 3.7 Add `UserStatsResponse` Pydantic model to `mindforge/api/schemas.py`
    - `class UserStatsResponse(BaseModel): streak_days: int = 0; due_today: int = 0`
    - Add after last existing schema class
  - [x] 3.8 Create `mindforge/api/routers/users.py`
    - Import: `from fastapi import APIRouter, Depends`, `from mindforge.api.deps import get_current_user`, `from mindforge.api.schemas import UserStatsResponse`
    - `router = APIRouter()`
    - Route: `@router.get("/me/stats", response_model=UserStatsResponse)` with `current_user = Depends(get_current_user)` — returns `UserStatsResponse(streak_days=0, due_today=0)`
    - No domain/application/infrastructure imports — pure stub
  - [x] 3.9 Register router in `mindforge/api/main.py`
    - Import `from mindforge.api.routers import users`
    - Add `app.include_router(users.router, prefix="/api/v1/users", tags=["users"])` alongside existing routers
  - [x] 3.10 Ensure all 5 tests from step 3.1 pass

**Acceptance Criteria:**
- `ThemeService` reads OS preference, persists toggle, sets `data-theme` on `<html>`
- `MfSnackbarService` creates DOM toast, auto-removes after 4000 ms
- `UserStatsResponse` in both `api.models.ts` and `schemas.py` with matching field names/types
- `GET /api/v1/users/me/stats` returns 200 with `streak_days: 0, due_today: 0`
- `APP_INITIALIZER` registered in `app.config.ts`

---

### Phase 1 — Component Library (FR-4)

---

### Task Group 4: Base mf-* Components
**Phase:** 1
**Dependencies:** Group 3
**Estimated Steps:** 12

- [x] 4.0 Complete base component library
  - [x] 4.1 Write 6 focused component tests
    - Test: `mf-button` with `variant="primary"` has host class `mf-btn-primary`
    - Test: `mf-button` with `[loading]="true"` renders spinner overlay element
    - Test: `mf-button` with `[disabled]="true"` sets `aria-disabled="true"` on host
    - Test: `mf-card` with `hoverable="true"` has `mf-card-hoverable` class
    - Test: `mf-input` two-way binding — updating internal input reflects in `value` model output
    - Test: `mf-input` with `[error]="'Required'"` renders error message text in DOM
  - [x] 4.2 Create `frontend/src/app/core/components/button/button.component.ts`
    - Directive-based (attribute selector `[mfButton]` or element `mf-button` — use attribute to allow `<button mfButton>` native element)
    - `ChangeDetectionStrategy.OnPush`
    - Inputs (signal-based): `variant = input<'primary' | 'secondary' | 'ghost' | 'danger' | 'icon'>('primary')`, `size = input<'sm' | 'md' | 'lg'>('md')`, `disabled = input(false)`, `loading = input(false)`
    - Host bindings: `[class]` applying variant/size/state classes, `[attr.aria-disabled]="disabled() || loading()"`
    - When `loading()` is true, append spinner overlay inside the button (use `@if (loading())` template)
    - No Angular Material imports
  - [x] 4.3 Create `frontend/src/app/core/components/button/button.component.scss`
    - Base styles using `--mf-*` tokens for each variant (primary: `bg-[--mf-primary]`, secondary: outlined, ghost: transparent, danger: `bg-[--mf-incorrect]`, icon: square)
    - Size variants (sm: h-8 px-3 text-sm; md: h-10 px-4 text-sm; lg: h-12 px-6)
    - Spinner overlay: absolute position, same size as button, flex center
  - [x] 4.4 Create `frontend/src/app/core/components/card/card.component.ts`
    - Standalone component, `ChangeDetectionStrategy.OnPush`
    - Inputs: `variant = input<'default' | 'elevated' | 'flat'>('default')`, `hoverable = input(false)`, `padding = input<'sm' | 'md' | 'lg'>('md')`
    - Template: `<ng-content>` slots for default, `[slot="header"]`, `[slot="footer"]`, `[slot="actions"]`
    - Host: `[class]` computed from inputs
  - [x] 4.5 Create `frontend/src/app/core/components/card/card.component.scss`
    - Base: `background: var(--mf-surface-1); border-radius: var(--mf-radius-lg); box-shadow: var(--mf-shadow-md); border: 1px solid var(--mf-border)`
    - Elevated: `box-shadow: var(--mf-shadow-lg)`; flat: `box-shadow: none`
    - Hoverable: `transition: box-shadow var(--mf-transition-normal); &:hover { box-shadow: var(--mf-shadow-card-hover) }`
    - Padding variants: sm=12px, md=16px, lg=24px
  - [x] 4.6 Create `frontend/src/app/core/components/input/input.component.ts`
    - Standalone, `ChangeDetectionStrategy.OnPush`
    - Inputs: `label = input('')`, `placeholder = input('')`, `type = input('text')`, `disabled = input(false)`, `error = input('')`, `helperText = input('')`
    - Two-way binding: `value = model<string>('')`
    - Template: label `<span>`, wrapper `<div>` with `<ng-content select="[slot=iconLeft]">`, native `<input>`, `<ng-content select="[slot=iconRight]">`, error span, helper span
    - `(input)` event updates `value` signal
  - [x] 4.7 Create `frontend/src/app/core/components/input/input.component.scss`
    - Focus ring: `--mf-primary` outline 2px offset 1px
    - Error state: `--mf-incorrect` border + error text color
    - Icon slots: absolute positioned inside wrapper
  - [x] 4.8 Create `frontend/src/app/core/components/skeleton/skeleton.component.ts`
    - Standalone, `ChangeDetectionStrategy.OnPush`
    - Inputs: `height = input<string | number>('1rem')`, `width = input<string | number>('100%')`, `variant = input<'rect' | 'circle' | 'text'>('rect')`
    - Host style binding applies `height` and `width` (normalize to px string if number)
    - Host class: `mf-skeleton` + `mf-skeleton-${variant()}`
    - No template content — purely styled host element
  - [x] 4.9 Create `frontend/src/app/core/components/skeleton/skeleton.component.scss`
    - `skeleton-shimmer` keyframe animation: gradient sweep from `var(--mf-surface-3)` → `var(--mf-border)` → `var(--mf-surface-3)` over 1.5s infinite
    - Apply `background: linear-gradient(90deg, …); background-size: 200% 100%; animation: skeleton-shimmer 1.5s infinite`
    - Circle variant: `border-radius: 50%`
    - Text variant: `border-radius: var(--mf-radius-sm); height: 1em`
  - [x] 4.10 Verify `ng build` still passes with all 4 new components
  - [x] 4.11 Ensure all 6 tests from step 4.1 pass

**Acceptance Criteria:**
- `mf-button`, `mf-card`, `mf-input`, `mf-skeleton` all exist as standalone components
- All use `ChangeDetectionStrategy.OnPush`, `inject()` DI, signal inputs
- No Angular Material imports in any of these files
- `ng build` passes with new components

---

### Task Group 5: Advanced mf-* Components
**Phase:** 1
**Dependencies:** Group 4
**Estimated Steps:** 12

- [x] 5.0 Complete advanced component library
  - [x] 5.1 Write 6 focused advanced component tests
    - Test: `mf-chip` keyboard Enter on variant `active` toggles active state
    - Test: `mf-chip` keyboard Delete on variant `removable` emits `removed` output
    - Test: `mf-dialog` opened via CDK `Dialog.open()` renders `title` input in header
    - Test: `mf-dialog` close button click closes the dialog (CDK `DialogRef.close()` called)
    - Test: `mf-progress` with `[value]="75"` sets `width: 75%` on inner bar element
    - Test: `mf-progress` with `[indeterminate]="true"` applies `mf-progress-indeterminate` class
  - [x] 5.2 Create `frontend/src/app/core/components/chip/chip.component.ts`
    - Standalone, `ChangeDetectionStrategy.OnPush`
    - Inputs: `variant = input<'default' | 'active' | 'removable' | 'subtle' | 'status'>('default')`, `size = input<'sm' | 'md'>('md')`, `color = input<'correct' | 'incorrect' | 'pending' | 'processing' | ''>('')`
    - Output: `removed = output<void>()`
    - `@HostListener('keydown', ['$event'])` for keyboard events:
      - Enter/Space on `active` variant: toggle internal `isActive = signal(false)` state
      - Delete/Backspace on `removable` variant: `this.removed.emit()`
    - `tabindex="0"` on host for keyboard accessibility
    - Render remove button (`×`) when `variant() === 'removable'`
  - [x] 5.3 Create `frontend/src/app/core/components/chip/chip.component.scss`
    - Base pill shape: `border-radius: var(--mf-radius-full); padding: 2px 10px; font-size: 12px`
    - Status colors map: correct → `--mf-correct`, incorrect → `--mf-incorrect`, pending → `--mf-text-tertiary`, processing → `--mf-accent`
    - Active variant: `bg-[--mf-primary-subtle] text-[--mf-primary] border-[--mf-primary]`
  - [x] 5.4 Create `frontend/src/app/core/components/dialog/dialog.component.ts`
    - Standalone, `ChangeDetectionStrategy.OnPush`
    - Import `Dialog, DialogRef, DIALOG_DATA` from `@angular/cdk/dialog` — NOT `@angular/material/dialog`
    - Inputs: `title = input('')`, `disableClose = input(false)`
    - Inject `DialogRef` and `DIALOG_DATA` via `inject()`
    - `close()` method calls `this.dialogRef.close()`
    - Template structure: header `div` (title `span` + close `button` [conditionally hidden when `disableClose()`]), scrollable content `<ng-content>`, actions slot `<ng-content select="[slot=actions]">`
    - Entry animation: `@Component({ animations: [trigger('dialogEnter', [transition(':enter', [style({ opacity: 0, transform: 'scale(0.95)' }), animate('200ms ease-out', style({ opacity: 1, transform: 'scale(1)' }))])] ]) })`
    - Host: `[@dialogEnter]` trigger on host element
  - [x] 5.5 Create `frontend/src/app/core/components/dialog/dialog.component.scss`
    - Dialog panel: `background: var(--mf-surface-1); border-radius: var(--mf-radius-lg); box-shadow: var(--mf-shadow-lg); max-width: 480px; width: 100%; padding: 24px`
    - Backdrop (applied via `Dialog.open()` config): `background: rgba(0,0,0,0.4); backdrop-filter: blur(4px)`
    - Header: flex row space-between, title `font-semibold text-lg`, close button ghost icon
    - Content: `overflow-y: auto; max-height: 60vh; padding: 16px 0`
    - Actions: flex row flex-end gap-2 padding-top-16
  - [x] 5.6 Create `frontend/src/app/core/components/progress/progress.component.ts`
    - Standalone, `ChangeDetectionStrategy.OnPush`
    - Inputs: `value = input(0)`, `indeterminate = input(false)`, `color = input<'primary' | 'success' | 'danger'>('primary')`
    - Template: outer track `div` → inner fill `div` with `[style.width]="value() + '%'"` (hidden when indeterminate)
    - `@if (!indeterminate())` for fill bar; `@if (indeterminate())` for sweep animation bar
    - Host class: `mf-progress mf-progress-${color()}`
  - [x] 5.7 Create `frontend/src/app/core/components/progress/progress.component.scss`
    - Track: `height: 6px; border-radius: var(--mf-radius-full); background: var(--mf-surface-3); overflow: hidden`
    - Fill: `height: 100%; transition: width var(--mf-transition-normal); border-radius: var(--mf-radius-full)`
    - Color variants: primary → `var(--mf-primary)`, success → `var(--mf-correct)`, danger → `var(--mf-incorrect)`
    - Indeterminate keyframe: `@keyframes mf-progress-sweep { 0% { left: -50%; width: 50% } 100% { left: 100%; width: 50% } }` — applied to indeterminate fill bar
  - [x] 5.8 Export all components from a barrel-free approach
    - Each component is a standalone export — no shared `index.ts` barrel needed
    - Import paths are direct: `from '../core/components/button/button.component'`
  - [x] 5.9 Verify `ng build` passes with all 7 mf-* components + 2 services
  - [x] 5.10 Ensure all 6 tests from step 5.1 pass

**Acceptance Criteria:**
- `mf-chip`, `mf-dialog`, `mf-progress` exist as standalone components
- `mf-dialog` uses `@angular/cdk/dialog` — zero Material imports
- `mf-chip` keyboard events (Enter/Space active toggle, Delete/Backspace removed emit) work correctly
- `mf-progress` indeterminate animation uses pure CSS keyframes
- All 7 `mf-*` components built without Material dependencies

---

### Phase 2 — Shell Redesign (FR-5)

---

### Task Group 6: Shell Refactor
**Phase:** 2
**Dependencies:** Group 5
**Estimated Steps:** 14

- [x] 6.0 Complete shell redesign
  - [x] 6.1 Write 5 focused shell tests
    - Test: `SidebarComponent` `sidebarCollapsed` signal starts `false` (desktop default); clicking toggle sets it `true`
    - Test: `SidebarComponent` on collapsed toggle, `localStorage.setItem('mf-sidebar-collapsed', 'true')` is called
    - Test: `SidebarComponent` init reads `localStorage.getItem('mf-sidebar-collapsed')` to restore state
    - Test: `ShellComponent` with window width < 768px triggers mobile drawer mode (sidebar `position: fixed`)
    - Test: `ToolbarComponent` theme toggle button calls `ThemeService.toggle()`
  - [x] 6.2 Create `frontend/src/app/shell/toolbar/toolbar.component.ts`
    - Standalone, `ChangeDetectionStrategy.OnPush`
    - Inputs: `sidebarCollapsed = input(false)`, `userDisplayName = input('')`
    - Outputs: `sidebarToggle = output<void>()`
    - Inject: `ThemeService` (via `inject()`), `AuthService` (via `inject()`), `Router` (via `inject()`)
    - Signals: `dropdownOpen = signal(false)`
    - Methods: `onToggleSidebar()` emits `sidebarToggle`, `onToggleTheme()` calls `themeService.toggle()`, `onLogout()` calls `authService.logout()` then `router.navigate(['/login'])`
    - Lucide icons: `MenuIcon`, `ArrowLeftIcon`, `SunIcon`, `MoonIcon` — import from `lucide-angular`
  - [x] 6.3 Create `frontend/src/app/shell/toolbar/toolbar.component.html`
    - `<header class="flex items-center justify-between h-[56px] px-4 bg-[--mf-surface-1] border-b border-[--mf-border]">`
    - Left: hamburger/arrow icon `<button mfButton variant="icon">` emitting `sidebarToggle`, then breadcrumb slot
    - Right: theme toggle button with `@if (themeService.isDark())` switching Sun/Moon icon; user avatar circle `<div class="w-8 h-8 rounded-full bg-[--mf-primary] flex items-center justify-center text-white text-sm font-medium">` with initials; dropdown `@if (dropdownOpen())` with profile/logout items
  - [x] 6.4 Create `frontend/src/app/shell/toolbar/toolbar.component.scss`
    - Base height + surface-1 background (covered by Tailwind classes in template)
    - Avatar dropdown: `position: absolute; top: 48px; right: 0; min-width: 160px; background: var(--mf-surface-1); border: 1px solid var(--mf-border); border-radius: var(--mf-radius-md); box-shadow: var(--mf-shadow-md)`
  - [x] 6.5 Create `frontend/src/app/shell/sidebar/sidebar.component.ts`
    - Standalone, `ChangeDetectionStrategy.OnPush`
    - Inputs: `isMobile = input(false)`
    - Outputs: `toggle = output<void>()`
    - Inject: `Router` (for active route detection), `ApiService`, `ActivatedRoute`
    - Signals: `sidebarCollapsed = signal(localStorage.getItem('mf-sidebar-collapsed') === 'true')`, `stats = signal<UserStatsResponse | null>(null)`, `statsLoading = signal(true)`
    - `effect(() => localStorage.setItem('mf-sidebar-collapsed', String(this.sidebarCollapsed())))` for persistence
    - `ngOnInit()`: call `apiService.getMyStats().pipe(takeUntilDestroyed()).subscribe({ next: s => { this.stats.set(s); this.statsLoading.set(false); }, error: () => this.statsLoading.set(false) })`
    - Nav items array (constant): Dashboard `/`, Knowledge Bases `/knowledge-bases`, — then contextual KB items if `kbId` route param present
    - Inject `DestroyRef` for `takeUntilDestroyed()`
  - [x] 6.6 Create `frontend/src/app/shell/sidebar/sidebar.component.html`
    - `<nav [class]="sidebarCollapsed() ? 'w-16' : 'w-60'" class="flex flex-col h-full bg-[--mf-surface-3] border-r border-[--mf-border] transition-[width] duration-250 overflow-hidden">`
    - Section labels `@if (!sidebarCollapsed())` hidden when collapsed
    - Nav items: 36px height, `border-radius: var(--mf-radius-md)`, Lucide icon + `@if (!sidebarCollapsed())` label
    - Active item: `bg-[--mf-primary-subtle] text-[--mf-primary]`
    - CDK Tooltip on each nav item when collapsed (for label on hover): use `cdkTooltip` from `@angular/cdk/overlay` or `@angular/cdk/tooltip`
    - Gamification footer (bottom of sidebar, above last section): `@if (!statsLoading())` show `🔥 {{ stats()?.streak_days ?? '—' }}` and `📚 {{ stats()?.due_today ?? '—' }} due`; `@if (sidebarCollapsed())` show icon-only mode
    - Mobile: `@if (isMobile() && !sidebarCollapsed())` add backdrop overlay div
  - [x] 6.7 Create `frontend/src/app/shell/sidebar/sidebar.component.scss`
    - Sidebar width transition: `transition: width var(--mf-transition-normal)` (CSS only — Tailwind `transition-[width]` handles this)
    - Mobile drawer: `:host.mobile-mode { position: fixed; z-index: 50; height: 100%; transform: translateX(-100%); } :host.mobile-mode.open { transform: translateX(0); }`
    - Gamification footer: `padding: 12px; border-top: 1px solid var(--mf-border); font-size: 13px`
    - Streak color: `color: var(--mf-streak-color)` (`--color-amber-500`)
  - [x] 6.8 Refactor `frontend/src/app/shell/shell.ts`
    - Add `sidebarCollapsed = signal(false)` and `isMobile = signal(false)` to shell
    - Inject `BreakpointObserver` (already imported) — reuse existing breakpoint constant `'(max-width: 768px)'`
    - In `ngOnInit()`: `this.breakpointObserver.observe(['(max-width: 768px)']).pipe(takeUntilDestroyed()).subscribe(result => this.isMobile.set(result.matches))`
    - Desktop (> 1024px): sidebar expanded; tablet (768–1024px): sidebar collapsed — set initial state from `localStorage` or breakpoint
    - Handle `sidebarToggle` from toolbar: `onSidebarToggle()` flips `sidebarCollapsed` signal
    - Handle `toggle` from sidebar: same flip
  - [x] 6.9 Update `frontend/src/app/shell/shell.html`
    - Replace inline `<mat-toolbar>` with `<app-toolbar [sidebarCollapsed]="sidebarCollapsed()" [userDisplayName]="userName()" (sidebarToggle)="onSidebarToggle()">`
    - Replace inline `<mat-sidenav-container>` / `<mat-sidenav>` with `<app-sidebar [isMobile]="isMobile()" (toggle)="onSidebarToggle()">`
    - Main content area: `<main class="flex-1 overflow-auto bg-[--mf-surface-2] p-6">`
    - Outer shell: `<div class="flex h-screen overflow-hidden">`
  - [x] 6.10 Update `frontend/src/app/shell/shell.scss`
    - Remove Material sidenav overrides (`::ng-deep .mat-sidenav-*`)
    - Add flexbox layout: `:host { display: flex; flex-direction: column; height: 100vh; }`, `.shell-body { display: flex; flex: 1; overflow: hidden; }`
  - [x] 6.11 Remove `MatSidenavModule`, `MatToolbarModule` imports from `shell.ts` (keep `BreakpointObserver` from CDK)
    - ⚠️ **Risk flag**: Do NOT remove `MatSnackBar` from other files yet — that is Phase 3 (Group 7)
  - [x] 6.12 Verify `ng build` passes; manually test sidebar collapse/expand in browser
  - [x] 6.13 Ensure all 5 tests from step 6.1 pass

**Acceptance Criteria:**
- `ToolbarComponent` and `SidebarComponent` exist as standalone components extracted from shell
- `sidebarCollapsed` state persists to/from `localStorage`
- Mobile breakpoint (< 768px) triggers drawer mode using existing `BreakpointObserver`
- Gamification footer renders `—` while loading stats and real values when loaded
- `MatSidenavModule` and `MatToolbarModule` removed from shell; `BreakpointObserver` retained
- `ng build` passes

---

### Phase 3 — Cross-Cutting Migration (FR-6)

---

### Task Group 7: MatSnackBar + MatDialog Migration
**Phase:** 3
**Dependencies:** Group 6
**Estimated Steps:** 8

- [x] 7.0 Complete cross-cutting service migration
  - [x] 7.1 Write 4 focused migration tests
    - Test: `MfSnackbarService.show('Saved', 'success')` creates DOM element with class `mf-toast-success`
    - Test: `MfSnackbarService.show('Error', 'error')` auto-removes toast after 4000ms (use fake timers)
    - Test: `MfSnackbarService.show('Info', 'info')` creates toast with class `mf-toast-info`
    - Test: `kb-create-dialog` opens via CDK `Dialog.open()` — `MatDialog` import is absent from the file
  - [x] 7.2 Replace `MatSnackBar` in `frontend/src/app/pages/login/login.ts`
    - Remove `MatSnackBar` import and injection
    - Add `MfSnackbarService` injection via `inject(MfSnackbarService)`
    - Replace `this.snackBar.open(msg, 'Close', {…})` calls with `this.snackbarService.show(msg, 'error')` or appropriate type
    - Remove `MatSnackBarModule` from `imports` array
  - [x] 7.3 Replace `MatSnackBar` in `frontend/src/app/pages/dashboard/dashboard.ts` (if exists) and `frontend/src/app/pages/knowledge-bases/knowledge-bases.ts`
    - Same pattern: remove import → add inject → replace calls
  - [x] 7.4 Replace `MatSnackBar` in `frontend/src/app/pages/flashcards/flashcards.ts`, `quiz/quiz.ts`, `chat/chat.ts`
    - Same pattern for each file
    - Note: preserve ALL existing business logic — only the snackbar calls change
  - [x] 7.5 Replace `MatSnackBar` in `frontend/src/app/pages/documents/documents.ts` and `frontend/src/app/pages/concepts/concept-map.ts`
    - 9th consumer: confirm total count = 9 files migrated
  - [x] 7.6 Migrate `kb-create-dialog.ts` from `MatDialog` to CDK `Dialog`
    - In `frontend/src/app/pages/knowledge-bases/kb-create-dialog/kb-create-dialog.ts`:
      - Remove `MatDialog`, `MatDialogRef`, `MAT_DIALOG_DATA` imports
      - Add `Dialog` from `@angular/cdk/dialog`, `DialogRef`, `DIALOG_DATA` injections
      - Replace `this.dialogRef.close()` calls with CDK `DialogRef.close()`
      - Remove `MatDialogModule` from imports
      - Update template to use `<mf-dialog [title]="'Nowa Baza Wiedzy'">`, `mf-input`, `mf-button` (Polish title preserved verbatim)
    - In `kb-create-dialog.html`: full template using `mf-dialog`, `mf-input`, `mf-button`
    - In calling code (`knowledge-bases.ts`): update `MatDialog.open()` to `Dialog.open()` from `@angular/cdk/dialog`
  - [x] 7.7 Verify `ng build` compiles with no `MatSnackBar` imports remaining across the 9 migrated files
    - Run: `grep -r "MatSnackBar" frontend/src/app/pages/` — expect zero results
  - [x] 7.8 Ensure all 4 tests from step 7.1 pass

**Acceptance Criteria:**
- All 9 `MatSnackBar` usages replaced with `MfSnackbarService` calls
- `kb-create-dialog` uses CDK `Dialog` — zero `MatDialog` imports
- `ng build` passes with no Material dialog/snackbar imports in page components
- Polish strings in dialog titles/buttons unchanged

---

### Phase 4 — Screen Redesigns (FR-7, FR-8)

---

### Task Group 8: Simple Screens (Login + Knowledge-Bases/Dashboard)
**Phase:** 4
**Dependencies:** Group 7
**Estimated Steps:** 14

- [x] 8.0 Complete simple screen redesigns
  - [x] 8.1 Write 6 focused screen tests
    - Test: `LoginComponent` renders Polish heading text (e.g., `Logowanie` or `MindForge`)
    - Test: `LoginComponent` submit button has `[loading]="isLoading()"` wired to form submission
    - Test: `LoginComponent` dark mode — `[data-theme="dark"]` present on `<html>` when `isDark()` is `true`
    - Test: `KnowledgeBasesComponent` renders KB list as grid `grid gap-4`
    - Test: `KnowledgeBasesComponent` "New Knowledge Base" button click opens `mf-dialog` (CDK `Dialog.open()` called)
    - Test: `KnowledgeBasesComponent` empty state renders when KB array is empty
  - [x] 8.2 Redesign Login screen
    - File: `frontend/src/app/pages/login/login.html` — full redesign:
      - Outer: `<div class="flex min-h-screen">`
      - Left (hero): `<div class="hidden md:flex w-1/2 flex-col justify-center items-center bg-[--mf-primary] text-white p-12">` — MindForge wordmark (Inter 700), subtitle, SVG decoration placeholder
      - Right (auth): `<div class="flex-1 flex flex-col justify-center items-center bg-[--mf-surface-1] px-4">` → `<div class="w-full max-w-[400px]">`
      - Discord OAuth button: `<button mfButton variant="secondary" class="w-full bg-[#5865F2] text-white">`
      - Divider: `<div class="flex items-center gap-3 my-6"><div class="flex-1 h-px bg-[--mf-border]">` + "lub" text
      - Segmented tab toggle: `@if (isLogin())` signal switching login/register form
      - Login form: `<mf-input label="Email" type="email" [(value)]="email">`, `<mf-input label="Hasło" type="password" [(value)]="password">`
      - Submit: `<button mfButton variant="primary" class="w-full" [loading]="isLoading()">Zaloguj się</button>`
    - File: `frontend/src/app/pages/login/login.ts` — remove all Material imports, add `mf-button`/`mf-input` component imports
    - File: `frontend/src/app/pages/login/login.scss` — replace all Material overrides with Tailwind + token styles; add hero gradient
  - [x] 8.3 Redesign Knowledge-Bases screen
    - File: `frontend/src/app/pages/knowledge-bases/knowledge-bases.html`:
      - Page header: `<div class="flex items-center justify-between mb-6">` — title `<h1 class="text-2xl font-bold text-[--mf-text-primary]">Bazy Wiedzy</h1>` + `<button mfButton variant="primary" (click)="openCreateDialog()">Nowa Baza Wiedzy</button>`
      - Grid: `<div class="grid gap-4" style="grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))">`
      - KB card per item: `<mf-card [hoverable]="true">` with top border accent `border-t-4 border-t-[--mf-primary]`, 40px icon circle `bg-[--mf-primary-subtle]`, KB name `font-semibold`, doc-count `mf-chip`, 2-line description `line-clamp-2`, divider `border-t border-[--mf-border]`, ghost action buttons (Documents, Quiz, Chat) using Lucide icons
      - Loading: `@if (isLoading())` shows 3 `<mf-skeleton height="200px" class="rounded-xl">` cards in same grid
      - Empty state: `@if (!isLoading() && kbs().length === 0)` — centered SVG, `<h3>` heading, CTA button
    - File: `frontend/src/app/pages/knowledge-bases/knowledge-bases.ts` — remove remaining Material module imports (MatCardModule, MatGridListModule, etc.), add mf-component imports
    - File: `frontend/src/app/pages/knowledge-bases/knowledge-bases.scss` — minimal; Tailwind covers most styles
  - [x] 8.4 Verify dark mode works on both screens (toggle `data-theme` in browser, verify token swap)
  - [x] 8.5 Verify Polish strings preserved: spot-check "Zaloguj się", "Bazy Wiedzy", "Nowa Baza Wiedzy", dialog title "Nowa Baza Wiedzy"
  - [x] 8.6 Verify `ng build` passes
  - [x] 8.7 Ensure all 6 tests from step 8.1 pass

**Acceptance Criteria:**
- Login uses split-hero layout matching spec FR-7 item 32
- Knowledge-Bases grid uses `mf-card`, `mf-skeleton`, `mf-chip`, `mf-button` — zero `mat-*` selectors
- Dark mode applies correctly to both screens via `data-theme` attribute
- All Polish strings intact
- `ng build` passes

---

### Task Group 9: Medium Screens (Documents + Quiz + Flashcards + Search)
**Phase:** 4
**Dependencies:** Group 7
**Estimated Steps:** 18

- [x] 9.0 Complete medium screen redesigns
  - [x] 9.1 Write 7 focused screen tests
  - [x] 9.2 Redesign Documents screen
  - [x] 9.3 Redesign Quiz screen
  - [x] 9.4 Redesign Flashcards screen
  - [x] 9.5 Redesign Search screen
  - [x] 9.6 Verify dark mode on all 4 screens
  - [x] 9.7 Spot-check Polish strings
  - [x] 9.8 Verify `ng build` passes
  - [x] 9.9 Ensure all 7 tests from step 9.1 pass

**Acceptance Criteria:**
- All 4 screens use `mf-*` components only — no `mat-*` selectors
- Flashcard 3D animation CSS values unchanged: `transition: 0.55s cubic-bezier(.4,0,.2,1)`, `transform-style: preserve-3d`, `backface-visibility: hidden`
- Rating buttons fade in after flip; correct CSS animation
- Polish strings preserved verbatim
- `ng build` passes

---

### Task Group 10: Complex Screens (Chat + Concept Map)
**Phase:** 4
**Dependencies:** Group 7
**Estimated Steps:** 16

- [x] 10.0 Complete complex screen redesigns
  - [x] 10.1 Write 5 focused complex-screen tests
  - [x] 10.2 Redesign Chat screen
  - [x] 10.3 Redesign Concept Map screen
  - [x] 10.4 Verify dark mode
  - [x] 10.5 Verify ng build passes
  - [x] 10.6 All 5 tests pass
    - File: `frontend/src/app/pages/chat/chat.html`:
      - Outer: `<div class="flex flex-col h-[calc(100vh-var(--mf-toolbar-height))] max-w-[800px] mx-auto w-full px-4">`
      - Messages list: `<div class="flex-1 overflow-y-auto flex flex-col gap-3 py-4">` — `@for (msg of messages(); track msg.id)`:
        - User message: `<div class="self-end bg-[--mf-primary] text-white px-4 py-3 max-w-[70%]" style="border-radius: 18px 18px 4px 18px">`
        - Assistant message: `<div class="self-start bg-[--mf-surface-3] text-[--mf-text-primary] px-4 py-3 max-w-[70%]" style="border-radius: 18px 18px 18px 4px">`
        - Source chips below assistant: `@for (src of msg.sources; track src) → <mf-chip variant="subtle">{{ src }}</mf-chip>`
      - Typing indicator: `@if (isTyping())` → `<div class="self-start bg-[--mf-surface-3]">` with 3 `span` dots using staggered `animation: bounce 1s infinite` with `animation-delay: 0/0.2/0.4s`
      - Sticky input: `<div class="sticky bottom-0 bg-[--mf-surface-1] border-t border-[--mf-border] py-3 flex items-end gap-2">` — `<mf-input class="flex-1" placeholder="Zadaj pytanie...">` (auto-grow textarea, max 4 rows) + `<button mfButton variant="icon" (click)="sendMessage()">` send Lucide icon
    - File: `frontend/src/app/pages/chat/chat.ts` — remove Material imports, add `mf-input`, `mf-button`, `mf-chip`
    - File: `frontend/src/app/pages/chat/chat.scss` — bubble border-radius already inline; add dot bounce keyframe and stagger
  - [ ] 10.3 Redesign Concept Map screen
    - File: `frontend/src/app/pages/concepts/concept-map.ts`:
      - Add `lightStylesheet` constant (white nodes, `#C7D2FE` node borders, `#CBD5E1` edges, Inter font, `var(--mf-surface-2)` canvas bg)
      - Add `darkStylesheet` constant (dark node bg `var(--mf-surface-3)`, muted text, darker edge colors)
      - Add `selectedNode = signal<any | null>(null)` signal
      - In Cytoscape `tap` event: `this.selectedNode.set(event.target.data())`
      - Add `effect(() => { if (this.cy) this.cy.style(this.themeService.isDark() ? this.darkStylesheet : this.lightStylesheet) })` — inject `ThemeService`
      - Add `panelOpen = computed(() => this.selectedNode() !== null)`
      - When `panelOpen()` changes to true: `setTimeout(() => this.cy.resize(), 210)` to recalculate Cytoscape canvas
      - Remove `MatSnackBar` — already done in Group 7
    - File: `frontend/src/app/pages/concepts/concept-map.html`:
      - Wrap in `<div class="relative h-full">` (position context for absolute elements)
      - Floating toolbar: `<div class="absolute top-3 left-1/2 -translate-x-1/2 flex gap-1 bg-[--mf-surface-1] border border-[--mf-border] rounded-[--mf-radius-lg] shadow-md p-1">` — zoom in/out/fit/reset `<button mfButton variant="icon">` with Lucide icons
      - Canvas: `<div id="cy-container" [class.panel-open]="panelOpen()" class="w-full h-full">`
      - Node detail panel: `@if (selectedNode())` → `<div [@panelSlide] class="absolute right-0 top-0 w-[280px] h-full bg-[--mf-surface-1] border-l border-[--mf-border] overflow-y-auto p-4">` — close button + node name + properties
    - File: `frontend/src/app/pages/concepts/concept-map.ts` — add `@panelSlide` animation: `trigger('panelSlide', [transition(':enter', [style({transform:'translateX(100%)'}), animate('200ms ease-out', style({transform:'translateX(0)'}))]), transition(':leave', [animate('200ms ease-in', style({transform:'translateX(100%)'}))])])`
    - File: `frontend/src/app/pages/concepts/concept-map.scss`:
      - `#cy-container { width: 100%; height: 100%; transition: width var(--mf-transition-normal); } #cy-container.panel-open { width: calc(100% - 280px); }`
      - Canvas background: `background: var(--mf-surface-2)` on `#cy-container`
    - Add `NodeDetailPanelComponent` inline in concept-map template (no separate file needed — small enough)
  - [ ] 10.4 Verify Cytoscape theme switch works: toggle `ThemeService.isDark()` and confirm `cy.style()` is called with correct stylesheet
  - [ ] 10.5 Verify `@panelSlide` animation fires on node tap (node detail panel slides in from right)
  - [ ] 10.6 Verify dark mode on both screens
  - [ ] 10.7 Spot-check Polish strings: "Zadaj pytanie...", any remaining Polish UI text in concept map
  - [ ] 10.8 Verify `ng build` passes
  - [ ] 10.9 Ensure all 5 tests from step 10.1 pass

**Acceptance Criteria:**
- Chat bubbles have correct alignment and border-radius per spec (user: flex-end, assistant: flex-start)
- Typing indicator animation with staggered dots
- Concept Map `selectedNode` signal drives panel visibility via `@if`
- Cytoscape reactively switches stylesheets on dark mode toggle
- `@panelSlide` animation: translateX(100%) → 0 in 200ms on enter
- `cy.resize()` called 210ms after panel open to recalculate canvas
- Polish strings preserved

---

### Phase 5 — Angular Material Removal (FR-9)

---

### Task Group 11: Angular Material Removal
**Phase:** 5
**Dependencies:** Groups 8, 9, 10 (all screens complete)
**Estimated Steps:** 11

- [x] 11.0 Complete Angular Material removal
  - [x] 11.1 Write 3 focused removal-verification tests
  - [x] 11.2 Audit all remaining MatXModule imports
  - [x] 11.3 Remove all remaining MatXModule imports from TypeScript files
  - [x] 11.4 Remove @include mat.theme() from styles.scss
  - [x] 11.5 Verify ng build passes with zero Material-related errors
  - [x] 11.6 Run npm uninstall @angular/material
  - [x] 11.7 Re-enable Tailwind Preflight (switched to @import "tailwindcss")
  - [x] 11.8 Remove all --mat-sys-* CSS variable references
  - [x] 11.9 Remove Material Icons link from index.html
  - [x] 11.10 Verify @angular/cdk remains in package.json
  - [x] 11.11 All 3 tests pass; ng build --configuration=production passes

- [x] 12.0 Review and fill critical test gaps
  - [x] 12.1 Run all tests: 61 passed, 0 failed (15 test files)
  - [x] 12.2 Fixed design-system.spec.ts Tailwind import assertion
  - [x] 12.3 Production build: ng build --configuration=production PASSES

**Acceptance Criteria:**
- `@angular/material` absent from `frontend/package.json`
- `@angular/cdk` v21.2.7 present in `frontend/package.json`
- `ng build --configuration=production` exits 0
- Zero `mat-*` selectors in template files
- Zero `--mat-sys-*` CSS variable references
- Tailwind Preflight re-enabled (or split imports kept — either valid)
- Material Icons `<link>` removed from `index.html`

---

### Task Group 12: Test Review & Gap Analysis
**Phase:** Post-implementation
**Dependencies:** All Groups 1–11
**Estimated Steps:** 5

- [ ] 12.0 Review and fill critical test gaps
  - [ ] 12.1 Review all tests written in Groups 1–11 (~41–61 tests across 11 groups)
    - Categorize by: infrastructure, components, shell, services, screens, removal
    - Identify coverage gaps for THIS redesign task only (not pre-existing coverage)
  - [ ] 12.2 Identify gaps — focus on:
    - Dark mode token cascade (light → dark transition for each new `mf-*` component)
    - `takeUntilDestroyed()` usage — no memory leaks on component destroy
    - Sidebar mobile/tablet/desktop breakpoint boundary behavior
    - `mf-dialog` CDK backdrop blur + close-on-backdrop-click (if `disableClose=false`)
    - Flashcard rating buttons ONLY appear after flip (not before)
  - [ ] 12.3 Write up to 10 additional strategic tests for identified gaps
    - Focus on: boundary conditions, error paths, and user interactions not covered
    - No exhaustive coverage — only critical gaps
  - [ ] 12.4 Run feature-specific tests only (expect 51–71 tests total)
    - Command: `ng test --include="**/core/**" --include="**/shell/**" --include="**/pages/**"` (Angular)
    - Command: `pytest tests/unit/api/test_users.py` (Python)
  - [ ] 12.5 All feature tests pass with 0 failures

**Acceptance Criteria:**
- All feature tests pass (~51–71 total)
- No more than 10 additional tests added in this group
- Critical gaps identified in 12.2 are covered

---

## Execution Order

| # | Group | Phase | Steps | Dependencies |
|---|-------|-------|-------|-------------|
| 1 | Build System Setup | 0 | 7 | None |
| 2 | Design System (Tokens + Styles) | 0 | 7 | Group 1 |
| 3 | Core Services + Backend Stub | 0 | 10 | Group 2 |
| 4 | Base mf-* Components | 1 | 12 | Group 3 |
| 5 | Advanced mf-* Components | 1 | 12 | Group 4 |
| 6 | Shell Refactor | 2 | 14 | Group 5 |
| 7 | MatSnackBar + MatDialog Migration | 3 | 8 | Group 6 |
| 8 | Simple Screens (Login + KB) | 4 | 14 | Group 7 |
| 9 | Medium Screens (Docs + Quiz + Flashcards + Search) | 4 | 18 | Group 7 |
| 10 | Complex Screens (Chat + Concept Map) | 4 | 16 | Group 7 |
| 11 | Angular Material Removal | 5 | 11 | Groups 8, 9, 10 |
| 12 | Test Review & Gap Analysis | Post | 5 | Group 11 |

**Note:** Groups 8, 9, 10 (Phase 4 screen redesigns) depend on Group 7 completing — but can be executed in any order relative to each other (each screen is independent). The numbered execution order above is the recommended sequential order.

---

## Risk Flags Summary

| # | Risk | Mitigation |
|---|------|-----------|
| R1 | Tailwind Preflight conflicts with Angular Material during migration | Use `@import "tailwindcss/theme"` + `@import "tailwindcss/utilities"` ONLY — never `@import "tailwindcss"` until Phase 5 |
| R2 | Build fails after Tailwind install | Verify `@tailwindcss/postcss` v4 in package.json, `postcssConfiguration` path correct in `angular.json` |
| R3 | Flashcard 3D animation broken | Copy animation CSS verbatim — never rewrite. Verify `transform-style: preserve-3d` and `backface-visibility: hidden` unchanged |
| R4 | FR-9 step order violation | Remove ALL `MatXModule` imports → `ng build` clean → ONLY THEN `npm uninstall @angular/material` |
| R5 | MatSnackBar missed in one of 9 consumers | Run `grep -r "MatSnackBar" frontend/src/app/pages/` after Group 7 — must be empty |
| R6 | `mf-dialog` uses wrong Dialog import | Must import from `@angular/cdk/dialog` — NOT `@angular/material/dialog` |
| R7 | Dark mode token values wrong | Use only spec.md Design Token Reference table values — supersedes feature-spec.md |
| R8 | `cy.resize()` not called after panel open | Call `setTimeout(() => this.cy.resize(), 210)` — 210ms to let CSS transition complete first |
| R9 | Shell breaks on tablet breakpoint | Test at 768px and 1024px explicitly — sidebar collapsed default on tablet, expanded on desktop |
| R10 | Polish strings accidentally changed | Spot-check each screen in steps X.5/X.7 — never change user-visible Polish text |

---

## Standards Compliance

Follow standards from `.maister/docs/standards/`:
- `global/` — Always applicable (naming, error handling, testing)
- `frontend/` — Angular patterns: `ChangeDetectionStrategy.OnPush`, `inject()` DI, signals, `@if`/`@for`, `takeUntilDestroyed()`
- `backend/` — FastAPI router pattern, Pydantic models, `get_current_user` dependency

### Angular Patterns (All New Components)
- `ChangeDetectionStrategy.OnPush` on every new component
- `inject()` for all dependency injection — no constructor injection
- Signal-based state: `signal()`, `computed()`, `effect()` for local state
- `@if` / `@for` control flow — not `*ngIf` / `*ngFor`
- `takeUntilDestroyed()` for all Observable subscriptions in components

### Backend Patterns
- `mindforge/api/routers/users.py` follows same auth dependency pattern as `auth.py` and `quiz.py`
- `UserStatsResponse` in `schemas.py` and TypeScript `api.models.ts` must have identical field names
- No domain, application, or agent imports in the new router — pure stub

### CSS Architecture
- `--mf-*` tokens for all color, spacing, shadow, radius, transition values
- Tailwind utilities for layout (flex, grid, spacing, sizing)
- No inline `style=""` except dynamic values (e.g., Cytoscape, progress width)
- Dark mode via CSS custom property override in `[data-theme="dark"]` — no JavaScript class toggling
