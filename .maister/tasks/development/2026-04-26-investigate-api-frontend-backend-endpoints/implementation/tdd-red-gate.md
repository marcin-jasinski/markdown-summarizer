# TDD Red Gate

## Confirmed Failing Tests (proving bugs exist before implementation)

### Test 1: Missing /lessons backend route
**File**: `tests/unit/api/test_lessons_tdd_red.py::test_list_lessons_endpoint_exists`
**Failure**: `AssertionError: Expected 200 but got 404. The GET /api/knowledge-bases/{kb_id}/lessons route is missing from knowledge_bases.py.`
**Proves**: `GET /api/knowledge-bases/{kb_id}/lessons` handler does not exist in `knowledge_bases.py`.

### Test 2: FlashcardService.reviewCard() URL bug
**File**: `frontend/src/tests/flashcard.service.tdd-red.spec.ts > reviewCard() should send POST with card_id in the URL path`
**Failure**: `Error: Expected one matching request for criteria "Match URL: .../flashcards/card-xyz-789/review", found none. Requests received are: POST .../flashcards/review.`
**Proves**: `FlashcardService.reviewCard()` omits the `card_id` path segment in the URL.

## Additional Pre-Existing Test Infrastructure Issues Fixed
- Import paths in `api.service.spec.ts`, `auth.service.spec.ts`, `auth.guard.spec.ts`: changed `../../app/...` → `../app/...`
- Jasmine matchers (`toBeTrue()`, `toBeFalse()`) → Vitest-compatible (`toBe(true)`, `toBe(false)`)
- `done` callback style → `return new Promise<void>()` in `api.service.spec.ts`

## Status
Red gate CONFIRMED. Both bugs are reproducible via automated tests.
