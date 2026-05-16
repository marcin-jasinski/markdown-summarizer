# MindForge UI Redesign — Design Context

**Created**: 2026-04-29
**Phase**: 1 — Context Synthesis
**Task**: Full visual redesign — light mode, modern, beautiful

---

## 1. Current State Analysis

### Tech Stack (Frontend)
- **Framework**: Angular 21 (standalone components, Signals, OnPush CD, `@if/@for`)
- **UI Library**: Angular Material 3 (v21.2.7) — already on M3, the most modern Material version
- **Theme**: Dark mode only, `color-scheme: dark`
- **Primary Palette**: Violet (`mat.$violet-palette`)
- **Tertiary Palette**: Cyan (`mat.$cyan-palette`)
- **Typography**: Roboto
- **Graph Visualization**: Cytoscape.js (Concept Map)

### Application Screens Inventory

| Screen | Route | Purpose |
|---|---|---|
| Login | `/login` | Auth with email/password + Discord OAuth |
| Dashboard | `/dashboard` or `/knowledge-bases` | KB grid overview |
| Documents | `/kb/:id/documents` | Upload & process documents |
| Concept Map | `/kb/:id/concepts` | Graph visualization |
| Quiz | `/kb/:id/quiz` | AI-generated question flow |
| Flashcards | `/kb/:id/flashcards` | 3D flip + SRS rating |
| Search | `/kb/:id/search` | Semantic/full-text search |
| Chat | `/kb/:id/chat` | RAG-grounded chat |

### Layout Architecture
- **Shell**: `<mat-sidenav-container>` with 256px sidebar + 64px sticky top toolbar
- **Sidebar**: Logo → global nav (Dashboard, Knowledge Bases) → KB-contextual nav (Docs, Concepts, Quiz, Flashcards, Search, Chat) → User menu
- **Responsive**: Side mode on desktop, overlay on mobile
- **Content area**: Router outlet, `min-height: calc(100vh - 64px)`

### Current Visual Characteristics (Before)
- ❌ **Dark mode only** — heavy, saturated, tiring for long study sessions
- ❌ **Roboto font** — generic Material default, not distinctive
- ❌ **Violet/Cyan dark theme** — high-contrast but visually fatiguing
- ✅ **Border radius already good** — 16px cards, 20px major components
- ✅ **CSS custom properties (Material tokens)** — easy to override for light mode
- ✅ **Good structural patterns** — card grids, max-width constraints, responsive layout
- ✅ **3D flip animation** — already a delightful interaction
- ✅ **Color-mix tints** — already using `color-mix(in srgb, ...)` for hover states
- ✅ **Modern Angular** — Signals, OnPush, standalone — code quality is high

### What Makes It Feel "Heavy"
1. **Dark backgrounds** saturate the entire viewport — no breathing room
2. **No surface hierarchy** visible in dark mode (all surfaces merge)
3. **Roboto** is utilitarian, not refined
4. **Missing gamification signals** visible above the fold (no streak/progress at-a-glance)
5. **Dense sidebar** — no visual grouping or whitespace between sections
6. **Top toolbar redundancy** — both toolbar title and sidebar logo show "MindForge"

---

## 2. Design Research Findings

### Learning SaaS UI Benchmarks (2026)
Best-in-class apps for reference:

| App | Key Design Virtue |
|---|---|
| **Linear** | Minimal chrome, monochrome + 1 accent, extreme clarity |
| **Quizlet** | Flashcard UX standard: SRS buttons, full-screen flip |
| **Duolingo** | Gamification standard: streak + XP always visible |
| **Notion** | Information hierarchy: collapsible sidebar, white canvas |
| **Khan Academy** | Calm quiz flow: `max-width: 720px`, large tap-targets |

### Key UI Trends for 2026
- **Light mode is the default** — all benchmark apps use light/white as primary surface
- **Airy layouts** — cards float on 3-tier surface: `#FFFFFF → #F8F9FA → #F0F2F5`
- **Borders replaced by subtle shadows** — no hard dividers, depth via shadow
- **Radical border-radius** — 16–20px cards, 8–12px buttons, full-pill chips
- **One vivid primary + one warm accent** — indigo/violet + amber/coral
- **Soft gradients only in contained regions** (card headers, progress rings)
- **Spring-physics microinteractions** — bounce on correct/incorrect, scale on press
- **Loading skeletons everywhere**, not spinners
- **Left collapsible sidebar** — industry-standard SaaS navigation
- **Gamification signals standard** — streak counter, XP bar, "due today" badge

### Recommended Color Palette
```
Primary:      #5B4FE9  (indigo-violet — scholarly + AI)
CTA Accent:   #F59E0B  (amber — streaks, urgency, CTAs)
Correct:      #10B981  (emerald green)
Incorrect:    #EF4444  (red)
Warning:      #F97316  (orange)

Surface 1:    #FFFFFF  (cards, main content)
Surface 2:    #F8F9FA  (page background)
Surface 3:    #F0F2F5  (sidebar, inputs)

Text Primary:   #111827
Text Secondary: #6B7280
Text Tertiary:  #9CA3AF
Border:         #E5E7EB
```

### Recommended Font: Inter
- Replace Roboto with **Inter** (Google Fonts, free)
- Used by Linear, Figma, Notion, Vercel — dominant SaaS font 2026
- `letter-spacing: -0.02em` for headings
- `letter-spacing: 0.05em` UPPERCASE for section labels

### Design System Recommendation
**Stay on Angular Material 3** — migration cost is near-zero.
Switch from dark to light via one Sass mixin change:
```scss
@include mat.theme((
  color: (
    theme-type: light,
    primary: mat.$indigo-palette,
    tertiary: mat.$amber-palette,
  ),
  typography: (brand-family: 'Inter', plain-family: 'Inter'),
));
```
Then add semantic token layer over `--mat-sys-*` CSS custom properties.

---

## 3. Cross-Reference Insights

### What to Keep
- The 3D flip card animation — already delightful, just restyle it
- Border radius values (16px cards, 20px major) — align with 2026 trends
- `color-mix()` hover state patterns — just update color references
- Left sidebar architecture — industry standard
- Max-width constraints (640px flashcards, 720px quiz, 860px chat) — correct
- Material 3 component structure — already modern, just reskin

### What to Change
- `theme-type: dark` → `theme-type: light`
- `mat.$violet-palette` → `mat.$indigo-palette`
- `mat.$cyan-palette` → `mat.$amber-palette` (warm, energizing accent)
- `Roboto` → `Inter` (swap via Google Fonts import)
- Top toolbar: remove redundant "MindForge" title (sidebar has logo)
- Sidebar: add visual grouping with section labels, more whitespace
- Add gamification bar to dashboard above KB grid (streak, due today count)
- Replace spinners with skeletons on key data-loading states

### New Patterns to Introduce
- **Semantic token layer** as CSS custom properties on `:root` (on top of M3 tokens)
- **3-tier surface system**: `--color-surface-1/2/3` mapped to `#FFFFFF/#F8F9FA/#F0F2F5`
- **Gamification header strip** on Dashboard (streak, due cards count, total XP)
- **Sidebar collapsible to icon-only** (64px) for more content space
- **Skeleton loaders** replacing spinners for list/card data loads
- **Progress ring** (circular) for overall knowledge mastery percentage on Dashboard

---

## 4. Implications for Design

### Transformation Summary
MindForge needs a **light mode transformation** — same structure, completely new visual feel.

The redesign is primarily:
1. **Theme flip** (dark → light) with new palette
2. **Font swap** (Roboto → Inter)
3. **Surface hierarchy** (introduce 3-tier background system)
4. **Enhanced sidebar** (collapse support, visual grouping, breathing room)
5. **Gamification layer** on Dashboard and persistent in sidebar
6. **Component polish** (shadows instead of borders, refined spacing, skeleton loaders)
7. **Screen-specific improvements** per page

### Design Constraints
- Must remain 100% Angular Material 3 (no library swap)
- All existing routes and navigation structure preserved
- Backend API unchanged — no schema changes
- Polish language content preserved where present
- Must maintain WCAG AA contrast ratios in light mode (especially important since light on light can fail)
- Responsive behavior preserved (desktop/mobile breakpoints)

### Success Criteria (Preliminary)
- The app should feel like it belongs next to Linear, Notion, or Quizlet
- Screenshots of the redesign should be immediately recognizable as "modern SaaS"
- Light surfaces dominate — no dark backgrounds by default
- Inter font is visible and readable at all sizes
- The gamification signals (streak, due cards) are visible without navigating
- First-time users should not need a tutorial for navigation
