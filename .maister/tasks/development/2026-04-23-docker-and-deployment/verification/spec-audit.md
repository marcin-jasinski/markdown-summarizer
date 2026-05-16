# Spec Audit — Phase 13: Docker and Deployment

**Auditor:** spec-auditor agent
**Date:** 2026-04-23
**Spec path:** `.maister/tasks/development/2026-04-23-docker-and-deployment/implementation/spec.md`
**Requirements path:** `.maister/tasks/development/2026-04-23-docker-and-deployment/implementation/requirements.md`

---

## Verdict

❌ **FAIL**

| Severity | Count |
|----------|-------|
| Critical | 2     |
| High     | 1     |
| Medium   | 2     |
| Low      | 2     |

Two Critical issues would prevent a working Docker image: one breaks the build itself, the other silently breaks SPA serving at runtime. Both must be fixed before implementation begins.

---

## Critical Issues

### C-1 — SPA path resolution fails with non-editable `pip install`

**Spec reference:** Stage 2, Step 4–5; "SPA Path Resolution (critical)"; "Key Implementation Notes → SPA Path"

**Spec claim:**
> "With `WORKDIR /app` and package installed to `/app/mindforge/`, this resolves to `/app/frontend/dist/frontend/browser`"

**Evidence — `mindforge/api/main.py` (lines 322–328):**
```python
spa_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "frontend", "dist", "frontend", "browser"
)
if os.path.isdir(spa_path):
    app.mount("/", StaticFiles(directory=spa_path, html=True), name="spa")
```

**Evidence — spec Stage 2, Step 4:**
> "Run `pip install --no-cache-dir .`"

**Gap:**
`pip install --no-cache-dir .` is a **non-editable** install. Python copies the `mindforge` package to site-packages (e.g., `/usr/local/lib/python3.12/site-packages/mindforge/`). At runtime `__file__` resolves to:

```
/usr/local/lib/python3.12/site-packages/mindforge/api/main.py
```

The relative path `../../frontend/dist/frontend/browser` therefore resolves to:

```
/usr/local/lib/python3.12/site-packages/frontend/dist/frontend/browser
```

This directory does **not** exist. `os.path.isdir(spa_path)` returns `False`, the SPA is never mounted, and every `GET /` returns `404`. The spec's claim that the package is "installed to `/app/mindforge/`" is factually incorrect for a non-editable install.

Source files remain at `/app/mindforge/` after the install but Python does **not** import from there — it uses site-packages. The spec's own test criterion #4 (`GET http://localhost:8080/` returns HTML) would fail silently (no build error, just a 404 at runtime).

**Category:** Incorrect
**Severity:** Critical — core feature (SPA serving) is broken in Docker

**Fix options (choose one):**
1. Add `ENV PYTHONPATH=/app` to Stage 2. Python prepends `/app` to `sys.path`; imports resolve from `/app/mindforge/api/main.py`; `__file__` points to the correct location. The SPA at `/app/frontend/dist/frontend/browser` is found.
2. Change to `pip install --no-cache-dir -e .` (editable install). `__file__` stays at `/app/mindforge/api/main.py`. Not ideal for production images.

Option 1 (`ENV PYTHONPATH=/app`) is the recommended fix — one line addition to Stage 2, no code change required.

---

### C-2 — `alembic.ini` does not exist at repo root; Docker build fails

**Spec reference:** Stage 2, Step 3

**Spec claim:**
> "Copy `pyproject.toml`, `mindforge/`, `migrations/`, `alembic.ini` to `/app/`."

**Evidence — filesystem search (1 result):**
```
d:\Dokumenty\Projekty\mindforge\migrations\alembic.ini
```
There is **no** `alembic.ini` at the repository root. It lives inside `migrations/`.

**Evidence — `mindforge/infrastructure/db.py` (lines 46–50):**
```python
cfg = Config("migrations/alembic.ini")
cfg.attributes["connection"] = sync_conn
command.upgrade(cfg, "head")
```

`run_migrations()` already references it correctly via `Config("migrations/alembic.ini")` relative to CWD `/app`. No root-level copy is needed.

**Impact:**
A Dockerfile that follows the spec literally (e.g., `COPY pyproject.toml mindforge/ migrations/ alembic.ini ./`) fails at build time with:
```
failed to solve: failed to read file content at path alembic.ini: no such file or directory
```

**Category:** Incorrect
**Severity:** Critical — the Docker image cannot be built

**Fix:** Remove `alembic.ini` from the list of separately copied files in Step 3. The file is already included inside `migrations/` which is copied as a directory. The correct copy list is:
```
COPY pyproject.toml mindforge/ migrations/ ./
```

---

## High Issues

### H-1 — Langfuse observability stack missing required container-level env vars

**Spec reference:** "Profile: observability" section; env var table

**Spec coverage:**
The spec documents app-side env vars that MindForge needs (e.g., `LANGFUSE_HOST=http://langfuse:3000`), but does not specify the environment variables that the **`langfuse`**, **`langfuse-db`**, and **`clickhouse`** containers themselves require.

**Gap:**
Langfuse v3 containers require at minimum:

| Service | Required Vars |
|---------|--------------|
| `langfuse-db` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` |
| `clickhouse` | `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` (if auth enabled) |
| `langfuse` | `DATABASE_URL` (→ `langfuse-db`), `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, `SALT` (or `ENCRYPTION_KEY`), `CLICKHOUSE_URL`, `CLICKHOUSE_USER` |

Without these, the `langfuse` container exits at startup with a configuration error. The `pg_isready -U langfuse` healthcheck (referenced in the spec) requires `POSTGRES_USER=langfuse` on `langfuse-db` — this is implied but never stated.

**Category:** Missing
**Severity:** High — observability profile would fail to start without this information

**Fix:** Add a service-internal env var table for the observability sub-stack to the spec's Environment Variables section.

---

## Medium Issues

### M-1 — Neo4j container auth not specified

**Spec reference:** "Profile: core" service topology; healthcheck table

**Gap:**
Neo4j 5 requires authentication configuration via `NEO4J_AUTH` (e.g., `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`). Without it, the container either starts with the initial password change prompt (blocking bolt connections) or uses its own defaults.

The spec lists `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` as application-side env vars but never specifies the `NEO4J_AUTH` variable for the neo4j service container in `compose.yml`.

**Category:** Missing
**Severity:** Medium — core `neo4j` service in compose.yml would start with mismatched credentials

**Fix:** Add `NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}` to the neo4j service environment in compose.yml guidance.

---

### M-2 — JWT_SECRET "no defaults" claim is inaccurate

**Spec reference:** "Environment Variables" section:
> "Sensitive values (`JWT_SECRET`, API keys) are loaded from `${VAR}` references with no defaults — operators must supply them via `.env` file."

**Evidence — `mindforge/infrastructure/config.py` (line ~88):**
```python
jwt_secret: str = "change-me-in-production"
```

**Evidence — `mindforge/infrastructure/config.py` (validate_settings):**
```python
_DEFAULT_JWT_SECRET = "change-me-in-production"
if settings.jwt_secret == _DEFAULT_JWT_SECRET:
    if settings.auth_secure_cookies:
        errors.append("JWT_SECRET is set to the default placeholder...")
    else:
        log.warning("JWT_SECRET is still the default placeholder...")
```

**Gap:**
`JWT_SECRET` has a default value (`"change-me-in-production"`). When `AUTH_SECURE_COOKIES=false` (which is the default, and typical for local Docker dev), the application starts successfully with this placeholder — it only emits a warning. The spec's claim of "no defaults" is inaccurate and may cause operators to skip setting the secret.

**Category:** Incorrect
**Severity:** Medium — security implication; the default JWT_SECRET would be used in Docker if not explicitly set

**Fix:** Update the spec to state: "`JWT_SECRET` has a placeholder default (`change-me-in-production`) which triggers a warning at startup. Always supply a strong random value in `.env` before running Docker."

---

## Low Issues

### L-1 — mc-init / api race window (documented but debatable)

**Spec reference:** "MinIO Init Container" topology note:
> "No explicit ordering between mc-init and api is needed — both wait for MinIO health independently."

**Gap:**
The `api` service depends on `minio` healthy but not on `mc-init` completing. There is a narrow window where:
1. MinIO passes its healthcheck
2. `mc-init` has not yet created the `mindforge-assets` bucket
3. The API starts and accepts a document upload
4. The MinIO `PutObject` call fails with "bucket does not exist"

In practice this window is very small (bucket creation is a single fast command). The spec acknowledges the design, but does not note that `quiz-agent` also depends on `api` healthy (which implies migrations complete), giving `mc-init` additional time. The risk is real but low in practice.

**Category:** Incomplete
**Severity:** Low — narrow race window under atypical load

**Note:** An alternative is to add `mc-init` as a dependency of `api` with `condition: service_completed_successfully`. This would close the race entirely.

---

### L-2 — Success criterion health response format is a partial subset

**Spec reference:** Success Criteria #3:
> "`GET http://localhost:8080/api/health` returns HTTP 200 with `{"status":"ok","database":"ok"}`"

**Evidence — `mindforge/api/schemas.py` (lines 320–325):**
```python
class HealthResponse(BaseModel):
    status: str
    database: str
    neo4j: str | None = None
    redis: str | None = None
```

**Gap:**
The actual response includes `neo4j` and `redis` fields (present when those services are configured). The success criterion omits them, making it appear the response has only two fields. With the full compose stack running, a typical response would be:
```json
{"status":"ok","database":"ok","neo4j":"ok","redis":"ok"}
```

This doesn't break any verification, but the criterion is misleading.

**Category:** Incomplete
**Severity:** Low — documentation accuracy only

**Fix:** Update criterion #3 to: "returns HTTP 200 with `{"status":"ok","database":"ok","neo4j":"ok","redis":"ok"}`" (for the full compose stack).

---

## What the Spec Gets Right

The following items were independently verified and are correct:

| Item | Verification |
|------|-------------|
| Entry point names | All 6 match `pyproject.toml` exactly: `mindforge-api`, `mindforge-pipeline`, `mindforge-quiz`, `mindforge-backfill`, `mindforge-discord`, `mindforge-slack` |
| Port (8080) | Confirmed in `main.py:run()` (`uvicorn.run(..., port=8080, ...)`) |
| SPA output path | `angular.json outputPath: "dist/frontend"` → `dist/frontend/browser/` (Angular 17+ appends `browser/`); COPY to `/app/frontend/dist/` is correct |
| `package-lock.json` exists | Confirmed at `frontend/package-lock.json` ✓ |
| `npm ci` then `npm run build` | Correct sequence for reproducible builds |
| Health endpoint path | `/api/health` confirmed in `health.py` (router prefix `/api`) |
| Health check command | `curl -f http://localhost:8080/api/health` correct |
| Alembic at startup | Confirmed in `main.py:lifespan()` with advisory lock |
| `run_migrations()` config path | `Config("migrations/alembic.ini")` resolves correctly from CWD `/app` |
| `alembic.ini script_location = migrations` | Resolves to `/app/migrations/` from CWD `/app` ✓ |
| Named volumes (7) | `postgres_data`, `neo4j_data`, `neo4j_logs`, `redis_data`, `minio_data`, `langfuse_db_data`, `clickhouse_data` — all needed |
| Docker compose service count (core) | 7 services: postgres, neo4j, redis, minio, mc-init, api, quiz-agent |
| `quiz-agent` CMD | `mindforge-pipeline` matches pyproject.toml |
| Bot stubs `restart: no` | Correct per requirements |
| `mc mb --ignore-existing` | Correct idempotency flag |
| `${MINIO_ROOT_USER}` in mc-init | Correct variable name for MinIO v3+ |
| `.dockerignore` content | Comprehensive and correct |
| Node 20 base image | npm@11.9.0 in package.json requires Node 20+ ✓ |
| Python 3.12 base image | `requires-python = ">=3.12"` in pyproject.toml ✓ |
| `langfuse/langfuse:3` image tag | Matches requirements.md (Langfuse v3) ✓ |

---

## Recommendations

**Before handing to implementer:**

1. **[Critical — C-1]** Add `ENV PYTHONPATH=/app` to Stage 2 of the Dockerfile, immediately after `WORKDIR /app`. Document this in the spec.

2. **[Critical — C-2]** Remove `alembic.ini` from the Stage 2 COPY instruction in the spec. The file is at `migrations/alembic.ini` and is already included in the `migrations/` directory copy.

3. **[High — H-1]** Add an environment variable table for the Langfuse sub-stack services (`langfuse-db`, `clickhouse`, `langfuse`) to the spec. At minimum cover `NEXTAUTH_SECRET`, `SALT`, `CLICKHOUSE_URL`, and `DATABASE_URL` for the `langfuse` container.

4. **[Medium — M-1]** Add `NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}` to the neo4j service specification in compose.yml guidance.

5. **[Medium — M-2]** Correct the JWT_SECRET "no defaults" claim to reflect the placeholder default behavior.

---

## Compliance Status

❌ **Non-Compliant** — 2 Critical issues present. The Docker image as specified would fail to build (C-2) or silently fail to serve the Angular SPA (C-1). Implement fixes for C-1 and C-2 before proceeding.
