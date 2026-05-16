"""
Stdout tracing adapter — early observability stub.

Logs every AI completion to stdout using structured logging.
Replaced at composition-root level by ``LangfuseAdapter`` (Phase 16)
when ``LANGFUSE_PUBLIC_KEY`` is configured.  No code changes needed
in the gateway when switching adapters.

Fulfils the same ``TracingAdapter`` protocol that Phase 16 will implement.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID, uuid4

log = logging.getLogger(__name__)


class TracingAdapter:
    """Protocol-compatible tracing adapter.

    Implementations: ``StdoutTracingAdapter`` (this module),
    ``LangfuseAdapter`` (Phase 16).
    """

    def start_trace(
        self,
        name: str,
        *,
        trace_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        raise NotImplementedError

    def record_completion(
        self,
        *,
        trace_id: UUID,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: float,
        provider: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError

    def end_trace(self, trace_id: UUID, *, error: str | None = None) -> None:
        raise NotImplementedError


class StdoutTracingAdapter(TracingAdapter):
    """Logs completions to stdout via the standard :mod:`logging` framework.

    Used as the default tracer when ``LANGFUSE_PUBLIC_KEY`` is absent.
    """

    def start_trace(
        self,
        name: str,
        *,
        trace_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UUID:
        tid = trace_id or uuid4()
        log.debug(
            "trace_start",
            extra={
                "event": "trace_start",
                "trace_id": str(tid),
                "name": name,
                **(metadata or {}),
            },
        )
        return tid

    def record_completion(
        self,
        *,
        trace_id: UUID,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        latency_ms: float,
        provider: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "event": "ai_completion",
            "trace_id": str(trace_id),
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost_usd": cost_usd,
            "latency_ms": round(latency_ms, 2),
        }
        if metadata:
            payload.update(metadata)
        log.info(json.dumps(payload))

    def end_trace(self, trace_id: UUID, *, error: str | None = None) -> None:
        payload: dict[str, Any] = {
            "event": "trace_end",
            "trace_id": str(trace_id),
        }
        if error:
            payload["error"] = error
        log.debug(json.dumps(payload))
