# Work Log — GUI Production-Ready Pass

## Summary

Three independent user-visible defects investigated and fixed.

## Changes

### 1. Concept map — text overflow + missing edges

**Backend (data path was incomplete):**

- [mindforge/infrastructure/graph/cypher_queries.py](../../../../mindforge/infrastructure/graph/cypher_queries.py) — added `GET_CONCEPT_EDGES` Cypher query that traverses `RELATES_TO` edges scoped by `kb_id`.
- [mindforge/domain/models.py](../../../../mindforge/domain/models.py) — `ConceptEdge` was already present; no model change needed.
- [mindforge/domain/ports.py](../../../../mindforge/domain/ports.py) — added `get_concept_edges(kb_id)` to `RetrievalPort`.
- [mindforge/infrastructure/graph/neo4j_retrieval.py](../../../../mindforge/infrastructure/graph/neo4j_retrieval.py) — implemented `get_concept_edges()` with deduplication and self-loop filtering.
- [mindforge/api/routers/concepts.py](../../../../mindforge/api/routers/concepts.py) — calls both `get_concepts()` and `get_concept_edges()`, validates that endpoints reference known nodes, and back-fills the per-node `related` list for the API response (frontend contract preserved).

**Frontend (Cytoscape styling):**

- [frontend/src/app/pages/concept-map/concept-map.ts](../../../../frontend/src/app/pages/concept-map/concept-map.ts):
  - Refactored duplicated stylesheet into `buildStyles(dark)` helper.
  - Node style: `text-wrap: 'wrap'`, `text-max-width: 140px`, `width: 'label'`, `height: 'label'`, `padding: 14px`, `shape: 'round-rectangle'` — labels now fit, nodes auto-size to content.
  - Edge style: arrow with rotated label, lighter palette, rounded label background.
  - Layout: `cose` with explicit `nodeRepulsion`, `idealEdgeLength`, `gravity` for breathable spacing; `fit: true` so view always shows the whole graph initially.
  - Hide noisy generic `related_to` edge label; show only specific relation types.

### 2. Flashcards — "doesn't work at all"

- [mindforge/application/flashcards.py](../../../../mindforge/application/flashcards.py) — `get_due_cards()` now combines:
  1. Cards with `study_progress.next_review <= today` (existing behavior).
  2. **Brand-new, never-reviewed cards from the KB's artifacts** with default SM-2 state (ease 2.5, interval 0, repetitions 0, `next_review = today`).

  Without (2), a fresh user with newly generated cards saw the empty-state screen because `study_progress` rows are only created on the first review — that was the actual root cause of "doesn't work at all".

  `due_count()` now mirrors `get_due_cards()` for consistency.

- [frontend/src/app/pages/flashcards/flashcards.ts](../../../../frontend/src/app/pages/flashcards/flashcards.ts) + [.html](../../../../frontend/src/app/pages/flashcards/flashcards.html) — added `errorMessage` signal and an error banner with retry. Previously HTTP errors were swallowed (`error: () => this.loading.set(false)`), leaving the page in a stuck/empty state with no feedback.

### 3. Quizzes (and all generated content) in English on a Polish KB

Two compounding bugs; both fixed.

**Bug 3A — KB locale not threaded into quiz pipeline:**

- [mindforge/application/quiz.py](../../../../mindforge/application/quiz.py) — `start_session()` and `submit_answer()` accept new keyword `prompt_locale: str | None`. When provided, the agent's `ProcessingSettings` is rebuilt with `dataclasses.replace(self._settings, prompt_locale=prompt_locale)` so `QuizGeneratorAgent` and `QuizEvaluatorAgent` see the KB's locale.
- [mindforge/api/routers/quiz.py](../../../../mindforge/api/routers/quiz.py) — both endpoints now load the KB once (already required for ownership check) and pass `kb.prompt_locale` to the service. `submit_answer` now also takes `kb_repo` to do the same.

**Bug 3B (the dominant cause) — every `pl/*.md` prompt was English with no Polish directive:**
Translated all 17 prompt files to actual Polish, with explicit "Cała treść MUSI być w języku polskim" instructions in every system prompt. Files:

- `quiz_generator_system.md`, `quiz_generator_user.md`
- `quiz_evaluator_system.md`, `quiz_evaluator_user.md`
- `flashcard_gen_system.md`, `flashcard_gen_user.md`
- `summarizer_system.md`, `summarizer_user.md`, `summarizer_article_context.md`, `summarizer_image_context.md`, `summarizer_prior_concepts.md`
- `concept_mapper_system.md`, `concept_mapper_user.md`
- `preprocessor_system.md`, `relevance_guard_system.md`, `image_analyzer_system.md`, `article_fetcher_system.md`

Programmatic identifiers (JSON keys like `card_type`, enum values like `BASIC`/`CLOZE`/`open_ended`, relation labels like `IS_A`/`RELATES_TO`, snake_case concept keys) are kept in their original technical form per inline instructions to avoid breaking parsers.

Per agent standards (PROMPT_VERSION must bump on prompt content change), bumped `_BASE_VERSION` from `1.0.0` → `1.1.0` in every prompt module under `mindforge/infrastructure/ai/agents/`. This invalidates checkpoint fingerprints so the pipeline re-generates content on next run.

## Tests

**New tests:**

- [tests/unit/application/test_flashcard_service.py](../../../../tests/unit/application/test_flashcard_service.py):
  - `test_unreviewed_cards_in_artifacts_are_returned_as_due` (regression for "doesn't work at all").
  - `test_combines_scheduled_and_new_cards_without_duplicates`.
  - `test_counts_combined_due_and_new_cards` (replaces stale `due_count` delegation test).
- [tests/unit/application/test_quiz_service.py](../../../../tests/unit/application/test_quiz_service.py):
  - `test_kb_prompt_locale_threaded_to_agent_context` (regression for English-quiz bug).
- [tests/integration/graph/test_graph.py](../../../../tests/integration/graph/test_graph.py):
  - `test_get_concept_edges_returns_relates_to`.

**Test infra:**

- [tests/conftest.py](../../../../tests/conftest.py) — `StubRetrievalAdapter` now satisfies the extended `RetrievalPort` (`get_concept_edges`).

## Verification

```
pytest tests/unit -q
→ 419 passed, 7 skipped
```

Two pre-existing failures unrelated to this work:

- `test_quiz_generator_not_in_pipeline_imports` — references hardcoded foreign filesystem path `d:\Dokumenty\Projekty\mindforge\...`.
- `test_strips_deep_path` — stale assertion vs current security-first absolute-path rejection in `UploadSanitizer`.

Five integration ERRORs in `TestMarkdownParser` are pre-existing collection errors due to optional parser deps not installed.

No new errors introduced. All TypeScript/Python files lint clean.
