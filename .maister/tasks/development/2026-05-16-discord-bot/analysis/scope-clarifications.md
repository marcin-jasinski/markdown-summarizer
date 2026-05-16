# Scope Clarifications — Phase 14: Discord Bot

**Date:** 2026-05-16
**Phase:** 2 (Gap Analysis)

---

## Design Decisions Made

### 1. KB Resolution Strategy: Interactive Dropdown
- User invokes `/quiz start` or `/search <query>` → bot queries `KnowledgeBaseService.list_for_user(user_id)` → shows Discord `Select` menu → user picks KB
- Fallback: if user has exactly one KB, skip the menu and use it directly
- KB name is displayed in the menu (not UUID)

### 2. Quiz Session State: Redis-Backed Tracking
- After `/quiz start`, store `{discord_user_id: {session_id, question_id, kb_id}}` in Redis (TTL = quiz_session_ttl_seconds)
- `/quiz answer <answer>` looks up the active session from Redis using `str(interaction.user.id)` as key
- Redis key format: `discord:quiz:pending:{discord_user_id}`
- If Redis unavailable: fail gracefully with a user-facing message (no silent fallback)
- Rationale: consistent with existing Redis-first session design; bot restarts don't lose sessions

### 3. SR User Enumeration: Extend Port + Implementation
- Add `async def list_by_provider(provider: str) -> list[tuple[UUID, str]]` to `ExternalIdentityRepository` protocol in `mindforge/domain/ports.py`
- Implement in `mindforge/infrastructure/persistence/identity_repo.py`
- Returns `(user_id, external_id)` pairs — reminder cog sends DM to `external_id` (Discord user ID)
- This method will also be reused by the Slack bot (Phase 15) for Slack workspace notifications

---

## Scope Boundaries

**In scope (Phase 14):**
- `mindforge/discord/bot.py` — full async composition root
- `mindforge/discord/auth.py` — guild allowlist + interaction ownership guard
- `mindforge/discord/cogs/quiz.py` — /quiz start, /quiz answer
- `mindforge/discord/cogs/search.py` — /search
- `mindforge/discord/cogs/upload.py` — /upload attachment
- `mindforge/discord/cogs/notifications.py` — SR reminder background task
- `mindforge/discord/cogs/__init__.py` — cog exports
- `mindforge/domain/ports.py` — add list_by_provider to ExternalIdentityRepository
- `mindforge/infrastructure/persistence/identity_repo.py` — implement list_by_provider
- `tests/unit/discord/` — unit tests for allowlist, identity resolution, interaction ownership

**Out of scope:**
- Slack bot (Phase 15)
- CLI entry points (Phase 16)
- Angular UI changes (no UI changes)
- New Alembic migration (no schema changes needed — external_identities table already exists)
