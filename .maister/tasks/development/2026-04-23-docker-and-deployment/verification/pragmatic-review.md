# Pragmatic Code Review — Phase 13: Docker and Deployment

**Date:** 2026-04-23
**Reviewer:** code-quality-pragmatist
**Scope:** `Dockerfile`, `compose.yml`, `scripts/STARTUP_GUIDE.md`, `tests/unit/test_deployment_config.py`, `tests/unit/test_startup_guide_coverage.py`

---

## Executive Summary

**Overall Status: ✅ Appropriate — with two actionable issues**

The Docker and deployment implementation is well-matched to the project's actual complexity. MindForge 2.0 is not an MVP — it has 9 AI agents, 14 API routers, Neo4j, Redis, MinIO, and optional LLM observability, Discord/Slack bots. The three-profile Compose setup and detailed STARTUP_GUIDE.md are proportionate, not over-engineered.

Two issues warrant attention before Phase 14: one is a real operational risk (Langfuse host hardcoded into the core stack), and one is a code smell that becomes an operational liability (`pip install -e .` in the container).

| Severity | Count |
|----------|-------|
| High     | 2     |
| Medium   | 2     |
| Low      | 2     |
| Info     | 1     |

---

## 1. Complexity Assessment

**Project scale:** Early-production. Phases 0–12 complete, full feature set, active users implied.

**Stack components in play:** FastAPI API, Angular SPA, PostgreSQL (primary store), Neo4j (graph projection), Redis (sessions/cache), MinIO (object storage), LiteLLM gateway, optional Langfuse/ClickHouse observability, Discord bot, Slack bot.

**Complexity indicators:**
- 7 named volumes
- 12 services across 3 profiles
- 4 documented startup modes

**Assessment: Proportionate.** Each service is justified by the architecture. None are speculative. The profile system exists to make the heavy observability stack optional — that is its intended use.

---

## 2. Issues Found

### HIGH — LANGFUSE_HOST hardcoded in core api service

**File:** `compose.yml`, `api` service environment block
**Evidence:**
```yaml
api:
  environment:
    LANGFUSE_HOST: http://langfuse:3000
```
The `langfuse` service is only started with `--profile observability`. When users run the core stack without that profile (`docker compose up -d`), `LANGFUSE_HOST` resolves to a hostname that doesn't exist in the network. If `ENABLE_TRACING=true` (the default in `env.example`), the API will fail to connect at startup or on first LLM call. The application handles Redis absence gracefully with a warning; Langfuse absence deserves the same treatment — or the env override should be omitted from the core service definition so the `.env` value (pointing to `localhost:3000`) falls through.

**Recommendation:** Remove `LANGFUSE_HOST` from the `api` service's environment block in `compose.yml`. Users running the observability profile already set this in `.env`, and the application should handle a missing/unreachable Langfuse host gracefully (the `ENABLE_TRACING` flag already exists for this).

---

### HIGH — Editable install (`pip install -e .`) in production container

**File:** `Dockerfile`, Stage 2
**Evidence:**
```dockerfile
RUN pip install --no-cache-dir -e .
```
**File:** `implementation-plan.md` (note):
> MUST be editable (`-e`) so `__file__` stays at `/app/mindforge/api/main.py`; regular install copies to site-packages and breaks SPA path resolution

This means the Angular SPA's path is resolved by computing `os.path.dirname(__file__)` relative to `main.py`. That is a code smell: a production container's static file path should not depend on whether the package was installed editably. The editable install leaves `mindforge.egg-link` and `__editable__` hooks in site-packages — not suitable for a production image and potentially brittle across Python versions.

**Recommendation:** Fix the SPA path resolution in `mindforge/api/main.py` to use an explicit, deployment-aware path (e.g., `Path(__file__).parents[3] / "frontend/dist/frontend/browser"` or an env var `STATIC_DIR`), then switch the Dockerfile to `pip install --no-cache-dir .`. This is a small targeted fix in `main.py`.

---

### MEDIUM — `latest` image tags for two services

**File:** `compose.yml`
**Evidence:**
```yaml
minio:
  image: minio/minio:latest

clickhouse:
  image: clickhouse/clickhouse-server:latest
```
`latest` tags produce non-deterministic builds — a `docker compose pull` months from now may pull a breaking release with no warning. This is the only place in the entire `compose.yml` where non-pinned tags appear; all other services use explicit version tags (`postgres:17-alpine`, `neo4j:5`, `redis:7-alpine`, `langfuse/langfuse:3`).

**Recommendation:** Pin to current stable versions, e.g., `minio/minio:RELEASE.2024-01-16T16-07-38Z` and `clickhouse/clickhouse-server:24.3`. Any minor-version pin is better than `latest`.

---

### MEDIUM — Missing OCI label `org.opencontainers.image.version`

**File:** `Dockerfile`
**Evidence:**
```dockerfile
LABEL org.opencontainers.image.source="https://github.com/mindforge/mindforge"
```
The implementation plan explicitly requires both `org.opencontainers.image.version` and `org.opencontainers.image.source`. Only `source` is present. This is a minor compliance gap against the plan's acceptance criteria.

**Recommendation:** Add `LABEL org.opencontainers.image.version="2.0.0"` (or parameterize with a build arg).

---

### LOW — Environment variable repetition between `api` and `quiz-agent`

**File:** `compose.yml`
**Evidence:** Both `api` and `quiz-agent` declare identical blocks for `DATABASE_URL`, `REDIS_URL`, `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`. When a new infrastructure variable is added, it must be duplicated in both services — a silent maintenance risk.

**Recommendation:** Use YAML anchors or a Compose extension field (`x-common-env: &common-env`) to define shared environment once. Not urgent, but reduces copy-paste bugs in future phases.

---

### LOW — `git` dependency described in plan, absent from Dockerfile

**File:** `Dockerfile` vs `implementation-plan.md` step 1.4
**Evidence:** The plan states to install `git` ("needed by some pip extras") as a system dependency alongside `curl`, `build-essential`, and `libpq-dev`. The Dockerfile omits it. Either `git` is not actually needed (the plan was over-specified) or it is silently missing.

**Recommendation:** Verify whether any dependency in `pyproject.toml` requires `git` at install time. If not, no action needed — remove the mention from the plan. If yes, add `git` to the `apt-get install` line.

---

### INFO — Phase number mismatch between task directory and roadmap

**Files:** `.maister/tasks/development/2026-04-23-docker-and-deployment/implementation/implementation-plan.md` vs `roadmap.md`
**Evidence:** The implementation plan is titled "Phase 13 — Docker and Deployment". The project roadmap lists this same work as "Phase 17 — Docker & Deployment" (phases 13–16 are Discord Bot, Slack Bot, CLI Entry Points, Observability). No functional impact, but creates context confusion for future task planning.

---

## 3. Questions Specifically Addressed

### Are 3 compose profiles appropriate for this project scale?

**Yes — appropriate.** The profile design follows Docker Compose best practices for optional-service separation:
- `core` (default): the minimal working stack needed by every developer
- `observability`: Langfuse + ClickHouse + dedicated Postgres — legitimately optional and heavy, adding 3 services and a second Postgres
- `bots`: Discord + Slack stubs — correctly isolated since they're placeholders pending Phase 14/15

This is not over-engineering. It prevents developers from being forced to start ClickHouse and a second Postgres just to run the API locally.

### Is STARTUP_GUIDE.md length proportionate?

**Yes — proportionate.** The guide is ~500 lines covering 4 startup modes, a complete ports reference, full env var reference table (35+ variables), health verification commands, and 6 troubleshooting scenarios. The length comes from the actual complexity of the stack — each service requires at least one env var, port reference, and a health command. The table format is dense but scannable. No section is redundant.

### Any unnecessary abstractions in the Docker setup?

**No.** The Dockerfile is 22 lines. The multi-stage build (Node → Python) is idiomatic and necessary. There are no custom entrypoint scripts, no wrapper shells, no init containers beyond the justified `mc-init`. The compose file uses standard healthchecks and dependency conditions throughout.

### Are 30 unit tests appropriate or excessive?

**Appropriate — they prevent documentation and configuration drift.** The breakdown:
- `test_deployment_config.py` (9 tests): 5 security/structural property checks against `.dockerignore`, `compose.yml`, and `env.example`. These guard against real regressions: secret leakage, idempotency break, startup ordering violation.
- `test_startup_guide_coverage.py` (21 tests): Content-presence checks for 4 mode keywords, 10 env var names, and 7 port numbers in the guide.

The second group is "grep the markdown" tests — they can pass even if context is wrong. However, their primary value is anti-drift: if a variable is removed from the guide or a port changes, the test catches it immediately without running Docker. The maintenance overhead is near-zero (they run in milliseconds with no I/O). 21 parametrized tests is not excessive when the alternative is the guide silently going out of date.

---

## 4. Developer Experience

**Setup friction:** Low. `cp env.example .env` → `docker compose up -d` is the path of least resistance and well-documented.

**Feedback loop:** The `start_period: 60s` on the api healthcheck means a developer running the full stack waits ~60-90 seconds before the API is reachable. This is unavoidable given PostgreSQL + Neo4j + MinIO must all be healthy first.

**Error discoverability:** The STARTUP_GUIDE.md troubleshooting covers the top failure modes (missing env vars, port conflicts, MinIO bucket, Neo4j auth, Langfuse unhealthy). The guide correctly points to `docker compose logs api` for Pydantic `ValidationError` diagnosis.

---

## 5. Recommended Actions (Priority Order)

### 1. Fix LANGFUSE_HOST in core stack (High, ~15 min)
Remove `LANGFUSE_HOST: http://langfuse:3000` from the `api` service environment block in `compose.yml`. Verify the infrastructure layer handles a missing/unreachable Langfuse endpoint gracefully when `ENABLE_TRACING=false` or Langfuse is not running.

### 2. Fix SPA path resolution, remove editable install (High, ~30 min)
In `mindforge/api/main.py`, replace the `__file__`-relative SPA path computation with an explicit absolute path or env-var-based path. Then change the Dockerfile to `pip install --no-cache-dir .` (non-editable). This makes the container image production-grade.

### 3. Pin `latest` image tags (Medium, ~5 min)
Replace `minio/minio:latest` and `clickhouse/clickhouse-server:latest` with pinned version tags in `compose.yml`.

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Files reviewed | 5 |
| Lines of config (Dockerfile + compose.yml) | ~230 |
| Lines of documentation | ~500 |
| Unit tests | 30 |
| Issues found | 7 (2H / 2M / 2L / 1I) |
| Over-engineering findings | 0 |
| Complexity verdict | Proportionate to project scale |
