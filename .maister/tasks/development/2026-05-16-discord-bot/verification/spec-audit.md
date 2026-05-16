# Specification Audit — Phase 14: Discord Bot

## Verdict

**PASS-WITH-CONCERNS**

## Summary

The specification is functionally complete, covers all six user stories from `requirements.md`, and is correct on the vast majority of interface signatures, exception names, config property names, and security constraints. However, one Critical defect (guild_check called after `defer()` causes a `discord.InteractionResponded` runtime error in every command handler) and three Important issues (undefined `_IdentityResolverFactory`, a Redis JSON key reference that doesn't exist, and an unresolved per-command session management pattern for stateful services) must be fixed before coding begins. The spec is implementable once these issues are resolved; no external decisions or new stakeholder input are required.

---

## Findings

### Critical (blockers — must fix before implementation)

| # | Location | Finding | Recommendation |
|---|----------|---------|----------------|
| C-1 | `cogs/quiz.py` `quiz_start`, `cogs/search.py` `search`, `cogs/upload.py` `upload` implementation contracts | **`guild_check` called after `interaction.response.defer()`** — all three command handlers defer first (step 1), then call `guild_check` (step 2). `guild_check` calls `await interaction.response.send_message(...)`, which raises `discord.InteractionResponded` because the initial response slot is already consumed by the `defer()`. This will crash every command invocation on non-allowlisted guilds at runtime. | Move `await guild_check(...)` call to **before** `await interaction.response.defer(...)` in all three command contracts (quiz_start, search, upload). `guild_check` should remain synchronous-path for the initial response slot; `defer()` comes after it passes. Alternatively, rewrite `guild_check` to use `interaction.followup.send()` when `interaction.response.is_done()` is `True`, but the simpler fix is reordering. |

---

### Important (should fix — risk of bugs/regressions)

| # | Location | Finding | Recommendation |
|---|----------|---------|----------------|
| I-1 | `bot.py` composition root pseudocode | **`_IdentityResolverFactory` is referenced but never defined.** The pseudocode shows `resolver = _IdentityResolverFactory(make_identity_repo, session_factory)` and then passes a `resolver: IdentityResolver` into every cog constructor. But `_IdentityResolverFactory` is not defined anywhere in the spec. Meanwhile, the composition root notes correctly say each command must construct `IdentityResolver(PostgresIdentityRepository(session))` inside its `async with session_factory()` block. The cog interface and the bot.py wiring are contradictory: you cannot pass a single long-lived `IdentityResolver` to a cog when that resolver holds a session-scoped `PostgresIdentityRepository`. | Remove `resolver: IdentityResolver` from all cog constructors. Pass `session_factory` instead (already present). Inside each command, construct the resolver fresh: `resolver = IdentityResolver(PostgresIdentityRepository(session))` within the `async with session_factory() as session:` block. Remove `_IdentityResolverFactory` reference from bot.py. This is the pattern already described correctly in the "Composition root implementation notes" prose — the pseudocode just needs to match. |
| I-2 | `cogs/quiz.py` `/quiz answer` data flow (step: `interaction_ownership_check`) | **`pending["user_discord_id"]` references a key that doesn't exist in the Redis JSON.** The Redis value stored during `/quiz start` is `{"session_id": "...", "question_id": "...", "kb_id": "..."}`. The `/quiz answer` flow calls `interaction_ownership_check(interaction, pending["user_discord_id"])` which would raise `KeyError` at runtime because the JSON has no `user_discord_id` field. (The Redis key itself — `discord:quiz:pending:{user.id}` — implicitly enforces ownership since `user.id` is the lookup key.) | Either (a) remove the `interaction_ownership_check` call from the `/quiz answer` flow entirely (the keyed lookup already guarantees ownership — only the session owner's key is fetched), or (b) add `"user_discord_id": str(interaction.user.id)` to the JSON stored in `/quiz start` and document it. Option (a) is simpler and correctly reflects the implicit ownership guarantee. |
| I-3 | `bot.py` composition root, `cogs/notifications.py` `send_reminders` contract | **Session management for stateful services (QuizService, FlashcardService, KnowledgeBaseService) is unspecified in the long-lived bot process.** The spec says services are "stateless — one instance per bot, sessions per call" but these services hold injected repositories that each wrap an `AsyncSession`. A single long-lived `FlashcardService(artifact_repo=..., study_progress=...)` whose repos were constructed at startup will hold stale/closed sessions after the first DB interaction. Additionally, `send_reminders` opens `async with session_factory() as session:` but never injects that session into `kb_service` or `flashcard_service` before calling their methods. The `NotificationsCog` also constructs a fresh `PostgresIdentityRepository(session)` locally in step 1 but then calls `await identity_repo.list_by_provider(...)` on the injected parameter (which has no session) in step 2 — these are two different objects. | Either: (a) construct all session-scoped services (KnowledgeBaseService, FlashcardService, QuizService) **per command** inside `async with session_factory()` rather than once in `main()`, mirroring how the API's FastAPI DI works; or (b) document a factory pattern where bot.py only passes `session_factory` to cogs, and cogs build services per invocation. For `NotificationsCog.send_reminders` specifically: replace `identity_repo.list_by_provider(...)` with `local_repo.list_by_provider(...)` (using the freshly-constructed repo from step 1), and add explicit per-iteration session construction for `FlashcardService` and `KnowledgeBaseService`. The spec must commit to one of these patterns and show it in the bot.py pseudocode. |
| I-4 | `cogs/quiz.py` implementation contract | **`QuizQuestionNotFoundError` raised by `QuizService.submit_answer()` is not handled.** The spec maps `QuizSessionNotFoundError` and `QuizAccessDeniedError` to user messages. `QuizQuestionNotFoundError` (raised when the `question_id` from Redis no longer matches any question in the retrieved session — e.g., after data corruption or a race condition) has no handler, so it would propagate as an unhandled exception. | Add exception mapping: `QuizQuestionNotFoundError` → `get_message("quiz_session_not_found")` (session/question mismatch is functionally equivalent to not found from a user perspective) and `await redis.delete(key)` to clean up the stale Redis entry. |

---

### Minor (nice to fix — clarity/consistency)

| # | Location | Finding | Recommendation |
|---|----------|---------|----------------|
| M-1 | `cogs/quiz.py`, `cogs/search.py`, `cogs/upload.py` | **`KBSelectView` placement is ambiguous.** The spec says "implement inline in each cog or in a shared `views.py`." Three cogs use identical `KBSelectView` logic; putting it inline will duplicate ≈25 lines three times. | Commit to `mindforge/discord/views.py` as the location. Mention it in the "New Components Required" table and the cog imports. This is a minor DRY concern and does not block implementation. |
| M-2 | `auth.py` spec, `interaction_ownership_check` signature | **`settings: AppSettings` parameter serves no documented purpose.** The function signature includes `settings: AppSettings` with the docstring comment "App settings (used for locale)," but `get_message()` defaults to `"pl"` and there is no `bot_locale` or `default_locale` field on `AppSettings`. The test mock `settings = AppSettings(discord_allowed_guilds=None)` confirms settings is passed but no locale extraction is shown. | Either drop `settings` from `interaction_ownership_check` (locale is always Polish in the current spec), or add a `bot_locale: str = "pl"` field to `AppSettings` and document using it. |
| M-3 | `cogs/notifications.py` `send_reminders` message format | **`QuizEvalResult.quality_flag` exists but is silently dropped from the quiz result message.** `quality_flag: str | None` is a field on `QuizEvalResult` (confirmed in `quiz.py`). The `quiz_result` message template only shows `emoji`, `score`, `feedback`, `explanation`. This is intentional per the spec but undocumented. | Add a spec note: "`quality_flag` is intentionally omitted from the Discord result message to keep it concise. Future improvement can append it." Prevents a developer from wondering whether they forgot to include it. |
| M-4 | `mindforge/discord/bot.py` (stub) | **Stub docstring says "Implemented in Phase 13" but this is Phase 14.** The current `bot.py` stub contains the comment `"""Discord bot setup and composition root. Implemented in Phase 13."""`. | Correct the docstring in the new `bot.py` to reference Phase 14. Trivial. |

---

## Open Questions Resolved

All three design decision questions from the gap analysis are answered in `scope-clarifications.md` and reflected in the spec:

1. **KB Resolution Strategy** → Interactive dropdown with auto-select for single KB. ✓ Confirmed and specced in detail.
2. **Quiz Session State** → Redis-backed tracking (`discord:quiz:pending:{user_id}`, TTL = `quiz_session_ttl_seconds`), graceful degradation message when Redis is absent. ✓ Confirmed and specced.
3. **SR User Enumeration** → Approach B: extend `ExternalIdentityRepository` protocol with `list_by_provider(provider: str) -> list[tuple[UUID, str]]` and implement in `PostgresIdentityRepository`. ✓ Confirmed, port/implementation interfaces fully specced.

---

## Open Questions Remaining

None are external blockers requiring new stakeholder input. The two items below are internal implementation decisions the developer can resolve during coding:

1. **Long-lived service construction pattern (per I-3):** The developer must choose between per-command service construction vs factory wiring and update bot.py accordingly. Recommended: per-command construction to match FastAPI DI pattern.
2. **`KBSelectView` location (per M-1):** Developer should pick `views.py` and add it to the file manifest before coding.

---

## Verification Evidence

### Files Read and Key Facts Verified

| File | Key Facts Verified |
|------|--------------------|
| `mindforge/application/quiz.py` | `QuizService.start_session(user_id, kb_id, topic=None, *, prompt_locale=None)` ✓; `QuizService.submit_answer(user_id, kb_id, session_id, question_id, user_answer, *, prompt_locale=None)` ✓; `QuizStartResult` fields: `session_id, question_id, question_text, question_type, lesson_id` (no `reference_answer`, no `grounding_context`) ✓; `QuizEvalResult` fields: `question_id, score, feedback, explanation, is_correct, quality_flag` ✓; Exception names: `NoWeakConceptsError`, `QuizSessionNotFoundError`, `QuizQuestionNotFoundError`, `QuizAccessDeniedError` all present ✓ |
| `mindforge/application/search.py` | `SearchService.search(query, kb_id, user_id, *, top_k=None)` ✓; `SearchResult.results: list[SearchResultItem]` ✓; `SearchResultItem` has `.content`, `.source_lesson_id`, `.score` ✓ |
| `mindforge/application/ingestion.py` | `IngestionService.ingest(raw_bytes, filename, knowledge_base_id, upload_source, uploaded_by=None, *, connection=None)` ✓; Exception names: `DuplicateContentError`, `PendingTaskLimitError`, `UploadRejectedError`, `UnresolvableLessonError` present ✓ |
| `mindforge/application/knowledge_base.py` | `KnowledgeBaseService.list_for_user(owner_id) -> list[KnowledgeBase]` ✓; `KnowledgeBase.kb_id: UUID` ✓ |
| `mindforge/application/flashcards.py` | `FlashcardService.due_count(user_id: UUID, kb_id: UUID) -> int` ✓ — no `today` parameter (uses `date.today()` internally); spec is correct |
| `mindforge/api/auth.py` | `UserInfo` dataclass: `provider, external_id, display_name, email=None, avatar_url=None` ✓; `IdentityResolver.__init__(identity_repo: ExternalIdentityRepository)`; `IdentityResolver.resolve(user_info: UserInfo) -> UUID` ✓; resolver is session-scoped (holds repo with AsyncSession) ✗ contradicts "single resolver per bot" composition pseudocode |
| `mindforge/domain/ports.py` | `ExternalIdentityRepository` protocol has: `find_user_id`, `link`, `create_user_and_link` — **no `list_by_provider`** (expected; spec correctly specifies adding it) ✓; `StudyProgressStore.due_count(user_id, kb_id, today: date)` present — different from `FlashcardService.due_count` (no `today`) ✓ |
| `mindforge/infrastructure/persistence/identity_repo.py` | `PostgresIdentityRepository` has: `find_user_id`, `link`, `create_user_and_link` — **no `list_by_provider`** (expected) ✓; all methods are `async` ✓ |
| `mindforge/infrastructure/config.py` | `discord_bot_token: str | None` ✓; `discord_allowed_guilds: str | None` (raw field) ✓; `discord_allowed_guild_list` property → `list[int]` ✓; `quiz_session_ttl_seconds: int = 1800` ✓; `max_document_size_mb: int = 10` ✓; **`discord_reminder_hour` absent** (expected — spec correctly specifies adding it) ✓ |
| `mindforge/domain/models.py` | `UploadSource.DISCORD = "DISCORD"` ✓; `KnowledgeBase.kb_id: UUID` ✓ |
| `mindforge/discord/bot.py` | Confirmed 10-line stub: `def main(): print("mindforge-discord: not yet implemented")` ✓ |
| `mindforge/discord/cogs/__init__.py` | Empty file ✓ |
| `pyproject.toml` | `"discord.py>=2.4.0"` dependency present ✓; `mindforge-discord = "mindforge.discord.bot:main"` entry point present ✓ |
| `mindforge/infrastructure/ai/infra/gateway.py` | `LiteLLMGateway` class present ✓; import path `mindforge.infrastructure.ai.infra.gateway` is correct ✓ |
| `mindforge/infrastructure/db.py` | `create_async_engine(database_url, *, echo=False)` present ✓; import path correct ✓ |
