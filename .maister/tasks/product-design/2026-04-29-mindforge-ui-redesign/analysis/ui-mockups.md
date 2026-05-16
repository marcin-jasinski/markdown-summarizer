# UI Mockups — MindForge UI Redesign

**Generated**: 2026-04-29
**Task Path**: `.maister/tasks/product-design/2026-04-29-mindforge-ui-redesign`
**Feature Type**: Enhancement (full visual redesign of existing screens)

---

## Screen 1: Dashboard — Knowledge Bases Grid

### ASCII Mockup

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOOLBAR (56px, surface-1, border-bottom)                                     │
│ [☰]  Knowledge Bases                                   [🌙]  [A▾]           │
├─────────────────────────┬────────────────────────────────────────────────────┤
│ SIDEBAR (240px)         │  PAGE CONTENT (surface-2, p-8)                    │
│ ┌───────────────────┐   │                                                    │
│ │ ◈  MindForge      │   │  Knowledge Bases            [+ New Knowledge Base]│
│ └───────────────────┘   │  ─────────────────────────────────────────────────│
│                         │                                                    │
│  GLOBAL                 │  ┌──────────────┐ ┌──────────────┐ ┌────────────┐│
│  ◈  Dashboard           │  │▓▓▓▓▓▓▓▓▓▓▓▓▓▓│ │▓▓▓▓▓▓▓▓▓▓▓▓▓▓│ │▓▓▓▓▓▓▓▓▓▓▓▓││
│  📚 Knowledge Bases ◀   │  │ (indigo top) │ │ (indigo top) │ │(indigo top)││
│  🔍 Search              │  │              │ │              │ │            ││
│  💬 Chat                │  │ (📚) Biology │ │ (📚) Physics │ │(📚) Math   ││
│                         │  │      bold    │ │      bold    │ │    bold    ││
│                         │  │ 3 docs · 🇵🇱  │ │ 5 docs · 🇵🇱  │ │2 docs · 🇵🇱 ││
│                         │  │              │ │              │ │            ││
│                         │  │ Intro to     │ │ Mechanics &  │ │ Calculus   ││
│                         │  │ cell biology │ │ wave theory  │ │ & limits   ││
│                         │  │ concepts...  │ │ fundamentals │ │ review...  ││
│                         │  │ ──────────── │ │ ──────────── │ │ ──────────  ││
│                         │  │ [📄] [⚡] [💬]│ │ [📄] [⚡] [💬]│ │[📄] [⚡] [💬]││
│                         │  └──────────────┘ └──────────────┘ └────────────┘│
│                         │                                                    │
│  ─────────────────────  │                                                    │
│  🔥 7 days   📚 12 due  │                                                    │
└─────────────────────────┴────────────────────────────────────────────────────┘
```

**Legend**:
- `◀` = active nav item (indigo bg, indigo text, primary-subtle)
- `▓▓▓` = 4px solid indigo top border on card (`border-t-4 border-t-[--mf-primary]`)
- `(📚)` = 40px icon circle (primary-subtle bg, indigo icon)
- `[📄] [⚡] [💬]` = ghost icon buttons: Documents, Start Quiz, Open Chat
- `[A▾]` = 32px avatar circle + dropdown trigger

**Annotation Notes**:
- Toolbar breadcrumb shows active page name ("Knowledge Bases") with no KB context prefix since this is the global list page.
- KB card grid uses `grid-cols-[repeat(auto-fill,minmax(280px,1fr))]` — 3 columns shown here at ~1200px wide viewport.
- Each card footer divider `──────` separates metadata from action zone; icon buttons use CDK Tooltip on hover.
- Sidebar gamification footer `🔥 7 days  📚 12 due` is always visible; clicking navigates to flashcards.
- Sidebar active item (`Knowledge Bases`) renders with `bg-[--mf-primary-subtle] text-[--mf-primary]`.

---

## Screen 2: Concept Map

### ASCII Mockup

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOOLBAR (56px)                                                               │
│ [☰]  Biology › Concept Map                              [🌙]  [A▾]          │
├─────────────────────────┬───────────────────────────────────┬────────────────┤
│ SIDEBAR (240px)         │  CANVAS  (surface-2 / #F8F9FA)   │ SIDE PANEL     │
│ ┌───────────────────┐   │                                   │ (280px)        │
│ │ ◈  MindForge      │   │     ╔ [+] [-] [⊡] [↺] ╗         │ ─────────────  │
│ └───────────────────┘   │     ║  floating toolbar  ║        │ CONCEPT        │
│                         │     ╚════════════════════╝        │                │
│  Biology                │                                   │ Mitochondria   │
│  LEARN                  │   ┌────────────────────────────┐  │ ─────────────  │
│  ⚡  Quiz               │   │       [Cell Biology]       │  │ Definition     │
│  🃏  Flashcards          │   │     ╭───────────────╮      │  │                │
│  KNOWLEDGE              │   │ ╭───┤ Mitochondria  ├───╮  │  │ Organelle      │
│  📄  Documents          │   │ │   │  (selected) ◀ │   │  │  │ responsible    │
│  ✦   Concepts      ◀   │   │ │   ╰───────────────╯   │  │  │ for ATP energy │
│  VISUALISE              │   │ │          │            │  │  │ production in  │
│  🔍  Search             │   │ ╰──────────────────────╯  │  │  │ eukaryotic     │
│  💬  Chat               │   │                            │  │  │ cells.         │
│                         │   │  ╭──────╮  ╭──────────╮  │  │  │                │
│                         │   │  │ ATP  │  │ Membrane │  │  │  │ Related        │
│                         │   │  ╰──────╯  ╰──────────╯  │  │  │ [Cell] [ATP]   │
│                         │   │                            │  │  │ [Organelle]    │
│                         │   │  ╭────────╮  ╭─────────╮  │  │  │                │
│                         │   │  │ Nucleus│  │Cytoplasm│  │  │  │ [Ask AI ✦]     │
│  ─────────────────────  │   │  ╰────────╯  ╰─────────╯  │  │  │ [View in docs] │
│  🔥 7 days   📚 12 due  │   └────────────────────────────┘  │ ─────────────  │
└─────────────────────────┴───────────────────────────────────┴────────────────┘
```

**Legend**:
- Floating toolbar `╔ [+] [-] [⊡] [↺] ╗` = Zoom In, Zoom Out, Fit to view, Reset; centered absolute above canvas.
- Selected node `(selected) ◀` renders with `bg-[#EEF2FF] border-[#5B4FE9] border-2.5`.
- `[Cell Biology]` center node is `type="main"` — solid indigo fill, white text, no border.
- `╭──────╮` rounded-rectangle nodes = white bg, `border-color: #C7D2FE` (indigo-200), Inter 12px.
- Thin lines between nodes = `line-color: #CBD5E1` bezier edges with small arrowheads.
- Side panel slides in from right on node tap; `[Ask AI ✦]` = primary button; `[View in docs]` = secondary button.
- `[Cell] [ATP] [Organelle]` = `mf-chip` pill badges in related concepts section.

**Annotation Notes**:
- Breadcrumb `Biology › Concept Map` identifies the KB context in the toolbar.
- Side panel is `@if (selectedNode())` — hidden when no node is selected; canvas expands to fill the space.
- `✦  Concepts` nav item is active (user is on the concepts/map page).
- Floating toolbar uses `position: absolute; top: 12px; left: 50%; transform: translateX(-50%)` over the canvas.
- On mobile, the side panel becomes a full-width bottom sheet overlay.

---

## Screen 3: Flashcards Screen

### ASCII Mockup

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOOLBAR (56px)                                                               │
│ [☰]  Biology › Flashcards                               [🌙]  [A▾]          │
├─────────────────────────┬────────────────────────────────────────────────────┤
│ SIDEBAR (240px)         │  PAGE CONTENT (surface-2, py-8 px-4)              │
│ ┌───────────────────┐   │                                                    │
│ │ ◈  MindForge      │   │       ┌──────────────────────────────────────┐    │
│ └───────────────────┘   │       │  max-width: 600px  (centered)        │    │
│                         │       │                                       │    │
│  Biology                │       │  Card 7 / 42              (text-sm)  │    │
│  LEARN                  │       │  ████████████░░░░░░░░░░░░░░░░░░░░░   │    │
│  ⚡  Quiz               │       │  (indigo progress bar, 6px tall)     │    │
│  🃏  Flashcards    ◀   │       │                                       │    │
│  KNOWLEDGE              │       │  ┌─────────────────────────────────┐ │    │
│  📄  Documents          │       │  │  QUESTION          (text-xs)    │ │    │
│  ✦   Concepts           │       │  │                                 │ │    │
│  VISUALISE              │       │  │                                 │ │    │
│  🔍  Search             │       │  │   What is the primary function  │ │    │
│  💬  Chat               │       │  │   of mitochondria in eukaryotic │ │    │
│                         │       │  │   cells?                        │ │    │
│                         │       │  │                                 │ │    │
│                         │       │  │                                 │ │    │
│                         │       │  │         Tap to flip ↩           │ │    │
│                         │       │  │         (text-xs tertiary)      │ │    │
│                         │       │  └─────────────────────────────────┘ │    │
│                         │       │                                       │    │
│                         │       │  ╭────────╮╭────────╮╭────────╮╭────────╮│    │
│  ─────────────────────  │       │  │ Again  ││  Hard  ││  Good  ││  Easy  ││    │
│  🔥 7 days   📚 12 due  │       │  │ (red)  ││(orange)││(indigo)││(green) ││    │
│                         │       │  ╰────────╯╰────────╯╰────────╯╰────────╯│    │
└─────────────────────────┴───────┴──────────────────────────────────────────┴────┘
```

**Legend**:
- `████████████░░░░░░░░` = `mf-progress` bar — filled portion is `--mf-primary` (indigo), remainder is `surface-3`.
- Card box is `mf-card` with `border-radius: --mf-radius-xl (20px)`, `min-height: 280px`, flex-col centered content.
- `QUESTION` label = `text-xs font-semibold uppercase tracking-widest text-tertiary` (top-left of card).
- Question text = `text-xl font-medium` centered in card body.
- `Tap to flip ↩` = `text-xs text-tertiary mt-4` — disappears after flip.
- Rating buttons `╭────────╮` = pill shape (`border-radius: --mf-radius-full`), color-coded borders and text.

**Annotation Notes**:
- Rating buttons (`Again`, `Hard`, `Good`, `Easy`) fade in only after the card is flipped to the answer side.
- Card flip uses existing 3D CSS `perspective`/`rotateY` animation — only surfaces are restyled.
- Card back (`ANSWER` side) uses `bg-[--mf-primary-subtle]` with an indigo-tinted border.
- Progress bar sits directly below the "Card N / 42" counter — no gap between counter and bar.
- `🃏 Flashcards` nav item is active in the sidebar.

---

## Screen 4: Quiz Screen — Evaluated State

### ASCII Mockup

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOOLBAR (56px)                                                               │
│ [☰]  Biology › Quiz                                     [🌙]  [A▾]          │
├─────────────────────────┬────────────────────────────────────────────────────┤
│ SIDEBAR (240px)         │  PAGE CONTENT (surface-2, py-8 px-4)              │
│ ┌───────────────────┐   │                                                    │
│ │ ◈  MindForge      │   │         ┌────────────────────────────────────┐    │
│ └───────────────────┘   │         │  max-width: 680px  (centered)      │    │
│                         │         │                                     │    │
│  Biology                │         │  ✓  4/5  (emerald icon, bold text) │    │
│  LEARN                  │         │                                     │    │
│  ⚡  Quiz         ◀   │         │  Great answer! You correctly        │    │
│  🃏  Flashcards          │         │  identified the core function and  │    │
│  KNOWLEDGE              │         │  provided an accurate example of   │    │
│  📄  Documents          │         │  ATP synthesis in the context of   │    │
│  ✦   Concepts           │         │  aerobic respiration.              │    │
│  VISUALISE              │         │                                     │    │
│  🔍  Search             │         │  ┄┄┄┄ Your answer ┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │    │
│  💬  Chat               │         │  ┆ "Mitochondria produce ATP via  ┆ │    │
│                         │         │  ┆  oxidative phosphorylation in  ┆ │    │
│                         │         │  ┆  the electron transport chain  ┆ │    │
│                         │         │  ┆  during cellular respiration." ┆ │    │
│                         │         │  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │    │
│                         │         │                                     │    │
│                         │         │              [Next Question ▶]  [Done]  │    │
│  ─────────────────────  │         │              (primary btn)   (ghost)│    │
│  🔥 7 days   📚 12 due  │         └────────────────────────────────────┘    │
└─────────────────────────┴────────────────────────────────────────────────────┘
```

**Legend**:
- `✓  4/5` = 40px emerald checkmark icon + `text-2xl font-bold` score in `--mf-correct` (#10B981) color (score ≥ 4).
- Feedback block = `text-sm` body text in `--mf-text-primary`.
- `┄┄┄ Your answer ┄┄┄` = section divider with centered label, `text-xs text-secondary`.
- `┆ "..." ┆` = quoted block: `bg-[--mf-surface-3] border-l-4 border-[--mf-border] italic text-sm text-secondary px-4 py-3 rounded-md`.
- `[Next Question ▶]` = `mfButton variant="primary"`, `[Done]` = `mfButton variant="ghost"`, both right-aligned.

**Annotation Notes**:
- Score color is dynamic: ≥4 → emerald (`#10B981`), 3 → indigo (`--mf-primary`), 2 → amber (`#F59E0B`), ≤1 → red (`#EF4444`).
- The entire evaluated state is displayed in a single `mf-card` with `p-6`; the question text is **not** repeated (grading context only).
- `[Next Question ▶]` is `disabled` when the quiz has ended; `[Done]` navigates back to the KB overview.
- Answer quote block uses `border-l-4` left-accent style, consistent with the `Documents` and `Chat` screen quote patterns.
- `⚡ Quiz` nav item is active in sidebar.

---

## Reusable Components Reference

| Component | File (to be created) | Used in |
|---|---|---|
| `mf-card` | `frontend/src/app/core/components/card/` | All 4 screens |
| `mf-button` | `frontend/src/app/core/components/button/` | All 4 screens |
| `mf-chip` | `frontend/src/app/core/components/chip/` | Concept Map side panel |
| `mf-progress` | `frontend/src/app/core/components/progress/` | Flashcards |
| `app-sidebar` | `frontend/src/app/shell/sidebar/` | All 4 screens |
| `app-toolbar` | `frontend/src/app/shell/toolbar/` | All 4 screens |
| Gamification footer | `app-sidebar` (inner widget) | All 4 screens |
| Concept side panel | `frontend/src/app/pages/concepts/node-detail-panel/` | Concept Map |

---

## Consistency Checklist

- ✅ All 4 screens share identical toolbar (56px, surface-1, same right-side actions)
- ✅ All 4 screens share identical sidebar (240px, section labels, gamification footer)
- ✅ Active nav item uses `bg-[--mf-primary-subtle] text-[--mf-primary]` consistently
- ✅ Page background is `surface-2` (#F8F9FA) on all screens
- ✅ Cards use `mf-card` with `radius-xl` and `shadow-md` everywhere
- ✅ Buttons use `mfButton` variants — no ad-hoc button styling
- ✅ Typography follows spec: h1 = `text-2xl font-bold tracking-tight`, labels = `text-xs uppercase tracking-widest`
- ✅ Breadcrumb in toolbar reflects KB context on all KB-scoped screens

---

*Generated by ui-mockup-generator agent — 2026-04-29*
