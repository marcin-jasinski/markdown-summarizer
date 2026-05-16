# Design Research Findings

## Learning SaaS UI Trends 2026

### Key Trends

- **Light-mode primary** is the default for all major learning/productivity SaaS apps in 2026 (Quizlet, Notion, Linear, Khan Academy, Coursera). Dark mode is offered as an option, not the default.
- **Airy layouts with white space as structure**: cards float on white/near-white backgrounds. Borders are mostly eliminated in favour of subtle `box-shadow` and background-colour tiers.
- **Radical border-radius increase**: interactive cards `16–20px`, buttons `8–12px`, chips/tags full-pill `border-radius: 999px`. Squircle shapes in avatars.
- **Expressive restraint**: one vivid primary accent (violet/indigo/sky-blue) on a near-white surface + one warm accent (amber/coral) for CTA. No multi-colour chaos.
- **Soft gradients in confined regions**: hero strips, progress rings, card headers — not body backgrounds. Common: `#5B4FE9 → #A78BFA` (indigo-to-lavender).
- **Spring-physics microinteractions** (Material 3 Expressive 2025): bounce on correct/incorrect state, haptic-style scale `0.97` on button press.
- **Loading skeletons** everywhere instead of spinners. Pulse animation `opacity: 0.4 → 1`.
- **Left sidebar, collapsible** is the dominant SaaS navigation pattern (Notion, Linear, Figma, Slack all use this).
- **Gamification signals** standard in learning apps: streak counter (fire icon + number), XP bar, "due today" badge on decks, completion checkmarks.

### Exemplary Apps and Why

| App | Why Benchmark | Takeaways for MindForge |
|---|---|---|
| **Linear** | Best-in-class SaaS UI 2026 — minimal chrome, data density, keyboard-first | Copy the sidebar structure, monochrome base, "ultra-clean" aesthetic |
| **Notion** | Information hierarchy done gracefully; sidebar navigation with collapsible sections | Vertical nav with icon+label mode, block-based content areas |
| **Quizlet** | Flashcard UX benchmark; swipe + tap-to-flip; confidence-colour scheme | Full-screen flashcard mode, `[Again][Hard][Good][Easy]` SRS buttons |
| **Duolingo** | Gamification champion; streak/XP visible on every screen | Streak chip in sidebar/header, progress bar below username, lesson completion nodes |
| **Khan Academy** | Calm, accessible; wide question cards, step-by-step quiz flow | `max-width: 720px` question container, large tap-target answer options |
| **Anki (AnkiWeb)** | Algorithmic leader but visually dated | **What NOT to do**: no whitespace, grey monotone, table-heavy layouts |

### Color Palette Patterns

**Recommended MindForge Light Palette**:
```
Primary:        #5B4FE9   (indigo-violet — "intelligent, scholarly")
Primary Light:  #EEF0FF   (tint for backgrounds, chips)
Accent CTA:     #F59E0B   (amber — urgency, gamification "fire")
Correct:        #10B981   (emerald green)
Incorrect:      #EF4444   (red)
Hard/Partial:   #F59E0B   (amber)

Surfaces:
--surface-0:  #FFFFFF    (modals, active cards)
--surface-1:  #F8F9FA    (page background)
--surface-2:  #F0F2F5    (sidebar background)
--surface-3:  #E8EBF0    (hover states)
--border:     #E5E7EB

Text:
--text-primary:   #111827
--text-secondary: #6B7280
--text-muted:     #9CA3AF
```

**Rationale**: Violet primary builds on existing MindForge brand (already using `mat.$violet-palette`). Shifting to light mode surfaces makes the violet pop rather than blend.

### Layout Patterns

**Dashboard**:
- Top gamification strip: streak counter chip + XP progress bar + "N items due today" badge.
- Below: knowledge-base card grid, `auto-fill minmax(280px, 1fr)`, gap `16px`.
- Each KB card: gradient header strip (violet→lavender), title, description (2-line clamp), progress bar, due-count badge.

**Sidebar Navigation** (replace any current top-nav):
```
Width expanded:  240px
Width collapsed:  64px
Background:       --surface-2 (#F0F2F5)
Active item:      12% primary tint background + 3px left border in primary
Icon size:        20px
Label font:       14px / 500 weight
Section headers:  11px / ALL-CAPS / letter-spacing 0.05em / --text-muted
```
Sections: `LEARN` (Flashcards, Quiz, Chat), `KNOWLEDGE` (Knowledge Bases, Documents, Search), `VISUALISE` (Concept Map).

**Flashcard UI**:
- Central card, `min-height: 280px`, `border-radius: 20px`, `box-shadow: 0 4px 24px rgba(0,0,0,.08)`.
- Front: term centred, `2rem / 700 weight`.
- Back: answer text, `1.125rem / 400 weight`, subtle tint background.
- Below card: SRS rating buttons `[Again][Hard][Good][Easy]` — colour-coded (red/amber/primary/green).
- Above card: progress strip `"Card 7 / 42"` + thin bar.

**Quiz UI**:
- Single question per screen — current structure is correct.
- Question text: `20px / 600 weight / line-height 1.5` (increase from current `18px`).
- Progress bar across top of question card (add this).
- After answer: inline feedback card slides in below — no navigation needed.
- Score screen: circular progress ring SVG + topic breakdown chips.

**Knowledge Base / Document list**:
- Grid/list toggle stored in user preference.
- Cards with coloured gradient header, status pill badge, progress bar for pipeline state.

### Typography Patterns

**Recommended font**: Replace Roboto with **Inter** (Google Fonts, free).
- Reason: Inter is the dominant SaaS typeface in 2026 (Figma, Linear, Notion all use it). Better screen legibility at `12–16px` than Roboto. More "modern" neutral feel.
- Alternative: **Plus Jakarta Sans** for a slightly warmer/friendlier feel (more Duolingo-adjacent).

**Type Scale**:
```
12px / 400 / 1.33 — timestamps, meta
14px / 400 / 1.43 — sidebar labels, helper text
16px / 400 / 1.50 — body copy
18px / 500 / 1.44 — card titles
20px / 600 / 1.50 — quiz question text (increase from current 18px)
24px / 600 / 1.33 — page headings
30px / 700 / 1.00 — flashcard front face
36px / 700 / 1.00 — score display, streak counter
```

**Letter spacing**:
- Headings: `letter-spacing: -0.02em`
- Section labels (uppercase, 11–12px): `letter-spacing: 0.05em`
- Body: no adjustment

---

## Best Design Systems 2026

### Top Contenders for Angular SaaS

| System | Angular Support | Light Mode | Token System | Modern Feel | Recommended? |
|---|---|---|---|---|---|
| **Angular Material 3 (M3)** | Native | Excellent | `--mat-sys-*` CSS props | High (M3 Expressive 2025) | **Yes — primary** |
| **PrimeNG v21** | Native | Excellent (Aura theme) | `--p-*` CSS props | High | Yes — if more components needed |
| **Taiga UI** | Native | Strong | CSS props | High | Yes — if leaving Material |
| **Spartan/UI** | Community Angular port | Outstanding | Tailwind + Radix | Very High | Partial — adds Tailwind complexity |
| **Ant Design (ng-zorro)** | Angular port | Medium | CSS tokens (partial) | Medium — enterprise feel | No |
| **Bootstrap 5 (ngx-bootstrap)** | Port | Medium | CSS vars (limited) | Low | No |
| **Carbon (IBM)** | Community | Medium | Strong tokens | Medium — IBM feel | No (unless IBM enterprise context) |

### Recommendation for Light, Modern Aesthetic

**Primary Recommendation: Stay on Angular Material 3 + Switch to Light Mode + Custom Token Layer**

```scss
// styles.scss — the core change
html {
  @include mat.theme((
    color: (
      theme-type: light,               // ← was: dark
      primary: mat.$indigo-palette,    // ← was: violet (indigo is sharper in light mode)
      tertiary: mat.$amber-palette,    // ← was: cyan (amber is warmer, more gamification-friendly)
    ),
    typography: (
      brand-family: 'Inter',           // ← was: Roboto
      plain-family: 'Inter',
    ),
    density: 0,
  ));
}
```

**Then add a semantic token layer** (Tier 2) on top of `--mat-sys-*`:
```css
:root {
  /* Semantic tokens aliasing Material system tokens */
  --color-surface:        var(--mat-sys-surface);
  --color-surface-subtle: var(--mat-sys-surface-container-low);
  --color-text:           var(--mat-sys-on-surface);
  --color-text-muted:     var(--mat-sys-on-surface-variant);
  --color-primary:        var(--mat-sys-primary);
  --color-border:         var(--mat-sys-outline-variant);

  /* App-specific semantic tokens */
  --color-correct:        #10B981;
  --color-incorrect:      #EF4444;
  --color-streak:         #F59E0B;

  /* Layout tokens */
  --radius-card:   16px;
  --radius-button: 10px;
  --radius-chip:   999px;
  --shadow-card:   0 1px 3px rgba(0,0,0,.06), 0 4px 12px rgba(0,0,0,.06);
  --shadow-hover:  0 4px 16px rgba(0,0,0,.10), 0 8px 24px rgba(0,0,0,.08);
}
```

**Why this approach wins over switching libraries**:
1. Zero migration cost — all existing `mat-*` components keep working.
2. Light mode switch is a literal 1-word change.
3. M3 Expressive (2025) gives spring physics, new components, and modern feel.
4. Custom token layer provides a clean vocabulary for the design team in Figma.
5. Future dark mode: add `[data-theme=dark]` selector that overrides Tier 2 tokens.

### Design Token Approach

**Three-Tier Architecture** (Adobe Spectrum / Material 3 convention):

```
Tier 1 — Global / Primitive (raw values, rarely used directly in components)
├── --global-color-indigo-500: #5B4FE9
├── --global-color-amber-400: #F59E0B
├── --global-radius-lg: 16px
└── --global-shadow-md: 0 4px 12px rgba(0,0,0,.08)

Tier 2 — Semantic / Alias (intent, maps to Tier 1)
├── --color-primary:           var(--mat-sys-primary)        ← M3 generated
├── --color-surface:           var(--mat-sys-surface)        ← M3 generated
├── --color-correct:           var(--global-color-emerald-500)
├── --color-incorrect:         var(--global-color-red-400)
└── --shadow-card:             var(--global-shadow-md)

Tier 3 — Component-specific (scoped to one component)
├── --flashcard-min-height:    280px
├── --quiz-question-font-size: 20px
├── --srs-btn-good-color:      var(--color-primary)
└── --sidebar-width:           240px
```

**Key benefits of this system**:
- Designer in Figma names variables identically → zero translation friction.
- Single source of truth: changing `--color-primary` at Tier 2 updates all components.
- CSS-only, no JS runtime — fast and SSR-compatible.
- `color-mix(in oklch, var(--color-primary) 12%, transparent)` for tints — no need to define every shade.
- Dark mode: only Tier 2 tokens need overriding, not every component.

**OKLCH advantage**: Use `oklch()` for Tier 1 global colours — perceptually uniform colour space means tints stay predictable (`oklch(58% .22 264)` for indigo). CSS-native as of 2023, all modern browsers support it.
