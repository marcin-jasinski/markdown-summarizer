# Development Roadmap

> Full phase-by-phase detail: [implementation-plan.md](../../../.github/docs/implementation-plan.md)

## Current State

- **Version**: 2.0.0 (active development)
- **Completed Phases (0–13)**: All core features + Docker deployment implemented
  - Domain layer, infrastructure foundation, AI gateway
  - Document parsing & ingestion pipeline (Markdown, PDF, DOCX, TXT)
  - 9 AI agents: summarizer, flashcard generator, quiz generator/evaluator,
    concept mapper, image analyzer, preprocessor, relevance guard, article fetcher
  - Neo4j knowledge graph with outbox event delivery
  - FastAPI REST API with 14 routers, JWT auth, OAuth2 (Discord/Google/GitHub)
  - Angular 21 SPA with Angular Material + Cytoscape.js concept map visualization
  - Quiz engine with server-authoritative state, Redis session support
  - Conversational RAG chat, full-text + semantic search
  - Multi-stage Dockerfile, Docker Compose with 3 profiles (core, observability, bots)
- **Remaining Phases (14–19)**: Bot integrations, observability, hardening, E2E testing

## Planned Enhancements

### High Priority — Phases 14–17

- [ ] **Phase 14 — Discord Bot** — Complete Discord integration with slash commands for quiz,
  document Q&A, and concept map queries. Enforce guild/channel allowlists. `[Effort: M]`
- [ ] **Phase 15 — Slack Bot** — Async Slack-Bolt handler for document upload and quiz flows,
  with interaction ownership enforcement. `[Effort: M]`
- [ ] **Phase 16 — CLI Entry Points** — Finalize `mindforge-pipeline`, `mindforge-quiz`,
  `mindforge-backfill`, and `mindforge-discord/slack` CLI commands. `[Effort: S]`
- [ ] **Phase 17 — Observability & Tracing** — Full Langfuse dashboard coverage, per-operation
  token/cost accounting, alerting thresholds for LLM cost anomalies. `[Effort: S]`

### Medium Priority — Quality Gates (Phases 18–19)

- [ ] **Phase 18 — Security Hardening** — Penetration testing pass, automated security
  regression suite, Redis-backed multi-worker rate limiting for production. `[Effort: L]`
- [ ] **Phase 19 — E2E Testing & CI/CD** — GitHub Actions workflow (ruff + mypy + pytest
  on PRs), testcontainers integration test suite in CI, minimum 80% coverage gate,
  Playwright E2E smoke scenarios. `[Effort: L]`

### Technical Debt

- [ ] **Coverage Measurement** — Add `pytest-cov` with minimum threshold to `pyproject.toml`;
  currently no coverage metrics collected.
- [ ] **English Locale Prompts** — Add `en/` prompt directory alongside existing `pl/`
  (Polish-only AI prompts limit non-Polish users).
- [ ] **Object Storage Adapter** — Verify/complete `MinioStorageAdapter` in
  `infrastructure/storage/` (directory exists but may be empty).
- [ ] **Integration API Tests** — `tests/integration/api/` directory is empty; needs
  at least smoke-level tests for upload, quiz, and auth flows.

## Future Considerations

- **Multi-language UI**: Extend prompt localization to support English and other languages
- **Mobile frontend**: Improve responsive layout for small screens
- **Scalability**: Redis-backed distributed rate limiting for multi-worker deployments
- **Knowledge graph export**: Allow exporting concept maps as structured data (JSON-LD, RDF)
- **Spaced repetition**: Add SM-2 / FSRS scheduling to the quiz/flashcard engine

---
*Last Updated*: 2026-05-16
*Effort Scale*: `S` 2–3 days | `M` 1 week | `L` 2+ weeks
*Reference*: [implementation-plan.md](../../../.github/docs/implementation-plan.md)
