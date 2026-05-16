"""
TDD Red Gate: GET /api/knowledge-bases/{kb_id}/lessons endpoint missing.

This test MUST FAIL before the fix is applied.

Bug: The frontend calls GET /api/knowledge-bases/{kb_id}/lessons but no
     handler exists in knowledge_bases.py router. The route returns 404.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create a test client with mocked database dependencies."""
    from mindforge.api.main import create_app

    app = create_app()

    from mindforge.api.deps import get_current_user, get_kb_repo
    from mindforge.domain.models import KnowledgeBase, User

    user_id = uuid4()
    fake_user = User(
        user_id=user_id,
        display_name="Test User",
        email="test@example.com",
        avatar_url=None,
        is_admin=False,
        created_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user

    # Mock KB repo so ownership check doesn't hit the DB
    fake_kb = KnowledgeBase(
        kb_id=uuid4(),
        owner_id=user_id,
        name="Test KB",
        description="",
        created_at=datetime.now(timezone.utc),
    )
    mock_kb_repo = MagicMock()
    mock_kb_repo.get_by_id = AsyncMock(return_value=fake_kb)
    app.dependency_overrides[get_kb_repo] = lambda: mock_kb_repo

    # Override read model repo if it has been added to deps (post-implementation)
    from mindforge.api import deps as _deps

    _get_rm = getattr(_deps, "get_read_model_repo", None)
    if _get_rm is not None:
        mock_rm_repo = MagicMock()
        mock_rm_repo.list_lessons = AsyncMock(return_value=[])
        app.dependency_overrides[_get_rm] = lambda: mock_rm_repo

    return TestClient(app)


def test_list_lessons_endpoint_exists(client):
    """
    GET /api/knowledge-bases/{kb_id}/lessons must return 200 with LessonResponse[].

    FAILS before fix: route does not exist → 404 Not Found.
    """
    kb_id = str(uuid4())

    response = client.get(f"/api/knowledge-bases/{kb_id}/lessons")

    # This assertion will FAIL before the route is added (currently returns 404)
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        "The GET /api/knowledge-bases/{{kb_id}}/lessons route is missing from knowledge_bases.py."
    )
    assert isinstance(response.json(), list)
