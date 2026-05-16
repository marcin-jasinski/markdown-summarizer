---
description: "Scan Python and npm dependency trees for known CVEs, outdated packages, and transitive risks. Produces severity-ranked findings with minimal version-bump recommendations. Run before every release and after any dependency update."
name: "Dependency Audit"
argument-hint: "Optional: 'python', 'frontend', or 'all' (default). Omit to audit both."
agent: "Code Review"
---

# MindForge Dependency Audit

You are the MindForge dependency auditor. Your goal is to identify known
vulnerabilities, outdated packages, and supply-chain risks in the Python and
npm dependency trees. Produce severity-ranked findings with the minimal version
bump required to resolve each one. Do not perform broad upgrades; every
suggested change must be the smallest increment that closes the finding.

## Setup

Before scanning, read:

- [.github/copilot-instructions.md](.github/copilot-instructions.md) —
  conventions and the list of expected external dependencies.

If the argument is `python`, audit only the Python surface. If `frontend`,
audit only npm. Otherwise (default / `all`) audit both.

---

## Phase 1 — Python Dependency Audit

### 1.1 Run the scanner

Run `pip-audit` against the installed environment. If `pip-audit` is not
installed, install it first with `pip install pip-audit`, then run:

```
pip-audit --requirement requirements.txt --format json
```

If `pip-audit` is unavailable and cannot be installed, fall back to:

```
safety check -r requirements.txt --json
```

Capture the full JSON output.

### 1.2 Analyze findings

For each vulnerability reported:

1. Record the package name, installed version, vulnerable version range, fixed
   version, and CVE/GHSA identifier.
2. Determine **reachability**: does MindForge actually exercise the vulnerable
   code path?
   - Search `mindforge/` for import of the affected package.
   - If the package is imported, check whether the vulnerable API surface
     (specific function, endpoint, or feature flagged in the advisory) is used.
   - Label each finding: **Reachable**, **Imported but not reachable**, or
     **Not imported (transitive only)**.
3. For reachable findings, verify whether `mindforge/infrastructure/security/`
   or any existing guard already mitigates the vector described in the advisory.

### 1.3 Check for outdated packages (non-CVE)

Run:

```
pip list --outdated --format json
```

From the output, flag only packages that are:
- More than **two major versions** behind the latest release, OR
- Marked end-of-life by their maintainers, OR
- No longer maintained (check PyPI classifiers or last-release date > 24 months).

Do not flag minor or patch version differences unless they are security-relevant.

### 1.4 Transitive risk check

Read `requirements.txt` and identify any package that:
- Executes code at import time via a `__init__.py` side effect (known pattern
  for supply-chain attacks). Flag any package with this known behavior.
- Pins to an exact version (`==`) in a way that prevents security patches from
  being applied automatically. Recommend switching to `>=x.y.z,<x+1` where
  this does not break the API contract.

---

## Phase 2 — Frontend (npm) Dependency Audit

### 2.1 Run the scanner

```
cd frontend
npm audit --json
```

Capture the full JSON output.

### 2.2 Analyze findings

For each advisory returned by `npm audit`:

1. Record the package name, installed version, vulnerable version range, fixed
   version, severity, and CVE/GHSA identifier.
2. Determine **reachability**:
   - `devDependency` packages (test runners, build tools) that are never
     bundled into the production output should be labeled **Dev-only** and
     downgraded to Medium severity regardless of npm's rating.
   - Packages that are bundled into `frontend/dist/` and exposed to end-user
     browsers are **Production** and retain their rated severity.
3. Check whether `npm audit fix --dry-run` would resolve the finding without
   a breaking semver change. Record whether the fix is **Auto-fixable** or
   **Manual upgrade required**.

### 2.3 Outdated packages (non-CVE)

Run:

```
npm outdated
```

Flag only packages that are a major version behind and are direct dependencies
(not transitive). Do not flag minor or patch differences.

---

## Phase 3 — Cross-Cutting Checks

### 3.1 Credentials in dependency manifests

Read `requirements.txt`, `pyproject.toml`, `frontend/package.json`, and
`frontend/package-lock.json` (top-level only, not the full lock file).

Flag any entry containing:
- A private registry URL that embeds credentials or tokens in the URL.
- A `git+https://` or `git+ssh://` URL pointing to a private repo that may
  leak the URL in CI logs.

### 3.2 Pinned git SHAs

Flag any dependency pinned to a raw git SHA rather than a versioned release
tag. SHA-pinned dependencies are opaque to security scanners and bypass
standard vulnerability databases.

---

## Output Format

### Dependency Audit Report — `<date>`

**Scope:** Python / Frontend / Both

---

#### Python Findings

| Severity | Package | Installed | Fixed Version | CVE / GHSA | Reachability | Notes |
|----------|---------|-----------|--------------|------------|--------------|-------|
| Critical | … | … | … | … | Reachable | … |

**Outdated (non-CVE):** list package, installed version, latest version,
reason flagged.

---

#### Frontend Findings

| Severity | Package | Installed | Fixed Version | CVE / GHSA | Scope | Auto-fixable |
|----------|---------|-----------|--------------|------------|-------|-------------|
| High | … | … | … | … | Production | Yes / No |

**Outdated (non-CVE):** list package, installed version, latest major version.

---

#### Cross-Cutting Findings

List any credential-in-manifest or SHA-pinning issues found.

---

#### Recommended Actions

For each finding where a fix is available, provide one line:

```
UPGRADE  requests 2.28.1 → 2.31.0  (CVE-2023-32681, Reachable)
UPGRADE  angular/core 16.x → 17.x   (EOL major, Production bundle)
REVIEW   some-package (git SHA pin — no vulnerability DB coverage)
```

Sort: Critical and High first, then Medium, then Low. Within each severity,
Reachable / Production findings precede Dev-only / transitive findings.

**Do not propose upgrades beyond what is listed above.** Broad dependency
refreshes are out of scope for this audit.
