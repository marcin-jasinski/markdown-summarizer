"""Deployment configuration tests for Phase 13.

Verifies security and structural properties of .dockerignore, compose.yml,
env.example, and STARTUP_GUIDE.md without requiring a running Docker daemon.

Gap coverage:
  1. .dockerignore excludes .env (secret leakage prevention)
  2. mc-init uses --ignore-existing (idempotency)
  3. STARTUP_GUIDE.md troubleshooting documents mc-init re-run
  4. quiz-agent waits for api health before starting
  5. env.example includes observability-profile variables
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).parents[2]
DOCKERIGNORE = ROOT / ".dockerignore"
COMPOSE_YML = ROOT / "compose.yml"
ENV_EXAMPLE = ROOT / "env.example"
STARTUP_GUIDE = ROOT / "scripts" / "STARTUP_GUIDE.md"


@pytest.fixture(scope="module")
def dockerignore_lines() -> set[str]:
    assert DOCKERIGNORE.exists(), f".dockerignore not found at {DOCKERIGNORE}"
    return {
        line.strip() for line in DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
    }


@pytest.fixture(scope="module")
def compose_data() -> dict:
    assert COMPOSE_YML.exists(), f"compose.yml not found at {COMPOSE_YML}"
    return yaml.safe_load(COMPOSE_YML.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def env_example_text() -> str:
    assert ENV_EXAMPLE.exists(), f"env.example not found at {ENV_EXAMPLE}"
    return ENV_EXAMPLE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def guide_text() -> str:
    assert STARTUP_GUIDE.exists(), f"STARTUP_GUIDE.md not found at {STARTUP_GUIDE}"
    return STARTUP_GUIDE.read_text(encoding="utf-8")


# ── Gap 1: .dockerignore excludes .env secrets ────────────────────────────


class TestDockerignoreSecrets:
    """Gap 1 — .env must not leak into the Docker build context."""

    @pytest.mark.parametrize("pattern", [".env", ".env.*"])
    def test_env_pattern_excluded(
        self, dockerignore_lines: set[str], pattern: str
    ) -> None:
        assert (
            pattern in dockerignore_lines
        ), f"'{pattern}' must appear in .dockerignore to prevent secret leakage into the image"


# ── Gap 2: mc-init is idempotent ──────────────────────────────────────────


class TestMcInitIdempotency:
    """Gap 2 — Re-running mc-init after bucket exists must exit 0."""

    def test_mc_mb_uses_ignore_existing(self, compose_data: dict) -> None:
        entrypoint = compose_data["services"]["mc-init"]["entrypoint"]
        assert (
            "--ignore-existing" in entrypoint
        ), "mc-init entrypoint must use 'mc mb --ignore-existing' so re-runs succeed when the bucket already exists"


# ── Gap 3: STARTUP_GUIDE troubleshooting covers mc-init re-run ───────────


class TestStartupGuideTroubleshooting:
    """Gap 3 — Troubleshooting section must document mc-init re-run."""

    def test_troubleshooting_section_exists(self, guide_text: str) -> None:
        assert (
            "## Troubleshooting" in guide_text
        ), "STARTUP_GUIDE.md must contain a '## Troubleshooting' section"

    def test_mc_init_rerun_command_documented(self, guide_text: str) -> None:
        assert (
            "docker compose up mc-init" in guide_text
        ), "Troubleshooting section must show 'docker compose up mc-init' to re-run the init container"


# ── Gap 4: quiz-agent waits for api health ────────────────────────────────


class TestQuizAgentStartupOrdering:
    """Gap 4 — quiz-agent must not start until the api healthcheck passes."""

    def test_quiz_agent_depends_on_api_with_service_healthy(
        self, compose_data: dict
    ) -> None:
        services = compose_data["services"]
        assert (
            "quiz-agent" in services
        ), "compose.yml must define a 'quiz-agent' service"
        depends_on = services["quiz-agent"].get("depends_on", {})
        assert "api" in depends_on, "quiz-agent must have 'api' in its depends_on"
        condition = depends_on["api"].get("condition")
        assert condition == "service_healthy", (
            "quiz-agent depends_on.api must have condition: service_healthy, "
            f"got: {condition!r}"
        )


# ── Gap 5: env.example includes observability-profile variables ───────────


class TestEnvExampleObservabilityVars:
    """Gap 5 — env.example must template every variable required for Mode 3."""

    @pytest.mark.parametrize("var", ["NEXTAUTH_SECRET", "SALT", "LANGFUSE_DB_PASSWORD"])
    def test_observability_var_in_env_example(
        self, env_example_text: str, var: str
    ) -> None:
        assert var in env_example_text, (
            f"env.example must include '{var}' — users enabling the observability profile "
            "need a template for this value"
        )
