# Gap Analysis: Phase 14 — Discord Bot

**Date**: 2026-05-16
**Task**: Implement Discord Bot with slash commands (quiz, search, upload), guild allowlists, IdentityResolver-based user mapping, application service delegation, and per-user SR reminder DMs

---

## Summary

- **Risk Level**: Low-Medium
- **Estimated Effort**: Medium
- **Detected Characteristics**: modifies_existing_code, creates_new_entities

The Discord bot is a purely additive implementation. `bot.py` is a 10-line stub; all cogs, auth guard, and tests are absent. Every required building block (config, services, `IdentityResolver`, `UploadSource.DISCORD`, `discord.py` dependency) is already in place. Three design decisions need to be confirmed before writing the specification.

---

## Task Characteristics

- Has reproducible defect: **no**
- Modifies existing code: **yes** — `bot.py` stub → full composition root; `cogs/__init__.py` → exports cog classes
- Creates new entities: **yes** — `mindforge/discord/auth.py`, `cogs/quiz.py`, `cogs/search.py`, `cogs/upload.py`, `cogs/reminder.py`, `tests/unit/discord/`
- Involves data operations: **no** — all reads/writes go through application services
- UI heavy: **no** — Discord slash commands; no Angular changes

---

## Gaps Identified

### Critical — Blocking (must exist before any cog can run)

| Gap | Evidence |
|-----|----------|
| **`bot.py` composition root** | File is a 10-line stub that just `print()`s. No DB engine, no services, no bot instantiation. |
| **`mindforge/discord/auth.py` missing** | `file_search` returns no results. Guild allowlist guard referenced in project docs and config, but no implementation exists. All cogs depend on this check. |
| **`cogs/quiz.py` missing** | `cogs/` directory contains only `__init__.py`. `/quiz start` and `/quiz answer` commands are the primary feature. |

### High — Core features absent

| Gap | Evidence |
|-----|----------|
| **`cogs/search.py` missing** | No file exists. `/search` command not implemented. |
| **`cogs/upload.py` missing** | No file exists. `/upload` command not implemented. `UploadSource.DISCORD` in domain models goes unused. |
| **`tests/unit/discord/` missing** | `tests/unit/` has no Discord subdirectory. Codebase analysis confirms 0 Discord tests exist. |

### Medium — Supporting feature absent

| Gap | Evidence |
|-----|----------|
| **`cogs/reminder.py` missing** | No file exists. Per-user SR reminder DMs (background `tasks.loop`) not implemented. |

### Low — Minor updates

| Gap | Evidence |
|-----|----------|
| **`cogs/__init__.py` needs exports** | Currently empty. Should export cog classes for `bot.py` to load. |

---

## New Capability Analysis

### Integration Points

- **Entry point**: `pyproject.toml` → `mindforge-discord = "mindforge.discord.bot:main"` already registered; `bot.main()` must become the async lifespan composition root.
- **Compose service**: `compose.yml` `discord-bot` service references `mindforge-discord` entry point — no changes required.
- **`IdentityResolver`**: imported from `mindforge.api.auth`. The `resolve()` method and `UserInfo` dataclass are ready; no changes needed upstream.
- **`FlashcardsService.due_count(user_id, kb_id) -> int`**: already the correct interface for reminder logic.

### Patterns to Follow

| Pattern | Source |
|---------|--------|
| Async composition root | `mindforge/api/main.py` `lifespan()` context manager |
| Guild guard `interaction_check()` | `mindforge/discord/auth.py` in Slack adapter pattern (per copilot-instructions.md reference) |
| Error → response mapping | `mindforge/api/routers/quiz.py` and `mindforge/api/routers/documents.py` |
| Identity resolution | `mindforge/api/auth.py` `IdentityResolver.resolve(UserInfo(...))` |
| Per-command DB session | `async with session_factory() as session: ... finally: await session.close()` |

### Architectural Impact: Low

All implementation is confined to `mindforge/discord/`. Zero changes required to domain, application, infrastructure, or API layers.

---

## Infrastructure Gap: SR Reminder User Enumeration

The `ExternalIdentityRepository` protocol only exposes:
- `find_user_id(provider, external_id) → UUID | None`
- `link(...) → None`
- `create_user_and_link(...) → UUID`

**No `list_by_provider()` method exists** in either the port protocol (`domain/ports.py`) or the implementation (`infrastructure/persistence/identity_repo.py`).

The reminder task needs to iterate all `(user_id, discord_external_id)` pairs for provider `"discord"`. Two approaches are available:

| Approach | Pros | Cons |
|----------|------|------|
| **A — Direct SQL in reminder cog** (`SELECT user_id, external_id FROM external_identities WHERE provider='discord'`) | No port change; minimal scope; pragmatic | Bypasses port abstraction (acceptable for a leaf adapter's internal scheduling task) |
| **B — Add `list_by_provider(provider) → list[tuple[UUID, str]]` to `ExternalIdentityRepository`** | Clean port design; reusable for Slack bot (Phase 15) | Small port/implementation change required; extends domain boundary |

See decision `sr_reminder_enumeration` below.

---

## Issues Requiring Decisions

### Important (Should Decide — Needed for Specification)

**1. `kb_resolution` — How should `/quiz` and `/search` let users pick a knowledge base?**

`KnowledgeBaseService.list_for_user(user_id)` is available to enumerate KBs.

| Option | Description |
|--------|-------------|
| **A — Name argument** | `/quiz start <kb_name> [topic]` — user types KB name as a slash command parameter |
| **B — Interactive dropdown** | Bot first sends an ephemeral select menu; user picks a KB; interaction continues |
| **C — Auto-select first KB** | If the user has exactly one KB, use it automatically; error if zero or more than one |

**Default**: A — Name argument. Simplest to implement, no multi-step interaction required, consistent with how the API accepts KB identifiers.

---

**2. `quiz_session_state` — How should pending quiz sessions be tracked across Discord interactions?**

After `/quiz start`, the user must call `/quiz answer` with the same `session_id`. The bot needs to associate the Discord user with their open session.

| Option | Description |
|--------|-------------|
| **A — In-memory dict on bot instance** | `bot._quiz_sessions: dict[discord_user_id, session_id]` — simple, lost on restart |
| **B — Redis** | Consistent, multi-worker-safe, requires Redis available |
| **C — PostgreSQL `QuizSessionStore`** | Already available via `PostgresQuizSessionStore`; `start_session()` returns `session_id` which the user must pass back to `/quiz answer` as an explicit argument |

**Default**: C — have `/quiz answer` take `session_id` as an explicit argument (user copies it from the bot's `/quiz start` response). This requires zero additional state management in the bot and is consistent with the existing server-authoritative session design.

---

**3. `sr_reminder_enumeration` — How should the reminder task enumerate Discord-linked users?**

See "Infrastructure Gap" section above.

| Option | Description |
|--------|-------------|
| **A — Direct SQL in reminder cog** | `SELECT user_id, external_id FROM external_identities WHERE provider='discord'` inside the cog's session |
| **B — Add `list_by_provider()` to port + implementation** | Clean extension; also useful for Phase 15 Slack bot |

**Default**: B — add `list_by_provider(provider: str) -> list[tuple[UUID, str]]` to `ExternalIdentityRepository`. The Slack bot (Phase 15) will need the same query; establishing it now avoids two separate SQL strings in two leaf adapters.

---

## Compatibility Requirements

**Strict** for application service interfaces — no changes to any method signatures, result types, or exception types in `application/`.

**Flexible** for `mindforge/discord/` internals — this is all new code.

**Moderate** for `ExternalIdentityRepository` — if option B is chosen for `sr_reminder_enumeration`, a new method must be added to both the protocol and the concrete implementation without breaking existing callers (additive only).

---

## Recommendations

1. Confirm the three decisions above before writing the specification; all have clear defaults that allow implementation to proceed without ambiguity.
2. Implement in order: `auth.py` guard → `bot.py` composition root → `SearchCog` (simplest) → `QuizCog` → `UploadCog` → `ReminderTask`.
3. Write unit tests for each cog in `tests/unit/discord/` alongside implementation, not after — guild allowlist check and identity helper are pure functions, easy to test in isolation.
4. Apply `ephemeral=True` to all responses that contain quiz questions or personal data to prevent leakage to other guild members.
5. Validate attachment MIME type via `upload_sanitizer.py` before calling `IngestionService.ingest()` — do not pass raw Discord bytes unchecked.

---

## Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| **Complexity Risk** | Low | Entirely additive; all services ready; clear templates in API layer |
| **Integration Risk** | Low | Zero upstream consumers; hexagonal boundary intact |
| **Regression Risk** | Very Low | No existing Discord code to break; no shared-layer changes |
| **Test Coverage Risk** | Medium | Zero existing tests; new code must be accompanied by unit tests to avoid future regressions |
| **SR Enumeration Gap** | Low-Medium | Two clean approaches identified; decision B preferred but A is a safe fallback |
