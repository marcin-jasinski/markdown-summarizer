# Scope Clarifications

## CSS Coexistence Strategy (Critical)
**Disable Tailwind Preflight** during the incremental migration. Tailwind's Preflight is disabled in `postcss.config.js` / Tailwind config while Material CSS is still active on unmigrated screens. Once all screens are migrated and `@angular/material` is uninstalled, Preflight can be re-enabled.

## Snackbar / Dialog Rollout (Critical)
**Phase 1 cross-cutting migration** — all 7 MatSnackBar consumers and MatDialog usage will be replaced with the custom mf-snackbar service and mf-dialog (CDK-based) **before** individual screen redesigns begin. This ensures shared infrastructure is stable before per-screen work.

## Knowledge-Bases Screen Scope (Important)
**Included as screen 9** — the knowledge-bases page will also be migrated from Material to CDK + Tailwind. Leaving one Material screen would leave the migration incomplete.

## Stats Router Location (Important)
**New `mindforge/api/routers/users.py`** — the stats endpoint `GET /api/v1/users/me/stats` will live in a dedicated users router for clean separation of concerns, registered in `main.py`.

## Concept Map Node Detail Panel (Important)
**Slide-in side panel** — 280–320px panel that slides in from the right and pushes the Cytoscape graph area when a node is clicked. Uses Angular `@panelSlide` animation.

## ThemeService Init Point (Default Applied)
**APP_INITIALIZER in app.config.ts** — ThemeService is initialized before first render so the Login page also respects OS dark mode preference. No user override needed for this decision.
