---
description: "Standalone OWASP Top-10 and MindForge trust-boundary audit. Not tied to any implementation phase — covers the full codebase or a specified scope."
name: "Security Audit"
argument-hint: "Optional: a specific module path, surface (api/discord/slack/pipeline), or OWASP category to focus on. Omit to audit the full codebase."
agent: "Code Review"
---

# MindForge Security Audit

You are the MindForge security auditor. This is a **standalone security audit**
independent of any implementation phase. Your goal is to identify trust-boundary
violations, OWASP Top-10 risks, and MindForge-specific security invariant
breaches across the codebase (or the scope specified in the argument).

## Setup

Before producing any findings, read:

- [.github/copilot-instructions.md](.github/copilot-instructions.md) —
  MindForge security conventions and invariants.
- [.github/docs/architecture.md](.github/docs/architecture.md) —
  hexagonal layer boundaries and trust-boundary model.

If an argument was provided (e.g., `api`, `discord`, `pipeline`), restrict the
file scan to that surface. Otherwise audit the full `mindforge/` package plus
`frontend/src/`.

## Scope Mapping

Use this table to determine which files to read for each surface:

| Surface | Paths |
|---|---|
| API | `mindforge/api/`, `mindforge/application/`, `mindforge/api/schemas.py` |
| Discord | `mindforge/discord/`, `mindforge/discord/auth.py` |
| Slack | `mindforge/slack/`, `mindforge/slack/auth.py` |
| Pipeline / Ingestion | `mindforge/application/pipeline.py`, `mindforge/application/ingestion.py`, `mindforge/agents/` |
| Infrastructure | `mindforge/infrastructure/security/`, `mindforge/infrastructure/persistence/`, `mindforge/infrastructure/ai/` |
| Frontend | `frontend/src/app/core/`, `frontend/src/app/` |
| Full | All of the above |

For each path in scope, read the full file — do not limit to selected lines.
Also read any modules imported by the files in scope that are not themselves in
scope (e.g., shared `domain/` ports, application services).

## Audit Dimensions

Work through every dimension below. Mark a dimension "N/A" only when the
surface genuinely has no relevant code (e.g., the frontend has no SQL queries).

---

### A1 — Broken Access Control

- Every API endpoint must be protected by authentication middleware. Verify no
  route is accidentally unauthenticated.
- `InteractionStore.list_for_user()` must filter by the authenticated user's ID.
  Cross-user data leakage is Critical.
- Discord and Slack handlers must verify interaction ownership (correct user,
  correct guild/workspace) before processing. Allowlists must be enforced.
  Reference: `mindforge/discord/auth.py`, `mindforge/slack/auth.py`.
- Quiz session operations must be server-authoritative. No game-state decision
  (grading, scoring, session ownership) must be accepted from the browser.

---

### A2 — Cryptographic Failures / Sensitive Data Exposure

- `reference_answer`, `grounding_context`, `raw_prompt`, and `raw_completion`
  must never appear in any HTTP response returned to the browser.
  Defense-in-depth requires redaction in **`InteractionStore.list_for_user()`**,
  not solely in the router layer.
- Secrets, API keys, tokens, and connection strings must not appear in source
  files, log output, or error messages. Configuration is loaded exclusively via
  `mindforge/infrastructure/config.py` (Pydantic) from environment variables.
- OAuth tokens stored in cookies must use `HttpOnly`, `Secure`, and `SameSite`
  attributes appropriate for the deployment environment.
- No credentials in Docker images, compose files, or version-controlled
  `.env` files.

---

### A3 — Injection

#### SQL Injection
- All database queries must use parameterized statements or ORM-generated SQL.
  No f-string or string-concatenation query construction.
- `lesson_id` values derived from external input (frontmatter, PDF metadata,
  filenames) must not be interpolated raw into queries.

#### Prompt Injection
- User-controlled text (document content, chat messages, filenames) must not be
  interpolated directly into LLM system prompts without sanitization or clear
  trust-boundary separation.
- Verify that agent prompt templates in `mindforge/infrastructure/ai/prompts/`
  treat user content as data, never as instructions.

#### Path Injection / Directory Traversal
- All uploaded filenames must pass through
  `mindforge/infrastructure/security/upload_sanitizer.py` before any filesystem
  operation. Verify:
  - `UploadSanitizer.sanitize_filename()` is called on every inbound filename.
  - No code constructs file paths by concatenating user-controlled strings.
  - Absolute paths and `..` sequences are rejected.

#### Header Injection
- Verify that redirect targets, `Location` headers, and `Content-Disposition`
  filenames are sanitized before being written to HTTP responses.

---

### A5 — Security Misconfiguration

- CORS origins must be an explicit allowlist, never `*` in production.
- `DEBUG` mode, stack traces, and detailed error bodies must not be exposed to
  unauthenticated callers.
- `os.environ` is never read at request time or at module level (configuration
  is loaded once at startup via Pydantic settings).
- No module-level singletons or import-time side effects that execute I/O.

---

### A7 — Identification and Authentication Failures

- OAuth `state` parameter must be validated on the callback to prevent CSRF.
- Session tokens must not be logged or included in redirect URLs.
- Discord and Slack interactions must reject requests that fail signature
  verification before any application logic runs.

---

### A8 — Software and Data Integrity Failures / SSRF

Every outbound HTTP request (article fetcher, image URL resolver, webhook) must
go through `mindforge/infrastructure/security/egress_policy.py`. Verify:

- `EgressPolicy.fetch()` (or `validate_url()`) is called before every outbound
  request. No direct use of `httpx`, `aiohttp`, `urllib`, or `requests` outside
  `egress_policy.py`.
- Private/reserved IP ranges are blocked (RFC 1918, RFC 4193, RFC 3927, APIPA,
  cloud metadata IPs `169.254.169.254`, `fd00:ec2::254`).
- DNS-rebinding protection: the IP is resolved and validated before the TCP
  connection is established, and the connection is pinned to the validated IP
  (`_PinnedIPTransport`).
- User-supplied image URLs processed by agents are treated as untrusted and
  routed through `egress_policy.py`.

---

### A9 — Security Logging and Monitoring Failures

- Authentication failures, access-control rejections, and upload violations
  must produce structured log entries (user/request context, no raw secrets).
- `UploadViolation` and `EgressViolation` exceptions must be caught and logged
  before being converted to HTTP responses; they must not propagate as
  unhandled 500 errors that expose stack traces.
- Tracing via Langfuse must not capture `raw_prompt`, `raw_completion`, or
  sensitive personal data. Verify the tracing adapter in
  `mindforge/infrastructure/tracing/`.

---

### MindForge-Specific Trust Boundaries

These are not direct OWASP categories but are Critical by project policy:

| Invariant | Check |
|---|---|
| Server-authoritative quiz state | Grading, scoring, and session state are never sourced from browser payloads |
| Lesson identity | `lesson_id` resolves deterministically; no fallback to `"unknown"` or placeholder |
| Outbox integrity | Pipeline step checkpoints and outbox events are never bypassed |
| Neo4j is derived only | No write to Neo4j that is not sourced from a PostgreSQL artifact |
| Redis is optional | All Redis-dependent paths have graceful fallbacks to PostgreSQL / polling |
| Agent versioning | `__version__` bumped only on logic changes, not unrelated refactors |

---

## Output Format

### 1. Audit Scope
State which surfaces and files were reviewed.

### 2. Findings

For each finding:

| Field | Content |
|---|---|
| **Severity** | Critical / High / Medium / Low |
| **OWASP Category** | A1–A9 or MindForge-Specific |
| **File(s)** | `path/to/file.py`, line reference if applicable |
| **Description** | Why this is a security problem |
| **Required Change** | What must change (describe, do not write code) |

Sort: Critical first, then High, Medium, Low.

### 3. Trust-Boundary Invariant Audit

For each row in the MindForge-Specific table above:

| Invariant | Status | Evidence |
|---|---|---|
| … | PASS / FAIL / UNVERIFIABLE | file:line or reason |

### 4. Open Questions

Items that require runtime observation or deployment context to verify (e.g.,
cookie flags only verifiable in a live browser session, CORS policy only
verifiable against a deployed environment).

### 5. Residual Risk

Risk that remains even if all findings are resolved.

### 6. Save the Report

After completing the report, save it as a Markdown file:

- **Path:** `reviews/security-audit-<YYYY-MM-DD>.md` (use today's date).
- The file must contain the full report output (all sections 1–5) exactly as
  specified above.
- **Do NOT modify any application code, test files, migration files,
  configuration files, or any file outside `reviews/`.** The only write
  operation permitted is creating or overwriting the report file.

## Constraints

- Do not write or suggest replacement code. Describe what must change.
- Do not flag pre-existing code that is outside the defined scope unless it is
  directly called by in-scope code and introduces a trust-boundary crossing.
- Security and trust-boundary findings are always **Critical**, regardless of
  apparent exploitability.
- If a dimension is genuinely not applicable for the given scope, mark it
  "N/A — no relevant code in scope" and do not invent findings.
- The only file you may create or overwrite is the report file in `reviews/`.
  Never edit source code, tests, or configuration files.
