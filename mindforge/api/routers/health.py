"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text

from mindforge.api.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Return service health — checks DB connectivity, optional Neo4j/Redis."""

    # Database
    db_status = "ok"
    try:
        engine = request.app.state.db_engine
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # Neo4j
    neo4j_status: str | None = None
    neo4j_ctx = getattr(request.app.state, "neo4j_context", None)
    if neo4j_ctx is not None:
        try:
            await neo4j_ctx.verify_connectivity()
            neo4j_status = "ok"
        except Exception:
            neo4j_status = "error"

    # Redis
    redis_status: str | None = None
    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client is not None:
        try:
            await redis_client.ping()
            redis_status = "ok"
        except Exception:
            redis_status = "error"

    overall = "ok" if db_status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        database=db_status,
        neo4j=neo4j_status,
        redis=redis_status,
    )
