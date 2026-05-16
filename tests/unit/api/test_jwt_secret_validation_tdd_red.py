"""TDD red tests for JWT secret validation."""

from __future__ import annotations

import pytest

from mindforge.infrastructure.config import AppSettings, validate_settings


def _make_settings(*, jwt_secret: str) -> AppSettings:
    return AppSettings.model_validate(
        {
            "database_url": "postgresql+asyncpg://test:test@localhost/test",
            "jwt_secret": jwt_secret,
        }
    )


def test_validate_settings_rejects_empty_jwt_secret() -> None:
    settings = _make_settings(jwt_secret="")

    with pytest.raises(ValueError, match="JWT_SECRET must not be empty"):
        validate_settings(settings)


def test_validate_settings_rejects_short_jwt_secret() -> None:
    settings = _make_settings(jwt_secret="too-short")

    with pytest.raises(ValueError, match="at least 32 bytes"):
        validate_settings(settings)
