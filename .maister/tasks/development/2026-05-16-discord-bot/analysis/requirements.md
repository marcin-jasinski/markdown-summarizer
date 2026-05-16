# Requirements — Phase 14: Discord Bot

**Date:** 2026-05-16
**Gathered from:** Q&A with user + gap analysis + codebase analysis

---

## Initial Description

Implement the Discord bot (Phase 14 per `.maister` implementation plan). The bot must:
- Provide slash commands: /quiz start, /quiz answer, /search, /upload
- Enforce guild allowlists via mindforge/discord/auth.py
- Resolve Discord users to internal UUIDs via IdentityResolver (provider='discord')
- Delegate all business logic to application services
- Wire composition root in mindforge/discord/bot.py
- Implement per-user SR reminders via DM (once daily)
- Write unit tests: identity resolution, allowlist enforcement, interaction ownership
- Ensure mindforge-discord entry point is callable

---

## Q&A

**Q: Does the user journey look right?**
A: Yes — `/quiz start` shows a dropdown of KBs, user selects, bot starts quiz, follow-up message with question.

**Q: Which slash commands?**
A: All — `/quiz start`, `/quiz answer`, `/search`, `/upload` (attachment), plus daily SR reminders via DM.

**Q: Language for response messages?**
A: Both — i18n-ready strings (Polish default, English supported). Use a simple dict-based approach with a `locale` parameter, not a heavy i18n framework.

**Q: Reminder schedule?**
A: Once daily — background task (discord.py tasks.loop), configurable hour via env variable (DISCORD_REMINDER_HOUR, default 8).

---

## Similar Features / Reusable Code

- `mindforge/api/main.py` — lifespan composition root pattern to replicate
- `mindforge/api/routers/quiz.py` — shows how QuizService is used (template for quiz cog)
- `mindforge/api/auth.py` — IdentityResolver (already importable, no changes needed)
- `mindforge/domain/models.py` — UploadSource.DISCORD already defined
- `mindforge/infrastructure/config.py` — discord_bot_token, discord_allowed_guilds already defined

---

## Visual Assets

None (Discord slash commands, no Angular UI).

---

## Functional Requirements

### FR-1: Composition Root (bot.py)
- Async `main()` function using `discord.Client` (with `app_commands.CommandTree`)
- On startup: load AppSettings, validate, create DB engine + session factory, create AI gateway, create Neo4j context, create Redis client, create repositories, create IdentityResolver, create all services, register cogs, call `bot.start(settings.discord_bot_token)`
- On shutdown: graceful teardown (close DB engine, close Neo4j, close Redis)
- No module-level singletons, no import-time I/O

### FR-2: Guild Allowlist (auth.py)
- `guild_check(interaction: discord.Interaction) -> bool` — verify `interaction.guild_id` is in `settings.discord_allowed_guild_list`
- If list is empty (not configured): ALLOW ALL guilds (open mode for development)
- If guild not allowed: respond with "Bot nie jest dostępny w tym serwerze." and return False
- `interaction_ownership_check(interaction, expected_user_id: int) -> bool` — verify invoking user is the session owner
- Both checks as reusable helper functions used by all cogs

### FR-3: /quiz start command (cogs/quiz.py)
- `/quiz start [topic: str (optional)]`
- Resolve Discord user → internal UUID via IdentityResolver
- Show KB selector (Discord Select menu) with user's knowledge bases
- On selection: call `QuizService.start_session(user_id, kb_id, topic)`
- Post follow-up message with question text + session_id (for the answer command)
- Store `{discord_user_id: {session_id, question_id, kb_id}}` in Redis (key: `discord:quiz:pending:{user_id}`)
- Error handling: `NoWeakConceptsError` → "Brak słabych pojęć do przećwiczenia w tej bazie."

### FR-4: /quiz answer command (cogs/quiz.py)
- `/quiz answer <answer: str>`
- Load pending session from Redis by Discord user ID
- If no pending session: "Brak aktywnej sesji quizu. Użyj /quiz start."
- Verify interaction ownership (invoking user = session owner)
- Call `QuizService.submit_answer(user_id, kb_id, session_id, question_id, answer)`
- Post formatted result: score (emoji rating), feedback, explanation
- Clear session from Redis after answer
- Error handling: `QuizSessionNotFoundError`, `QuizAccessDeniedError` → appropriate messages

### FR-5: /search command (cogs/search.py)
- `/search <query: str>`
- Show KB selector if user has multiple KBs; auto-select if only one
- Call `SearchService.search(query, kb_id, user_id)`
- Post results (top 3-5) as embed with concept names and text snippets
- Empty results: "Nie znaleziono wyników dla zapytania: {query}"

### FR-6: /upload command (cogs/upload.py)
- `/upload <attachment: discord.Attachment>`
- Show KB selector if user has multiple KBs; auto-select if only one
- Download attachment bytes (verify size ≤ max_document_size_mb)
- Call `IngestionService.ingest(raw_bytes, filename, kb_id, UploadSource.DISCORD, user_id)`
- Post confirmation: "Dokument '{filename}' przesłany. ID zadania: {task_id}"
- Error handling: `DuplicateContentError` → "Ten dokument już istnieje.", `PendingTaskLimitError` → "Zbyt wiele oczekujących zadań.", `UploadRejectedError` → "Dokument odrzucony: {reason}"

### FR-7: SR Reminder DMs (cogs/notifications.py)
- Background task via `@tasks.loop(hours=24)` starting at DISCORD_REMINDER_HOUR (default 8 UTC)
- Enumerate Discord-linked users via `ExternalIdentityRepository.list_by_provider('discord')`
- For each user: query `StudyProgressStore.due_count(user_id, kb_id)` across all user's KBs
- If due_count > 0: send DM "Masz {n} kart do powtórzenia w bazie '{kb_name}'. Użyj /quiz start!"
- Skip if DM delivery fails (do not raise, log warning)

### FR-8: ExternalIdentityRepository Extension (ports.py + identity_repo.py)
- Add to `ExternalIdentityRepository` protocol in `mindforge/domain/ports.py`:
  `async def list_by_provider(self, provider: str) -> list[tuple[UUID, str]]`
  - Returns list of `(user_id, external_id)` pairs
- Implement in `mindforge/infrastructure/persistence/identity_repo.py`
- SQL: `SELECT user_id, external_id FROM external_identities WHERE provider = $1`

### FR-9: i18n-Ready Messages
- Simple `MESSAGES = {"pl": {...}, "en": {...}}` dict in each cog or a shared `mindforge/discord/messages.py`
- Default locale: Polish ("pl")
- No heavy i18n framework needed

### FR-10: Unit Tests (tests/unit/discord/)
- `test_auth.py`: guild allowlist enforcement (allowed, denied, empty list = allow-all), interaction ownership check
- `test_quiz_cog.py`: identity resolution auto-provision, quiz start flow (mock QuizService), answer flow, session-not-found error
- `test_search_cog.py`: search flow (mock SearchService), empty results
- `test_upload_cog.py`: upload success, duplicate content, pending limit exceeded
- `test_notifications.py`: reminder trigger with due cards, no DM on zero due cards

---

## Reusability Opportunities

- `IdentityResolver` from `mindforge/api/auth.py` — import directly, no changes
- `AppSettings` composition root pattern from `mindforge/api/main.py`
- `UploadSource.DISCORD` from domain models
- `KnowledgeBaseService.list_for_user()` for KB dropdown

---

## Scope Boundaries

**In scope**: bot.py, auth.py, 4 cog files, cogs/__init__.py, domain port extension, identity_repo extension, unit tests
**Out of scope**: Slack bot, CLI, Angular UI, new Alembic migrations, Discord OAuth2 web flow

---

## Technical Considerations

- Use `discord.py` (already a dependency)
- Use `discord.app_commands.CommandTree` for slash commands
- Use `discord.ui.Select` for KB dropdown (View-based component)
- Guild allowlist: if `discord_allowed_guild_list` is empty → allow all (dev mode)
- Redis key TTL for quiz sessions: `quiz_session_ttl_seconds` from settings
- DISCORD_REMINDER_HOUR env var (int, default 8) for daily reminder time
- All cog methods are `async`
- `@app_commands.guilds(*allowed_guilds)` registration for guild-scoped commands (faster propagation)
