# Code Review Report — Phase 13: Docker and Deployment

**Date**: 2026-04-23
**Path**: `d:\Dokumenty\Projekty\mindforge` (scoped to 6 new files)
**Scope**: Security · Dockerfile correctness · compose.yml · Test quality
**Status**: ⚠️ Issues Found

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High     | 1 |
| Medium   | 2 |
| Low      | 3 |
| Info     | 3 |

Files analyzed: 6
(`Dockerfile`, `.dockerignore`, `compose.yml`, `scripts/STARTUP_GUIDE.md`,
`tests/unit/test_startup_guide_coverage.py`, `tests/unit/test_deployment_config.py`)

---

## High Issues

### H1 — Dockerfile: Container runs as root

**File**: `Dockerfile` (Stage 2 — Python runtime)
**Category**: Security

The `python:3.12-slim` base image defaults to root. No `USER` instruction is present, so `mindforge-api`, `mindforge-pipeline`, and all bot entry points execute as UID 0 inside the container.

**Risk**: If the API has an exploitable vulnerability (RCE, path traversal, SSRF to internal metadata), an attacker obtains a root shell inside the container. While Docker namespace isolation limits the blast radius, it does not protect against misconfigured bind-mounts, writable Docker socket mounts, or kernel exploits.

**Recommendation**: Create a non-root user and switch to it before `CMD`.

```dockerfile
# Stage 2: Python runtime
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY mindforge/ ./mindforge/
COPY migrations/ ./migrations/
RUN pip install --no-cache-dir -e .
COPY --from=builder /build/frontend/dist/ ./frontend/dist/

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

LABEL org.opencontainers.image.source="https://github.com/mindforge/mindforge"
EXPOSE 8080
CMD ["mindforge-api"]
```

---

## Medium Issues

### M1 — Dockerfile: Source code copy invalidates dependency install cache

**File**: `Dockerfile` lines 14–18
**Category**: Performance / Build correctness

The current layer order is:
```
COPY pyproject.toml ./          # layer N
COPY mindforge/ ./mindforge/    # layer N+1  ← changes on every code edit
COPY migrations/ ./migrations/  # layer N+2
RUN pip install --no-cache-dir -e .  # layer N+3  ← always re-runs
```

Because `COPY mindforge/` precedes `RUN pip install`, any change to application source (the most frequent change) invalidates the dependency install layer. This causes Docker to re-download and recompile all dependencies on every build, even when `pyproject.toml` is unchanged.

**Recommendation**: Separate dependency installation from source copying using a stub package pattern:

```dockerfile
WORKDIR /app
COPY pyproject.toml ./
# Stub source — allows pip to resolve and install all deps without real source
RUN mkdir -p mindforge && touch mindforge/__init__.py
RUN pip install --no-cache-dir -e .
# Now copy actual source — only invalidates the COPY layers, not pip install
COPY mindforge/ ./mindforge/
COPY migrations/ ./migrations/
```

This way `pip install` is re-executed only when `pyproject.toml` changes.

---

### M2 — compose.yml: Three services use unpinned `latest` image tags

**File**: `compose.yml` lines 45, 153, 65
**Category**: Security / Reproducibility

| Service | Image |
|---------|-------|
| `minio` | `minio/minio:latest` |
| `mc-init` | `minio/mc:latest` |
| `clickhouse` | `clickhouse/clickhouse-server:latest` |

Using `latest` means a `docker compose pull` can silently introduce a breaking API change, removed CLI flags, or a compromised image layer.

**Recommendation**: Pin to a specific version tag, e.g.:

```yaml
minio:
  image: minio/minio:RELEASE.2024-11-07T00-52-20Z

mc-init:
  image: minio/mc:RELEASE.2024-11-05T11-29-27Z

clickhouse:
  image: clickhouse/clickhouse-server:24.10
```

---

## Low Issues

### L1 — compose.yml: Default passwords are weak and identical

**File**: `compose.yml` lines 8, 24
**Category**: Security

Both `POSTGRES_PASSWORD` and `NEO4J_PASSWORD` default to the literal string `"secret"` when not set in `.env`:

```yaml
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-secret}
NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-secret}
```

These are the same value, which means a misconfigured deployment (missing `.env`) silently starts with well-known credentials. The `compose.yml` has no comment warning operators that these must be overridden in non-development environments.

**Recommendation**: Add an inline comment or `x-` extension label flagging that these defaults are dev-only and must be rotated for any shared or production deployment. Alternatively, set no default (`${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}`) to fail fast.

---

### L2 — compose.yml: ClickHouse defaults to no authentication

**File**: `compose.yml` line 169
**Category**: Security

```yaml
CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-}
```

When `CLICKHOUSE_PASSWORD` is unset, ClickHouse runs with the `default` user and an empty password. ClickHouse is only reachable within the Docker network, but the exposure is unnecessary.

**Recommendation**: Default to a randomly generated value or require the variable to be set explicitly when the observability profile is enabled.

---

### L3 — compose.yml: mc-init shell variables unquoted

**File**: `compose.yml` lines 69–75 (mc-init entrypoint)
**Category**: Correctness / Security

```sh
mc alias set local http://minio:9000 ${MINIO_ACCESS_KEY:-minioadmin} ${MINIO_SECRET_KEY:-minioadmin}
```

The credential variables are not double-quoted. If either value contains spaces or shell metacharacters, this would be interpreted incorrectly. While MinIO credentials rarely contain such characters, the pattern is fragile and could introduce a command-injection vector if credentials are generated by automation.

**Recommendation**:
```sh
mc alias set local http://minio:9000 "${MINIO_ACCESS_KEY:-minioadmin}" "${MINIO_SECRET_KEY:-minioadmin}"
```

---

## Informational

### I1 — Dockerfile: Base images not pinned to digest

**File**: `Dockerfile` lines 2, 9
**Category**: Supply chain security

`FROM node:20-alpine` and `FROM python:3.12-slim` use floating version tags. A compromised or unintentionally updated base image would be silently incorporated on rebuild.

**Suggestion**: For production pipelines, pin to a specific digest:
```dockerfile
FROM node:20-alpine@sha256:<digest> AS builder
FROM python:3.12-slim@sha256:<digest>
```

---

### I2 — test_startup_guide_coverage.py: Neo4j bolt port 7687 not tested

**File**: `tests/unit/test_startup_guide_coverage.py` lines 47–49
**Category**: Test coverage

`REQUIRED_PORTS` checks for `"7474"` (Neo4j browser) but not `"7687"` (Neo4j bolt). Port 7687 is the primary driver connection port, is exposed in `compose.yml`, and appears in the guide's ports reference table. It should be included in the parametrized test to prevent it from being accidentally dropped from the guide.

**Suggestion**:
```python
REQUIRED_PORTS = ["8080", "4200", "5432", "7474", "7687", "6379", "9001", "3000"]
```

---

### I3 — Dockerfile: `build-essential` retained in final image

**File**: `Dockerfile` line 11
**Category**: Image size

`build-essential` (~200 MB) is required during native extension compilation (e.g., `psycopg2-binary` fallback, `cryptography`) but is not needed at runtime. It remains in the final image because there is no separate build stage for Python dependencies.

**Suggestion**: Use a multi-stage pip install (copy only compiled wheels) or ensure all packages resolve to pre-built binary wheels (`pip install --only-binary :all:`). Low priority unless image size is a CI/production concern.

---

## Confirmed Correct

The following items were checked and found to be properly implemented:

| Check | Result |
|-------|--------|
| `.env` and `.env.*` excluded from build context via `.dockerignore` | ✓ |
| `NEXTAUTH_SECRET` and `SALT` not hardcoded — loaded from `${VAR}` with no default | ✓ |
| Editable install used: `pip install -e .` (not `pip install .`) | ✓ |
| SPA static path alignment: `COPY --from=builder /build/frontend/dist/ ./frontend/dist/` → resolves to `frontend/dist/frontend/browser` matching `main.py` and `angular.json` | ✓ |
| All core services have `healthcheck` definitions | ✓ |
| Named volumes used throughout (no anonymous volumes) | ✓ |
| `quiz-agent` depends on `api` with `condition: service_healthy` | ✓ |
| `mc-init` uses `--ignore-existing` for idempotency | ✓ |
| STARTUP_GUIDE.md covers all 4 runnable modes | ✓ |
| STARTUP_GUIDE.md includes troubleshooting section with `docker compose up mc-init` | ✓ |
| `env.example` contains `NEXTAUTH_SECRET`, `SALT`, `LANGFUSE_DB_PASSWORD` | ✓ |
| Test assertions are meaningful and not trivially true | ✓ |
| No hardcoded credentials in `Dockerfile` or `compose.yml` (uses `${VAR}` substitution) | ✓ |

---

## Prioritized Recommendations

1. **Add a non-root USER to Dockerfile** (H1) — Reduces attack surface in production; low effort change.
2. **Reorder Dockerfile layers for pip cache efficiency** (M1) — Speeds up every development rebuild; stub pattern is straightforward.
3. **Pin `latest` image tags in compose.yml** (M2) — Prevents silent breakage; look up current stable tags for minio, mc, and clickhouse.
4. **Quote shell variables in mc-init entrypoint** (L3) — Defensive correctness; one-line change.
5. **Add 7687 to REQUIRED_PORTS in test** (I2) — Prevents guide regression; trivial fix.

---

## Structured Result

```yaml
status: "passed_with_issues"
report_path: ".maister/tasks/development/2026-04-23-docker-and-deployment/verification/code-review-report.md"

summary:
  critical: 0
  high: 1
  medium: 2
  low: 3
  info: 3
  files_analyzed: 6

issues:
  - source: "code_review"
    severity: "high"
    category: "security"
    description: "Dockerfile container runs as root — no USER instruction present"
    location: "Dockerfile:9-22"
    fixable: true
    suggestion: "Add RUN addgroup/adduser and USER instruction before CMD"

  - source: "code_review"
    severity: "medium"
    category: "performance"
    description: "COPY mindforge/ before pip install invalidates dependency cache on every source change"
    location: "Dockerfile:14-18"
    fixable: true
    suggestion: "Copy pyproject.toml, create stub __init__.py, run pip install, then COPY actual source"

  - source: "code_review"
    severity: "medium"
    category: "security"
    description: "Three services use unpinned :latest image tags (minio, mc-init, clickhouse)"
    location: "compose.yml:45,65,153"
    fixable: true
    suggestion: "Pin to specific version tags or digests"

  - source: "code_review"
    severity: "low"
    category: "security"
    description: "Default passwords 'secret' for POSTGRES_PASSWORD and NEO4J_PASSWORD are weak and identical"
    location: "compose.yml:8,24"
    fixable: true
    suggestion: "Add a comment flagging dev-only defaults; consider using :? to fail fast when unset"

  - source: "code_review"
    severity: "low"
    category: "security"
    description: "ClickHouse defaults to no authentication (empty password)"
    location: "compose.yml:169"
    fixable: true
    suggestion: "Default to a non-empty value or require explicit opt-in"

  - source: "code_review"
    severity: "low"
    category: "security"
    description: "mc-init shell variables not double-quoted — fragile with special characters"
    location: "compose.yml:69-75"
    fixable: true
    suggestion: "Wrap variable expansions in double quotes"

  - source: "code_review"
    severity: "info"
    category: "security"
    description: "Base Docker images not pinned to SHA digest"
    location: "Dockerfile:2,9"
    fixable: true
    suggestion: "Use @sha256:<digest> suffix on FROM lines"

  - source: "code_review"
    severity: "info"
    category: "quality"
    description: "Neo4j bolt port 7687 missing from REQUIRED_PORTS in test"
    location: "tests/unit/test_startup_guide_coverage.py:47"
    fixable: true
    suggestion: "Add '7687' to REQUIRED_PORTS list"

  - source: "code_review"
    severity: "info"
    category: "performance"
    description: "build-essential retained in final image (~200 MB overhead)"
    location: "Dockerfile:11"
    fixable: false
    suggestion: "Use multi-stage build or binary-only wheels to avoid compiler toolchain in runtime image"

issue_counts:
  critical: 0
  high: 1
  medium: 2
  low: 3
  info: 3
```
