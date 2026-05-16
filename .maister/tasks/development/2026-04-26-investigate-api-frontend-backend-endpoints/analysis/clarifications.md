# Phase 1 Clarifications

## Clarifying Questions & Answers

**Q1: Handle the 2 confirmed broken endpoints?**
Answer: Yes, fix both:
- FlashcardService.reviewCard() URL mismatch (missing `{card_id}` path segment)
- Missing `/api/knowledge-bases/{kb_id}/lessons` backend route

**Q2: Playwright E2E infrastructure?**
Answer: Yes, set up Playwright and write E2E tests for all endpoints.
- Create `playwright.config.ts`, install `@playwright/test`
- Write E2E tests covering all API flows

**Q3: Missing frontend services (interactions, admin, auto-refresh)?**
Answer: Implement missing Angular services only (no UI pages).
- `InteractionsService`
- Auto-refresh logic in `AuthService`
- Admin service
