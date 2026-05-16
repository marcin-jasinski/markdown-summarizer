"""Documents router — upload, list, get, reprocess."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from mindforge.api.deps import (
    get_current_user,
    get_db_session,
    get_doc_repo,
    get_ingestion,
    get_kb_repo,
)
from mindforge.api.schemas import DocumentResponse, ReprocessRequest, UploadResponse
from mindforge.application.ingestion import (
    DuplicateContentError,
    IngestionService,
    PendingTaskLimitError,
    UploadRejectedError,
)
from mindforge.domain.events import DocumentIngested
from mindforge.domain.models import DocumentStatus, UploadSource, User
from mindforge.infrastructure.events.outbox_publisher import OutboxEventPublisher
from mindforge.infrastructure.persistence.artifact_repo import (
    PostgresArtifactRepository,
)
from mindforge.infrastructure.persistence.document_repo import (
    PostgresDocumentRepository,
)
from mindforge.infrastructure.persistence.pipeline_task_repo import (
    PostgresPipelineTaskRepository,
)
from mindforge.infrastructure.security.upload_sanitizer import UploadSanitizer

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-bases/{kb_id}/documents", tags=["documents"])


def _to_response(doc) -> DocumentResponse:
    return DocumentResponse(
        document_id=doc.document_id,
        knowledge_base_id=doc.knowledge_base_id,
        lesson_id=doc.lesson_id,
        title=doc.title,
        source_filename=doc.source_filename,
        mime_type=doc.mime_type,
        status=doc.status.value,
        upload_source=doc.upload_source.value,
        revision=doc.revision,
        is_active=doc.is_active,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=UploadResponse)
async def upload_document(
    kb_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> UploadResponse:
    # Verify KB ownership
    async with request.app.state.session_factory() as _kb_session:
        kb_repo = get_kb_repo(request, _kb_session)
        kb = await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    raw_bytes = await file.read()
    filename = file.filename or "upload"

    # Build a per-request ingestion service with a fresh session so that the
    # entire ingestion flow runs inside one transaction that the service controls.
    async with request.app.state.session_factory() as session:
        settings = request.app.state.settings
        svc = IngestionService(
            doc_repo=PostgresDocumentRepository(session),
            sanitizer=UploadSanitizer(
                global_max_bytes=settings.max_document_size_mb * 1024 * 1024
            ),
            parsers=request.app.state.parser_registry,
            task_store=PostgresPipelineTaskRepository(session),
            event_publisher=OutboxEventPublisher(session),
        )

        try:
            result = await svc.ingest(
                raw_bytes=raw_bytes,
                filename=filename,
                knowledge_base_id=kb_id,
                upload_source=UploadSource.API,
                uploaded_by=current_user.user_id,
            )
            await session.commit()
        except UploadRejectedError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except DuplicateContentError:
            raise HTTPException(
                status_code=409, detail="Dokument o tej samej treści już istnieje."
            )
        except PendingTaskLimitError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except Exception as exc:
            log.exception("Ingestion failed for %s", filename)
            raise HTTPException(
                status_code=500, detail="Błąd podczas importu dokumentu."
            )

    return UploadResponse(
        document_id=result.document_id,
        task_id=result.task_id,
        lesson_id=result.lesson_id,
        revision=result.revision,
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    kb_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
    offset: int = 0,
) -> list[DocumentResponse]:
    async with request.app.state.session_factory() as _kb_session:
        kb_repo = get_kb_repo(request, _kb_session)
        if await kb_repo.get_by_id(kb_id, owner_id=current_user.user_id) is None:
            raise HTTPException(status_code=404, detail="Baza wiedzy nie istnieje.")

    async with request.app.state.session_factory() as session:
        repo = PostgresDocumentRepository(session)
        docs = await repo.list_by_knowledge_base(kb_id, limit=limit, offset=offset)
    return [_to_response(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    kb_id: UUID,
    document_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocumentResponse:
    async with request.app.state.session_factory() as session:
        repo = PostgresDocumentRepository(session)
        doc = await repo.get_by_id(document_id)
    if doc is None or doc.knowledge_base_id != kb_id:
        raise HTTPException(status_code=404, detail="Dokument nie istnieje.")
    return _to_response(doc)


@router.post("/{document_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(
    kb_id: UUID,
    document_id: UUID,
    request: Request,
    payload: ReprocessRequest,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Enqueue a re-run of the processing pipeline for an existing document."""
    async with request.app.state.session_factory() as session:
        doc_repo = PostgresDocumentRepository(session)
        doc = await doc_repo.get_by_id(document_id)
        if doc is None or doc.knowledge_base_id != kb_id:
            raise HTTPException(status_code=404, detail="Dokument nie istnieje.")

        task_repo = PostgresPipelineTaskRepository(session)
        task_id = await task_repo.create_task(document_id)

        publisher = OutboxEventPublisher(session)
        await publisher.publish_in_tx(
            DocumentIngested(
                document_id=document_id,
                knowledge_base_id=kb_id,
                lesson_id=doc.lesson_id,
                upload_source=doc.upload_source.value,
                content_sha256=doc.content_hash.sha256,
                uploaded_by=doc.uploaded_by,
                timestamp=datetime.now(timezone.utc),
            ),
            session,
        )
        await session.commit()

    return {"task_id": str(task_id), "detail": "Przetwarzanie ponownie zakolejkowane."}
