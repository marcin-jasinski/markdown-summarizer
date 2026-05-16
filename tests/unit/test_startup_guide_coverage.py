"""Doc-coverage tests for scripts/STARTUP_GUIDE.md.

These tests verify that the guide covers all four startup modes, all
service ports, and all required / Docker-override environment variables
so the document never silently goes out of date.
"""

from __future__ import annotations

import pathlib

import pytest

GUIDE_PATH = pathlib.Path(__file__).parents[2] / "scripts" / "STARTUP_GUIDE.md"


@pytest.fixture(scope="module")
def guide_text() -> str:
    assert GUIDE_PATH.exists(), f"STARTUP_GUIDE.md not found at {GUIDE_PATH}"
    return GUIDE_PATH.read_text(encoding="utf-8")


# ── Test 1: all four runnable modes are documented ────────────────────────


class TestModesCoverage:
    REQUIRED_MODES = [
        # (label, distinctive keyword that must appear in the guide)
        ("Local venv", "pip install -e"),
        ("Docker quick start", "docker compose up -d"),
        ("Observability / Langfuse", "observability"),
        ("Bots profile", "--profile bots"),
    ]

    @pytest.mark.parametrize("label,keyword", REQUIRED_MODES)
    def test_mode_is_documented(
        self, guide_text: str, label: str, keyword: str
    ) -> None:
        assert (
            keyword in guide_text
        ), f"Mode '{label}' is not covered — expected to find '{keyword}' in STARTUP_GUIDE.md"


# ── Test 2: required env vars and all service ports are present ───────────


class TestEnvAndPortsCoverage:
    REQUIRED_ENV_VARS = [
        "DATABASE_URL",
        "JWT_SECRET",
        "MODEL_SMALL",
        "MODEL_LARGE",
        "OPENROUTER_API_KEY",
        "REDIS_URL",
        "NEO4J_URI",
        "MINIO_ENDPOINT",
        "LANGFUSE_PUBLIC_KEY",
        "NEXTAUTH_SECRET",
    ]

    REQUIRED_PORTS = ["8080", "4200", "5432", "7474", "6379", "9001", "3000"]

    @pytest.mark.parametrize("var", REQUIRED_ENV_VARS)
    def test_env_var_is_documented(self, guide_text: str, var: str) -> None:
        assert (
            var in guide_text
        ), f"Environment variable '{var}' is missing from STARTUP_GUIDE.md"

    @pytest.mark.parametrize("port", REQUIRED_PORTS)
    def test_port_is_documented(self, guide_text: str, port: str) -> None:
        assert port in guide_text, f"Port {port} is not mentioned in STARTUP_GUIDE.md"
