# Phase 1 Clarifications

## Migration Approach
**Screen-by-screen (incremental)** — Angular Material removed per-screen, not big-bang. App remains usable and testable throughout the migration.

## Tailwind CSS v4 Integration
**`@tailwindcss/postcss` plugin in PostCSS** — standard Angular-compatible setup via `postcss.config.js`. NOT the Vite plugin.

## Icon Set
**Switch to Lucide icons** — replace Material Icons (Google font) with Lucide (lightweight, tree-shakeable, no font download required). Remove `material-icons` font link from `index.html`.

Package to install: `lucide-angular`

## Backend Stats Endpoint
**Stub initially** — `GET /api/v1/users/me/stats` will return `{ "streak_days": 0, "due_today": 0 }` as a placeholder. Real streak and due-count logic deferred. This unblocks frontend sidebar gamification widget without blocking on complex SQL queries.
