"""TDD Red: API should log unexpected 500 errors with request context."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from _pytest.logging import LogCaptureFixture
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient


def test_unhandled_exception_is_logged_with_request_context(
    caplog: LogCaptureFixture,
) -> None:
    """Unhandled exceptions should produce a structured ERROR log entry."""
    from mindforge.api.main import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.middleware("http")
    async def _inject_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = request.headers.get("X-Request-ID", "-")
        return await call_next(request)

    @app.get("/boom")
    async def _boom() -> dict[str, str]:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        with caplog.at_level(logging.ERROR):
            response = client.get("/boom", headers={"X-Request-ID": "req-123"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Wewnętrzny błąd serwera."}
    assert any(
        "Unhandled exception during GET /boom [request_id=req-123]" in rec.getMessage()
        for rec in caplog.records
    ), "Expected centralized 500 log with request context and traceback."
