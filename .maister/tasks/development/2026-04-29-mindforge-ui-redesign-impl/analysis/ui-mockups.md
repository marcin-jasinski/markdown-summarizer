# UI Mockups — MindForge UI Redesign (Development Phase)

**Phase**: Phase 4 UI Mockups
**Task Path**: `.maister/tasks/development/2026-04-29-mindforge-ui-redesign-impl`
**Source**: Extended from product design mockups at `.maister/tasks/product-design/2026-04-29-mindforge-ui-redesign/analysis/ui-mockups.md`

---

## Reference Mockups (from product design)

The following 4 screens have full ASCII mockups in the product design artifacts:

1. **Dashboard / Knowledge Bases Grid** → see product design `analysis/ui-mockups.md` Screen 1
2. **Concept Map** (with slide-in node detail panel) → Screen 2
3. **Flashcards** (SRS buttons, progress bar) → Screen 3
4. **Quiz** (evaluated state, score, feedback) → Screen 4

---

## Screen 5: Login — Split Hero Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌───────────────────────────┐  ┌───────────────────────────────────────┐   │
│  │ HERO PANEL                │  │ AUTH PANEL                            │   │
│  │ (surface-3 / #F0F2F5)    │  │ (surface-1 / #FFFFFF)                 │   │
│  │ min-h: 100vh              │  │ min-h: 100vh                          │   │
│  │                           │  │                                       │   │
│  │                           │  │        ◈  MindForge                  │   │
│  │    ◈  MindForge           │  │                                       │   │
│  │    (40px logo icon)       │  │  Welcome back                        │   │
│  │                           │  │  (text-3xl font-bold)                │   │
│  │    "Your intelligent      │  │                                       │   │
│  │     study companion."     │  │  ┌─────────────────────────────────┐ │   │
│  │    (text-xl font-medium   │  │  │ ✉  Email address                │ │   │
│  │     text-secondary)       │  │  └─────────────────────────────────┘ │   │
│  │                           │  │  ┌─────────────────────────────────┐ │   │
│  │    ─────────────────────  │  │  │ 🔒  Password                    │ │   │
│  │                           │  │  └─────────────────────────────────┘ │   │
│  │    "Upload documents,     │  │                                       │   │
│  │     generate quizzes &    │  │  [Sign In]  (primary, full-width)    │   │
│  │     build lasting         │  │                                       │   │
│  │     knowledge with AI."   │  │  ─── or ───                          │   │
│  │    (text-sm text-tertiary)│  │                                       │   │
│  │                           │  │  Don't have an account?              │   │
│  │                           │  │  [Create account]  (ghost/link)      │   │
│  │                           │  │                                       │   │
│  └───────────────────────────┘  └───────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Notes**:
- Two-column layout: left = hero panel (40% on desktop), right = auth form (60%)
- On mobile: hero panel hidden, auth panel takes full width
- Login / Register tabs replaced with single state + "Create account" link toggle
- No Material tabs — use `@if (isLogin())` signal to toggle between login/register forms
- Input fields: `mf-input` component with leading icon slot

---

## Screen 6: Documents

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOOLBAR (56px)                                                               │
│ [☰]  Biology › Documents                               [🌙]  [A▾]           │
├─────────────────────────┬────────────────────────────────────────────────────┤
│ SIDEBAR (240px)         │  PAGE CONTENT (surface-2, p-8)                    │
│ (same structure as      │                                                    │
│  previous screens)      │  Documents                    [+ Upload Document] │
│                         │  ─────────────────────────────────────────────────│
│                         │                                                    │
│                         │  ┌──────────────────────────────────────────────┐ │
│                         │  │ ●  biology-intro.pdf         DONE            │ │
│                         │  │   Uploaded 3 days ago · 24 pages             │ │
│                         │  │   ████████████████████████████ 100%          │ │
│                         │  └──────────────────────────────────────────────┘ │
│                         │                                                    │
│                         │  ┌──────────────────────────────────────────────┐ │
│                         │  │ ○  cell-biology-notes.pdf    PROCESSING...   │ │
│                         │  │   Just uploaded · 18 pages                   │ │
│                         │  │   ████████████░░░░░░░░░░░░░░░  48%           │ │
│                         │  └──────────────────────────────────────────────┘ │
│                         │                                                    │
│                         │  ┌──────────────────────────────────────────────┐ │
│                         │  │ ○  photosynthesis.pdf        PENDING         │ │
│                         │  │   Uploading…                                 │ │
│                         │  │   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0%           │ │
│                         │  └──────────────────────────────────────────────┘ │
│  ─────────────────────  │                                                    │
│  🔥 7 days   📚 12 due  │                                                    │
└─────────────────────────┴────────────────────────────────────────────────────┘
```

**Notes**:
- Replace `mat-table` with plain `mf-card` rows
- Status badge (DONE/PROCESSING/PENDING/FAILED) → `mf-chip` with color variant
- Progress bar → `mf-progress` component
- No sortable columns — simple list layout is sufficient
- `●` = filled circle (DONE status, emerald); `○` = empty circle (other statuses)

---

## Screen 7: Search

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOOLBAR (56px)                                                               │
│ [☰]  Search                                             [🌙]  [A▾]          │
├─────────────────────────┬────────────────────────────────────────────────────┤
│ SIDEBAR (240px)         │  PAGE CONTENT (surface-2, p-8)                    │
│                         │                                                    │
│  (same sidebar)         │  ┌──────────────────────────────────────────────┐ │
│                         │  │ 🔍  Search across all knowledge bases...     │ │
│  🔍  Search     ◀      │  └──────────────────────────────────────────────┘ │
│                         │  Filter: [All ✕] [Biology ✕] [+ Add filter]      │
│                         │                                                    │
│                         │  ─────────── 12 results ───────────────────────   │
│                         │                                                    │
│                         │  ┌──────────────────────────────────────────────┐ │
│                         │  │  Mitochondria ATP synthesis              0.94  │ │
│                         │  │  biology-intro.pdf · Page 4                   │ │
│                         │  │  "...the mitochondria produce ATP via         │ │
│                         │  │   oxidative phosphorylation in the electron   │ │
│                         │  │   transport chain..."                         │ │
│                         │  │  [Biology] [Cell Biology]        [Open doc →] │ │
│                         │  └──────────────────────────────────────────────┘ │
│                         │                                                    │
│                         │  ┌──────────────────────────────────────────────┐ │
│                         │  │  Cellular respiration overview          0.91  │ │
│                         │  │  cell-biology-notes.pdf · Page 2              │ │
│                         │  │  "...cellular respiration is the process by   │ │
│                         │  │   which cells convert glucose into ATP..."    │ │
│                         │  │  [Biology] [Metabolism]          [Open doc →] │ │
│                         │  └──────────────────────────────────────────────┘ │
│  ─────────────────────  │                                                    │
│  🔥 7 days   📚 12 due  │                                                    │
└─────────────────────────┴────────────────────────────────────────────────────┘
```

**Notes**:
- `mf-input` for search bar with 🔍 leading icon (full-width)
- Filter chips = `mf-chip` with variant="removable" (✕ close button)
- Result cards = `mf-card` with score badge (right-aligned, text-secondary)
- Excerpt text = `text-sm text-secondary`, truncated at 2 lines
- KB/topic chips = `mf-chip` variant="subtle" (small, non-interactive)

---

## Screen 8: Chat

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOOLBAR (56px)                                                               │
│ [☰]  Biology › Chat                                    [🌙]  [A▾]           │
├─────────────────────────┬────────────────────────────────────────────────────┤
│ SIDEBAR (240px)         │  CHAT CONTENT (surface-2, flex-col, h-full)       │
│                         │                                                    │
│  (same sidebar)         │  ┌──────────────────────────────────────────────┐ │
│                         │  │  MESSAGES (flex-col, overflow-y: auto,       │ │
│  💬  Chat       ◀      │  │  flex: 1, gap-4, px-8 py-6)                  │ │
│                         │  │                                               │ │
│                         │  │  ┌──────────────────────────────────────┐    │ │
│                         │  │  │ ASSISTANT (left-aligned)             │    │ │
│                         │  │  │ bg: surface-1, border, shadow-sm     │    │ │
│                         │  │  │ "Hello! I can help you explore        │    │ │
│                         │  │  │  your Biology knowledge base.        │    │ │
│                         │  │  │  What would you like to know?"       │    │ │
│                         │  │  └──────────────────────────────────────┘    │ │
│                         │  │                                               │ │
│                         │  │           ┌──────────────────────────────┐   │ │
│                         │  │           │ USER (right-aligned)         │   │ │
│                         │  │           │ bg: primary (#5B4FE9)         │   │ │
│                         │  │           │ text: white                  │   │ │
│                         │  │           │ "What is cellular respiration │   │ │
│                         │  │           │  and why is it important?"   │   │ │
│                         │  │           └──────────────────────────────┘   │ │
│                         │  │                                               │ │
│                         │  │  ┌──────────────────────────────────────┐    │ │
│                         │  │  │ ASSISTANT                            │    │ │
│                         │  │  │ "Cellular respiration is the...      │    │ │
│                         │  │  │  [typing indicator ●●●]              │    │ │
│                         │  │  └──────────────────────────────────────┘    │ │
│                         │  └──────────────────────────────────────────────┘ │
│                         │  ┌──────────────────────────────────────────────┐ │
│                         │  │ ✎  Ask about Biology...          [Send ▶]   │ │
│  ─────────────────────  │  └──────────────────────────────────────────────┘ │
│  🔥 7 days   📚 12 due  │                                                    │
└─────────────────────────┴────────────────────────────────────────────────────┘
```

**Notes**:
- Chat uses CSS Grid or flexbox, NOT Material layout
- User bubbles: `bg-[--mf-primary] text-white rounded-2xl rounded-br-sm px-4 py-3` right-aligned, max-w-[70%]
- Assistant bubbles: `bg-[--mf-surface-1] border border-[--mf-border] rounded-2xl rounded-bl-sm` left-aligned
- Input bar: `mf-input` + `mf-button` variant="primary" with ▶ icon
- Typing indicator: 3 dots with bounce animation
- No `MatSnackBar` — use `mf-snackbar` service for errors

---

## Screen 9: Knowledge Bases (List + Create Dialog)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOOLBAR (56px)                                                               │
│ [☰]  Knowledge Bases                                   [🌙]  [A▾]           │
├─────────────────────────┬────────────────────────────────────────────────────┤
│ SIDEBAR (240px)         │  PAGE CONTENT (surface-2, p-8)                    │
│                         │                                                    │
│  📚  Knowledge Bases ◀ │  Knowledge Bases                 [+ New]          │
│  (+ other items)        │  ─────────────────────────────────────────────────│
│                         │                                                    │
│                         │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐│
│                         │  │ 📚  Biology  │  │ 📚  Physics  │  │  + New   ││
│                         │  │              │  │              │  │          ││
│                         │  │ 3 docs       │  │ 5 docs       │  │          ││
│                         │  │ [⚡] [🃏] [💬] │  │ [⚡] [🃏] [💬] │  │          ││
│                         │  └──────────────┘  └──────────────┘  └──────────┘│
│                         │                                                    │
│                         │  ┌───────────────────────────────────────────┐    │
│                         │  │  CDK DIALOG OVERLAY                       │    │
│                         │  │                                           │    │
│                         │  │  Create Knowledge Base                    │    │
│                         │  │  ─────────────────────                    │    │
│                         │  │  ┌───────────────────────────────────┐    │    │
│                         │  │  │ Name (required)                   │    │    │
│                         │  │  └───────────────────────────────────┘    │    │
│                         │  │  ┌───────────────────────────────────┐    │    │
│                         │  │  │ Description (optional)            │    │    │
│                         │  │  └───────────────────────────────────┘    │    │
│                         │  │                         [Cancel] [Create]  │    │
│                         │  └───────────────────────────────────────────┘    │
│  ─────────────────────  │                                                    │
│  🔥 7 days   📚 12 due  │                                                    │
└─────────────────────────┴────────────────────────────────────────────────────┘
```

**Notes**:
- This screen is the same visual as Dashboard but with the KB grid as the primary content
- "Create Knowledge Base" dialog = `mf-dialog` (CDK overlay) — replaces `MatDialog`
- `kb-create-dialog.ts` is the one existing `MatDialog` consumer; convert to CDK-based `mf-dialog`
- `[+ New]` add-card uses `mf-card` with dashed border, hover state with `bg-[--mf-primary-subtle]`

---

## Reusable Components Reference

| Component | File | Used In |
|---|---|---|
| `mf-button` | `core/components/mf-button/` | All screens |
| `mf-card` | `core/components/mf-card/` | All screens |
| `mf-input` | `core/components/mf-input/` | Login, Search, Chat, Quiz |
| `mf-chip` | `core/components/mf-chip/` | Search filters, Concept Map, status badges |
| `mf-progress` | `core/components/mf-progress/` | Flashcards, Documents |
| `mf-skeleton` | `core/components/mf-skeleton/` | All data-loading states |
| `mf-dialog` | `core/components/mf-dialog/` | KB Create |
| `mf-snackbar` | `core/services/mf-snackbar.service.ts` | Chat, error states |
| `app-sidebar` | `shell/sidebar/` | All screens |
| `app-toolbar` | `shell/toolbar/` | All screens |
| `node-detail-panel` | `pages/concept-map/node-detail-panel/` | Concept Map |

---

## Consistency Checklist

- ✅ All 9 screens share identical toolbar (56px, surface-1, same right-side actions)
- ✅ All 9 screens share identical sidebar (240px, gamification footer)
- ✅ Active nav item: `bg-[--mf-primary-subtle] text-[--mf-primary]`
- ✅ Page background is `surface-2` (#F8F9FA) everywhere
- ✅ All cards use `mf-card` with `radius-xl` + `shadow-sm`/`shadow-md`
- ✅ All buttons use `mf-button` variants — no ad-hoc styling
- ✅ Dark mode: `[data-theme="dark"]` on `<html>` governs all `--mf-*` token overrides

---

*Phase 4 UI Mockups — Development Workflow — 2026-04-29*
