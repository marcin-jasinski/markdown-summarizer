# Research Context — MindForge UI Redesign

Sourced from: `.maister/tasks/product-design/2026-04-29-mindforge-ui-redesign/`

## Key Artifacts

- **Feature Spec (8 sections)**: `analysis/feature-spec.md`
- **UI Mockups (4 screens)**: `analysis/ui-mockups.md`
- **Design Decisions (5)**: `analysis/design-decisions.md`
- **Product Brief**: `outputs/product-brief.md`

## Decisions Made

| Area | Decision |
|---|---|
| UI Library | Angular CDK + Tailwind CSS v4 (replaces Angular Material 3) |
| Token Architecture | Custom `--mf-*` CSS tokens + Tailwind `@theme` |
| Concept Map | Restyle Cytoscape + 280px slide-in node detail panel |
| Navigation | Slim toolbar (56px) + collapsible sidebar (64px ↔ 240px) |
| Gamification | Sidebar footer: 🔥 streak + 📚 due count |
| Default Theme | Light mode default, dark toggle with OS preference detection |
| Typography | Inter variable font (all weights 100–900) replaces Roboto |

## Color System

- Primary: `#5B4FE9` (indigo-violet)
- Surface-1 (cards): `#FFFFFF`
- Surface-2 (page): `#F8F9FA`
- Surface-3 (inputs): `#F0F2F5`
- Dark mode: navy `#0F1117 / #161B27 / #1E2535`

## Priority Implementation Order

1. Design tokens + Inter font (Section 1+2)
2. Shell + Sidebar (Section 3)
3. Component library: mf-button, mf-card, mf-input, mf-chip, skeleton, dialog, snackbar, progress (Section 4)
4. Concept Map redesign (Section 6) — priority screen
5. Remaining 7 screens (Section 5)
6. Dark mode system (Section 7)
7. M3 removal + cleanup (Section 8)

## New Backend Endpoint Required

```
GET /api/v1/users/me/stats
Auth: Bearer JWT
Response: { "streak_days": 7, "due_today": 12 }
```
