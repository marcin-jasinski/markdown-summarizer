"""
FastAPI dependency providers.

All providers read from ``request.app.state`` — zero module-level globals.
Separation of concerns: routers import providers; they never access
``app.state`` directly.
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

try:
    import jwt as _jwt
except ImportError:  # pragma: no cover
    _jwt = None  # type: ignore[assignment]

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mindforge.api.auth import JWTService
from mindforge.application.flashcards import FlashcardService
from mindforge.application.quiz import QuizService
from mindforge.application.chat import ChatService, _InMemorySessionCache
from mindforge.application.search import SearchService
from mindforge.domain.agents import ProcessingSettings
from mindforge.domain.models import User
from mindforge.infrastructure.config import AppSettings
from mindforge.infrastructure.events.outbox_publisher import OutboxEventPublisher
from mindforge.infrastructure.persistence.artifact_repo import (
    PostgresArtifactRepository,
)
from mindforge.infrastructure.persistence.document_repo import (
    PostgresDocumentRepository,
)
from mindforge.infrastructure.persistence.identity_repo import (
    PostgresIdentityRepository,
)
from mindforge.infrastructure.persistence.interaction_repo import (
    PostgresInteractionStore,
)
from mindforge.infrastructure.persistence.kb_repo import (
    PostgresKnowledgeBaseRepository,
)
from mindforge.infrastructure.persistence.read_models import (
    PostgresReadModelRepository,
)
from mindforge.infrastructure.persistence.models import UserModel
from mindforge.infrastructure.persistence.pipeline_task_repo import (
    PostgresPipelineTaskRepository,
)
from mindforge.infrastructure.persistence.study_progress_repo import (
    PostgresStudyProgressRepository,
)
from mindforge.infrastructure.security.upload_sanitizer import UploadSanitizer
from mindforge.application.ingestion import IngestionService
from sqlalchemy import select

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def get_settings(request: Request) -> AppSettings:
    return request.app.state.settings


# ---------------------------------------------------------------------------
# Database session — one per request, auto-committed on success
# ---------------------------------------------------------------------------


async def get_db_session(request: Request) -> AsyncSession:  # type: ignore[return]
    session_factory: async_sessionmaker[AsyncSession] = (
        request.app.state.session_factory
    )
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Infrastructure adapters pulled from app.state
# ---------------------------------------------------------------------------


def get_gateway(request: Request):
    return request.app.state.gateway


def get_artifact_repo(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return PostgresArtifactRepository(session)


def get_doc_repo(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return PostgresDocumentRepository(session)


def get_kb_repo(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return PostgresKnowledgeBaseRepository(session)


def get_read_model_repo(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return PostgresReadModelRepository(session)


def get_identity_repo(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return PostgresIdentityRepository(session)


def get_interaction_store(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return PostgresInteractionStore(session)


def get_study_progress(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return PostgresStudyProgressRepository(session)


def get_pipeline_task_repo(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return PostgresPipelineTaskRepository(session)


def get_event_publisher(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    return OutboxEventPublisher(session)


def get_retrieval(request: Request):
    return request.app.state.retrieval


def get_quiz_sessions(request: Request):
    return request.app.state.quiz_session_store


def get_ingestion(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Build an IngestionService scoped to the current request's session."""
    settings: AppSettings = request.app.state.settings
    return IngestionService(
        document_repo=PostgresDocumentRepository(session),
        sanitizer=UploadSanitizer(
            max_size_bytes=settings.max_document_size_mb * 1024 * 1024
        ),
        parser_registry=request.app.state.parser_registry,
        task_store=PostgresPipelineTaskRepository(session),
        event_publisher=OutboxEventPublisher(session),
    )


# ---------------------------------------------------------------------------
# JWT service
# ---------------------------------------------------------------------------


def get_jwt_service(request: Request) -> JWTService:
    return request.app.state.jwt_service


# ---------------------------------------------------------------------------
# Current user — resolved from HttpOnly cookie or Authorization header
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> User:
    """Extract and validate the JWT access token; return the associated User.

    Accepts the token from:
    1. ``access_token`` HttpOnly cookie (browser clients)
    2. ``Authorization: Bearer <token>`` header (CLI / bot clients)
    """
    if _jwt is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT support not available.",
        )

    token: str | None = access_token
    if token is None:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer ") :]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nie jesteś zalogowany.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jwt_service: JWTService = request.app.state.jwt_service
    try:
        payload = jwt_service.decode_access(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token jest nieprawidłowy lub wygasł.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str: str = payload.get("sub", "")
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token zawiera nieprawidłowy identyfikator użytkownika.",
        )

    # Load user from DB
    session_factory: async_sessionmaker[AsyncSession] = (
        request.app.state.session_factory
    )
    async with session_factory() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.user_id == user_id)
        )
        user_row = result.scalar_one_or_none()

    if user_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Użytkownik nie istnieje.",
        )

    return User(
        user_id=user_row.user_id,
        display_name=user_row.display_name,
        email=user_row.email,
        password_hash=user_row.password_hash,
        avatar_url=user_row.avatar_url,
        created_at=user_row.created_at,
        last_login_at=user_row.last_login_at,
        is_admin=user_row.is_admin,
    )


async def get_optional_user(
    request: Request,
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> User | None:
    """Like ``get_current_user`` but returns ``None`` instead of raising 401."""
    try:
        return await get_current_user(request, access_token)
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# Application service providers
# ---------------------------------------------------------------------------


def _build_processing_settings(settings: AppSettings) -> ProcessingSettings:
    """Construct ProcessingSettings from AppSettings (no I/O)."""
    return ProcessingSettings(
        chunk_max_tokens=settings.chunk_max_tokens,
        chunk_min_tokens=settings.chunk_min_tokens,
        chunk_overlap_tokens=settings.chunk_overlap_tokens,
        enable_graph=settings.enable_graph,
        enable_image_analysis=settings.enable_image_analysis,
        enable_article_fetch=settings.enable_article_fetch,
        model_tier_map=settings.model_map,
    )


def get_quiz_service(
    request: Request,
    study_progress: Annotated[object, Depends(get_study_progress)],
    interaction_store: Annotated[object, Depends(get_interaction_store)],
    event_publisher: Annotated[object, Depends(get_event_publisher)],
) -> QuizService:
    """Build a QuizService scoped to the current request.

    Raises HTTP 503 when the graph retrieval adapter is unavailable —
    quiz targeting depends on Graph RAG weak-concept queries.
    """
    retrieval = request.app.state.retrieval
    if retrieval is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graf wiedzy nie jest dostępny. Przetwórz najpierw dokumenty.",
        )
    settings: AppSettings = request.app.state.settings
    return QuizService(
        gateway=request.app.state.gateway,
        retrieval=retrieval,
        quiz_sessions=request.app.state.quiz_session_store,
        study_progress=study_progress,
        interaction_store=interaction_store,
        settings=_build_processing_settings(settings),
        quiz_generator=request.app.state.quiz_generator,
        quiz_evaluator=request.app.state.quiz_evaluator,
        event_publisher=event_publisher,
        quiz_ttl_seconds=settings.quiz_session_ttl_seconds,
    )


def get_flashcard_service(
    artifact_repo: Annotated[object, Depends(get_artifact_repo)],
    study_progress: Annotated[object, Depends(get_study_progress)],
) -> FlashcardService:
    """Build a FlashcardService scoped to the current request."""
    return FlashcardService(
        artifact_repo=artifact_repo,
        study_progress=study_progress,
    )


def get_chat_service(
    request: Request,
    interaction_store: Annotated[object, Depends(get_interaction_store)],
) -> ChatService:
    """Build a ChatService scoped to the current request.

    The shared :class:`_InMemorySessionCache` from ``app.state`` is injected so
    sessions created in one request survive to the next on the same worker.
    Raises HTTP 503 when the graph retrieval adapter is unavailable.
    """
    retrieval = request.app.state.retrieval
    if retrieval is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graf wiedzy nie jest dostępny. Przetwórz najpierw dokumenty.",
        )
    settings: AppSettings = request.app.state.settings
    return ChatService(
        gateway=request.app.state.gateway,
        retrieval=retrieval,
        interaction_store=interaction_store,
        redis_client=request.app.state.redis_client,
        system_with_context=request.app.state.chat_system_with_context,
        system_no_context=request.app.state.chat_system_no_context,
        session_ttl_seconds=settings.quiz_session_ttl_seconds,
        memory_cache=request.app.state.chat_memory_cache,
    )


def get_search_service(
    request: Request,
    interaction_store: Annotated[object, Depends(get_interaction_store)],
) -> SearchService:
    """Build a SearchService scoped to the current request.

    Raises HTTP 503 when the graph retrieval adapter is unavailable.
    """
    retrieval = request.app.state.retrieval
    if retrieval is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graf wiedzy nie jest dostępny. Przetwórz najpierw dokumenty.",
        )
    return SearchService(
        retrieval=retrieval,
        gateway=request.app.state.gateway,
        interaction_store=interaction_store,
    )
