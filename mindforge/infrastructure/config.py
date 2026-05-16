"""
Application settings loaded once at startup from environment variables.

Never call os.environ or read settings at request time — pass `AppSettings`
instances explicitly through dependency injection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

_DEFAULT_JWT_SECRET = "change-me-in-production-min-32-bytes"
_MIN_JWT_SECRET_BYTES = 32


# ---------------------------------------------------------------------------
# EgressSettings (used by EgressPolicy in Phase 4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EgressSettings:
    allow_private_networks: bool = False
    allow_nonstandard_ports: bool = False
    allowed_protocols: tuple[str, ...] = ("http", "https")
    max_response_bytes: int = 10 * 1024 * 1024  # 10 MB
    timeout_seconds: float = 30.0


# ---------------------------------------------------------------------------
# AppSettings
# ---------------------------------------------------------------------------


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Database -----------------------------------------------------------
    database_url: str = "postgresql+asyncpg://mindforge:secret@localhost:5432/mindforge"
    redis_url: str | None = None

    # -- Neo4j --------------------------------------------------------------
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "secret"
    neo4j_database: str = "neo4j"

    # -- AI Models ----------------------------------------------------------
    model_small: str = "openai/gpt-4o-mini"
    model_large: str = "openai/gpt-4o"
    model_vision: str = "openai/gpt-4o"
    model_embedding: str = "openai/text-embedding-3-small"
    model_fallback: str = "anthropic/claude-3-haiku-20240307"
    openrouter_api_key: str | None = None
    ollama_api_base: str | None = None

    # -- Auth (OAuth) -------------------------------------------------------
    discord_client_id: str | None = None
    discord_client_secret: str | None = None
    discord_redirect_uri: str = "http://localhost:8080/api/auth/callback/discord"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None

    # -- Auth (Basic / JWT) -------------------------------------------------
    enable_basic_auth: bool = True
    bcrypt_cost_factor: int = 12
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_access_token_ttl_minutes: int = 60
    jwt_refresh_token_ttl_days: int = 30
    auth_secure_cookies: bool = False

    # -- Slack --------------------------------------------------------------
    slack_bot_token: str | None = None
    slack_app_token: str | None = None
    slack_signing_secret: str | None = None
    slack_allowed_workspaces: str | None = None  # comma-separated workspace IDs

    # -- Discord Bot --------------------------------------------------------
    discord_bot_token: str | None = None
    discord_allowed_guilds: str | None = None  # comma-separated guild IDs

    # -- Object Storage (MinIO / S3) ----------------------------------------
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "mindforge-assets"
    minio_secure: bool = False

    # -- Feature Flags ------------------------------------------------------
    enable_graph: bool = True
    enable_image_analysis: bool = True
    enable_article_fetch: bool = True
    enable_flashcards: bool = True
    enable_diagrams: bool = True
    enable_tracing: bool = True
    enable_embeddings: bool = True
    enable_relevance_guard: bool = True

    # -- Limits -------------------------------------------------------------
    max_document_size_mb: int = 10
    max_concurrent_pipelines: int = 2
    max_pending_tasks_per_user: int = 10
    pipeline_task_stale_threshold_minutes: int = 30
    quiz_session_ttl_seconds: int = 1800

    # -- Tracing (Langfuse) -------------------------------------------------
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3000"

    # -- Logging ------------------------------------------------------------
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"

    # -- Chunking -----------------------------------------------------------
    chunk_max_tokens: int = 512
    chunk_min_tokens: int = 64
    chunk_overlap_tokens: int = 64

    # -- Egress -------------------------------------------------------------
    egress_allow_private_networks: bool = False
    egress_allow_nonstandard_ports: bool = False
    egress_max_response_bytes: int = 10 * 1024 * 1024
    egress_timeout_seconds: float = 30.0

    # -----------------------------------------------------------------------

    @field_validator("bcrypt_cost_factor")
    @classmethod
    def _bcrypt_range(cls, v: int) -> int:
        if not (4 <= v <= 31):
            raise ValueError("bcrypt_cost_factor must be between 4 and 31")
        return v

    @field_validator("jwt_access_token_ttl_minutes")
    @classmethod
    def _jwt_ttl_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("jwt_access_token_ttl_minutes must be positive")
        return v

    # -----------------------------------------------------------------------

    # Provider prefixes that route to a specific backend — never rewrite these.
    _LOCAL_PREFIXES: tuple[str, ...] = (
        "ollama/",
        "openrouter/",
        "vertex_ai/",
        "bedrock/",
        "azure/",
        "anthropic/",  # keep explicit Anthropic calls as-is if user set them
    )

    @staticmethod
    def _openrouter_prefix(model: str) -> str:
        """Prepend ``openrouter/`` to *model* unless it already targets a
        specific backend (Ollama, Azure, etc.)."""
        _local = (
            "ollama/",
            "openrouter/",
            "vertex_ai/",
            "bedrock/",
            "azure/",
        )
        if any(model.startswith(p) for p in _local):
            return model
        return f"openrouter/{model}"

    @property
    def model_map(self) -> dict[str, str]:
        """Logical model name → LiteLLM model string.

        When ``OPENROUTER_API_KEY`` is provided, completion models (small,
        large, vision, fallback) are automatically routed through OpenRouter
        by prepending the ``openrouter/`` provider prefix.  The embedding
        model is left unchanged because OpenRouter does not proxy OpenAI
        embedding endpoints.
        """
        raw = {
            "small": self.model_small,
            "large": self.model_large,
            "vision": self.model_vision,
            "embedding": self.model_embedding,
            "fallback": self.model_fallback,
        }
        if self.openrouter_api_key:
            return {
                k: (self._openrouter_prefix(v) if k != "embedding" else v)
                for k, v in raw.items()
            }
        return raw

    @property
    def slack_allowed_workspace_list(self) -> list[str]:
        if not self.slack_allowed_workspaces:
            return []
        return [
            w.strip() for w in self.slack_allowed_workspaces.split(",") if w.strip()
        ]

    @property
    def discord_allowed_guild_list(self) -> list[int]:
        if not self.discord_allowed_guilds:
            return []
        return [
            int(g.strip()) for g in self.discord_allowed_guilds.split(",") if g.strip()
        ]


# ---------------------------------------------------------------------------
# Cross-field validation
# ---------------------------------------------------------------------------


def validate_settings(settings: AppSettings) -> None:
    """
    Perform cross-field validation.  Called once at composition-root startup.
    Raises ValueError with a descriptive message on misconfiguration.
    """
    errors: list[str] = []

    if settings.enable_graph and not settings.neo4j_uri:
        errors.append("enable_graph=true requires NEO4J_URI to be set")

    # Warn when OpenRouter is the only key: it does not proxy OpenAI embeddings,
    # so MODEL_EMBEDDING must point to a locally-reachable or Ollama model, or
    # the user must also supply OPENAI_API_KEY / another embedding provider key.
    import os as _os

    has_openai_key = bool(_os.environ.get("OPENAI_API_KEY"))
    if (
        settings.openrouter_api_key
        and not has_openai_key
        and settings.enable_embeddings
        and not settings.model_embedding.startswith("ollama/")
    ):
        log.warning(
            "OPENROUTER_API_KEY is set but OPENAI_API_KEY is absent. "
            "Embedding calls to %r will still target OpenAI directly — "
            "set OPENAI_API_KEY or switch MODEL_EMBEDDING to an Ollama model "
            "(e.g. ollama/nomic-embed-text) to avoid auth errors.",
            settings.model_embedding,
        )

    if settings.enable_tracing and not settings.langfuse_public_key:
        log.warning(
            "ENABLE_TRACING=true but LANGFUSE_PUBLIC_KEY is not set — "
            "tracing will use stdout adapter"
        )

    jwt_secret = settings.jwt_secret.strip()
    if not jwt_secret:
        errors.append(
            "JWT_SECRET must not be empty. Generate one with: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    elif len(jwt_secret.encode("utf-8")) < _MIN_JWT_SECRET_BYTES:
        errors.append("JWT_SECRET must be at least 32 bytes for HS256")

    if jwt_secret == _DEFAULT_JWT_SECRET:
        if settings.auth_secure_cookies:
            errors.append(
                "JWT_SECRET is set to the default placeholder value. "
                "Set a strong random secret before deploying."
            )
        else:
            log.warning(
                "JWT_SECRET is still the default placeholder — "
                "set a strong random value before deploying to production"
            )

    if settings.enable_image_analysis and settings.model_vision == settings.model_small:
        log.warning(
            "ENABLE_IMAGE_ANALYSIS=true but MODEL_VISION == MODEL_SMALL — "
            "consider using a dedicated vision model"
        )

    if not settings.redis_url:
        log.warning(
            "Redis not configured — using PostgreSQL fallbacks "
            "(quiz sessions, SSE polling, semantic cache disabled)"
        )

    if errors:
        raise ValueError(
            "Configuration errors:\n" + "\n".join(f"  • {e}" for e in errors)
        )


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_settings() -> AppSettings:
    """Load and return settings (cached for the process lifetime)."""
    settings = AppSettings()
    return settings


def load_egress_settings(settings: AppSettings | None = None) -> EgressSettings:
    """Build an EgressSettings dataclass from AppSettings."""
    s = settings or load_settings()
    return EgressSettings(
        allow_private_networks=s.egress_allow_private_networks,
        allow_nonstandard_ports=s.egress_allow_nonstandard_ports,
        allowed_protocols=("http", "https"),
        max_response_bytes=s.egress_max_response_bytes,
        timeout_seconds=s.egress_timeout_seconds,
    )


def load_auth_settings(settings: AppSettings | None = None) -> dict:
    """Return auth-related settings as a plain dict (for auth middleware)."""
    s = settings or load_settings()
    return {
        "jwt_secret": s.jwt_secret,
        "jwt_access_token_ttl_minutes": s.jwt_access_token_ttl_minutes,
        "jwt_refresh_token_ttl_days": s.jwt_refresh_token_ttl_days,
        "auth_secure_cookies": s.auth_secure_cookies,
        "enable_basic_auth": s.enable_basic_auth,
        "bcrypt_cost_factor": s.bcrypt_cost_factor,
    }


def load_credentials() -> dict:
    """Return provider OAuth credentials (for OAuth flow setup)."""
    s = load_settings()
    return {
        "discord": {
            "client_id": s.discord_client_id,
            "client_secret": s.discord_client_secret,
            "redirect_uri": s.discord_redirect_uri,
        },
        "google": {
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
        },
        "github": {
            "client_id": s.github_client_id,
            "client_secret": s.github_client_secret,
        },
    }
