"""TDD red test for document upload route wiring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mindforge.api.deps import get_current_user
from mindforge.api.routers import documents as documents_router
from mindforge.domain.models import BlockType, ContentBlock, ParsedDocument, User


class _SessionContext:
    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeSession:
    async def commit(self) -> None:
        return None


class _SessionFactory:
    def __call__(self) -> _SessionContext:
        return _SessionContext(_FakeSession())


class _FakeKbRepo:
    async def get_by_id(self, kb_id, owner_id=None):
        return object()


class _FakeDocRepo:
    async def get_by_content_hash(self, kb_id, content_hash):
        return None

    async def deactivate_lesson(self, kb_id, lesson_id):
        return 0

    async def save(self, document) -> None:
        return None


class _FakeTaskRepo:
    async def count_pending_for_user(self, user_id):
        return 0

    async def create_task(self, document_id):
        return uuid4()


class _FakePublisher:
    async def publish_in_tx(self, event, connection) -> None:
        return None


class _FakeParser:
    def parse(self, raw_bytes: bytes, filename: str) -> ParsedDocument:
        return ParsedDocument(
            text_content="# Heading\nbody",
            metadata={"lesson_id": "lesson-1", "title": "Heading"},
            content_blocks=[
                ContentBlock(
                    block_type=BlockType.TEXT,
                    content="# Heading\nbody",
                    position=0,
                )
            ],
            embedded_images=[],
        )


class _FakeParserRegistry:
    def get(self, mime_type: str) -> _FakeParser:
        return _FakeParser()


def _make_user() -> User:
    return User(
        user_id=uuid4(),
        display_name="Upload Tester",
        email="upload@example.com",
        avatar_url=None,
        is_admin=False,
        created_at=datetime.now(timezone.utc),
    )


def test_upload_document_returns_202_for_valid_markdown(monkeypatch) -> None:
    """Valid upload should be accepted and queued (HTTP 202)."""
    app = FastAPI()
    app.state.session_factory = _SessionFactory()
    app.state.settings = SimpleNamespace(max_document_size_mb=10)
    app.state.parser_registry = _FakeParserRegistry()

    app.include_router(documents_router.router)

    app.dependency_overrides[get_current_user] = _make_user

    monkeypatch.setattr(
        documents_router, "get_kb_repo", lambda request, session: _FakeKbRepo()
    )
    monkeypatch.setattr(
        documents_router, "PostgresDocumentRepository", lambda session: _FakeDocRepo()
    )
    monkeypatch.setattr(
        documents_router,
        "PostgresPipelineTaskRepository",
        lambda session: _FakeTaskRepo(),
    )
    monkeypatch.setattr(
        documents_router, "OutboxEventPublisher", lambda session: _FakePublisher()
    )

    kb_id = str(uuid4())
    files = {"file": ("lesson.md", b"# Heading\nbody", "text/markdown")}

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f"/api/knowledge-bases/{kb_id}/documents", files=files)

    assert response.status_code == 202
    body = response.json()
    assert "document_id" in body
    assert "task_id" in body
    assert body["lesson_id"] == "lesson-1"
