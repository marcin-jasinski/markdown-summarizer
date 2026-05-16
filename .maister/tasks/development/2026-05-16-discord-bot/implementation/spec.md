# Specification: Phase 14 — Discord Bot

## Goal

Implement a fully functional Discord bot adapter for MindForge that exposes `/quiz start`, `/quiz answer`, `/search`, and `/upload` slash commands, enforces guild allowlists, maps Discord users to internal UUIDs via `IdentityResolver`, and sends per-user spaced-repetition reminder DMs once daily — delegating all business logic to existing application services.

## User Stories

- As a Discord user, I want to start a quiz in my knowledge base via `/quiz start` so I can practice weak concepts directly from Discord.
- As a Discord user, I want to answer an active quiz question via `/quiz answer <text>` and see my score and feedback.
- As a Discord user, I want to search my knowledge base with `/search <query>` and see the top results as an embed.
- As a Discord user, I want to upload a document attachment via `/upload` so it enters the MindForge ingestion pipeline.
- As a Discord user, I want to receive a DM reminder when I have spaced-repetition cards due today.
- As a server admin, I want to restrict the bot to specific guilds so it isn't usable on unauthorized servers.

## Core Requirements

1. **Composition root** — `bot.py:main()` wires all services and starts the bot; zero module-level singletons or import-time I/O.
2. **Guild allowlist** — every command rejects interactions from non-allowlisted guilds; empty list = allow all.
3. **Identity resolution** — every command calls `IdentityResolver.resolve()` to obtain an internal `UUID` before any service call.
4. **`/quiz start [topic]`** — KB selector (dropdown if >1 KB, auto-select if =1), calls `QuizService.start_session()`, stores pending session in Redis, posts question.
5. **`/quiz answer <text>`** — loads pending session from Redis, verifies ownership, calls `QuizService.submit_answer()`, posts graded result, clears Redis key.
6. **`/search <query>`** — KB selector, calls `SearchService.search()`, posts top results as Discord embed.
7. **`/upload <attachment>`** — KB selector, downloads attachment bytes, validates size, calls `IngestionService.ingest(..., upload_source=UploadSource.DISCORD)`, posts confirmation.
8. **SR reminder task** — `discord.ext.tasks.loop` running daily; iterates all `(user_id, discord_user_id)` pairs via new `list_by_provider("discord")`; sends DM for each KB with due cards.
9. **`list_by_provider` port extension** — add `async def list_by_provider(provider: str) -> list[tuple[UUID, str]]` to `ExternalIdentityRepository` protocol + `PostgresIdentityRepository` implementation.
10. **i18n messages** — all user-visible text in `messages.py` as a `MESSAGES` dict; Polish default; English supported via `locale` parameter.
11. **Unit tests** — test auth guards, identity resolution, quiz cog, search cog, upload cog, and reminder task with mocked dependencies.
12. **`DISCORD_REMINDER_HOUR`** env variable (int, default 8 UTC) added to `AppSettings`.

## Visual Design

No visual assets. Commands use Discord's native slash-command UI, embeds, and select menus.

## Reusable Components

### Existing Code to Leverage

| Component | File | How Used |
|-----------|------|----------|
| `IdentityResolver` | `mindforge/api/auth.py` | Called in every command; `resolve(UserInfo(...))` → `UUID` |
| `UserInfo` dataclass | `mindforge/api/auth.py` | Constructed per-command: `provider="discord"`, `external_id=str(interaction.user.id)` |
| `AppSettings` + `discord_allowed_guild_list` property | `mindforge/infrastructure/config.py` | Used in guild allowlist check and bot token startup |
| `QuizService.start_session()` | `mindforge/application/quiz.py` | Called by `/quiz start` |
| `QuizService.submit_answer()` | `mindforge/application/quiz.py` | Called by `/quiz answer` |
| `QuizStartResult`, `QuizEvalResult` | `mindforge/application/quiz.py` | Response formatting source |
| `NoWeakConceptsError`, `QuizSessionNotFoundError`, `QuizAccessDeniedError` | `mindforge/application/quiz.py` | Exception → user message mapping |
| `SearchService.search()` | `mindforge/application/search.py` | Called by `/search` |
| `SearchResult`, `SearchResultItem` | `mindforge/application/search.py` | Embed construction source |
| `IngestionService.ingest()` | `mindforge/application/ingestion.py` | Called by `/upload` |
| `DuplicateContentError`, `PendingTaskLimitError`, `UploadRejectedError` | `mindforge/application/ingestion.py` | Exception → user message mapping |
| `UploadSource.DISCORD` | `mindforge/domain/models.py` | Passed as `upload_source` to `ingest()` |
| `KnowledgeBaseService.list_for_user()` | `mindforge/application/knowledge_base.py` | KB dropdown population |
| `FlashcardService.due_count()` | `mindforge/application/flashcards.py` | Reminder task due-card check |
| `lifespan` composition root pattern | `mindforge/api/main.py` | Bot async startup/teardown structure |
| `quiz.py` router error-mapping pattern | `mindforge/api/routers/quiz.py` | Exception-to-message template |
| `ExternalIdentityRepository` protocol | `mindforge/domain/ports.py` | Extended with `list_by_provider` |
| `PostgresIdentityRepository` | `mindforge/infrastructure/persistence/identity_repo.py` | `list_by_provider` implementation added |

### New Components Required

| Component | File | Justification |
|-----------|------|---------------|
| Async composition root | `mindforge/discord/bot.py` | Rewrite stub; no discord.py-aware composition root exists anywhere |
| Guild + ownership guards | `mindforge/discord/auth.py` | Discord-specific; no analogous file exists; cannot reuse API auth (different paradigm) |
| Quiz cog | `mindforge/discord/cogs/quiz.py` | Discord slash command handler; no HTTP equivalent exists |
| Search cog | `mindforge/discord/cogs/search.py` | Discord slash command handler |
| Upload cog | `mindforge/discord/cogs/upload.py` | Discord attachment handling; different from HTTP multipart |
| Notifications cog | `mindforge/discord/cogs/notifications.py` | `tasks.loop` DM scheduler; no existing equivalent |
| i18n messages | `mindforge/discord/messages.py` | Centralized user-visible text store |
| `list_by_provider` | `mindforge/domain/ports.py` + `identity_repo.py` | Required for reminder task; no existing bulk-enumeration method |
| Test package + tests | `tests/unit/discord/` | No Discord tests exist |

## Technical Approach

### Composition Root (`bot.py`)

Mirror `api/main.py` lifespan pattern using `discord.Client` with `app_commands.CommandTree`. The bot object carries injected services as instance attributes. All services are created in `main()` and injected into cogs at construction time. The bot token is read once from `settings.discord_bot_token`; missing token raises `ValueError` before startup.

```
main()
 └─ AppSettings()
 └─ validate_settings()
 └─ create_async_engine()
 └─ async_sessionmaker()
 └─ [optional] Neo4jContext
 └─ LiteLLMGateway
 └─ [optional] redis.asyncio.from_url()
 └─ QuizSessionStore (Redis or PG fallback)
 └─ Repos + Services (constructed per-session inside commands)
 └─ IdentityResolver
 └─ KnowledgeBaseService
 └─ QuizService
 └─ SearchService
 └─ IngestionService
 └─ FlashcardService
 └─ bot.add_cog(QuizCog(...))
 └─ bot.add_cog(SearchCog(...))
 └─ bot.add_cog(UploadCog(...))
 └─ bot.add_cog(NotificationsCog(...))
 └─ await bot.start(settings.discord_bot_token)
```

### Per-Command DB Session Pattern

Each command creates its own `async with session_factory() as session` for the DB calls it needs. Services that require a `connection` parameter (e.g., `IngestionService.ingest`) receive the session directly. This matches how the API router `Depends` pattern works but without FastAPI's DI.

### Redis Quiz Tracking

The Discord-side pending-session record is separate from the `QuizSessionStore` (which is the application-layer session). The Discord cog stores a lightweight pointer in Redis:
- **Key**: `discord:quiz:pending:{discord_user_id}` (string, where `discord_user_id` is `str(interaction.user.id)`)
- **Value**: JSON `{"session_id": "...", "question_id": "...", "kb_id": "..."}`
- **TTL**: `settings.quiz_session_ttl_seconds` (default 1800 s)
- **Graceful degradation**: if Redis is `None`, respond with `MSG["quiz_redis_unavailable"]` and abort.

### KB Selector Flow

```
list_for_user(user_id) → kbs
if len(kbs) == 0:  → MSG["no_knowledge_bases"]
elif len(kbs) == 1: → use kbs[0] directly
else:              → send KBSelectView (discord.ui.View + discord.ui.Select)
                     → callback triggers the deferred operation
```

### Reminder Task

`@tasks.loop(hours=24)` started after cog is added. On `before_loop`, sleep until the next occurrence of `DISCORD_REMINDER_HOUR` UTC using `discord.utils.sleep_until`. On each tick: call `identity_repo.list_by_provider("discord")`, iterate `(user_id, discord_external_id)` pairs, query `KnowledgeBaseService.list_for_user(user_id)`, for each KB call `FlashcardService.due_count(user_id, kb_id)`, DM the Discord user if count > 0.

### Data Flow for `/quiz start`

```
/quiz start [topic]
→ guild_check()
→ resolver.resolve(UserInfo("discord", str(user.id), user.display_name))
→ kb_service.list_for_user(user_id) → KB select or auto-pick
→ quiz_service.start_session(user_id, kb_id, topic)
→ redis.setex("discord:quiz:pending:{user.id}", ttl, json.dumps({session_id, question_id, kb_id}))
→ interaction.followup.send(question_text)
```

### Data Flow for `/quiz answer`

```
/quiz answer <answer>
→ guild_check()         ← before defer()
→ interaction.response.defer()
→ redis.get("discord:quiz:pending:{user.id}") → parse JSON  (key scoped to user — ownership implicit)
→ resolver.resolve(UserInfo("discord", str(user.id), ...))  ← per-command IdentityResolver
→ quiz_service.submit_answer(user_id, kb_id, session_id, question_id, answer)
→ redis.delete("discord:quiz:pending:{user.id}")
→ interaction.followup.send(format_eval_result(result))
```

## Implementation Guidance

### File-by-File Interfaces

---

#### `mindforge/infrastructure/config.py` (extend)

Add one field to `AppSettings`:

```python
discord_reminder_hour: int = 8  # UTC hour for daily SR reminder DMs
```

---

#### `mindforge/domain/ports.py` (extend `ExternalIdentityRepository`)

Add one method to the `ExternalIdentityRepository` protocol:

```python
async def list_by_provider(self, provider: str) -> list[tuple[UUID, str]]:
    """Return all (user_id, external_id) pairs linked to *provider*."""
    ...
```

The return type is `list[tuple[UUID, str]]` where the first element is the internal `user_id` and the second is the raw `external_id` string (e.g., Discord snowflake as a string).

---

#### `mindforge/infrastructure/persistence/identity_repo.py` (extend)

Add to `PostgresIdentityRepository`:

```python
async def list_by_provider(self, provider: str) -> list[tuple[uuid.UUID, str]]:
    """Return all (user_id, external_id) pairs for *provider*.

    SQL:
        SELECT user_id, external_id
        FROM external_identities
        WHERE provider = :provider
        ORDER BY user_id
    """
    result = await self._session.execute(
        select(
            ExternalIdentityModel.user_id,
            ExternalIdentityModel.external_id,
        ).where(
            ExternalIdentityModel.provider == provider
        ).order_by(ExternalIdentityModel.user_id)
    )
    return [(row.user_id, row.external_id) for row in result]
```

---

#### `mindforge/discord/messages.py` (new)

```python
"""
Centralised i18n message strings for the Discord bot.

Usage:
    from mindforge.discord.messages import get_message
    text = get_message("quiz_no_session", locale="pl")
"""

from __future__ import annotations

MESSAGES: dict[str, dict[str, str]] = {
    # Guild / auth
    "guild_not_allowed": {
        "pl": "Bot nie jest dostępny w tym serwerze.",
        "en": "This bot is not available on this server.",
    },
    "not_your_interaction": {
        "pl": "To nie jest Twoja sesja.",
        "en": "This is not your session.",
    },
    # Knowledge bases
    "no_knowledge_bases": {
        "pl": "Nie masz żadnych baz wiedzy. Utwórz bazę w aplikacji MindForge.",
        "en": "You have no knowledge bases. Create one in the MindForge app.",
    },
    "select_kb_placeholder": {
        "pl": "Wybierz bazę wiedzy…",
        "en": "Select a knowledge base…",
    },
    # Quiz
    "quiz_no_weak_concepts": {
        "pl": "Brak słabych pojęć do przećwiczenia w tej bazie. Dodaj dokumenty.",
        "en": "No weak concepts to practise in this knowledge base. Add documents.",
    },
    "quiz_started": {
        "pl": "📚 **Quiz rozpoczęty** (sesja `{session_id}`)\n\n{question_text}",
        "en": "📚 **Quiz started** (session `{session_id}`)\n\n{question_text}",
    },
    "quiz_no_session": {
        "pl": "Brak aktywnej sesji quizu. Użyj `/quiz start`.",
        "en": "No active quiz session. Use `/quiz start`.",
    },
    "quiz_redis_unavailable": {
        "pl": "Sesja quizu niedostępna (brak Redis). Spróbuj ponownie później.",
        "en": "Quiz session unavailable (Redis offline). Try again later.",
    },
    "quiz_session_not_found": {
        "pl": "Sesja wygasła lub nie istnieje. Użyj `/quiz start` aby zacząć nową.",
        "en": "Session expired or not found. Use `/quiz start` to begin a new one.",
    },
    "quiz_access_denied": {
        "pl": "Brak dostępu do tej sesji quizu.",
        "en": "You do not have access to this quiz session.",
    },
    "quiz_result": {
        "pl": (
            "{emoji} **Ocena: {score}/5**\n\n"
            "**Feedback:** {feedback}\n\n"
            "**Wyjaśnienie:** {explanation}"
        ),
        "en": (
            "{emoji} **Score: {score}/5**\n\n"
            "**Feedback:** {feedback}\n\n"
            "**Explanation:** {explanation}"
        ),
    },
    "quiz_generation_failed": {
        "pl": "Nie udało się wygenerować pytania. Spróbuj ponownie.",
        "en": "Failed to generate a question. Please try again.",
    },
    # Search
    "search_no_results": {
        "pl": "Nie znaleziono wyników dla zapytania: **{query}**",
        "en": "No results found for query: **{query}**",
    },
    "search_results_title": {
        "pl": "Wyniki wyszukiwania: {query}",
        "en": "Search results: {query}",
    },
    # Upload
    "upload_success": {
        "pl": "✅ Dokument **{filename}** przesłany. ID zadania: `{task_id}`",
        "en": "✅ Document **{filename}** uploaded. Task ID: `{task_id}`",
    },
    "upload_too_large": {
        "pl": "Plik jest za duży. Maksymalny rozmiar: {max_mb} MB.",
        "en": "File is too large. Maximum size: {max_mb} MB.",
    },
    "upload_rejected": {
        "pl": "Plik odrzucony: {reason}",
        "en": "File rejected: {reason}",
    },
    "upload_duplicate": {
        "pl": "Ten dokument już istnieje w bazie wiedzy.",
        "en": "This document already exists in the knowledge base.",
    },
    "upload_limit_reached": {
        "pl": "Masz zbyt wiele zadań w kolejce. Poczekaj na przetworzenie.",
        "en": "You have too many pending tasks. Wait for them to finish.",
    },
    "upload_failed": {
        "pl": "Nie udało się przesłać dokumentu.",
        "en": "Failed to upload the document.",
    },
    # Reminder DM
    "reminder_dm": {
        "pl": "📖 Masz **{count}** fiszek do powtórki w **{kb_name}**. Użyj `/quiz start`!",
        "en": "📖 You have **{count}** flashcards due in **{kb_name}**. Use `/quiz start`!",
    },
    # Generic error
    "unexpected_error": {
        "pl": "Wystąpił nieoczekiwany błąd. Spróbuj ponownie.",
        "en": "An unexpected error occurred. Please try again.",
    },
}

_SCORE_EMOJI: dict[int, str] = {
    0: "❌",
    1: "❌",
    2: "⚠️",
    3: "✅",
    4: "✅",
    5: "⭐",
}


def get_message(key: str, locale: str = "pl", **kwargs: object) -> str:
    """Return the message string for *key* in *locale*, formatted with *kwargs*.

    Falls back to Polish if *locale* is not found. Falls back to key name if
    the key is not registered (should not happen in production).
    """
    locale_map = MESSAGES.get(key, {})
    template = locale_map.get(locale) or locale_map.get("pl") or key
    if kwargs:
        return template.format(**kwargs)
    return template


def score_emoji(score: int) -> str:
    """Return the emoji for a quiz score 0–5."""
    return _SCORE_EMOJI.get(score, "✅")
```

---

#### `mindforge/discord/auth.py` (new)

```python
"""
Discord bot — guild allowlist and interaction-ownership guards.

All functions are pure helpers called at the start of every cog command.
"""

from __future__ import annotations

import discord

from mindforge.infrastructure.config import AppSettings


async def guild_check(
    interaction: discord.Interaction,
    settings: AppSettings,
) -> bool:
    """Return True if the interaction's guild is allowed.

    When settings.discord_allowed_guild_list is empty, all guilds pass
    (open / development mode).  When the list is non-empty and the guild is
    absent, respond with an error message and return False.

    Args:
        interaction: The Discord interaction to check.
        settings: App settings carrying discord_allowed_guild_list.

    Returns:
        True if allowed, False if blocked (response already sent).
    """
    ...

async def interaction_ownership_check(
    interaction: discord.Interaction,
    expected_user_id: int,
    settings: AppSettings,
) -> bool:
    """Return True if interaction.user.id == expected_user_id.

    When they differ, respond with "not your session" message and return False.

    Args:
        interaction: The Discord interaction to check.
        expected_user_id: The Discord user ID that owns the session.
        settings: App settings (used for locale).

    Returns:
        True if owner, False if not (response already sent).
    """
    ...
```

**Implementation notes**:
- `guild_check`: check `settings.discord_allowed_guild_list`; if empty list → return `True`; if `interaction.guild_id not in allowed_list` → `await interaction.response.send_message(get_message("guild_not_allowed"), ephemeral=True)` → return `False`.
- `interaction_ownership_check`: if `interaction.user.id != expected_user_id` → `await interaction.response.send_message(get_message("not_your_interaction"), ephemeral=True)` → return `False`.
- Both functions must call `interaction.response.send_message` with `ephemeral=True` so the error is only visible to the invoking user.
- Both are `async` to support potential `await interaction.response` calls; the check itself is synchronous.

---

#### `mindforge/discord/cogs/quiz.py` (new)

```python
"""Discord cog for /quiz commands."""

from __future__ import annotations

import json
import logging
from uuid import UUID

import discord
from discord import app_commands
from discord.ext import commands

from mindforge.api.auth import IdentityResolver, UserInfo
from mindforge.application.knowledge_base import KnowledgeBaseService
from mindforge.application.quiz import (
    NoWeakConceptsError,
    QuizAccessDeniedError,
    QuizEvalResult,
    QuizQuestionNotFoundError,
    QuizService,
    QuizSessionNotFoundError,
    QuizStartResult,
)
from mindforge.discord.auth import guild_check
from mindforge.discord.messages import get_message, score_emoji
from mindforge.infrastructure.config import AppSettings

log = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    """Slash commands: /quiz start, /quiz answer."""

    def __init__(
        self,
        quiz_service: QuizService,
        kb_service: KnowledgeBaseService,
        redis_client: object | None,          # redis.asyncio.Redis | None
        settings: AppSettings,
        session_factory: object,              # async_sessionmaker[AsyncSession]
    ) -> None:
        self._quiz = quiz_service
        self._kb = kb_service
        self._redis = redis_client
        self._settings = settings
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # /quiz group
    # ------------------------------------------------------------------

    quiz_group = app_commands.Group(name="quiz", description="Quiz commands")

    @quiz_group.command(name="start", description="Rozpocznij nowy quiz")
    @app_commands.describe(topic="Opcjonalny temat do ćwiczenia")
    async def quiz_start(
        self,
        interaction: discord.Interaction,
        topic: str | None = None,
    ) -> None:
        """Handle /quiz start [topic]."""
        ...

    @quiz_group.command(name="answer", description="Odpowiedz na pytanie quizu")
    @app_commands.describe(answer="Twoja odpowiedź")
    async def quiz_answer(
        self,
        interaction: discord.Interaction,
        answer: str,
    ) -> None:
        """Handle /quiz answer <answer>."""
        ...
```

**`quiz_start` implementation contract**:
1. `await guild_check(interaction, self._settings)` → return if `False`. **(Must precede `defer()` — `guild_check` sends the initial response slot; calling `defer()` first would consume it and raise `discord.InteractionResponded`.)**
2. `await interaction.response.defer(ephemeral=False)` (defer because KB lookup + AI can take >3 s).
3. Build `user_info = UserInfo(provider="discord", external_id=str(interaction.user.id), display_name=interaction.user.display_name)`.
4. `async with self._session_factory() as session:` → `resolver = IdentityResolver(PostgresIdentityRepository(session))` → `user_id: UUID = await resolver.resolve(user_info)`.
5. `async with session_factory() as session:` → `await kb_service.list_for_user(user_id)` → `kbs`.
6. If `len(kbs) == 0`: `await interaction.followup.send(get_message("no_knowledge_bases"), ephemeral=True)` → return.
7. If `len(kbs) == 1`: `kb_id = kbs[0].kb_id`; skip dropdown.
8. If `len(kbs) > 1`: construct `KBSelectView(kbs, callback=_do_quiz_start, ...)` → `await interaction.followup.send("Wybierz bazę wiedzy:", view=view)` → return (callback handles the rest asynchronously).
9. `_do_quiz_start(interaction, kb_id, user_id, topic, ...)`:
   - If Redis is `None`: `await interaction.followup.send(get_message("quiz_redis_unavailable"))` → return.
   - `async with session_factory() as session:` → call `await quiz_service.start_session(user_id, kb_id, topic)`.
   - On `NoWeakConceptsError`: `await interaction.followup.send(get_message("quiz_no_weak_concepts"))` → return.
   - On `RuntimeError`: log error → `await interaction.followup.send(get_message("quiz_generation_failed"))` → return.
   - Store in Redis: `await redis.setex(f"discord:quiz:pending:{interaction.user.id}", settings.quiz_session_ttl_seconds, json.dumps({"session_id": str(result.session_id), "question_id": result.question_id, "kb_id": str(kb_id)}))`.
   - `await interaction.followup.send(get_message("quiz_started", session_id=str(result.session_id)[:8], question_text=result.question_text))`.

**`quiz_answer` implementation contract**:
1. `await guild_check(interaction, self._settings)` → return if `False`. **(Must precede `defer()`.)**
2. `await interaction.response.defer()`.
3. If Redis is `None`: `await interaction.followup.send(get_message("quiz_redis_unavailable"))` → return.
4. `raw = await redis.get(f"discord:quiz:pending:{interaction.user.id}")`.
5. If `raw is None`: `await interaction.followup.send(get_message("quiz_no_session"))` → return.
6. `pending = json.loads(raw)` → extract `session_id: UUID`, `question_id: str`, `kb_id: UUID`.
7. `user_info = UserInfo(provider="discord", external_id=str(interaction.user.id), display_name=interaction.user.display_name)`; `async with self._session_factory() as session:` → `resolver = IdentityResolver(PostgresIdentityRepository(session))` → `user_id: UUID = await resolver.resolve(user_info)`. *(Redis key is scoped to `interaction.user.id`, so only the session owner can fetch this key — ownership is implicit.)*
8. `async with self._session_factory() as session:` → call `await quiz_service.submit_answer(user_id, kb_id, session_id, question_id, answer)`.
9. On `QuizSessionNotFoundError`: `await interaction.followup.send(get_message("quiz_session_not_found"))` → `await redis.delete(key)` → return.
10. On `QuizQuestionNotFoundError`: `await interaction.followup.send(get_message("quiz_session_not_found"))` → `await redis.delete(key)` → return. *(Session/question mismatch is functionally session-not-found; stale Redis entry cleaned up.)*
11. On `QuizAccessDeniedError`: `await interaction.followup.send(get_message("quiz_access_denied"))` → return.
12. `await redis.delete(f"discord:quiz:pending:{interaction.user.id}")`.
13. Format and send result: `get_message("quiz_result", emoji=score_emoji(result.score), score=result.score, feedback=result.feedback, explanation=result.explanation)`.
14. **Never include `reference_answer`, `grounding_context`, `raw_prompt`, `raw_completion` in any message.**

---

#### `mindforge/discord/cogs/search.py` (new)

```python
"""Discord cog for /search command."""

class SearchCog(commands.Cog):
    def __init__(
        self,
        search_service: SearchService,
        kb_service: KnowledgeBaseService,
        settings: AppSettings,
        session_factory: object,
    ) -> None: ...

    @app_commands.command(name="search", description="Przeszukaj bazę wiedzy")
    @app_commands.describe(query="Zapytanie do wyszukania")
    async def search(
        self,
        interaction: discord.Interaction,
        query: str,
    ) -> None: ...
```

**`search` implementation contract**:
1. `await guild_check(interaction, self._settings)` → return if `False`. **(Must precede `defer()`.)**
2. `await interaction.response.defer()`.
3. `async with self._session_factory() as session:` → `resolver = IdentityResolver(PostgresIdentityRepository(session))` → `user_id: UUID = await resolver.resolve(UserInfo(provider="discord", external_id=str(interaction.user.id), display_name=interaction.user.display_name))`.
4. `await kb_service.list_for_user(user_id)` → `kbs`.
5. If `len(kbs) == 0`: send `get_message("no_knowledge_bases")` → return.
6. KB select logic (same as quiz: auto-pick if 1, dropdown if >1).
7. `await search_service.search(query=query, kb_id=kb_id, user_id=user_id, top_k=5)` → `result`.
8. If `result.results` is empty: `await interaction.followup.send(get_message("search_no_results", query=query))` → return.
9. Build `discord.Embed(title=get_message("search_results_title", query=query), color=0x5865F2)`.
10. For each item in `result.results[:5]`: `embed.add_field(name=item.source_lesson_id, value=item.content[:500], inline=False)`.
11. `await interaction.followup.send(embed=embed)`.

---

#### `mindforge/discord/cogs/upload.py` (new)

```python
"""Discord cog for /upload command."""

class UploadCog(commands.Cog):
    def __init__(
        self,
        ingestion_service: IngestionService,
        kb_service: KnowledgeBaseService,
        settings: AppSettings,
        session_factory: object,
    ) -> None: ...

    @app_commands.command(name="upload", description="Prześlij dokument do bazy wiedzy")
    @app_commands.describe(attachment="Plik do przesłania (PDF, DOCX, MD, TXT)")
    async def upload(
        self,
        interaction: discord.Interaction,
        attachment: discord.Attachment,
    ) -> None: ...
```

**`upload` implementation contract**:
1. `await guild_check(interaction, self._settings)` → return if `False`. **(Must precede `defer()`.)**
2. `await interaction.response.defer()`.
3. Validate `attachment.size <= settings.max_document_size_mb * 1024 * 1024`; if exceeded: `await interaction.followup.send(get_message("upload_too_large", max_mb=settings.max_document_size_mb))` → return.
4. `async with self._session_factory() as session:` → `resolver = IdentityResolver(PostgresIdentityRepository(session))` → `user_id: UUID = await resolver.resolve(UserInfo(provider="discord", external_id=str(interaction.user.id), display_name=interaction.user.display_name))`.
5. KB select logic.
6. `raw_bytes: bytes = await attachment.read()` (after KB selection to avoid holding bytes during dropdown).
7. `async with session_factory() as session:` → call `await ingestion_service.ingest(raw_bytes, attachment.filename, kb_id, UploadSource.DISCORD, user_id, connection=session)` → `await session.commit()`.
8. Exception mapping:
   - `UploadRejectedError` → `get_message("upload_rejected", reason=str(e))`.
   - `DuplicateContentError` → `get_message("upload_duplicate")`.
   - `PendingTaskLimitError` → `get_message("upload_limit_reached")`.
   - Any other `Exception` → log error → `get_message("upload_failed")`.
9. `await interaction.followup.send(get_message("upload_success", filename=attachment.filename, task_id=str(result.task_id)))`.

---

#### `mindforge/discord/cogs/notifications.py` (new)

```python
"""Discord cog — daily SR reminder DMs."""

class NotificationsCog(commands.Cog):
    def __init__(
        self,
        bot: discord.Client,
        settings: AppSettings,
        session_factory: object,  # async_sessionmaker[AsyncSession]
    ) -> None: ...

    @tasks.loop(hours=24)
    async def send_reminders(self) -> None:
        """Iterate all Discord users and DM those with due flashcards."""
        ...

    @send_reminders.before_loop
    async def before_reminders(self) -> None:
        """Sleep until the next occurrence of settings.discord_reminder_hour UTC."""
        await self.bot.wait_until_ready()
        now = datetime.now(timezone.utc)
        target = now.replace(
            hour=self._settings.discord_reminder_hour,
            minute=0,
            second=0,
            microsecond=0,
        )
        if target <= now:
            target += timedelta(days=1)
        await discord.utils.sleep_until(target)
```

**`send_reminders` implementation contract**:
1. `async with self._session_factory() as session:` → `local_repo = PostgresIdentityRepository(session)` → `pairs: list[tuple[UUID, str]] = await local_repo.list_by_provider("discord")`.
2. For each `(user_id, discord_external_id)` in `pairs`:
   a. `async with self._session_factory() as session:` → construct session-scoped repos → `kb_service = KnowledgeBaseService(...)` → `kbs = await kb_service.list_for_user(user_id)`.
   b. For each `kb` in `kbs`:
      - `async with self._session_factory() as session:` → construct session-scoped repos → `flashcard_service = FlashcardService(...)` → `count = await flashcard_service.due_count(user_id, kb.kb_id)`.
      - If `count > 0`: `discord_user = await self._bot.fetch_user(int(discord_external_id))` → `await discord_user.send(get_message("reminder_dm", count=count, kb_name=kb.name))`.
   c. Catch `discord.Forbidden` (user blocked DMs) and `discord.NotFound` (user left) silently — log at DEBUG level only.
3. Log total reminders sent at INFO level.

---

#### `mindforge/discord/cogs/__init__.py` (update)

```python
"""Discord bot cogs package."""

from mindforge.discord.cogs.notifications import NotificationsCog
from mindforge.discord.cogs.quiz import QuizCog
from mindforge.discord.cogs.search import SearchCog
from mindforge.discord.cogs.upload import UploadCog

__all__ = ["QuizCog", "SearchCog", "UploadCog", "NotificationsCog"]
```

---

#### `mindforge/discord/bot.py` (rewrite)

```python
"""Discord bot — async composition root."""

from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands

from mindforge.discord.cogs import NotificationsCog, QuizCog, SearchCog, UploadCog
from mindforge.infrastructure.config import AppSettings, validate_settings

log = logging.getLogger(__name__)


class MindForgeBot(discord.Client):
    def __init__(self, *, settings: AppSettings, **kwargs: object) -> None:
        intents = discord.Intents.default()
        intents.dm_messages = True
        super().__init__(intents=intents, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.settings = settings

    async def setup_hook(self) -> None:
        await self.tree.sync()
        log.info("Application commands synced")

    async def on_ready(self) -> None:
        log.info("MindForge Discord bot ready as %s", self.user)


async def _async_main() -> None:
    """Async composition root — wire services, build bot, run."""
    # 1. Settings
    settings = AppSettings()
    validate_settings(settings)
    _configure_logging(settings.log_level)

    if not settings.discord_bot_token:
        raise ValueError("DISCORD_BOT_TOKEN is not set.")

    # 2. DB engine + session factory
    from mindforge.infrastructure.db import create_async_engine
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # 3. [Optional] Neo4j
    neo4j_context = _init_neo4j(settings)

    # 4. AI Gateway
    from mindforge.infrastructure.ai.infra.gateway import LiteLLMGateway
    gateway = LiteLLMGateway(
        default_model=settings.model_small,
        model_map=settings.model_map,
        fallback_models=[settings.model_fallback],
        timeout_seconds=30.0,
        max_retries=3,
        api_key=settings.openrouter_api_key,
    )

    # 5. [Optional] Redis
    redis_client = await _init_redis(settings)

    # 6. Quiz session store
    quiz_session_store = _make_quiz_store(settings, redis_client, session_factory)

    # 7. Retrieval adapter (optional)
    retrieval = _make_retrieval(settings, neo4j_context)

    # 8. Build service layer (stateless — one instance per bot, sessions per call)
    from mindforge.api.auth import IdentityResolver
    from mindforge.application.flashcards import FlashcardService
    from mindforge.application.ingestion import IngestionService
    from mindforge.application.knowledge_base import KnowledgeBaseService
    from mindforge.application.quiz import QuizService
    from mindforge.application.search import SearchService
    from mindforge.domain.agents import ProcessingSettings as PS
    from mindforge.infrastructure.parsing.registry import ParserRegistry
    from mindforge.infrastructure.persistence.identity_repo import (
        PostgresIdentityRepository,
    )
    from mindforge.infrastructure.security.upload_sanitizer import UploadSanitizer
    from mindforge.agents.quiz_generator import QuizGeneratorAgent
    from mindforge.agents.quiz_evaluator import QuizEvaluatorAgent
    from mindforge.infrastructure.persistence.artifact_repo import (
        PostgresArtifactRepository,
    )
    from mindforge.infrastructure.persistence.study_progress import (
        PostgresStudyProgressStore,
    )

    # 8. Build service layer
    # All services that need a DB session are constructed per-command inside
    # `async with session_factory() as session:` blocks in each cog command.
    # No long-lived IdentityResolver is created at startup; each command
    # constructs `IdentityResolver(PostgresIdentityRepository(session))` fresh.
    from mindforge.application.flashcards import FlashcardService
    from mindforge.application.ingestion import IngestionService
    from mindforge.application.knowledge_base import KnowledgeBaseService
    from mindforge.application.quiz import QuizService
    from mindforge.application.search import SearchService
    from mindforge.infrastructure.parsing.registry import ParserRegistry
    from mindforge.infrastructure.security.upload_sanitizer import UploadSanitizer
    from mindforge.agents.quiz_generator import QuizGeneratorAgent
    from mindforge.agents.quiz_evaluator import QuizEvaluatorAgent

    quiz_service = QuizService(...)
    search_service = SearchService(...)
    ingestion_service = IngestionService(...)
    kb_service = KnowledgeBaseService(...)

    bot = MindForgeBot(settings=settings)
    await bot.add_cog(QuizCog(quiz_service, kb_service, redis_client, settings, session_factory))
    await bot.add_cog(SearchCog(search_service, kb_service, settings, session_factory))
    await bot.add_cog(UploadCog(ingestion_service, kb_service, settings, session_factory))
    await bot.add_cog(NotificationsCog(bot, settings, session_factory))

    try:
        await bot.start(settings.discord_bot_token)
    finally:
        await engine.dispose()
        if neo4j_context:
            await neo4j_context.close()
        if redis_client:
            await redis_client.aclose()


def main() -> None:
    """Entry point for the mindforge-discord CLI command."""
    asyncio.run(_async_main())
```

**Composition root implementation notes**:
- `IdentityResolver` wraps `ExternalIdentityRepository`. Since repos need a session, each command constructs the resolver fresh: `async with session_factory() as session: resolver = IdentityResolver(PostgresIdentityRepository(session)); user_id = await resolver.resolve(user_info)`. This mirrors how the FastAPI DI pattern works. No long-lived `IdentityResolver` is created at startup.
- `setup_hook` calls `await self.tree.sync()` to register global slash commands with Discord.
- All services that take per-command DB sessions are constructed fresh inside each command handler using `async with session_factory() as session:`.

---

| `KBSelectView` shared utility | `mindforge/discord/views.py` | Reusable KB dropdown used by all 3 command cogs |

```python
class KBSelectView(discord.ui.View):

    def __init__(
        self,
        kbs: list[KnowledgeBase],
        callback: Callable[[discord.Interaction, UUID], Awaitable[None]],
        *,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self._callback = callback
        options = [
            discord.SelectOption(label=kb.name[:100], value=str(kb.kb_id))
            for kb in kbs
        ]
        select = discord.ui.Select(
            placeholder=get_message("select_kb_placeholder"),
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        kb_id = UUID(interaction.data["values"][0])
        self.stop()
        await self._callback(interaction, kb_id)
```

---

### Testing Approach

2–8 focused tests per test file; mock all I/O; no real DB or Discord API calls.

#### `tests/unit/discord/__init__.py`

Empty file.

#### `tests/unit/discord/test_auth.py` — 6 tests

| Test | Setup | Assertion |
|------|-------|-----------|
| `test_guild_check_passes_when_list_empty` | `settings.discord_allowed_guilds = None`; `interaction.guild_id = 12345` | Returns `True`, no response sent |
| `test_guild_check_passes_allowed_guild` | `settings.discord_allowed_guilds = "12345"`; `interaction.guild_id = 12345` | Returns `True`, no response sent |
| `test_guild_check_blocks_unknown_guild` | `settings.discord_allowed_guilds = "99999"`; `interaction.guild_id = 12345` | Returns `False`; `interaction.response.send_message` called with `"guild_not_allowed"` text |
| `test_ownership_check_passes_matching_user` | `interaction.user.id = 1001`; `expected_user_id = 1001` | Returns `True`, no response sent |
| `test_ownership_check_blocks_wrong_user` | `interaction.user.id = 1001`; `expected_user_id = 9999` | Returns `False`; `interaction.response.send_message` called with `"not_your_interaction"` text |
| `test_guild_check_ephemeral_flag` | blocked guild scenario | `interaction.response.send_message` called with `ephemeral=True` |

**Mock setup**: Use `unittest.mock.AsyncMock` for `interaction.response.send_message`. Use `MagicMock(spec=discord.Interaction)` for the interaction.

#### `tests/unit/discord/test_quiz_cog.py` — 8 tests

| Test | Setup | Assertion |
|------|-------|-----------|
| `test_quiz_start_single_kb_starts_session` | 1 KB returned; QuizService returns `QuizStartResult`; Redis mock | `quiz_service.start_session` called; Redis `setex` called with correct key; `followup.send` called with question text |
| `test_quiz_start_no_kb_sends_message` | `list_for_user` returns `[]` | `followup.send` called with `"no_knowledge_bases"` message |
| `test_quiz_start_no_weak_concepts` | `start_session` raises `NoWeakConceptsError` | `followup.send` called with `"quiz_no_weak_concepts"` message |
| `test_quiz_start_redis_unavailable` | `redis_client = None` | `followup.send` called with `"quiz_redis_unavailable"` message |
| `test_quiz_answer_loads_session` | Redis returns valid JSON; `submit_answer` returns `QuizEvalResult` | `submit_answer` called with correct `session_id`, `question_id`, `kb_id`; Redis `delete` called |
| `test_quiz_answer_no_session` | Redis returns `None` | `followup.send` called with `"quiz_no_session"` message; `submit_answer` not called |
| `test_quiz_answer_session_expired` | `submit_answer` raises `QuizSessionNotFoundError` | `followup.send` called with `"quiz_session_not_found"`; Redis `delete` called |
| `test_quiz_answer_never_exposes_reference_answer` | `submit_answer` returns result | `followup.send` call args do not contain string `"reference_answer"` |

**Mock setup**:
```python
quiz_service = AsyncMock(spec=QuizService)
kb_service = AsyncMock(spec=KnowledgeBaseService)
redis = AsyncMock()
settings = AppSettings(discord_allowed_guilds=None)
# session_factory mock: async context manager yielding a mock session
mock_session = AsyncMock()
session_factory = MagicMock()
session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
cog = QuizCog(quiz_service, kb_service, redis, settings, session_factory)
interaction = MagicMock(spec=discord.Interaction)
interaction.user.id = 1001
interaction.user.display_name = "TestUser"
interaction.response = AsyncMock()
interaction.followup = AsyncMock()
# Patch IdentityResolver to return a fixed UUID in tests that invoke commands
# e.g., with patch("mindforge.discord.cogs.quiz.IdentityResolver") as mock_cls:
#     mock_cls.return_value.resolve = AsyncMock(return_value=UUID("00000000-..."))
```

#### `tests/unit/discord/test_search_cog.py` — 4 tests

| Test | Setup | Assertion |
|------|-------|-----------|
| `test_search_returns_embed` | `search_service.search` returns 3 results | `followup.send` called with `embed=` keyword arg; embed has 3 fields |
| `test_search_no_results` | `search_service.search` returns 0 results | `followup.send` called with `"search_no_results"` text containing query |
| `test_search_auto_picks_single_kb` | 1 KB | `search_service.search` called without KB dropdown |
| `test_search_blocked_guild` | `guild_check` returns `False` | `search_service.search` not called |

#### `tests/unit/discord/test_upload_cog.py` — 5 tests

| Test | Setup | Assertion |
|------|-------|-----------|
| `test_upload_success` | `ingestion_service.ingest` returns `IngestionResult` | `followup.send` called with `"upload_success"` containing filename and task_id |
| `test_upload_file_too_large` | `attachment.size = 100 * 1024 * 1024`; `max_document_size_mb = 10` | `followup.send` called with `"upload_too_large"`; `ingest` not called |
| `test_upload_duplicate_content` | `ingest` raises `DuplicateContentError` | `followup.send` called with `"upload_duplicate"` |
| `test_upload_limit_reached` | `ingest` raises `PendingTaskLimitError` | `followup.send` called with `"upload_limit_reached"` |
| `test_upload_uses_discord_upload_source` | `ingest` succeeds | `ingest` called with `upload_source=UploadSource.DISCORD` |

#### `tests/unit/discord/test_notifications.py` — 4 tests

| Test | Setup | Assertion |
|------|-------|-----------|
| `test_reminders_sent_for_due_cards` | 2 users with 1 KB each; `due_count` returns 3 | `fetch_user` called 2 times; `user.send` called 2 times with due-count in message |
| `test_no_reminder_when_zero_due` | `due_count` returns 0 | `user.send` not called |
| `test_reminder_survives_dm_blocked` | `user.send` raises `discord.Forbidden` | No exception propagates; remaining users still processed |
| `test_list_by_provider_called_with_discord` | standard setup | `identity_repo.list_by_provider` called with `"discord"` |

### Standards Compliance

- **No module-level singletons**: all services instantiated in `main()` / per-command sessions (`mindforge/discord/bot.py`).
- **No import-time I/O**: Redis/DB/Neo4j connections opened inside `_async_main()`.
- **Port extension via protocol**: `list_by_provider` added to `ExternalIdentityRepository` protocol before implementing in the adapter.
- **Security**: never expose `reference_answer`, `grounding_context`, `raw_prompt`, `raw_completion` — enforced via `QuizEvalResult` return type (these fields don't exist on it) and explicit test assertion.
- **`UploadSource.DISCORD`**: always passed to `IngestionService.ingest`.
- **Egress**: attachment download uses `discord.Attachment.read()` (Discord's own CDN bytes, controlled by the bot framework) — not a raw outbound HTTP call, so egress policy does not apply.
- **Configuration**: `DISCORD_REMINDER_HOUR` env var added to `AppSettings`; never read via `os.environ` at request time.
- **Guild allowlist**: empty list = allow all (development mode); non-empty = strict allowlist; enforced in every command.
- **Open/Closed**: each new command group = new cog; `bot.py` only registers cogs by calling `add_cog()`, never reads command internals.

## Out of Scope

- Slack bot (Phase 15)
- CLI refactor (Phase 16)
- Angular/frontend changes (no UI changes)
- New Alembic migration (the `external_identities` table already exists; `list_by_provider` is a read query)
- Channel-level or role-level access control (guild-level only per scope decisions)
- Persistent quiz state fallback when Redis is unavailable (per scope decision: fail gracefully with user message)
- Discord OAuth flow for the bot (bot uses its token, not OAuth; `IdentityResolver` auto-provisions on first command)

## Success Criteria

- `mindforge-discord` entry point starts without error when `DISCORD_BOT_TOKEN` is set.
- `/quiz start` creates a Redis key `discord:quiz:pending:{user_id}` after successful session start.
- `/quiz answer` reads the Redis key, calls `QuizService.submit_answer`, deletes the key, and posts score/feedback.
- `/search` returns a Discord embed with ≤5 results from `SearchService`.
- `/upload` calls `IngestionService.ingest` with `UploadSource.DISCORD` and posts `task_id`.
- Guild check rejects unknown guilds when allowlist is non-empty; allows all when list is empty.
- `ExternalIdentityRepository.list_by_provider("discord")` returns all Discord-linked user pairs from PostgreSQL.
- SR reminder task fires at `DISCORD_REMINDER_HOUR` UTC and sends DMs only to users with due cards.
- All 27 unit tests pass with no real DB, Redis, or Discord API calls.
- No `reference_answer`, `grounding_context`, `raw_prompt`, or `raw_completion` appears in any Discord message.
