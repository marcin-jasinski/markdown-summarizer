# Feature Specification — MindForge UI Redesign

**Phase**: 6 — Feature Specification
**Task**: Full GUI redesign — light mode, modern, beautiful
**Date**: 2026-04-29

---

## Section 1: Design Token System ✅ APPROVED

### File Structure
`frontend/src/styles/design-tokens.css`

### Full Token Definition

```css
/* =============================================
   MINDFORGE DESIGN TOKEN SYSTEM
   Structure: Primitives → Semantic → Domain
   ============================================= */

/* --- Primitive Color Palette --- */
:root {
  /* Indigo/Violet scale */
  --color-indigo-50:  #EEF2FF;
  --color-indigo-100: #E0E7FF;
  --color-indigo-200: #C7D2FE;
  --color-indigo-300: #A5B4FC;
  --color-indigo-400: #818CF8;
  --color-indigo-500: #6366F1;
  --color-indigo-600: #5B4FE9;   /* brand primary */
  --color-indigo-700: #4338CA;
  --color-indigo-800: #3730A3;
  --color-indigo-900: #312E81;

  /* Amber scale */
  --color-amber-50:  #FFFBEB;
  --color-amber-400: #FBBF24;
  --color-amber-500: #F59E0B;    /* brand accent */
  --color-amber-600: #D97706;

  /* Semantic feedback */
  --color-emerald-500: #10B981;
  --color-red-500:     #EF4444;
  --color-orange-500:  #F97316;

  /* Gray scale */
  --color-gray-50:  #F9FAFB;
  --color-gray-100: #F3F4F6;
  --color-gray-200: #E5E7EB;
  --color-gray-300: #D1D5DB;
  --color-gray-400: #9CA3AF;
  --color-gray-500: #6B7280;
  --color-gray-700: #374151;
  --color-gray-900: #111827;
}

/* --- Semantic Tokens (Light Mode Default) --- */
:root {
  /* Brand */
  --mf-primary:         var(--color-indigo-600);
  --mf-primary-hover:   var(--color-indigo-700);
  --mf-primary-subtle:  var(--color-indigo-50);
  --mf-accent:          var(--color-amber-500);
  --mf-accent-hover:    var(--color-amber-600);

  /* Surfaces (3-tier system) */
  --mf-surface-1:  #FFFFFF;      /* cards, dialogs */
  --mf-surface-2:  #F8F9FA;      /* page background */
  --mf-surface-3:  #F0F2F5;      /* sidebar, inputs, code blocks */

  /* Text */
  --mf-text-primary:   var(--color-gray-900);
  --mf-text-secondary: var(--color-gray-500);
  --mf-text-tertiary:  var(--color-gray-400);
  --mf-text-on-primary: #FFFFFF;

  /* Borders */
  --mf-border:        var(--color-gray-200);
  --mf-border-strong: var(--color-gray-300);

  /* Shadows */
  --mf-shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --mf-shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05);
  --mf-shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.07), 0 4px 6px -4px rgb(0 0 0 / 0.05);
  --mf-shadow-card-hover: 0 20px 25px -5px rgb(0 0 0 / 0.08), 0 8px 10px -6px rgb(0 0 0 / 0.04);

  /* Feedback */
  --mf-correct:   var(--color-emerald-500);
  --mf-incorrect: var(--color-red-500);
  --mf-warning:   var(--color-orange-500);

  /* Spacing scale */
  --mf-space-1: 4px;   --mf-space-2: 8px;   --mf-space-3: 12px;
  --mf-space-4: 16px;  --mf-space-5: 20px;  --mf-space-6: 24px;
  --mf-space-8: 32px;  --mf-space-10: 40px; --mf-space-12: 48px;

  /* Border radius */
  --mf-radius-sm:   6px;
  --mf-radius-md:   10px;
  --mf-radius-lg:   16px;
  --mf-radius-xl:   20px;
  --mf-radius-full: 9999px;

  /* Transitions */
  --mf-transition-fast:   150ms ease;
  --mf-transition-normal: 250ms ease;
  --mf-transition-slow:   350ms cubic-bezier(0.4, 0, 0.2, 1);

  /* Domain-specific */
  --mf-streak-color:      var(--color-amber-500);
  --mf-graph-node:        var(--mf-primary);
  --mf-graph-edge:        var(--color-gray-300);
  --mf-graph-bg:          var(--mf-surface-3);
  --mf-sidebar-width:     240px;
  --mf-sidebar-collapsed: 64px;
  --mf-toolbar-height:    56px;
}

/* --- Dark Mode Token Overrides --- */
[data-theme="dark"] {
  --mf-surface-1:  #1C1B23;
  --mf-surface-2:  #16151C;
  --mf-surface-3:  #111018;

  --mf-text-primary:   #F3F4F6;
  --mf-text-secondary: #9CA3AF;
  --mf-text-tertiary:  #6B7280;

  --mf-border:        #2D2B38;
  --mf-border-strong: #3D3B4A;

  --mf-shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.3);
  --mf-shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.4), 0 2px 4px -2px rgb(0 0 0 / 0.3);
  --mf-shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.4), 0 4px 6px -4px rgb(0 0 0 / 0.3);

  --mf-primary-subtle:  #2D2B4A;
  --mf-graph-bg:        var(--mf-surface-2);
  --mf-graph-edge:      #3D3B4A;
}
```

### Tailwind v4 Integration

In `frontend/src/styles.scss`:
```css
@import "tailwindcss";
@import "./styles/design-tokens.css";

@theme {
  --color-primary:    var(--mf-primary);
  --color-primary-hover: var(--mf-primary-hover);
  --color-primary-subtle: var(--mf-primary-subtle);
  --color-accent:     var(--mf-accent);
  --color-surface-1:  var(--mf-surface-1);
  --color-surface-2:  var(--mf-surface-2);
  --color-surface-3:  var(--mf-surface-3);
  --color-text:       var(--mf-text-primary);
  --color-text-secondary: var(--mf-text-secondary);
  --color-text-tertiary:  var(--mf-text-tertiary);
  --color-border:     var(--mf-border);
  --color-correct:    var(--mf-correct);
  --color-incorrect:  var(--mf-incorrect);
  --color-warning:    var(--mf-warning);
  --shadow-card:      var(--mf-shadow-md);
  --shadow-card-hover: var(--mf-shadow-card-hover);
  --radius-sm:        var(--mf-radius-sm);
  --radius-md:        var(--mf-radius-md);
  --radius-lg:        var(--mf-radius-lg);
  --radius-xl:        var(--mf-radius-xl);
}
```

### WCAG AA Compliance Requirements
The following text/background pairs MUST be verified with a contrast checker before ship:
- `--mf-text-primary` on `--mf-surface-1` (light mode) — target ≥ 4.5:1
- `--mf-text-secondary` on `--mf-surface-2` (light mode) — target ≥ 4.5:1
- `--mf-text-on-primary` on `--mf-primary` — target ≥ 4.5:1
- `--mf-primary` on `--mf-primary-subtle` — used for link text — target ≥ 4.5:1
- All dark mode equivalents of the above pairs

---

## Section 2: Typography & Inter Integration ✅ APPROVED

### Font Setup

Add to `frontend/src/index.html` `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap" rel="stylesheet">
```

Base reset in `frontend/src/styles.scss`:
```css
*, *::before, *::after {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
```

Remove from `styles.scss`: all `@import url(...Roboto...)`, all `mat.typography-*` mixin calls.

### Type Scale

| Usage | Size | Weight | Letter-spacing | Tailwind utility |
|---|---|---|---|---|
| Page heading (h1) | 24px | 700 | -0.02em | `text-2xl font-bold tracking-tight` |
| Section heading (h2) | 18px | 600 | -0.01em | `text-lg font-semibold tracking-tight` |
| Sub-heading (h3) | 16px | 600 | 0 | `text-base font-semibold` |
| Body text | 14px | 400 | 0 | `text-sm` |
| Body strong | 14px | 600 | 0 | `text-sm font-semibold` |
| Question/card text | 20px | 500 | 0 | `text-xl font-medium` |
| Label — ALL CAPS | 11px | 600 | +0.08em | `text-xs font-semibold uppercase tracking-widest` |
| Caption / small | 12px | 400 | 0 | `text-xs` |
| Nav item | 14px | 500 | 0 | `text-sm font-medium` |
| Chip / badge | 12px | 500 | 0 | `text-xs font-medium` |

### Inter-Specific Conventions
- **Heading letter-spacing**: Always `tracking-tight` (`-0.02em`) for anything ≥ 18px
- **Section labels in sidebar** (LEARN, KNOWLEDGE, VISUALISE): `uppercase tracking-widest text-xs font-semibold text-[--mf-text-tertiary]`
- **Numbers** (streak, due count, scores): `font-variant-numeric: tabular-nums` for alignment
- **Concept map node labels**: Inter 13px weight-500 white, `font-family: 'Inter', sans-serif` in Cytoscape stylesheet

---

## Section 3: Shell Layout (Sidebar + Toolbar) ✅ APPROVED

### Top Toolbar (`app-toolbar` component)

**Dimensions**: `height: var(--mf-toolbar-height)` (56px)
**Background**: `var(--mf-surface-1)`
**Border**: `border-bottom: 1px solid var(--mf-border)`
**Layout**: `display: flex; align-items: center; gap: 8px; padding: 0 16px`

**Content left-to-right**:
1. `<button class="sidebar-toggle">` — hamburger icon (expanded) / arrow icon (collapsed). Toggles `sidebarCollapsed` signal.
2. **Breadcrumb** — current KB name (if inside KB context) → `/` → current page name. Global pages: just page name. Styled as `text-sm font-medium text-secondary`.
3. `<div class="spacer flex-1">` — pushes right-side actions to end
4. `<button class="theme-toggle">` — sun icon (dark mode) / moon icon (light mode). Calls `ThemeService.toggle()`.
5. **User avatar** (32×32px circle, initials or photo) + `<button>` → dropdown menu (Profile name display, Logout action).

**Remove**: "MindForge" text from toolbar. Branding lives only in sidebar.

### Sidebar (`app-sidebar` component)

**Widths**:
- Expanded: `var(--mf-sidebar-width)` = 240px
- Collapsed: `var(--mf-sidebar-collapsed)` = 64px (icon-only rail)

**Styling**:
```css
app-sidebar {
  width: var(--mf-sidebar-width);
  background: var(--mf-surface-3);
  border-right: 1px solid var(--mf-border);
  transition: width var(--mf-transition-normal);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: sticky;
  top: 0;
}
app-sidebar.collapsed { width: var(--mf-sidebar-collapsed); }
```

**State persistence**: `localStorage.setItem('mf-sidebar-collapsed', 'true'/'false')` read on init.

### Sidebar Structure (top to bottom)

```
┌──────────────────────────────────────┐
│ [Logo Mark]  MindForge               │  HEADER — wordmark hidden when collapsed
├──────────────────────────────────────┤
│ GLOBAL                               │  section label (hidden when collapsed)
│  ◈  Dashboard                        │  nav item
│  📚  Knowledge Bases                  │
├──────────────────────────────────────┤
│ [KB Name]  (when inside a KB)        │  KB context header — hidden when collapsed
│ LEARN                                │  section label
│  ⚡  Quiz                              │
│  🃏  Flashcards                        │
│ KNOWLEDGE                            │
│  📄  Documents                         │
│  ✦   Concepts                          │
│ VISUALISE                            │
│  🔍  Search                            │
│  💬  Chat                              │
├──────────────────────────────────────┤
│                 (flex-1 spacer)      │
├──────────────────────────────────────┤
│  🔥 7 days      📚 12 due            │  gamification footer widget
└──────────────────────────────────────┘
```

### Nav Item Anatomy

```css
.nav-item {
  height: 36px;
  padding: 0 12px;
  border-radius: var(--mf-radius-md);
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  color: var(--mf-text-secondary);
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  transition: background var(--mf-transition-fast), color var(--mf-transition-fast);
}
.nav-item:hover {
  background: color-mix(in srgb, var(--mf-border) 60%, transparent);
  color: var(--mf-text-primary);
}
.nav-item.active {
  background: var(--mf-primary-subtle);
  color: var(--mf-primary);
}
.nav-item .icon { font-size: 18px; flex-shrink: 0; }
.nav-item .label { /* hidden when collapsed via overflow:hidden on parent */ }
```

When collapsed: nav item shows icon only, centered. Angular CDK Tooltip (or native `title`) shows nav item label on hover.

### Gamification Footer Widget

```html
<div class="gamification-footer" (click)="navigateToFlashcards()">
  <span class="stat streak">
    <span class="icon">🔥</span>
    <span class="value">{{ streakDays() }}</span>
    <span class="label" *ngIf="!collapsed()">days</span>
  </span>
  <span class="stat due">
    <span class="icon">📚</span>
    <span class="value">{{ dueToday() }}</span>
    <span class="label" *ngIf="!collapsed()">due</span>
  </span>
</div>
```

```css
.gamification-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--mf-border);
  display: flex;
  gap: 16px;
  cursor: pointer;
  color: var(--mf-text-secondary);
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.streak { color: var(--mf-streak-color); }
/* Collapsed: flex-direction: column, gap: 8px */
```

**Data source**: New backend endpoint `GET /api/v1/users/me/stats` returning `{ streak_days: number, due_today: number }`. Loaded in `ShellComponent` on init. Shown as `—` while loading or on error (no spinner, no blocking).

**Click behavior**: Navigates to current KB's `/flashcards` if `kbId` is in route params; otherwise navigates to `/knowledge-bases`.

### Logo Mark

**New SVG mark**: Custom spark/forge symbol, 24×24px, `fill: var(--mf-primary)`. Details to be designed in Phase 7 (visual prototyping).
**Wordmark**: "MindForge" in Inter 600 weight, `color: var(--mf-text-primary)`. Hidden in collapsed state (opacity 0 + max-width 0 transition).

### Responsive Behavior

| Breakpoint | Sidebar behavior |
|---|---|
| `< 768px` (mobile) | `position: fixed; z-index: 50`, hidden off-screen left. Toolbar hamburger opens as overlay. Clicking outside closes. Implemented via Angular CDK `Dialog` or custom overlay. |
| `768px–1024px` (tablet) | In document flow, collapsed by default (64px icon rail) |
| `> 1024px` (desktop) | In document flow, expanded by default (240px) |

### Angular Component Architecture

```typescript
// ShellComponent
sidebarCollapsed = signal(this.loadSidebarState());
// persists to localStorage on change

// SidebarComponent
@Input() collapsed: boolean;
@Output() toggle = new EventEmitter<void>();
activeKbId = input<string | null>(); // from Router

// ToolbarComponent
@Input() sidebarCollapsed: boolean;
@Output() toggleSidebar = new EventEmitter<void>();
@Output() toggleTheme = new EventEmitter<void>();

// ThemeService
toggle(): void { /* flip [data-theme] on <html>, persist to localStorage */ }
isDark = signal(false);
```

---

## Section 4: Global Component Library ✅ APPROVED

All components are standalone Angular components using Tailwind CSS v4 utility classes referencing `--mf-*` design tokens. No Angular Material imports.

### Button (`mf-button`)

```html
<button mfButton variant="primary" [loading]="isLoading" [disabled]="isDisabled">
  Label
</button>
```

| Variant | Classes |
|---|---|
| Primary | `bg-[--mf-primary] text-white hover:bg-[--mf-primary-hover] active:scale-[0.97]` |
| Secondary | `border border-[--mf-border] bg-[--mf-surface-1] text-[--mf-text-primary] hover:bg-[--mf-surface-3]` |
| Ghost | `bg-transparent text-[--mf-text-secondary] hover:bg-[--mf-surface-3] hover:text-[--mf-text-primary]` |
| Danger | `bg-red-50 text-red-600 hover:bg-red-100 border border-red-200` |
| Icon | `rounded-full w-9 h-9 flex items-center justify-center` + ghost variant |

Base classes (all variants): `h-9 px-4 rounded-[--mf-radius-md] text-sm font-medium transition-all duration-150 inline-flex items-center gap-2 cursor-pointer`

Disabled: `opacity-40 cursor-not-allowed pointer-events-none`
Loading: replace content with `<div class="spinner-sm">` (14px, 2px indigo border, spin animation)

### Card (`mf-card`)

```css
.mf-card {
  background: var(--mf-surface-1);
  border-radius: var(--mf-radius-lg);
  box-shadow: var(--mf-shadow-md);
  border: 1px solid var(--mf-border);
  padding: 20px;
  transition: box-shadow var(--mf-transition-normal), transform var(--mf-transition-normal);
}
.mf-card.hoverable:hover {
  box-shadow: var(--mf-shadow-card-hover);
  transform: translateY(-2px);
}
```

### Form Field (`mf-input`, `mf-textarea`)

```html
<div class="mf-field">
  <label class="mf-label">Email</label>
  <input mfInput type="email" placeholder="you@example.com" />
  <span class="mf-helper-text">We'll never share your email.</span>
</div>
```

```css
.mf-field input, .mf-field textarea {
  width: 100%;
  border: 1px solid var(--mf-border);
  background: var(--mf-surface-3);
  border-radius: var(--mf-radius-md);
  padding: 8px 12px;
  font-size: 14px;
  color: var(--mf-text-primary);
  outline: none;
  transition: border-color var(--mf-transition-fast), box-shadow var(--mf-transition-fast);
}
.mf-field input:focus {
  border-color: var(--mf-primary);
  box-shadow: 0 0 0 3px var(--mf-primary-subtle);
}
.mf-field input.error { border-color: var(--mf-incorrect); }
.mf-label { font-size: 12px; font-weight: 600; color: var(--mf-text-secondary); margin-bottom: 4px; display: block; }
.mf-helper-text { font-size: 12px; color: var(--mf-text-tertiary); margin-top: 4px; }
.mf-helper-text.error { color: var(--mf-incorrect); }
```

### Chip / Badge

```css
.mf-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px;
  border-radius: var(--mf-radius-full);
  font-size: 12px; font-weight: 500;
  background: var(--mf-surface-3);
  color: var(--mf-text-secondary);
  white-space: nowrap;
}
.mf-chip.primary { background: var(--mf-primary-subtle); color: var(--mf-primary); }
.mf-chip.correct  { background: #ECFDF5; color: #065F46; }
.mf-chip.incorrect { background: #FEF2F2; color: #991B1B; }
.mf-chip.pending  { background: #FFFBEB; color: #92400E; }
.mf-chip.processing { background: #EEF2FF; color: #3730A3; }
```

### Skeleton Loader

```css
.skeleton {
  background: linear-gradient(90deg,
    var(--mf-surface-3) 25%,
    var(--mf-border) 50%,
    var(--mf-surface-3) 75%
  );
  background-size: 200% 100%;
  animation: skeleton-shimmer 1.5s ease-in-out infinite;
  border-radius: var(--mf-radius-md);
}
@keyframes skeleton-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

Usage:
- KB grid loading: 3 skeleton cards (`min-h-[160px]`)
- Document list loading: 4 skeleton rows (`h-12 w-full`)
- Replace all `<mat-progress-bar mode="indeterminate">` in list/grid contexts

### Dialog / Modal (`mf-dialog`)

- Angular CDK `Dialog` service + `MfDialogComponent` wrapper
- Backdrop: `rgba(0,0,0,0.4)` + `backdrop-filter: blur(4px)`
- Panel: `bg-[--mf-surface-1] rounded-[--mf-radius-xl] shadow-[--mf-shadow-lg] p-6 w-full max-w-[480px]`
- Enter animation: `scale(0.95) opacity(0)` → `scale(1) opacity(1)` over 200ms
- Close: ESC key, backdrop click, explicit close button

### Snackbar / Toast

- `position: fixed; bottom: 24px; right: 24px; z-index: 9999`
- `bg-[--mf-text-primary] text-[--mf-surface-1] rounded-[--mf-radius-md] px-4 py-3 text-sm font-medium shadow-[--mf-shadow-lg]`
- Success prefix: emerald `✓` icon; Error prefix: red `✗` icon
- Auto-dismiss: 4000ms; manual dismiss button `✕`

### Status Badges (Document Processing)

| Status | Background | Text Color | Icon |
|---|---|---|---|
| `pending` | `#FFFBEB` | `#92400E` | ⏳ |
| `processing` | `#EEF2FF` | `#3730A3` | ⟳ (spin) |
| `done` | `#ECFDF5` | `#065F46` | ✓ |
| `failed` | `#FEF2F2` | `#991B1B` | ✗ |

### Progress Bar (`mf-progress`)

```html
<div class="mf-progress" [style.--progress]="value + '%'">
  <div class="mf-progress-fill"></div>
</div>
```
```css
.mf-progress { height: 6px; background: var(--mf-surface-3); border-radius: var(--mf-radius-full); overflow: hidden; }
.mf-progress-fill { height: 100%; width: var(--progress); background: var(--mf-primary); border-radius: inherit; transition: width var(--mf-transition-slow); }
```

---

## Section 5: Screen-Specific Redesigns ✅ APPROVED

### Login Screen

**Desktop layout**: Two-column split (50/50)
- Left half: `bg-[--mf-primary]` hero panel. MindForge logo mark (white), heading "AI-powered knowledge mastery" in white Inter 700 32px, subtitle in `rgba(255,255,255,0.7)` 16px, decorative abstract spark illustration (SVG, white/translucent).
- Right half: `bg-[--mf-surface-1]` auth panel, `flex items-center justify-center`, inner card `max-w-[400px] w-full p-8`.

**Mobile**: Single column, `bg-[--mf-surface-2]`, centered card `max-w-[400px] m-auto p-8 bg-[--mf-surface-1] rounded-xl shadow-lg`.

**Auth card contents**:
1. MindForge wordmark (Inter 600, indigo primary)
2. Discord OAuth button: `bg-[#5865F2] text-white rounded-md h-10 w-full font-medium flex items-center justify-center gap-2` + Discord SVG icon
3. Divider: `<hr>` with `"or"` text centered, `text-xs text-tertiary`
4. Pill tab toggle: `"Sign In"` / `"Register"` — styled as segmented control (not Material tabs)
5. Form using `mf-input` components
6. Submit: `mf-button` primary, full-width, shows spinner when loading
7. Error message: `text-sm text-[--mf-incorrect]` below submit

### Dashboard / Knowledge Bases

**Layout**: `p-8` page padding, `bg-[--mf-surface-2]` page background.

**Page header**: flex row — `"Knowledge Bases"` `text-2xl font-bold tracking-tight` + spacer + `"New Knowledge Base"` primary button with `+` icon.

**Grid**: `grid gap-4 grid-cols-[repeat(auto-fill,minmax(280px,1fr))]`

**KB Card** (`mf-card hoverable`):
```
┌─ 4px colored top border (indigo gradient) ────────────────┐
│  [📚 icon 40px in indigo-50 circle]  KB Name (semibold)   │
│                                      3 docs · 🇵🇱 Polish   │
│  Description text (2-line clamp, text-secondary)          │
│  ─────────────────────────────────────────────────────    │
│  [Docs icon btn] [Quiz icon btn] [Chat icon btn]          │
└───────────────────────────────────────────────────────────┘
```
- Top accent: `border-t-4 border-t-[--mf-primary]`
- Icon circle: `w-10 h-10 rounded-full bg-[--mf-primary-subtle] flex items-center justify-center text-[--mf-primary]`
- Footer action buttons: ghost icon buttons with tooltips (Documents, Start Quiz, Open Chat)

**Loading state**: 3 skeleton cards in grid
**Empty state**: Center-aligned, 64px indigo spark SVG icon, `"No knowledge bases yet"` h2, `"Create your first knowledge base to get started"` body, `"Create Knowledge Base"` primary CTA

### Documents Screen

**Page header**: KB breadcrumb (`text-sm text-secondary`) / `"Documents"` h1 + `"Upload Document"` primary button.

**Upload zone**:
```css
.upload-zone {
  border: 2px dashed var(--mf-border);
  border-radius: var(--mf-radius-xl);
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all var(--mf-transition-fast);
}
.upload-zone:hover, .upload-zone.drag-active {
  border-color: var(--mf-primary);
  background: var(--mf-primary-subtle);
}
```

**Documents table**:
- `<table class="w-full">` with `border-collapse`
- Header row: `text-xs font-semibold text-secondary uppercase tracking-widest bg-[--mf-surface-3]`
- Data rows: `border-b border-[--mf-border] hover:bg-[--mf-surface-3]`
- Columns: Name + `lesson_id` (sub-row), Status (badge), Format (chip), Uploaded (date), Actions (icon button)
- Loading: 4 skeleton rows `h-12 w-full`
- Empty state within table: centered row `"No documents uploaded yet"`

### Quiz Screen

**Max-width**: 680px, centered, `py-8 px-4`.

**Idle state**: Centered, 72px indigo spark SVG, `"Quiz Mode"` h1, description text-secondary, `"Start Quiz"` primary button.

**Loading state**: Skeleton card `h-40 w-full rounded-xl` — no spinner.

**Question state**:
```
[mf-card p-6]
  [text-xs text-secondary uppercase tracking-widest mb-3] lesson: [lesson_id]
  [text-xl font-medium mb-6] [question text]
  [mf-textarea min-h-[120px] placeholder="Type your answer..."]
  [Submit Answer] primary button, right-aligned, disabled when empty
```

**Evaluated state**:
```
[mf-card p-6]
  [40px correct/incorrect icon] + [Score badge: "4/5" text-2xl font-bold colored]
  [Feedback text text-sm]
  ─── Your answer ───
  [italic quote block text-secondary text-sm]
  [Next Question] primary + [Done] ghost — right-aligned
```

Score colors: ≥4 → emerald, 3 → indigo, 2 → amber, ≤1 → red.

### Flashcards Screen

**Max-width**: 600px, centered, `py-8 px-4`.

**Progress row**: `"Card 7 / 42"` `text-sm text-secondary` + `mf-progress` bar below.

**Flip card** (preserve existing 3D CSS animation, restyle surfaces only):
```css
.card-front {
  background: var(--mf-surface-1);
  border: 1px solid var(--mf-border);
  box-shadow: var(--mf-shadow-md);
  border-radius: var(--mf-radius-xl);
}
.card-back {
  background: var(--mf-primary-subtle);
  border: 1px solid color-mix(in srgb, var(--mf-primary) 20%, transparent);
  border-radius: var(--mf-radius-xl);
}
```
- Both sides: `min-height: 280px`, `padding: 32px`, flex-col center
- Label: `"QUESTION"` / `"ANSWER"` `text-xs font-semibold uppercase tracking-widest text-tertiary`
- `"Tap to flip"` hint: `text-xs text-tertiary mt-4` — front only

**Rating buttons** (fade-in after flip):
```css
.rating-btn { border: 1px solid; border-radius: var(--mf-radius-full); padding: 6px 20px; font-size: 13px; font-weight: 500; }
.again { border-color: #FECACA; color: #DC2626; } .again:hover { background: #FEF2F2; }
.hard  { border-color: #FED7AA; color: #EA580C; } .hard:hover  { background: #FFF7ED; }
.good  { border-color: var(--mf-border); color: var(--mf-primary); } .good:hover { background: var(--mf-primary-subtle); }
.easy  { border-color: #A7F3D0; color: #059669; } .easy:hover  { background: #ECFDF5; }
```

**End state**: Large centered icon, `"🎉 All caught up!"` h2, subtitle, `"Back to Knowledge Bases"` ghost button.

### Search Screen

**Page header**: `"Search"` h1.

**Search form**: `flex gap-2` — `mf-input` with search icon prefix (flex-1) + `"Search"` primary button.

**Results list**: `flex flex-col gap-3 mt-6`

**Result card** (`mf-card p-4`):
```
[flex gap-2 mb-2]  [mf-chip] lesson_id  [mf-chip primary] 87% match
[text-sm] snippet text — matched terms in <strong>
```

### Chat Screen

**Layout**: `flex flex-col h-[calc(100vh-var(--mf-toolbar-height))] max-w-[800px] mx-auto w-full px-4`

**User bubble**: `align-self: flex-end; background: var(--mf-primary); color: white; border-radius: 18px 18px 4px 18px; padding: 10px 16px; max-width: 72%; font-size: 14px;`

**Assistant bubble**: `align-self: flex-start; background: var(--mf-surface-3); color: var(--mf-text-primary); border-radius: 18px 18px 18px 4px; padding: 10px 16px; max-width: 72%;`

**Source chips** below assistant messages: `flex flex-wrap gap-1 mt-2`

**Typing indicator**: 3 dots `w-2 h-2 rounded-full bg-[--mf-border]`, staggered scale animation.

**Input area** (`sticky bottom-0 border-t border-[--mf-border] bg-[--mf-surface-1] p-3`): `mf-textarea` auto-grow (max 4 rows) + send icon button.

**Welcome state**: Centered 64px chat SVG icon, `"Chat with your Knowledge Base"` h2, description text-secondary.

---

## Section 6: Concept Map Redesign ✅ APPROVED

### Cytoscape Stylesheet (light theme)

```javascript
const lightStylesheet = [
  {
    selector: 'node',
    style: {
      'background-color': '#FFFFFF',
      'border-width': 1.5,
      'border-color': '#C7D2FE',        // indigo-200
      'label': 'data(label)',
      'color': '#1E293B',               // --mf-text-primary
      'font-size': 12,
      'font-family': 'Inter, sans-serif',
      'font-weight': 500,
      'text-valign': 'center',
      'text-halign': 'center',
      'text-wrap': 'wrap',
      'text-max-width': '100px',
      'width': 'label',
      'height': 'label',
      'padding': '10px',
      'shape': 'round-rectangle',
    }
  },
  {
    selector: 'node:selected',
    style: {
      'background-color': '#EEF2FF',    // indigo-50
      'border-color': '#5B4FE9',        // --mf-primary
      'border-width': 2.5,
    }
  },
  {
    selector: 'node[type="main"]',
    style: {
      'background-color': '#5B4FE9',
      'color': '#FFFFFF',
      'border-width': 0,
      'font-size': 13,
      'font-weight': 700,
    }
  },
  {
    selector: 'edge',
    style: {
      'line-color': '#CBD5E1',           // slate-300
      'width': 1.5,
      'curve-style': 'bezier',
      'target-arrow-shape': 'triangle',
      'target-arrow-color': '#CBD5E1',
      'arrow-scale': 0.8,
      'label': 'data(label)',
      'font-size': 10,
      'color': '#94A3B8',               // slate-400
      'font-family': 'Inter, sans-serif',
      'edge-text-rotation': 'autorotate',
    }
  },
  {
    selector: 'edge:selected',
    style: {
      'line-color': '#5B4FE9',
      'target-arrow-color': '#5B4FE9',
    }
  }
];
```

**Canvas background**: `background: var(--mf-surface-2)` (`#F8F9FA`).

### Floating Toolbar

`position: absolute; top: 12px; left: 50%; transform: translateX(-50%); z-index: 10`
`background: var(--mf-surface-1); border: 1px solid var(--mf-border); border-radius: var(--mf-radius-lg); padding: 4px; display: flex; gap: 2px; box-shadow: var(--mf-shadow-md)`

Buttons: Zoom in (+), Zoom out (−), Fit (⊡), Reset layout (↺) — all `mf-button icon ghost`

### Node Detail Side Panel

**Angular signals**:
```typescript
selectedNode = signal<CyNode | null>(null);
panelVisible = computed(() => this.selectedNode() !== null);

ngAfterViewInit() {
  this.cy = cytoscape({ container: this.cyContainer.nativeElement, stylesheet: lightStylesheet, ... });

  this.cy.on('tap', 'node', (evt) => {
    const n = evt.target;
    this.selectedNode.set({ id: n.id(), label: n.data('label'), definition: n.data('definition'), type: n.data('type') });
    setTimeout(() => this.cy.resize(), 210);
  });
  this.cy.on('tap', (evt) => {
    if (evt.target === this.cy) {
      this.selectedNode.set(null);
      setTimeout(() => this.cy.resize(), 160);
    }
  });
}
```

**Template**:
```html
<div class="concept-map-wrapper relative w-full h-full overflow-hidden">
  <div #cyContainer [class.panel-open]="panelVisible()"
       class="cy-container w-full h-full transition-[width] duration-200"></div>

  @if (panelVisible()) {
    <aside class="node-panel" [@panelSlide]>
      <div class="panel-header flex justify-between items-start p-4 border-b border-[--mf-border]">
        <div>
          <p class="text-xs font-semibold uppercase tracking-widest text-[--mf-text-tertiary] mb-1">
            {{ selectedNode()?.type ?? 'Concept' }}
          </p>
          <h3 class="text-lg font-semibold text-[--mf-text-primary]">{{ selectedNode()?.label }}</h3>
        </div>
        <button mfButton variant="icon" (click)="selectedNode.set(null)">✕</button>
      </div>

      <div class="panel-body p-4 overflow-y-auto flex-1 flex flex-col gap-5">
        @if (selectedNode()?.definition) {
          <section>
            <p class="text-xs font-semibold uppercase tracking-widest text-[--mf-text-tertiary] mb-2">Definition</p>
            <p class="text-sm text-[--mf-text-primary] leading-relaxed">{{ selectedNode()?.definition }}</p>
          </section>
        }

        @if (relatedConcepts().length) {
          <section>
            <p class="text-xs font-semibold uppercase tracking-widest text-[--mf-text-tertiary] mb-2">Related</p>
            <div class="flex flex-wrap gap-1">
              @for (concept of relatedConcepts(); track concept.id) {
                <button class="mf-chip cursor-pointer hover:bg-[--mf-primary-subtle] hover:text-[--mf-primary]"
                        (click)="selectNodeById(concept.id)">
                  {{ concept.label }}
                </button>
              }
            </div>
          </section>
        }

        <section class="mt-auto flex flex-col gap-2">
          <button mfButton variant="ghost" class="w-full justify-start gap-2 text-sm">✦ Ask AI about this</button>
          <button mfButton variant="ghost" class="w-full justify-start gap-2 text-sm">📄 View in documents</button>
        </section>
      </div>
    </aside>
  }
</div>
```

**Panel CSS**:
```css
.node-panel {
  position: absolute; right: 0; top: 0; bottom: 0; width: 280px;
  background: var(--mf-surface-1);
  border-left: 1px solid var(--mf-border);
  box-shadow: -4px 0 16px rgba(0,0,0,0.06);
  display: flex; flex-direction: column; z-index: 20;
}
.cy-container.panel-open { width: calc(100% - 280px); }
```

**Slide animation**:
```typescript
trigger('panelSlide', [
  transition(':enter', [
    style({ transform: 'translateX(100%)' }),
    animate('200ms ease-out', style({ transform: 'translateX(0)' }))
  ]),
  transition(':leave', [
    animate('150ms ease-in', style({ transform: 'translateX(100%)' }))
  ])
])
```

---

## Section 7: Dark Mode System ✅ APPROVED

### Token Overrides

`[data-theme="dark"]` block in `design-tokens.css`:
```css
[data-theme="dark"] {
  /* Surfaces — deep navy, not pure black */
  --mf-surface-1: #0F1117;
  --mf-surface-2: #161B27;
  --mf-surface-3: #1E2535;

  /* Text */
  --mf-text-primary:    #F8FAFC;
  --mf-text-secondary:  #94A3B8;
  --mf-text-tertiary:   #475569;
  --mf-text-disabled:   #334155;

  /* Border */
  --mf-border: rgba(255, 255, 255, 0.08);

  /* Primary — stays indigo */
  --mf-primary:        #5B4FE9;
  --mf-primary-hover:  #4A3ED8;
  --mf-primary-subtle: rgba(91, 79, 233, 0.15);

  /* Shadows */
  --mf-shadow-sm:         0 1px 2px rgba(0,0,0,0.4);
  --mf-shadow-md:         0 2px 8px rgba(0,0,0,0.5);
  --mf-shadow-lg:         0 8px 24px rgba(0,0,0,0.6);
  --mf-shadow-card-hover: 0 8px 20px rgba(0,0,0,0.6);
}
```

### ThemeService

`frontend/src/app/core/services/theme.service.ts`:
```typescript
import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly STORAGE_KEY = 'mf-theme';
  isDark = signal(false);

  constructor() {
    const saved = localStorage.getItem(this.STORAGE_KEY);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const dark = saved !== null ? saved === 'dark' : prefersDark;
    this.applyTheme(dark);
  }

  toggle(): void { this.applyTheme(!this.isDark()); }

  private applyTheme(dark: boolean): void {
    this.isDark.set(dark);
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
    localStorage.setItem(this.STORAGE_KEY, dark ? 'dark' : 'light');
  }
}
```

### Cytoscape Dark Stylesheet

```typescript
effect(() => {
  this.cy?.style(this.themeService.isDark() ? darkStylesheet : lightStylesheet);
});
```

Dark overrides: `node → background-color: #1E2535, border-color: rgba(91,79,233,0.4), color: #F8FAFC` | `edge → line-color: #334155, color: #475569`

### Smooth Transition

```css
html { transition: background-color 200ms ease, color 200ms ease; }
/* NOT transition:all — causes layout jank */
```

---

## Section 8: Migration Plan ✅ APPROVED

### Phase 1 — Install New Dependencies

```bash
cd frontend
npm install tailwindcss @tailwindcss/postcss @tailwindcss/vite
npm install @angular/cdk
```

**`frontend/postcss.config.js`** (create):
```js
module.exports = { plugins: { '@tailwindcss/postcss': {} } }
```

**`frontend/src/styles.scss`** (add at top):
```scss
@import "tailwindcss";
@import "./app/core/styles/design-tokens.css";
```

### Phase 2 — Create Design Token File

Create `frontend/src/app/core/styles/design-tokens.css` with the full Section 1 token definitions (primitives, semantic tokens, dark mode overrides, Tailwind `@theme` mapping).

### Phase 3 — Create New Component Library

Create `frontend/src/app/core/components/`:
- `mf-button/button.component.ts`
- `mf-card/card.component.ts`
- `mf-input/input.component.ts`
- `mf-chip/chip.component.ts`
- `mf-skeleton/skeleton.component.ts`
- `mf-dialog/dialog.component.ts` (CDK `Dialog`)
- `mf-snackbar/snackbar.service.ts`
- `mf-progress/progress.component.ts`

Create `frontend/src/app/core/services/theme.service.ts` (Section 7 spec).

### Phase 4 — Screen-by-Screen Migration

Replace Angular Material imports in this order (least risky → most visible):

| # | Target | M3 → replacement |
|---|---|---|
| 1 | `ThemeService` | New file (no migration) |
| 2 | `ShellComponent` | `MatSidenavModule` → `SidebarComponent` (CSS collapsible) |
| 3 | `ToolbarComponent` | `MatToolbarModule` → plain HTML + Tailwind |
| 4 | Login | `MatFormField`, `MatButton` → `mf-input`, `mf-button` |
| 5 | Dashboard / KB list | `MatCard` → `mf-card`; add skeleton states |
| 6 | Documents | `MatTable`, `MatProgressBar` → table + `mf-progress` |
| 7 | Quiz | M3 components → `mf-card`, `mf-textarea`, `mf-button` |
| 8 | Flashcards | M3 → restyle existing 3D flip CSS |
| 9 | Search | M3 → `mf-input`, `mf-card` results |
| 10 | Chat | M3 → pure CSS bubbles, `mf-input` |
| 11 | Concept Map | Restyle Cytoscape + add `NodePanelComponent` |
| 12 | Dialogs (global) | `MatDialog` → CDK `Dialog` + `mf-dialog` |
| 13 | Snackbars | `MatSnackBar` → `mf-snackbar` service |

### Phase 5 — Remove Angular Material

After all screens migrated:
```bash
npm uninstall @angular/material
```

- Remove all `MatXModule` imports from component/app files
- Remove M3 theme import from `styles.scss` (e.g., `@import "@angular/material/prebuilt-themes/..."`)
- Remove `provideAnimationsAsync()` if only used for Material (CDK animations use `BrowserAnimationsModule` separately — keep if needed)

### Phase 6 — Inter Font Swap

In `frontend/src/index.html` — replace Roboto link:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&display=swap" rel="stylesheet">
```

Remove any `Roboto` `@import` from `styles.scss`.

### New Backend Endpoint (Gamification Widget)

```
GET /api/v1/users/me/stats
Authorization: Bearer <JWT>
Response 200: { "streak_days": 7, "due_today": 12 }
```

- **streak_days**: count of consecutive days with quiz/flashcard activity in `document_interactions`
- **due_today**: count of flashcard reviews where `due_date <= now()` for the current user
- Register in `mindforge/api/routers/` (new `stats.py` or append to `users.py`)
- Add Pydantic response model `UserStatsResponse` to `mindforge/api/schemas.py`
- Add Angular model to `frontend/src/app/core/models/api.models.ts`

---

