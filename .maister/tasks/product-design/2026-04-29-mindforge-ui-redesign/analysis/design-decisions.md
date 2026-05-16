# Design Decisions — MindForge UI Redesign

**Phase**: 5 — Idea Convergence
**Approved**: 2026-04-29

---

## Summary

| Decision Area | Selected Approach | Confidence |
|---|---|---|
| UI Component Library | Angular CDK + Tailwind CSS v4 | High |
| Token Architecture | Custom CSS Token System | High |
| Concept Map | Restyle + Node Detail Side Panel | High |
| Navigation Shell | Slim toolbar + collapsible sidebar | High |
| Gamification | Sidebar footer widget | High |

---

## Decision 1: UI Component Library — Angular CDK + Tailwind CSS v4

**Selected**: Alternative C — Angular CDK + Tailwind CSS v4

**Rationale**: The user explicitly removed the "stay on Angular Material" constraint. Angular CDK + Tailwind is how Linear, Vercel, and Supabase achieve their distinctive premium aesthetic. It eliminates the "Material fingerprint" (ripple effects, form field notch, specific button shapes) that makes Angular Material apps immediately recognizable. It aligns directly with both personas: Alex sees an app that "feels like a reward to open"; Maya sees something "credible enough to show a colleague."

**Trade-offs accepted**:
- 6–10 weeks implementation effort vs. 2–4 weeks for M3 override
- No automatic component accessibility — must wire ARIA attributes manually using Angular CDK primitives
- Custom components for sidebar, dialogs, snackbars, menus, dropdowns

**Key decisions per this choice**:
- Angular CDK used for: overlay, focus trap, a11y, drag-and-drop (concept map)
- Tailwind CSS v4 for all visual styling
- Custom components built for: sidebar, top toolbar, KB card, data table, form fields, buttons, chips, dialogs
- Cytoscape.js remains (not replaced by CDK)
- Remove: all `@angular/material` imports from every component

**Alternatives considered**: See `analysis/alternatives.md` — Decision Area 1

---

## Decision 2: Token Architecture — Custom CSS Token System

**Selected**: Alternative C — Fully Custom CSS Token System

**Rationale**: With Tailwind CSS v4 as the visual layer, the correct architecture is `@theme` CSS variables in a `design-tokens.css` file. This makes the token system completely readable, design-spec-aligned, and library-independent. Dark mode is explicit: a `[data-theme="dark"]` block remaps semantic tokens. No dependency on `--mat-sys-*` variables.

**Token structure**:
```css
/* Global Primitives */
--color-indigo-600: #5B4FE9;
--color-amber-500: #F59E0B;
/* ... */

/* Semantic Tokens */
--mf-primary: var(--color-indigo-600);
--mf-accent: var(--color-amber-500);
--mf-surface-1: #FFFFFF;
--mf-surface-2: #F8F9FA;
--mf-surface-3: #F0F2F5;
--mf-text-primary: #111827;
--mf-text-secondary: #6B7280;
--mf-text-tertiary: #9CA3AF;
--mf-border: #E5E7EB;

/* Domain Tokens */
--mf-streak-color: var(--color-amber-500);
--mf-correct: #10B981;
--mf-incorrect: #EF4444;
--mf-node-concept: var(--mf-primary);
```

**Trade-offs accepted**:
- Dark mode tokens must be manually specified (no automatic palette generation)
- WCAG contrast ratios must be manually verified for each dark-mode pair
- ~60–80 semantic tokens to define in the dark block

---

## Decision 3: Concept Map — Restyle + Node Detail Side Panel

**Selected**: Alternative B — Restyle + Node Detail Side Panel

**Rationale**: A pure restyle (Alternative A) would improve the map dramatically but leave it as a passive display. Adding a side panel that slides in on node click transforms it into an interactive knowledge tool — exactly the "proof-of-intelligence" moment Maya needs when showing a colleague. The panel shows concept name, definition, related concepts, and a "Study Flashcards" CTA. This is achievable with a Cytoscape.js `tap` event + a custom Angular panel component.

**Implementation approach**:
- Cytoscape.js stylesheet updated: indigo nodes with 8px radius, Inter font, subtle drop shadows, `#F8F9FA` canvas background
- Edges: thin `#E5E7EB` lines with small, readable Inter labels
- `tap` event → emit selected concept ID to Angular component
- Angular side panel: `@if (selectedNode())` — slide in from right (240px), shows concept name + definition (from API) + related concept chips + CTA
- Mobile: panel covers full width as a bottom sheet

**Trade-offs accepted**:
- Side panel requires a new API call for concept details (or pre-loading from graph data — TBD in spec)
- More complex state management (selected node, panel open/close, mobile vs. desktop layout)
- Not as visually rich as Alternative D (no minimap or focus mode) — those remain future enhancements

---

## Decision 4: Navigation Shell — Slim Toolbar + Collapsible Sidebar

**Selected**: Alternative B — Slim top toolbar preserved + collapsible sidebar

**Rationale**: The user preferred the safer, more familiar option. Keeping the top toolbar provides a natural place for the current KB context indicator, breadcrumbs, and the dark mode toggle button. The sidebar collapses to a 64px icon rail on toggle (button in toolbar) or persists as 240px expanded. This is the standard pattern for SaaS apps that need both maximum content space and visible context (e.g., Notion with sidebar, GitHub with sidebar).

**Toolbar redesign**:
- Remove redundant "MindForge" text (sidebar logo handles branding)
- Content: `[collapse toggle] | [current page breadcrumb] | [spacer] | [dark mode toggle] | [user avatar + menu]`
- Height: 56px (down from 64px)
- Background: `--mf-surface-1` (#FFFFFF) with subtle bottom border

**Sidebar redesign**:
- Width: 240px expanded / 64px collapsed (icon-only)
- Toggle: button in toolbar OR keyboard shortcut `[`
- Sections with labels: `LEARN` / `KNOWLEDGE` / `VISUALISE`
- Footer widget: 🔥 streak + 📚 due count
- Logo: new MindForge mark + "MindForge" text (text hidden in collapsed state)

**Trade-offs accepted**:
- Top toolbar takes 56px of vertical space that could be content
- Redundant MindForge branding removed from toolbar (only sidebar logo)
- Mobile behavior unchanged (sidenav overlay mode on small screens)

---

## Decision 5: Gamification — Sidebar Footer Widget

**Selected**: Alternative A — Sidebar footer widget

**Rationale**: Pinning the gamification widget to the sidebar footer ensures it's always visible without cluttering the navigation items. In icon-only (collapsed) mode, only the flame and card icons are shown; in expanded mode, streak count and due count are shown inline. This matches the Duolingo/learning-app pattern of making the "return trigger" (streak + due cards) persistently visible without being intrusive.

**Widget design**:
```
[EXPANDED 240px]
━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 Streak: 7 days    📚 12 due
━━━━━━━━━━━━━━━━━━━━━━━━━━

[COLLAPSED 64px]
━━━━━━━
🔥 7
📚 12
━━━━━━━
```
- Streak count sourced from backend interaction history
- Due count sourced from flashcard review queue
- Clicking the widget navigates to Flashcards

**Trade-offs accepted**:
- Requires 2 new lightweight API calls (or a combined `/me/stats` endpoint) to populate the widget
- Widget shows "—" when data is loading or unavailable; no blocking spinner
