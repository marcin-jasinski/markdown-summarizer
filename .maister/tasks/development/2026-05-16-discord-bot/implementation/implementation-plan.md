# Implementation Plan — Phase 14: Discord Bot

## Overview

Implements the MindForge Discord bot adapter end-to-end: domain/infrastructure extensions for user enumeration, Discord-specific auth guards and i18n messages, four slash-command cogs (quiz, search, upload, notifications), an async composition root in `bot.py`, and a full unit-test suite. All work is additive within `mindforge/discord/` with two small extensions to `domain/ports.py` and `infrastructure/persistence/identity_repo.py`. The `mindforge-discord` entry point in `pyproject.toml` already exists — no packaging changes needed.

---

## Task Groups

### Group 1: Domain & Infrastructure Extensions

**Files**:
- `mindforge/infrastructure/config.py`
- `mindforge/domain/ports.py`
- `mindforge/infrastructure/persistence/identity_repo.py`

**Dependencies**: None

**Steps**:

- [ ] 1.0 Complete domain & infrastructure extension layer
  - [ ] 1.1 Write tests for `list_by_provider` (2 tests, placed in `tests/unit/discord/test_infrastructure.py` temporarily — moved or deleted after Group 5 supersedes)
    - `test_list_by_provider_returns_pairs`: mock SQLAlchemy result → assert returns `list[tuple[UUID, str]]`
    - `test_list_by_provider_filters_by_provider`: two providers in DB mock → only matching provider rows returned
  - [ ] 1.2 Extend `AppSettings` in `mindforge/infrastructure/config.py`
    - Add `discord_reminder_hour: int = 8` after `discord_allowed_guilds` field
    - Spec ref: §"mindforge/infrastructure/config.py (extend)"
  - [ ] 1.3 Extend `ExternalIdentityRepository` protocol in `mindforge/domain/ports.py`
    - Add abstract method `async def list_by_provider(self, provider: str) -> list[tuple[UUID, str]]`
    - Docstring: "Return all (user_id, external_id) pairs linked to *provider*."
    - Spec ref: §"mindforge/domain/ports.py (extend ExternalIdentityRepository)"
  - [ ] 1.4 Implement `list_by_provider` in `PostgresIdentityRepository` (`mindforge/infrastructure/persistence/identity_repo.py`)
    - SQL: `SELECT user_id, external_id FROM external_identities WHERE provider = :provider ORDER BY user_id`
    - Use `select(ExternalIdentityModel.user_id, ExternalIdentityModel.external_id).where(...)`
    - Return `[(row.user_id, row.external_id) for row in result]`
    - Spec ref: §"mindforge/infrastructure/persistence/identity_repo.py (extend)"
  - [ ] 1.5 Ensure Group 1 tests pass
    - Run only the 2 tests written in 1.1
    - Verify protocol conformance: `PostgresIdentityRepository` satisfies updated `ExternalIdentityRepository`

**Acceptance Criteria**:
- The 2 tests pass
- `PostgresIdentityRepository` passes a `isinstance`/`Protocol` check for `ExternalIdentityRepository`
- No existing callers of `find_user_id`, `link`, `create_user_and_link` broken (additive only)

---

### Group 2: Discord Core (messages, auth, views)

**Files**:
- `mindforge/discord/messages.py`
- `mindforge/discord/auth.py`
- `mindforge/discord/views.py`

**Dependencies**: Group 1 (needs `AppSettings` with `discord_reminder_hour`)

**Steps**:

- [ ] 2.0 Complete Discord core helpers layer
  - [ ] 2.1 Write 6 tests for auth guards (`tests/unit/discord/test_auth.py`) — **tests first**
    - `test_guild_check_passes_when_list_empty`: `discord_allowed_guilds=None`, any guild_id → returns `True`, no response sent
    - `test_guild_check_passes_allowed_guild`: `discord_allowed_guilds="12345"`, `guild_id=12345` → returns `True`
    - `test_guild_check_blocks_unknown_guild`: `discord_allowed_guilds="99999"`, `guild_id=12345` → returns `False`; `send_message` called
    - `test_ownership_check_passes_matching_user`: `user.id=1001`, `expected=1001` → returns `True`
    - `test_ownership_check_blocks_wrong_user`: `user.id=1001`, `expected=9999` → returns `False`; `send_message` called
    - `test_guild_check_ephemeral_flag`: blocked guild → `send_message` called with `ephemeral=True`
    - Mock: `AsyncMock` for `interaction.response.send_message`; `MagicMock(spec=discord.Interaction)` for interaction
    - Spec ref: §"tests/unit/discord/test_auth.py"
  - [ ] 2.2 Create `mindforge/discord/__init__.py` package marker for test directory
    - `tests/unit/discord/__init__.py` — empty file
  - [ ] 2.3 Create `mindforge/discord/messages.py`
    - Full `MESSAGES` dict with all keys from spec: guild/auth, KB, quiz (8 keys), search (2), upload (6), reminder, generic error
    - `get_message(key, locale="pl", **kwargs) -> str` — Polish default, format with kwargs, key-name fallback
    - `score_emoji(score: int) -> str` — `_SCORE_EMOJI` dict mapping 0–5 → emoji
    - Spec ref: §"mindforge/discord/messages.py (new)" — use exact message strings from spec
  - [ ] 2.4 Create `mindforge/discord/auth.py`
    - `async def guild_check(interaction, settings) -> bool`
      - Empty `discord_allowed_guild_list` → return `True` (allow all / dev mode)
      - `interaction.guild_id not in allowed_list` → `await interaction.response.send_message(get_message("guild_not_allowed"), ephemeral=True)` → return `False`
    - `async def interaction_ownership_check(interaction, expected_user_id, settings) -> bool`
      - `interaction.user.id != expected_user_id` → send `"not_your_interaction"` ephemeral → return `False`
    - **Critical**: both functions use `interaction.response.send_message` (not `followup`); they must be called **before** any `defer()` in command handlers
    - Spec ref: §"mindforge/discord/auth.py (new)" + audit finding C-1
  - [ ] 2.5 Create `mindforge/discord/views.py`
    - `class KBSelectView(discord.ui.View)` with `timeout=60.0`
    - Constructor accepts `kbs: list[KnowledgeBase]`, `callback: Callable[[discord.Interaction, UUID], Awaitable[None]]`
    - `discord.ui.Select` with `SelectOption(label=kb.name[:100], value=str(kb.kb_id))`
    - `placeholder=get_message("select_kb_placeholder")`
    - `_on_select` callback: parse `UUID(interaction.data["values"][0])`, call `self.stop()`, then `await self._callback(interaction, kb_id)`
    - Spec ref: §"KBSelectView shared utility"
  - [ ] 2.6 Ensure Group 2 tests pass
    - Run only the 6 auth tests written in 2.1
    - Verify `get_message` returns Polish strings by default and falls back to key name for unknown keys

**Acceptance Criteria**:
- All 6 auth tests pass
- `messages.py` contains all message keys referenced in cog specs
- `guild_check` uses `interaction.response` (not `followup`), ensuring no `discord.InteractionResponded`

---

### Group 3: Command Cogs

**Files**:
- `mindforge/discord/cogs/quiz.py`
- `mindforge/discord/cogs/search.py`
- `mindforge/discord/cogs/upload.py`
- `mindforge/discord/cogs/notifications.py`
- `mindforge/discord/cogs/__init__.py`

**Dependencies**: Group 2

**Steps**:

- [ ] 3.0 Complete command cogs layer
  - [ ] 3.1 Write 8 tests for `QuizCog` (`tests/unit/discord/test_quiz_cog.py`) — **tests first**
    - `test_quiz_start_single_kb_starts_session`: 1 KB, `QuizStartResult` returned → `start_session` called, Redis `setex` called, `followup.send` with question text
    - `test_quiz_start_no_kb_sends_message`: `list_for_user=[]` → `followup.send` with `"no_knowledge_bases"`
    - `test_quiz_start_no_weak_concepts`: `start_session` raises `NoWeakConceptsError` → `followup.send` with `"quiz_no_weak_concepts"`
    - `test_quiz_start_redis_unavailable`: `redis_client=None` → `followup.send` with `"quiz_redis_unavailable"`
    - `test_quiz_answer_loads_session`: Redis returns valid JSON, `submit_answer` returns `QuizEvalResult` → `submit_answer` called correctly, Redis `delete` called
    - `test_quiz_answer_no_session`: Redis returns `None` → `followup.send` with `"quiz_no_session"`, `submit_answer` not called
    - `test_quiz_answer_session_expired`: `submit_answer` raises `QuizSessionNotFoundError` → `followup.send` with `"quiz_session_not_found"`, Redis `delete` called
    - `test_quiz_answer_never_exposes_reference_answer`: `submit_answer` returns result → `followup.send` args do not contain `"reference_answer"`
    - Mock: patch `IdentityResolver` to return fixed UUID; `AsyncMock(spec=QuizService)`, `AsyncMock(spec=KnowledgeBaseService)`, `AsyncMock()` for Redis; `async_sessionmaker` mock as async context manager
    - Spec ref: §"tests/unit/discord/test_quiz_cog.py"
  - [ ] 3.2 Write 4 tests for `SearchCog` (`tests/unit/discord/test_search_cog.py`) — **tests first**
    - `test_search_returns_embed`: 3 results → `followup.send` called with `embed=` kwarg, embed has 3 fields
    - `test_search_no_results`: 0 results → `followup.send` with `"search_no_results"` containing query
    - `test_search_auto_picks_single_kb`: 1 KB → `search` called without dropdown
    - `test_search_blocked_guild`: `guild_check` returns `False` → `search_service.search` not called
    - Spec ref: §"tests/unit/discord/test_search_cog.py"
  - [ ] 3.3 Write 5 tests for `UploadCog` (`tests/unit/discord/test_upload_cog.py`) — **tests first**
    - `test_upload_success`: `ingest` returns `IngestionResult` → `followup.send` with `"upload_success"` containing filename and task_id
    - `test_upload_file_too_large`: `attachment.size=100MB`, `max_document_size_mb=10` → `followup.send` with `"upload_too_large"`, `ingest` not called
    - `test_upload_duplicate_content`: `ingest` raises `DuplicateContentError` → `followup.send` with `"upload_duplicate"`
    - `test_upload_limit_reached`: `ingest` raises `PendingTaskLimitError` → `followup.send` with `"upload_limit_reached"`
    - `test_upload_uses_discord_upload_source`: `ingest` succeeds → called with `upload_source=UploadSource.DISCORD`
    - Spec ref: §"tests/unit/discord/test_upload_cog.py"
  - [ ] 3.4 Write 4 tests for `NotificationsCog` (`tests/unit/discord/test_notifications.py`) — **tests first**
    - `test_reminders_sent_for_due_cards`: 2 users, 1 KB each, `due_count=3` → `fetch_user` called 2×, `user.send` called 2× with due count
    - `test_no_reminder_when_zero_due`: `due_count=0` → `user.send` not called
    - `test_reminder_survives_dm_blocked`: `user.send` raises `discord.Forbidden` → no exception propagates, other users still processed
    - `test_list_by_provider_called_with_discord`: standard setup → `list_by_provider` called with `"discord"`
    - Spec ref: §"tests/unit/discord/test_notifications.py"
  - [ ] 3.5 Create `mindforge/discord/cogs/quiz.py`
    - `class QuizCog(commands.Cog)` — constructor: `quiz_service, kb_service, redis_client, settings, session_factory`
    - `quiz_group = app_commands.Group(name="quiz", description="Quiz commands")`
    - `quiz_start(interaction, topic=None)`: guild_check **first** → defer → resolve identity → KB select → `_do_quiz_start`
    - `_do_quiz_start(interaction, kb_id, user_id, topic)`: Redis availability check → fresh session → `start_session` → store JSON in Redis with `setex` → `followup.send` question
    - `quiz_answer(interaction, answer)`: guild_check **first** → defer → Redis get → resolve identity (fresh session) → fresh session → `submit_answer` → Redis delete → format result
    - Exception mapping: `NoWeakConceptsError`, `QuizSessionNotFoundError`, `QuizQuestionNotFoundError`, `QuizAccessDeniedError`, `RuntimeError`
    - **Security**: never include `reference_answer`, `grounding_context`, `raw_prompt`, `raw_completion`
    - **Session pattern**: every DB call in its own `async with self._session_factory() as session:` block; `IdentityResolver(PostgresIdentityRepository(session))` created fresh per command
    - Spec ref: §"mindforge/discord/cogs/quiz.py (new)" + audit findings C-1, I-1, I-2, I-4
  - [ ] 3.6 Create `mindforge/discord/cogs/search.py`
    - `class SearchCog(commands.Cog)` — constructor: `search_service, kb_service, settings, session_factory`
    - `search(interaction, query)`: guild_check **first** → defer → resolve identity (fresh session) → KB select → `search_service.search(query, kb_id, user_id, top_k=5)` → embed or no-results message
    - Build `discord.Embed` with title from `get_message("search_results_title", query=query)`, color `0x5865F2`; add up to 5 fields truncated to 500 chars
    - Spec ref: §"mindforge/discord/cogs/search.py (new)"
  - [ ] 3.7 Create `mindforge/discord/cogs/upload.py`
    - `class UploadCog(commands.Cog)` — constructor: `ingestion_service, kb_service, settings, session_factory`
    - `upload(interaction, attachment)`: guild_check **first** → defer → size check (`attachment.size <= settings.max_document_size_mb * 1024 * 1024`) → resolve identity (fresh session) → KB select → `attachment.read()` → fresh session → `ingest(..., UploadSource.DISCORD, ..., connection=session)` → `session.commit()`
    - Exception mapping: `UploadRejectedError`, `DuplicateContentError`, `PendingTaskLimitError`, generic `Exception` (log + `"upload_failed"`)
    - Spec ref: §"mindforge/discord/cogs/upload.py (new)"
  - [ ] 3.8 Create `mindforge/discord/cogs/notifications.py`
    - `class NotificationsCog(commands.Cog)` — constructor: `bot, settings, session_factory`
    - `@tasks.loop(hours=24)` on `send_reminders`
    - `send_reminders`: fresh session → `local_repo = PostgresIdentityRepository(session)` → `pairs = await local_repo.list_by_provider("discord")` → iterate → per-user fresh session for KB service → per-KB fresh session for flashcard service → `fetch_user` → DM if `count > 0`
    - `before_reminders`: `await bot.wait_until_ready()` → sleep until next `discord_reminder_hour` UTC using `discord.utils.sleep_until`
    - Silent `discord.Forbidden` + `discord.NotFound` — DEBUG log only
    - Spec ref: §"mindforge/discord/cogs/notifications.py (new)" + audit finding I-3
  - [ ] 3.9 Update `mindforge/discord/cogs/__init__.py`
    - Export: `QuizCog`, `SearchCog`, `UploadCog`, `NotificationsCog`
    - `__all__ = ["QuizCog", "SearchCog", "UploadCog", "NotificationsCog"]`
    - Spec ref: §"mindforge/discord/cogs/__init__.py (update)"
  - [ ] 3.10 Ensure Group 3 tests pass
    - Run only the 21 tests written in 3.1–3.4 (8+4+5+4)
    - All mocks in place; no real DB/Discord/Redis calls

**Acceptance Criteria**:
- All 21 cog tests pass
- `guild_check` called **before** `defer()` in every command handler — verified by test assertions
- Per-command `async with session_factory()` pattern used consistently — no session held across awaits
- `IdentityResolver` constructed fresh per command — no cog-level singleton
- `reference_answer` absence asserted by dedicated test

---

### Group 4: Composition Root & Entry Point

**Files**:
- `mindforge/discord/bot.py`

**Dependencies**: Group 3

**Steps**:

- [ ] 4.0 Complete async composition root
  - [ ] 4.1 Write 2 tests for `bot.py` startup behavior
    - `test_main_raises_on_missing_token`: `AppSettings(discord_bot_token=None)` → `main()` raises `ValueError` before any network call
    - `test_bot_adds_all_four_cogs`: mock all services; call `_async_main` up to `bot.add_cog` → verify `QuizCog`, `SearchCog`, `UploadCog`, `NotificationsCog` added
    - Note: these bootstrap tests may be placed in a lightweight `tests/unit/discord/test_bot.py`
  - [ ] 4.2 Rewrite `mindforge/discord/bot.py` — `MindForgeBot` class
    - `class MindForgeBot(discord.Client)` — constructor sets `discord.Intents` with `dm_messages=True`, creates `self.tree = app_commands.CommandTree(self)`, stores `self.settings`
    - `setup_hook`: `await self.tree.sync()` to register global slash commands
    - `on_ready`: log `"MindForge Discord bot ready as %s"`
    - Spec ref: §"mindforge/discord/cogs/bot.py (rewrite)"
  - [ ] 4.3 Implement `_async_main()` composition root
    - Step 1: `AppSettings()` → `validate_settings()` → configure logging → guard `discord_bot_token`
    - Step 2: `create_async_engine(settings.database_url)` → `async_sessionmaker(..., expire_on_commit=False)`
    - Step 3: optional `_init_neo4j(settings)`
    - Step 4: `LiteLLMGateway(default_model=..., model_map=..., fallback_models=..., timeout_seconds=30.0, max_retries=3, api_key=...)`
    - Step 5: optional Redis via `_init_redis(settings)` — `redis.asyncio.from_url(settings.redis_url)` or `None`
    - Step 6: `QuizSessionStore` (Redis or PG fallback)
    - Step 7: retrieval adapter (optional Neo4j)
    - Step 8: construct application-layer services with session-scoped repos; **no long-lived IdentityResolver** — each cog command builds one fresh
    - Step 9: `bot.add_cog(QuizCog(...))`, `SearchCog`, `UploadCog`, `NotificationsCog`
    - Step 10: `try: await bot.start(token) finally: await engine.dispose()` + cleanup Redis + Neo4j
    - **Audit fix I-1**: no `_IdentityResolverFactory` — remove from composition root, pass `session_factory` to cogs instead
    - Spec ref: §"mindforge/discord/bot.py (rewrite)" + audit finding I-1
  - [ ] 4.4 Implement `main()` entry point
    - `def main() -> None: asyncio.run(_async_main())`
    - Must be the exact function referenced by `mindforge-discord` entry point in `pyproject.toml`
  - [ ] 4.5 Fix Phase reference in docstring
    - Module docstring: `"""Discord bot — async composition root. Phase 14."""` — audit finding M-4
  - [ ] 4.6 Ensure Group 4 tests pass
    - Run only the 2 tests written in 4.1

**Acceptance Criteria**:
- Both startup tests pass
- `bot.py` imports cleanly with no module-level side effects
- `mindforge-discord` entry point correctly calls `main()` → `asyncio.run(_async_main())`
- No `_IdentityResolverFactory` reference anywhere in `bot.py`

---

### Group 5: Unit Test Suite

**Files**:
- `tests/unit/discord/__init__.py`
- `tests/unit/discord/test_auth.py` (written in 2.1)
- `tests/unit/discord/test_quiz_cog.py` (written in 3.1)
- `tests/unit/discord/test_search_cog.py` (written in 3.2)
- `tests/unit/discord/test_upload_cog.py` (written in 3.3)
- `tests/unit/discord/test_notifications.py` (written in 3.4)
- `tests/unit/discord/test_bot.py` (written in 4.1)

**Dependencies**: Group 3, Group 4

**Steps**:

- [ ] 5.0 Review and fill critical test gaps
  - [ ] 5.1 Review all 29 tests written in Groups 2–4 (6+8+4+5+4+2)
    - Verify mock strategies are consistent across files
    - Verify `guild_check → defer` ordering is tested in quiz, search, upload cogs
    - Verify session factory mock pattern (`__aenter__`/`__aexit__` as `AsyncMock`) is applied uniformly
  - [ ] 5.2 Analyze gaps specific to Phase 14 features
    - Check: `KBSelectView` callback invocation tested? (multi-KB scenario)
    - Check: `before_reminders` UTC sleep-until logic tested?
    - Check: `score_emoji` for all score values (0–5) tested?
    - Check: `get_message` locale fallback (English locale) tested?
  - [ ] 5.3 Write up to 6 additional strategic tests to close identified gaps
    - `test_messages_locale_fallback`: `get_message("guild_not_allowed", locale="en")` → English string returned
    - `test_score_emoji_all_values`: `score_emoji(0)` = `"❌"`, `score_emoji(5)` = `"⭐"` etc.
    - `test_kb_select_view_callback_invoked`: mock `callback`, simulate `_on_select` → assert `callback` called with correct `UUID`
    - Additional tests as gaps are found (up to 3 more)
  - [ ] 5.4 Run full Phase 14 test suite
    - `pytest tests/unit/discord/ -v`
    - Target: all 29 + up to 6 additional (≤35 total) passing
    - No skipped tests; no warnings about missing fixtures

**Acceptance Criteria**:
- All feature tests pass (29–35 total)
- No more than 6 additional tests added
- `pytest tests/unit/discord/` exits 0
- Existing `tests/unit/` tests remain green (regression check: `pytest tests/unit/ -v --ignore=tests/unit/discord/` before and after)

---

## Dependency Graph

```
Group 1: Domain & Infrastructure Extensions
  (config.py + ports.py + identity_repo.py)
        │
        ▼
Group 2: Discord Core
  (messages.py + auth.py + views.py)
        │
        ▼
Group 3: Command Cogs
  (quiz.py + search.py + upload.py + notifications.py + cogs/__init__.py)
        │
        ▼
Group 4: Composition Root
  (bot.py)
        │
        ▼
Group 5: Test Suite Review
  (test_auth.py ← written in G2, test_*_cog.py ← written in G3, test_bot.py ← written in G4)
```

Linear dependency chain — each group builds directly on the prior. No parallel groups.

---

## Risk Register

| ID | Risk | Impact | Mitigation |
|----|------|--------|------------|
| R-1 | **`discord.InteractionResponded` on non-allowlisted guilds** (audit C-1) | High — crashes every command invocation at runtime | `guild_check` called **before** `interaction.response.defer()` in all three command cogs; enforced by test assertions that verify call order |
| R-2 | **Stale session in long-lived services** (audit I-3) | High — `AsyncSession` closed after first command, future commands fail with detached-instance errors | Per-command `async with session_factory() as session:` blocks in every cog; no session-scoped service held at cog level; cogs receive `session_factory` not pre-built services |
| R-3 | **`IdentityResolver` held as cog-level singleton** (audit I-1) | High — resolver wraps session-scoped repo; second command raises `InvalidRequestError` on closed session | No `IdentityResolver` passed to cog constructors; each command builds `IdentityResolver(PostgresIdentityRepository(session))` fresh inside its session block |
| R-4 | **`pending["user_discord_id"]` KeyError in `/quiz answer`** (audit I-2) | Medium — Redis key scoped to `interaction.user.id` already guarantees ownership; explicit check is redundant and broken | Removed `interaction_ownership_check` call from `/quiz answer` per audit recommendation; Redis key scoping is the ownership mechanism |
| R-5 | **`QuizQuestionNotFoundError` unhandled** (audit I-4) | Medium — propagates as uncaught exception if question_id in Redis no longer matches DB | Mapped to `"quiz_session_not_found"` message + `redis.delete(key)` cleanup; covered by dedicated test |
| R-6 | **Redis unavailable at startup** | Low — bot startup fails if Redis client throws on connection | `redis_client = None` graceful degradation; quiz commands respond with `"quiz_redis_unavailable"`; reminder task uses direct DB, no Redis dependency |
| R-7 | **`discord.Forbidden` / `discord.NotFound` in reminder task** | Low — bot process crashes if DM blocked | Silent except block (DEBUG log only); remaining users continue processing; covered by `test_reminder_survives_dm_blocked` |
| R-8 | **`KBSelectView` `settings` parameter not carrying locale** (audit M-2) | Low — `interaction_ownership_check(settings=...)` parameter serves no documented purpose | `settings` parameter retained for future `bot_locale` field; current implementation always uses Polish default; no functional risk |

---

## Acceptance Criteria

Mirrors spec §"Success Criteria" — all items are checkable post-implementation:

- [ ] `/quiz start` with 1 KB calls `QuizService.start_session()` and posts a question; session stored in Redis under `discord:quiz:pending:{user_id}`
- [ ] `/quiz start` with >1 KB presents a `KBSelectView` dropdown before starting
- [ ] `/quiz answer <text>` loads the Redis session, calls `QuizService.submit_answer()`, posts score/feedback, deletes Redis key
- [ ] `/quiz answer` with no active session responds with `"quiz_no_session"` message
- [ ] `/search <query>` posts a Discord embed with up to 5 results
- [ ] `/upload <attachment>` downloads bytes, calls `IngestionService.ingest(..., UploadSource.DISCORD)`, posts task ID
- [ ] All three commands (`/quiz start`, `/search`, `/upload`) return an ephemeral `"guild_not_allowed"` error on non-allowlisted guild, **without crashing**
- [ ] `NotificationsCog` DMs users with `due_count > 0` once daily at `DISCORD_REMINDER_HOUR` UTC; skips users with `due_count == 0`
- [ ] `mindforge-discord` entry point starts the bot (calls `asyncio.run(_async_main())`); missing `DISCORD_BOT_TOKEN` raises `ValueError` before any network call
- [ ] `ExternalIdentityRepository` protocol has `list_by_provider`; `PostgresIdentityRepository` implements it
- [ ] `AppSettings` includes `discord_reminder_hour: int = 8`
- [ ] All 29–35 unit tests in `tests/unit/discord/` pass with `pytest tests/unit/discord/`
- [ ] No `reference_answer`, `grounding_context`, `raw_prompt`, `raw_completion` appear in any Discord message payload
- [ ] `get_errors()` reports no new type errors in modified/created files
- [ ] Existing unit tests (`tests/unit/`) remain green

---

## Standards Compliance

Follow standards from `.maister/docs/standards/`:
- `global/` — always applicable (no module-level singletons, no import-time I/O, all imports at module top level, `try/except ImportError` for optional dependencies)
- `backend/` — per-command DB session pattern; configuration via `AppSettings` only; `UploadSource` enum usage
- `security/` — server-authoritative grading: never expose `reference_answer` or `grounding_context`; guild allowlist enforced in every command; untrusted attachment filenames handled by `IngestionService`

## Notes

- **Test-Driven**: every group starts with writing tests before the implementation files
- **Run Incrementally**: after each group, run only that group's new tests — not the full suite
- **Mark Progress**: check off each `[ ]` step as completed
- **Reuse First**: `IdentityResolver`, `UserInfo`, `AppSettings`, all application services — all pre-built; cogs are thin adapters only
- **No pyproject.toml changes**: `mindforge-discord` entry point already registered; `discord.py>=2.4.0` already a dependency
- **Audit fixes built in**: C-1 (guild_check ordering), I-1 (no singleton resolver), I-2 (remove redundant ownership check), I-3 (per-command sessions), I-4 (QuizQuestionNotFoundError handler) all addressed in the steps above
