# Codebase Analysis Report

**Date**: 2026-05-16
**Task**: Implement Phase 14 — Discord Bot with slash commands, guild allowlists, IdentityResolver user mapping, application service delegation, and per-user SR reminder DMs
**Description**: Implement Phase 14 — Discord Bot with slash commands (quiz, search, upload), guild allowlists, IdentityResolver-based user mapping, application service delegation, and per-user SR reminder DMs
**Analyzer**: codebase-analyzer skill (3 Explore agents: File Discovery, Code Analysis, Pattern Mining)

---

## Summary

The Discord bot entry point (`mindforge/discord/bot.py`) is a complete stub with no implementation. All the required building blocks already exist — application services (`QuizService`, `SearchService`, `IngestionService`, `FlashcardsService`), the `IdentityResolver`, `UploadSource.DISCORD`, `discord_bot_token`/`discord_allowed_guilds` config fields, and `discord.py>=2.4.0` as a declared dependency. The implementation is greenfield within `mindforge/discord/` and requires only additive work with zero changes to any other layer.

---

## Files Identified

### Primary Files

**mindforge/discord/bot.py** (~10 lines)
- Current stub: only `main()` printing "mindforge-discord: not yet implemented"
- Becomes the composition root (async lifespan, service wiring, bot startup)
- Entry point registered in `pyproject.toml` as `mindforge-discord`

**mindforge/discord/cogs/__init__.py** (empty)
- Will export cog classes (`QuizCog`, `SearchCog`, `UploadCog`, `ReminderTask`)

**mindforge/discord/__init__.py** (empty)
- Package init, no changes needed

**mindforge/api/auth.py** (~400 lines — lines 320–400 relevant)
- Contains `IdentityResolver` and `UserInfo` — shared by API, Discord, Slack adapters
- `IdentityResolver.resolve(user_info: UserInfo) -> UUID` auto-provisions users
- `UserInfo(provider, external_id, display_name, email, avatar_url)`
- `make_discord_provider()` factory helper already present

**mindforge/infrastructure/config.py** (~350 lines)
- `discord_bot_token: str | None`
- `discord_allowed_guilds: str | None` (comma-separated)
- `discord_allowed_guild_list -> list[int]` property (already parses the string)
- No role-level or channel-level allowlists — guild-level only

**mindforge/api/main.py** (~300 lines)
- Template for the composition root pattern (`lifespan` async context manager)
- Pattern: load settings → init engine → build services → attach to `app.state`
- Discord bot must replicate this structure using `bot` state object instead of `app.state`

### Related Files

**mindforge/application/quiz.py**
- `QuizService` — target for `/quiz` slash command
- Public result types: `QuizStartResult`, `QuizEvalResult` (no sensitive fields)
- Exceptions: `NoWeakConceptsError`, `QuizSessionNotFoundError`, `QuizAccessDeniedError`

**mindforge/application/search.py**
- `SearchService` — target for `/search` slash command
- `SearchService.search(query, kb_id, user_id, top_k) -> SearchResult`
- `SearchResult.results: list[SearchResultItem]` — each item has `content`, `source_lesson_id`, `score`

**mindforge/application/ingestion.py**
- `IngestionService` — target for `/upload` slash command
- `IngestionService.ingest(raw_bytes, filename, kb_id, upload_source, uploaded_by, connection) -> IngestionResult`
- `UploadSource.DISCORD` already defined in `mindforge/domain/models.py`
- Exceptions: `DuplicateContentError`, `PendingTaskLimitError`, `UploadRejectedError`

**mindforge/application/flashcards.py**
- `FlashcardsService.due_count(user_id, kb_id) -> int` — used for SR reminder DMs
- Wraps `StudyProgressStore.due_count(user_id, kb_id, today)`

**mindforge/domain/ports.py**
- `ExternalIdentityRepository` protocol — backing store for `IdentityResolver`
- `StudyProgressStore` protocol — `due_count(user_id, kb_id, today) -> int`

**mindforge/domain/models.py**
- `UploadSource.DISCORD = "DISCORD"` — already present, no change needed

**mindforge/api/routers/quiz.py**
- Best template for quiz cog: shows QuizService usage, error-to-response mapping

**mindforge/api/routers/documents.py**
- Template for ingestion error handling pattern (`UploadRejectedError`, `DuplicateContentError`, `PendingTaskLimitError`)

---

## Current Functionality

The `mindforge/discord/` package is entirely unimplemented. The cogs/ subdirectory is an empty package. The single `main()` function in `bot.py` is a placeholder. No Discord interactions, slash commands, guild checks, identity resolution, or DM tasks exist.

### Key Components to Build

- **`bot.py` composition root**: async lifespan pattern (mirrors `api/main.py`), wires DB engine → session factory → repos → services → identity resolver → bot; starts the event loop
- **Guild allowlist guard**: `on_interaction` / `interaction_check` on every cog — reject if `interaction.guild_id not in settings.discord_allowed_guild_list`
- **`IdentityResolver` integration**: in every command handler, construct `UserInfo(provider="discord", external_id=str(interaction.user.id), ...)` and call `await resolver.resolve(user_info)` to obtain `user_id: UUID`
- **`QuizCog`** (`/quiz start`, `/quiz answer`): delegate to `QuizService.start_session()` and `QuizService.submit_answer()`
- **`SearchCog`** (`/search`): delegate to `SearchService.search()`
- **`UploadCog`** (`/upload`): receive Discord attachment, read bytes, call `IngestionService.ingest(..., upload_source=UploadSource.DISCORD)`
- **`ReminderTask`** (background `discord.ext.tasks.loop`): periodically query `FlashcardsService.due_count()` per user per KB and send DMs for non-zero counts

### Data Flow

```
Discord interaction
  → guild allowlist check (interaction.guild_id in allowed_guilds)
  → IdentityResolver.resolve(UserInfo("discord", user.id, ...)) → user_id: UUID
  → application service call (QuizService / SearchService / IngestionService)
  → ephemeral Discord response (Polish text, no sensitive fields)
```

SR Reminder flow:
```
tasks.loop(hours=X)
  → for each known (user_id, discord_id, kb_id) triple
  → FlashcardsService.due_count(user_id, kb_id) > 0
  → bot.fetch_user(discord_id).send("Masz N kart do powtórki w KB …")
```

---

## Dependencies

### Imports (What the Bot Depends On)

- `discord.py >= 2.4.0` — already in `pyproject.toml`; provides `discord.Bot`, `app_commands`, `ext.tasks`
- `mindforge.infrastructure.config.AppSettings` — settings with discord fields
- `mindforge.api.auth.IdentityResolver`, `UserInfo` — identity mapping
- `mindforge.application.quiz.QuizService` (+ exception types)
- `mindforge.application.search.SearchService`
- `mindforge.application.ingestion.IngestionService` (+ exception types)
- `mindforge.application.flashcards.FlashcardsService` — SR reminder counts
- `mindforge.infrastructure.db.create_async_engine` — DB pool
- `mindforge.domain.models.UploadSource` — `DISCORD` value
- `mindforge.infrastructure.persistence.*` — repositories injected into services
- `mindforge.infrastructure.security.upload_sanitizer` — sanitizer for ingestion
- `sqlalchemy.ext.asyncio.async_sessionmaker` — per-command session scope

### Consumers (What Depends on the Bot)

- `pyproject.toml` entry point `mindforge-discord = "mindforge.discord.bot:main"` — invokes `bot.main()`
- `compose.yml` `discord-bot` service — Docker entry point
- Nothing in the application or domain layer depends on the Discord adapter (correct hexagonal boundary)

**Consumer Count**: 2 (entry point, compose service)
**Impact Scope**: Low — Discord is a leaf adapter; no other code references it

---

## Test Coverage

### Test Files

- **None exist** — `tests/unit/` has no Discord-related tests
- `tests/integration/` has no Discord-related tests

### Coverage Assessment

- **Test count**: 0
- **Gaps**: All Discord functionality is untested. Unit tests should be added for:
  - Guild allowlist check logic
  - `UserInfo` construction from Discord interaction
  - Error-to-message mapping for all command handlers
  - SR reminder trigger logic (due_count > 0 → DM)

---

## Coding Patterns

### Naming Conventions

- **Cog classes**: `QuizCog`, `SearchCog`, `UploadCog` (PascalCase noun + `Cog` suffix)
- **Background tasks**: `ReminderTask` as a separate cog or task loop inside `bot.py`
- **Slash commands**: snake_case names matching the CLI intent (`/quiz`, `/search`, `/upload`)
- **Files**: one cog per file, e.g. `cogs/quiz.py`, `cogs/search.py`, `cogs/upload.py`, `cogs/reminder.py`

### Architecture Patterns

- **Style**: async, class-based cogs (`discord.ext.commands.Cog` subclasses with `app_commands`)
- **Composition root**: single `async with` block in `main()`, all shared state stored on `bot` object (no module-level globals)
- **Session scope**: new `async_sessionmaker` session per command handler, closed in `finally`
- **No business logic in cogs**: every cog method resolves identity then calls a service; all domain logic stays in `application/`
- **Security**: ephemeral responses only; never include `reference_answer`, `grounding_context`, `raw_prompt`, or `raw_completion` in any Discord message
- **User-facing messages**: Polish language (consistent with rest of project)

---

## Complexity Assessment

| Factor | Value | Level |
|--------|-------|-------|
| Files to create | ~5 new files | Medium |
| Service dependencies | ~6 application services + repos | Medium |
| Consumers affected | 0 (leaf adapter) | Low |
| Test coverage | 0 tests existing | High gap |
| Cross-cutting concerns | Identity resolution, security, SR scheduling | Medium |

### Overall: Moderate

All infrastructure (services, config, identity resolver, domain constants) is in place. The work is additive greenfield within `mindforge/discord/`. The main complexity is correctly wiring the composition root and implementing the SR background task, which requires iterating over all Discord-linked users.

---

## Key Findings

### Strengths

- `IdentityResolver` is already designed for multi-adapter use ("shared by API, Discord, and Slack adapters" per its docstring)
- `UploadSource.DISCORD` is already present in domain models — no domain changes needed
- `discord_bot_token` and `discord_allowed_guild_list` are already in `AppSettings` with correct parsing
- `discord.py >= 2.4.0` is already a declared dependency
- `FlashcardsService.due_count()` provides exactly what SR reminder DMs need
- Application services' public result types already exclude sensitive fields by design

### Concerns

- **SR reminder requires user enumeration**: `ReminderTask` needs a way to iterate all users who have Discord identities linked. No existing port exposes this — `ExternalIdentityRepository` only supports lookup by `(provider, external_id)`. A new query method `list_discord_users() -> list[tuple[UUID, str]]` (returning `(user_id, discord_id)` pairs) may be needed in the infrastructure layer.
- **KB selection in slash commands**: Commands like `/quiz start` and `/search` require a `kb_id`. A KB picker interaction (select menu or required parameter) must be designed. `KnowledgeBaseService.list_for_user(user_id)` is available.
- **No role/channel allowlists**: Config only supports guild-level allowlists (`discord_allowed_guilds`). If per-channel or per-role restrictions are needed, that is out of scope per current settings.
- **Session scope for ingestion**: `IngestionService.ingest()` takes a `connection` parameter (caller-owned transaction). The bot must manage this correctly, similar to the API router pattern.
- **Zero existing tests**: All new code must be accompanied by unit tests.

### Opportunities

- The Slack adapter is in the same state (stub) — patterns established here can be replicated directly for Phase 15 (Slack bot)
- SR reminder task can later be extended to push flashcard content (not just counts) if needed
- Discord OAuth flow (`discord_client_id`, `discord_client_secret`, `discord_redirect_uri`) is already configured for web login; the bot identity provider is separate (`discord_bot_token`)

---

## Impact Assessment

- **Primary changes**: `mindforge/discord/bot.py`, `mindforge/discord/cogs/` (new files: `quiz.py`, `search.py`, `upload.py`, `reminder.py`, updated `__init__.py`)
- **Related changes**:
  - `mindforge/infrastructure/persistence/` — potentially add `list_discord_users()` to `ExternalIdentityRepository` implementation if SR reminders require full user enumeration
  - `tests/unit/discord/` — new test directory
- **No changes required** to: `mindforge/domain/`, `mindforge/application/`, `mindforge/api/`, `mindforge/infrastructure/config.py`, `pyproject.toml`

### Risk Level: Low-Medium

The adapter is fully isolated (hexagonal boundary). No existing code is modified. Risk comes from the SR reminder needing user enumeration (potential new infrastructure query) and from the zero test baseline.

---

## Recommendations

### Implementation Strategy

1. **Composition root first** (`bot.py`):
   - Mirror `api/main.py` `lifespan()` pattern
   - Load `AppSettings`, validate `discord_bot_token` is set
   - Build DB engine → `async_sessionmaker` → all repos → all services → `IdentityResolver`
   - Store all state on `bot` object; never use module-level globals
   - Register cogs, then `await bot.start(settings.discord_bot_token)`

2. **Guild allowlist guard** (apply to all cogs):
   ```python
   async def interaction_check(self, interaction: discord.Interaction) -> bool:
       allowed = self.bot.settings.discord_allowed_guild_list
       if allowed and interaction.guild_id not in allowed:
           await interaction.response.send_message("Bot niedostępny na tym serwerze.", ephemeral=True)
           return False
       return True
   ```

3. **Identity resolution helper** (shared utility, not a service):
   ```python
   async def resolve_discord_user(resolver, interaction) -> UUID:
       return await resolver.resolve(UserInfo(
           provider="discord",
           external_id=str(interaction.user.id),
           display_name=interaction.user.display_name,
           email=None,
           avatar_url=str(interaction.user.display_avatar.url),
       ))
   ```

4. **Cog order**: `SearchCog` (simplest — one call, no session state), then `QuizCog` (multi-turn), then `UploadCog` (file handling), then `ReminderTask` (background)

5. **SR Reminder approach**: If `ExternalIdentityRepository` does not expose `list_discord_users()`, implement a PostgreSQL query directly in the reminder task using the `session_factory` to run `SELECT user_id, external_id FROM external_identities WHERE provider='discord'`. This avoids changing the port protocol for a single use case.

### Testing Strategy

- Unit test each cog's `interaction_check` with mock `interaction.guild_id`
- Unit test `resolve_discord_user` helper with a mock `IdentityResolver`
- Unit test error-to-message mapping for all command handlers
- Integration test: `IngestionService.ingest()` with `UploadSource.DISCORD` (reuse existing ingestion integration test patterns)

### Security Requirements

- Always use `ephemeral=True` for quiz question responses (prevents answers being visible to other users)
- Never include `reference_answer`, `grounding_context`, `raw_prompt`, or `raw_completion` in any Discord message
- Validate attachment content type before calling `IngestionService.ingest()` — use `upload_sanitizer.py`
- Guild allowlist check must run before any identity resolution or service call

---

## Next Steps

Proceed to gap analysis (`/maister-development` specification phase) to identify any missing infrastructure (particularly the `list_discord_users` enumeration query for SR reminders) and finalize the slash command UX design (KB picker, multi-turn quiz session state in Discord).
