# Problem Statement — MindForge UI Redesign

**Phase**: 2 — Problem Exploration
**Approved**: 2026-04-29

---

## Problem Statement

MindForge is a capable AI-powered learning tool held back by a visual design that feels heavy, dated, and uninspiring. The current dark-mode-only interface with Roboto font and saturated violet/cyan palette creates cognitive fatigue rather than the focus and inspiration that effective studying requires. The concept map — arguably the most visually distinctive feature — looks like it was built in 2005 (thick borders, poor colors, poor typography, no meaningful interaction).

The core challenge: **transform MindForge into an app that feels as beautiful as it is smart**, so that opening it feels like entering a calm, focused, inspiring study environment — not a developer debug console.

## Emotional Target

> "Inspiring and calm, focused"

A user opening MindForge should immediately feel that this is a tool worthy of serious study. Not overwhelming. Not corporate. Not like homework. Like a premium, thoughtful environment that respects their time and intelligence.

## Identified Root Causes of "Heavy" Feeling

1. **Dark mode only** — no breathing room, saturated backgrounds dominate the entire viewport
2. **No surface hierarchy** — all dark surfaces merge visually
3. **Roboto font** — utilitarian Material default, not distinctive or refined
4. **Concept map** — colors, thick borders, typography all dated; lacks modern graph aesthetic
5. **No visible gamification** — streak, due cards, progress invisible at a glance
6. **Dense sidebar** — no visual grouping or whitespace between navigation sections
7. **Redundant toolbar** — "MindForge" appears in both toolbar and sidebar simultaneously

## Priority Screen

The **Concept Map** is the most broken screen and the top redesign priority. It is also potentially the most spectacular screen if done well — a beautiful knowledge graph is a showpiece. Get this right and the rest of the redesign follows naturally.

## Constraints

| Constraint | Value |
|---|---|
| Screen sizes | All — desktop, tablet, mobile (responsive) |
| Light/Dark mode | Light as default + dark mode as toggleable option |
| UI library | **Open** — can switch from Angular Material 3 if it enables better outcomes |
| Backend API | Unchanged |
| Language/content | Polish content preserved exactly as-is |
| Angular framework | Stay on Angular 21 (standalone, Signals, OnPush) |

## Success Criteria

1. The app opens to a light, airy interface that evokes "calm focus"
2. The concept map is the showpiece screen — modern graph styling, refined typography, meaningful interaction
3. Inter font used throughout — no Roboto
4. Indigo/violet primary + amber accent palette in light mode
5. Collapsible sidebar (icon-only 64px, hover/toggle to expand at ~240px)
6. Subtle gamification visible in sidebar (streak count + due-card count)
7. New logo mark for MindForge (still named "MindForge")
8. Dark mode toggle works correctly with the same modern aesthetic
9. WCAG AA contrast maintained in both light and dark modes
10. All 8 screens redesigned: Login, Dashboard/KBs, Documents, Concept Map, Quiz, Flashcards, Search, Chat
11. Fully responsive across all screen sizes

## Key Assumptions

- The redesign is primarily CSS/theme changes + component restructuring (no backend changes)
- Cytoscape.js (used by concept map) can be restyled via its stylesheet API
- Angular Material 3's `--mat-sys-*` tokens can be overridden to match the new design system
- Inter font is available via Google Fonts (free, no licensing cost)
- The existing 3D flashcard flip animation is a valuable interaction — preserve and enhance it
