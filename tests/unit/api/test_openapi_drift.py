"""
CI drift test — `api.models.ts` must declare every Pydantic schema.

This test implements the check described in Phase 12, task 12.0.3:

    Add a CI check or test that fails if ``api.models.ts`` drifts from the
    OpenAPI spec.

How it works
------------
1. Import the FastAPI app and call ``app.openapi()`` to get the spec — no
   server required, no database needed.
2. Extract all schema component names from ``spec["components"]["schemas"]``.
3. Read ``frontend/src/app/core/models/api.models.ts``.
4. Assert that every schema name appears at least once in the TypeScript file.

The check is intentionally loose (existence, not field-level type equality) to
avoid false positives from TypeScript naming conventions.  If a Pydantic class
is renamed, this test will catch the missing interface immediately.
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TS_MODELS = (
    _REPO_ROOT / "frontend" / "src" / "app" / "core" / "models" / "api.models.ts"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_openapi_schema_names() -> set[str]:
    """Return the set of Pydantic schema names from the FastAPI OpenAPI spec."""
    from mindforge.api.main import create_app

    app = create_app()
    spec = app.openapi()
    components = spec.get("components", {}).get("schemas", {})
    return set(components.keys())


def _get_ts_model_names() -> set[str]:
    """Extract TypeScript interface/type names from ``api.models.ts``."""
    ts_source = _TS_MODELS.read_text(encoding="utf-8")
    # Match `export interface Foo` and `export type Foo`
    return set(re.findall(r"export\s+(?:interface|type)\s+(\w+)", ts_source))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApiModelsDrift:
    """Verify ``api.models.ts`` is not missing any OpenAPI schema component."""

    def test_ts_models_file_exists(self) -> None:
        assert _TS_MODELS.exists(), (
            f"TypeScript models file not found: {_TS_MODELS}\n"
            "Run the frontend setup or restore the file from source control."
        )

    def test_all_openapi_schemas_declared_in_ts(self) -> None:
        """Every Pydantic response/request schema must have a matching TS interface."""
        openapi_names = _get_openapi_schema_names()
        ts_names = _get_ts_model_names()

        # Skip internal FastAPI / Pydantic utility schemas (ValidationError etc.)
        _SKIP_PATTERNS = {
            "ValidationError",
            "HTTPValidationError",
            "Body_",
        }

        missing: list[str] = []
        for name in sorted(openapi_names):
            if any(name.startswith(p) for p in _SKIP_PATTERNS):
                continue
            if name not in ts_names:
                missing.append(name)

        assert not missing, (
            f"The following OpenAPI schema(s) are missing from api.models.ts "
            f"({_TS_MODELS.relative_to(_REPO_ROOT)}):\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\nUpdate api.models.ts or run `npm run openapi:generate` to regenerate it."
        )

    def test_openapi_spec_has_schemas(self) -> None:
        """Smoke test — the OpenAPI spec must expose at least 10 named schemas."""
        names = _get_openapi_schema_names()
        assert len(names) >= 10, (
            f"OpenAPI spec returned fewer schemas than expected ({len(names)}). "
            "Check that all routers are registered in create_app()."
        )
