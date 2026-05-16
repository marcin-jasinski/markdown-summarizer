# Codebase Analysis — GUI Production-Ready Pass

## Issue 1: Concept map renders unusably

**Library**: Cytoscape.js v3.33.2 (already a solid choice — keep it). Files:

- [frontend/src/app/pages/concept-map/concept-map.ts](frontend/src/app/pages/concept-map/concept-map.ts)
- [frontend/src/app/pages/concept-map/concept-map.html](frontend/src/app/pages/concept-map/concept-map.html)
- [frontend/src/app/pages/concept-map/concept-map.scss](frontend/src/app/pages/concept-map/concept-map.scss)
- [frontend/src/app/core/services/concept.service.ts](frontend/src/app/core/services/concept.service.ts)

### Defect 1A — text overflows tiny circles

[concept-map.ts](frontend/src/app/pages/concept-map/concept-map.ts#L58) — node Cytoscape style:

```ts
{ selector: 'node', style: {
  label: 'data(label)', 'font-size': '12px', padding: '10px',
  /* no text-wrap, no text-max-width, no width/height set */
}}
```

Cytoscape defaults a node to ~30px circle. With no `text-wrap`/`text-max-width`/sized `width`/`height`, multi-word labels render outside the node.

### Defect 1B — no edges drawn

The backend always returns an empty `edges` array because the Cypher query never fetches RELATES_TO edges:

- [mindforge/infrastructure/graph/cypher_queries.py](mindforge/infrastructure/graph/cypher_queries.py#L250) — `GET_CONCEPTS` does not return related neighbours.
- [mindforge/infrastructure/graph/neo4j_retrieval.py](mindforge/infrastructure/graph/neo4j_retrieval.py#L215) — `get_concepts()` builds `ConceptNode(...)` with `related` defaulting to `[]`.
- [mindforge/api/routers/concepts.py](mindforge/api/routers/concepts.py) — builds edges from `node.related`, which is empty → response always has `edges: []`.

(RELATES_TO edges DO exist in Neo4j — confirmed by `tests/integration/graph/test_graph.py::test_relates_to_edges_rebuilt`.)

---

## Issue 2: Flashcards "don't work at all"

Files: [frontend/src/app/pages/flashcards/flashcards.ts](frontend/src/app/pages/flashcards/flashcards.ts), [mindforge/api/routers/flashcards.py](mindforge/api/routers/flashcards.py), [mindforge/application/flashcards.py](mindforge/application/flashcards.py).

### Defect 2A — first-time cards never show as "due" (most likely real cause)

[mindforge/application/flashcards.py](mindforge/application/flashcards.py) — `get_due_cards()`:

```python
due_states = await self._progress.get_due_cards(user_id, kb_id, today)
if not due_states:
    return []   # <-- returns empty even if KB has hundreds of unreviewed cards
```

A `study_progress` row only exists AFTER a card is first reviewed. So a brand-new user with freshly generated flashcards sees the "Wszystko gotowe!" empty state immediately. This matches "doesn't work at all" exactly.

### Defect 2B — silent HTTP error handling

[frontend/src/app/pages/flashcards/flashcards.ts](frontend/src/app/pages/flashcards/flashcards.ts) `loadDueCards()`:

```ts
error: () => this.loading.set(false); // swallows 401/404/500 silently
```

If anything goes wrong (auth expired, server error), the user sees a blank or stuck loading state with no message.

---

## Issue 3: Quizzes (and flashcards) asked in English on a Polish KB

There are **two** independent bugs that both need fixing:

### Defect 3A — KB's `prompt_locale` is never threaded into quiz pipeline

[mindforge/api/deps.py](mindforge/api/deps.py#L294) `_build_processing_settings()` doesn't read `settings.prompt_locale` from `AppSettings`, and [mindforge/application/quiz.py](mindforge/application/quiz.py#L160) `start_session()` / `submit_answer()` never query the KB for its locale. So quiz agents always run with the dataclass default `"pl"`.

### Defect 3B — the `pl/` prompt files are written in English with no language directive (THE smoking gun)

[mindforge/infrastructure/ai/prompts/pl/quiz_generator_system.md](mindforge/infrastructure/ai/prompts/pl/quiz_generator_system.md):

```
You are an expert quiz question author for a spaced-repetition learning system.
Generate a single educational quiz question based on the provided concept context.
...
```

Same is true for `quiz_evaluator_system.md`, `flashcard_gen_system.md`, `summarizer_system.md`, etc. The prompt content is English with no "Odpowiadaj po polsku" instruction. The model dutifully replies in English. **This is why everything comes out in English even though the locale resolution code is fine in many places** (for the pipeline `pipeline_runner.py` already passes the KB locale correctly — but the prompt content is still English so the LLM still outputs English).

Even fixing 3A in isolation would not fix the user-visible bug. **3B is the dominant root cause.**

---

## Summary of fixes required

| #   | File                                                        | Change                                                                                                                                                                                               |
| --- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1A  | `concept-map.ts`                                            | Cytoscape node style: `text-wrap:'wrap'`, `text-max-width: 120`, `width:'label'+padding`, `height:'label'+padding`, `shape:'round-rectangle'`. Also use a force-directed layout with proper spacing. |
| 1B  | `cypher_queries.py` + `neo4j_retrieval.py`                  | `GET_CONCEPTS` collects related concept keys via `OPTIONAL MATCH (c)-[:RELATES_TO]-(r:Concept)` and returns `collect(DISTINCT r.key)`. `get_concepts()` populates `ConceptNode.related`.             |
| 2A  | `application/flashcards.py`                                 | `get_due_cards()` returns the union of: (a) cards with `study_progress.next_review <= today` AND (b) cards in artifacts that have NO `study_progress` row yet (new).                                 |
| 2B  | `flashcards.ts` + `flashcards.html`                         | Add `error` signal, render an error banner with retry.                                                                                                                                               |
| 3A  | `api/deps.py`, `application/quiz.py`, `api/routers/quiz.py` | Thread KB's `prompt_locale` into `start_session()` / `submit_answer()` and into `AgentContext.settings`.                                                                                             |
| 3B  | `prompts/pl/*.md`                                           | Translate all PL prompts to actual Polish, with explicit "Odpowiedz wyłącznie w języku polskim" directive in every system prompt.                                                                    |
