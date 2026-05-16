# MindForge UI Redesign — Product Brief

**Status**: Ready for Implementation
**Date**: 2026-04-29
**Phase**: Product Design Complete → Handoff to Development

---

## Executive Summary

MindForge's current GUI uses a dark-only color scheme, Angular Material 3 default styles, Roboto typography, and flat component hierarchy — resulting in a heavy, visually dated look. This brief specifies a complete, implementation-ready redesign to make MindForge look **beautiful, modern, and inspiring** while preserving all backend logic and Angular 21 architecture.

**Emotional target**: Inspiring and calm, focused
**Key benchmark**: Linear, Quizlet, Notion (2025–2026)

---

## Design Decisions (Summary)

| Decision Area | Choice |
|---|---|
| UI Library | Angular CDK + Tailwind CSS v4 (replace Angular Material 3) |
| Token Architecture | Custom CSS token system (`--mf-*`) with Tailwind `@theme` |
| Concept Map | Restyle Cytoscape + 280px node detail side panel |
| Navigation | Slim top toolbar (56px) + collapsible sidebar (64px ↔ 240px) |
| Gamification | Sidebar footer widget: 🔥 streak + 📚 due count |
| Default Theme | Light mode, OS-preference-aware dark mode toggle |
| Typography | Inter variable font (replace Roboto) |
| Primary Color | `#5B4FE9` indigo-violet |

---

## Implementation Artifacts

All detailed specifications are in `.maister/tasks/product-design/2026-04-29-mindforge-ui-redesign/analysis/`:

| File | Contents |
|---|---|
| [feature-spec.md](../analysis/feature-spec.md) | Full implementation spec (Sections 1–8) |
| [ui-mockups.md](../analysis/ui-mockups.md) | ASCII mockups for 4 key screens |
| [design-decisions.md](../analysis/design-decisions.md) | 5 architectural decisions with rationale |
| [problem-statement.md](../analysis/problem-statement.md) | Root cause analysis + success criteria |
| [personas.md](../analysis/personas.md) | Alex (self-learner) + Maya (professional) |
| [design-context.md](../analysis/design-context.md) | Codebase analysis + research synthesis |

---

## Feature Spec Summary

### Section 1: Design Token System
- `design-tokens.css` with primitive → semantic → domain token hierarchy
- `--mf-surface-1/2/3` three-tier surface system
- `[data-theme="dark"]` CSS overrides for dark mode
- Tailwind `@theme` mapping for utility class integration
- WCAG AA compliant contrast ratios

### Section 2: Typography
- Inter variable font via Google Fonts (replace Roboto)
- 9-level type scale (10px–32px), all Inter weights 100–900
- Tight letter-spacing for headings, relaxed for body

### Section 3: Shell Layout
- **Toolbar** (56px): hamburger → logo → breadcrumb → spacer → theme toggle → avatar
- **Sidebar** (240px ↔ 64px): collapsible, nav items with icons + labels, gamification footer
- **Gamification footer**: 🔥 N-day streak + 📚 N due today (taps → flashcards)
- **New endpoint required**: `GET /api/v1/users/me/stats` → `{ streak_days, due_today }`

### Section 4: Global Component Library
Components: `mf-button` (4 variants), `mf-card` (hoverable), `mf-input/textarea`, `mf-chip` (5 states), skeleton loader (shimmer), CDK dialog, snackbar/toast, status badges, progress bar.

### Section 5: Screen-Specific Redesigns
8 screens: Login (split-layout hero), Dashboard (KB grid cards), Documents (upload zone + table), Quiz (3 states), Flashcards (restyled 3D flip + SRS buttons), Search (result cards), Chat (bubble layout).

### Section 6: Concept Map Redesign (Priority Screen)
- Cytoscape restyled: white nodes, indigo-200 borders, `round-rectangle` shape, Inter labels
- Main concept nodes: solid indigo fill, white text
- Canvas background: `#F8F9FA`
- Node detail side panel: 280px slide-in, Angular `@if` + `[@panelSlide]` animation, definition + related chips + AI/docs CTAs

### Section 7: Dark Mode System
- Dark surfaces: `#0F1117 / #161B27 / #1E2535` (navy, not pure black)
- `ThemeService` with OS preference detection + `localStorage` persistence
- Cytoscape reacts to theme change via `effect()`
- Smooth `200ms` background-color transition

### Section 8: Migration Plan
6-phase migration: install Tailwind + CDK → create tokens → create components → screen-by-screen M3 removal → uninstall `@angular/material` → swap Roboto → Inter.

---

## User Personas

**Alex** (self-learner, 25–35, desktop evenings): Wants calm + motivating UI, visible habit loop, progress signals. Cares about the learning streak.

**Maya** (certification professional, 28–40, desktop power user): Wants credible + impressive UI, keyboard-first navigation, the concept map as proof of intelligence.

---

## Success Criteria

1. ✓ Light mode is default, dark mode toggle in toolbar
2. ✓ Three-tier surface hierarchy eliminates flatness
3. ✓ Inter font throughout (no Roboto)
4. ✓ Concept map uses clean, modern Cytoscape styling
5. ✓ Node detail panel slide-in on node click
6. ✓ Sidebar collapsible (64px / 240px)
7. ✓ Gamification widget in sidebar footer
8. ✓ All screens redesigned with spec-defined component library
9. ✓ WCAG AA contrast on all text
10. ✓ Angular Material 3 fully removed
11. ✓ Polish content preserved throughout

---

## Priority Implementation Order

1. **Design tokens + Inter font** (Section 1+2) — foundation everything depends on
2. **Shell + Sidebar** (Section 3) — frame for all screens
3. **Component library** (Section 4) — building blocks
4. **Concept Map** (Section 6) — highest-visibility screen
5. **Remaining screens** (Section 5) — Login → Dashboard → Documents → Quiz → Flashcards → Search → Chat
6. **Dark mode** (Section 7) — after light mode is solid
7. **M3 removal** (Section 8 Phase 5) — final cleanup

---

*Product brief assembled by MindForge Product Design workflow — 2026-04-29*
