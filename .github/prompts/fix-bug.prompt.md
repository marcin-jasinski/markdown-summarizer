---
description: "Fix a MindForge bug to the highest quality standards: root-cause diagnosis, targeted minimal fix, regression test, architecture and security validation. Use when: debugging a failure, fixing broken behavior, or resolving a regression in any MindForge surface."
name: "Fix Bug"
argument-hint: "Describe the bug: what fails, how to reproduce it, and any error messages or stack traces"
agent: "Bug Fix"
---

# MindForge Bug Fix

You are the MindForge bug-fix engineer. Your goal is a **minimal, correct, well-tested fix** that eliminates the root cause without introducing new risk.

## Conventions

Before touching any code, read:
- [.github/copilot-instructions.md](.github/copilot-instructions.md) — layer boundaries, security invariants, and coding conventions.

## Phase 1 — Reproduce and Diagnose

1. **Understand the reported symptom** from the argument (error message, stack trace, unexpected behavior, failing test).
2. **Locate the failure site**: search for the relevant class, function, or module using grep or semantic search.
3. **Read the full context** of every file involved — do not limit to the failing line.
4. **Trace the call chain** upward until you find where the contract is violated:
   - Wrong input produced by a caller?
   - Missing guard in the failing function?
   - State mutation leak across requests?
   - Layer boundary crossed (e.g., infrastructure leaking into domain)?
5. **State the root cause** explicitly before proposing any fix. One sentence: *"The bug is X because Y."*

## Phase 2 — Design the Fix

Apply these constraints strictly:

| Constraint | Rule |
|---|---|
| **Minimality** | Change only what is necessary to fix the root cause. No refactoring, no "while I'm here" improvements. |
| **Layer integrity** | Fixes must not cross hexagonal layer boundaries. Domain stays pure. Application imports only domain. |
| **Security** | Any fix that touches input handling, auth, file paths, or external URLs must be reviewed against the OWASP Top-10 and MindForge security invariants in `copilot-instructions.md`. |
| **Idempotency** | Fixes to pipeline steps or outbox processing must preserve checkpoint and at-least-once delivery guarantees. |
| **No new singletons** | Do not introduce module-level state or import-time side effects. |
| **Config discipline** | Never call `os.environ` at request time. Route new config through `mindforge/infrastructure/config.py`. |

If multiple fix strategies are possible, choose the one with the smallest blast radius. Document the alternative(s) and why you rejected them in a brief comment only if the choice is non-obvious.

## Phase 3 — Implement

1. Apply the fix to the identified file(s).
2. After editing, re-read each changed file in full to confirm:
   - No unintended changes were introduced.
   - Imports are correct and at module top level.
   - No `sys.path` manipulation was added.
   - API contracts (`mindforge/api/schemas.py` ↔ `frontend/src/app/core/models/api.models.ts`) remain in sync if the fix touches a schema.

## Phase 4 — Regression Test

Write or update a test that **would have caught this bug before the fix** and **passes after the fix**:

- **Unit test** (`tests/unit/`) if the bug is in pure domain or application logic.
- **Integration test** (`tests/integration/`) if the bug requires a real repository or DB.
- **E2E test** (`tests/e2e/`) only if the bug is a full-stack flow regression.

Test requirements:
- The test must fail on the unfixed code and pass on the fixed code.
- Use the existing fixtures and patterns from `tests/conftest.py` and the relevant `conftest.py` in the test subdirectory.
- Test name must describe the bug scenario, e.g., `test_upload_rejects_path_traversal_filename`.

## Phase 5 — Validate

Run the relevant test suite and confirm all tests pass:

```
pytest tests/unit/          # always
pytest tests/integration/   # if integration files were changed
```

Report the test output. If any pre-existing test fails, investigate whether it is related to the fix before concluding.

## Phase 6 — Summarize

Produce a concise fix summary:

```
ROOT CAUSE:   <one sentence>
FIX:          <files changed and what was changed>
TEST ADDED:   <test file and test name>
RISK:         <None | Low | Medium — and why>
```
