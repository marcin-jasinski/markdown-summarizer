# Scope Clarifications

## Decisions Made in Phase 2

### Critical Decision 1: LessonResponse.document_count
- **Decision**: Hardcode `document_count=1`
- **Rationale**: lesson_projections PK is (kb_id, lesson_id) — enforces 1:1 relationship; minimal code

### Critical Decision 2: Playwright test location
- **Decision**: TypeScript in `frontend/` using `@playwright/test`
- **Rationale**: Shares TypeScript types from api.models.ts; standard Angular ecosystem approach

### Important Decision 3: Auth auto-refresh strategy
- **Decision**: HTTP interceptor — catch 401, call refresh, retry original request
- **Rationale**: Handles all expiry scenarios; standard Angular pattern

### Important Decision 4: FlashcardService.reviewCard() fix approach
- **Decision**: Extract card_id from request body for URL (no component changes)
- **Rationale**: Zero blast radius; flashcards.ts:68 already passes card_id in req body
