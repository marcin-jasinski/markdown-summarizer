"""Unit test: GET /api/v1/users/me/stats returns 200 with stub zeros."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mindforge.api.deps import get_current_user
from mindforge.api.routers import users as users_router
from mindforge.domain.models import User


def _make_stub_user() -> User:
    from uuid import uuid4
    from datetime import datetime, timezone

    return User(
        user_id=uuid4(),
        display_name="Test User",
        email="test@example.com",
        password_hash="hashed",
        avatar_url=None,
        created_at=datetime.now(timezone.utc),
        last_login_at=None,
        is_admin=False,
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(users_router.router, prefix="/api/v1/users", tags=["users"])

    stub_user = _make_stub_user()
    app.dependency_overrides[get_current_user] = lambda: stub_user

    return app


def test_get_my_stats_returns_200_with_stub_zeros() -> None:
    """GET /api/v1/users/me/stats → 200 {"streak_days": 0, "due_today": 0}."""
    client = TestClient(_build_app())
    response = client.get("/api/v1/users/me/stats")

    assert response.status_code == 200
    data = response.json()
    assert data == {"streak_days": 0, "due_today": 0}
