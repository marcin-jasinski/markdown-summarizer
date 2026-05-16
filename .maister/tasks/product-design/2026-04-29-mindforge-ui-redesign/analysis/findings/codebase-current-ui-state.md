# Codebase Research: MindForge Current UI State

## Files Analysed
- `frontend/src/styles.scss` (global theme + utilities)
- `frontend/src/app/pages/dashboard/dashboard.scss`
- `frontend/src/app/pages/quiz/quiz.scss`
- `frontend/src/app/pages/flashcards/flashcards.scss`
- `frontend/src/app/pages/knowledge-bases/knowledge-bases.scss`
- `frontend/src/app/pages/chat/chat.scss`
- `frontend/src/app/pages/documents/documents.scss`
- `frontend/src/app/app.routes.ts` (route structure)
- `frontend/src/app/pages/` (page list)

---

## 1. Theme System (styles.scss)

**Current Setup**: Angular Material 3, dark-first.
```scss
html {
  @include mat.theme((
    color: (
      theme-type: dark,
      primary: mat.$violet-palette,
      tertiary: mat.$cyan-palette,
    ),
    typography: Roboto,
    density: 0,
  ));
}
body { color-scheme: dark; }
```

**Key observation**: The theme is single-line switchable to light mode. Typography uses Roboto (Material default).

**Design tokens in use**: `--mat-sys-surface`, `--mat-sys-on-surface`, `--mat-sys-primary`, `--mat-sys-on-primary-container`, `--mat-sys-primary-container`, `--mat-sys-on-surface-variant`, `--mat-sys-outline-variant`, `--mat-sys-outline`, `--mat-sys-surface-container`.

**Layout utilities defined**:
- `.page-container`: `padding: 24px; max-width: 1200px; margin: 0 auto`
- `.page-header`: flex row, gap 16px, `h1` uses `--mat-sys-headline-medium`
- `.card-grid`: `grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px`

**Status badges**: coloured pill system (pending/processing/done/failed) already exists with rgba colour backgrounds.

**Flashcard flip animation**: 3D CSS flip already implemented with `perspective(1000px) rotateY(180deg)`, `transition: 0.55s cubic-bezier(.4,0,.2,1)`. Well-implemented.

**Scrollbar**: custom styled. Will need updating for light mode (current track colour references dark surface tokens).

---

## 2. Dashboard Page (dashboard.scss)

**Current classes**:
- `.kb-card`: `cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; border-radius: 16px`. Hover: `translateY(-2px)`, shadow `0 8px 24px rgba(0,0,0,.3)`.
- `.kb-avatar`: `background: --mat-sys-primary-container; border-radius: 8px`.
- `.kb-description`: `font-size: 14px; line-height clamp; -webkit-line-clamp: 2`.
- `.empty-state`: Centred column, 64px padding, icon `72px opacity: 0.4`, CTA button.

**Gaps identified**:
- No streak counter / gamification strip.
- No "due today" badge on deck cards.
- No XP/progress bar for the user.
- Shadow value `rgba(0,0,0,.3)` is very dark — fine for dark mode, too strong for light mode (should be `rgba(0,0,0,.08–.12)`).
- No cover image / gradient header on KB cards — purely icon-based.

---

## 3. Quiz Page (quiz.scss)

**Current classes**:
- `.quiz-page`: `max-width: 720px` — correct pattern (content constraint).
- `.quiz-start`: centred column, hero icon `80px`, well-structured.
- `.question-card`, `.evaluation-card`: `border-radius: 16px`.
- `.question-text`: `font-size: 18px; line-height: 1.6; font-weight: 500` — slightly small for primary question.
- `.feedback-text`: `font-size: 15px; line-height: 1.6`.
- Score colours: `.score-excellent → #81c784`, `.score-good → #64b5f6`, `.score-partial → #ffd54f`, `.score-poor → #e57373` — hardcoded hex, not tokens.

**Gaps identified**:
- Question text `18px` — should be `20–22px` for primary question.
- No SRS-style rating buttons (Again/Hard/Good/Easy) visible in styles — quiz uses freeform text answer.
- Score colours hardcoded instead of using token variables.
- No progress bar across top of quiz session.

---

## 4. Flashcard Page (flashcards.scss)

The main flashcard 3D flip CSS is in `styles.scss` (globally shared). The component-specific `flashcards.scss` covers additional flashcard-specific layout.

**Key finding**: Flip animation is well-implemented and should be preserved in redesign.

---

## 5. Pages Inventory

| Page | Route (inferred) | Key UI Needs |
|---|---|---|
| Dashboard | `/` | Gamification strip, KB card grid with due badges |
| Knowledge Bases | `/knowledge-bases` | Card grid, empty state, create flow |
| Documents | `/documents` | List view, status badges, upload |
| Flashcards | `/flashcards` | Card flip UI, SRS rating buttons, progress |
| Quiz | `/quiz` | Single-question flow, inline feedback, score screen |
| Search | `/search` | Search results list |
| Chat | `/chat` | Conversation UI |
| Concept Map | `/concept-map` | Graph visualisation |
| Login | `/login` | Auth form |

---

## 6. Summary: What to Change vs. What to Keep

### Keep
- `.card-grid` auto-fill layout — correct pattern
- `.page-container` max-width constraint — correct
- Flashcard flip animation CSS — polished, use as-is
- Status badge system (`.status-badge.*`) — solid, update colours for light mode
- Material 3 token system (`--mat-sys-*`) — extend, don't replace
- Card hover `translateY(-2px)` effect — keep, reduce shadow opacity

### Change
- `theme-type: dark` → `theme-type: light`
- Roboto → Inter (or Plus Jakarta Sans)
- Shadow `rgba(0,0,0,.3)` → `rgba(0,0,0,.08)` throughout
- Score colours: hardcoded hex → CSS custom properties
- Question text size: `18px` → `20px` minimum

### Add
- Gamification strip (streak, XP, items-due)
- "Due today" badge on flashcard deck cards
- SRS rating buttons on flashcard evaluation
- Progress bar on quiz session
- Sidebar navigation (if currently using top nav)
- `--color-*` semantic token layer on top of `--mat-sys-*`
