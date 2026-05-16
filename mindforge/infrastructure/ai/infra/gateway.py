"""
LiteLLM-backed AI Gateway adapter.

Responsibilities:
- Resolve logical model names via model_map
- Enforce deadline profiles (INTERACTIVE=15s, BATCH=180s, BACKGROUND=300s)
- Retry with exponential backoff + jitter on transient failures
- Circuit breaker: open after 5 consecutive failures, half-open after 60s
- Provider fallback chain: on primary failure try each fallback in order
- Record the actually-used model in CompletionResult
- Respect Retry-After headers from rate-limited responses
- Emit traces via TracingAdapter (stdout or Langfuse)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

try:
    import litellm
    from litellm import acompletion
    from litellm.exceptions import (
        RateLimitError,
        ServiceUnavailableError,
        Timeout,
    )

    _LITELLM_AVAILABLE = True
except ImportError:
    _LITELLM_AVAILABLE = False

from mindforge.domain.models import CompletionResult, DeadlineProfile, DeadlineExceeded
from mindforge.infrastructure.ai.infra.embeddings import embed_batched
from mindforge.infrastructure.tracing.stdout_adapter import (
    StdoutTracingAdapter,
    TracingAdapter,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deadline budgets (seconds)
# ---------------------------------------------------------------------------

_DEADLINE_BUDGETS_S: dict[str, float] = {
    DeadlineProfile.INTERACTIVE: 15.0,
    DeadlineProfile.BATCH: 180.0,
    DeadlineProfile.BACKGROUND: 300.0,
}

# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------


class _CBState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class _CircuitBreaker:
    failure_threshold: int = 5
    cooldown_s: float = 60.0

    _state: _CBState = field(default=_CBState.CLOSED, init=False, repr=False)
    _consecutive_failures: int = field(default=0, init=False, repr=False)
    _opened_at: float | None = field(default=None, init=False, repr=False)

    @property
    def is_open(self) -> bool:
        if self._state == _CBState.OPEN:
            if (
                self._opened_at is not None
                and (time.monotonic() - self._opened_at) >= self.cooldown_s
            ):
                self._state = _CBState.HALF_OPEN
                log.info("circuit_breaker half_open")
                return False
            return True
        return False

    def record_success(self) -> None:
        self._consecutive_failures = 0
        if self._state != _CBState.CLOSED:
            log.info("circuit_breaker closed")
        self._state = _CBState.CLOSED
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._state == _CBState.HALF_OPEN or (
            self._consecutive_failures >= self.failure_threshold
            and self._state == _CBState.CLOSED
        ):
            self._state = _CBState.OPEN
            self._opened_at = time.monotonic()
            log.warning(
                "circuit_breaker opened after %d consecutive failures",
                self._consecutive_failures,
            )


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------


def _build_retryable() -> tuple[type[Exception], ...]:
    if not _LITELLM_AVAILABLE:
        return (OSError,)
    return (RateLimitError, ServiceUnavailableError, Timeout, OSError)


def _is_rate_limit_error(exc: Exception) -> bool:
    if not _LITELLM_AVAILABLE:
        return False
    return isinstance(exc, RateLimitError)


def _retry_after_seconds(exc: Exception) -> float | None:
    """Extract Retry-After value (seconds) from a rate-limit response, if present."""
    try:
        response = getattr(exc, "response", None)
        if response is None:
            return None
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            return float(retry_after)
    except Exception:
        pass
    return None


async def _with_retry(
    coro_factory,
    *,
    max_retries: int,
    base_delay_s: float = 1.0,
    max_delay_s: float = 60.0,
) -> Any:
    retryable = _build_retryable()
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except retryable as exc:
            last_exc = exc
            if attempt == max_retries:
                break

            # Respect Retry-After header if present
            wait = _retry_after_seconds(exc)
            if wait is None:
                # Exponential backoff with full jitter
                wait = min(
                    base_delay_s * (2**attempt) + random.uniform(0, 1), max_delay_s
                )

            log.warning(
                "LiteLLM transient error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1,
                max_retries + 1,
                wait,
                exc,
            )
            await asyncio.sleep(wait)

    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# LiteLLMGateway
# ---------------------------------------------------------------------------


class LiteLLMGateway:
    """``AIGateway`` implementation backed by LiteLLM.

    Accepts a ``model_map`` so callers use logical names like ``"small"``
    or ``"large"`` rather than provider strings.  Model resolution order:

    1. ``model_map[model]`` — logical name present in map
    2. ``model`` as-is — treat as a literal LiteLLM model string

    When the primary model fails (after retries), each fallback model is
    tried in order.  ``CompletionResult.model`` always reflects the model
    that actually succeeded.
    """

    def __init__(
        self,
        *,
        default_model: str = "openai/gpt-4o-mini",
        model_map: dict[str, str] | None = None,
        fallback_models: list[str] | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        tracer: TracingAdapter | None = None,
        api_key: str | None = None,
    ) -> None:
        self._default_model = default_model
        self._model_map: dict[str, str] = model_map or {}
        self._fallback_models: list[str] = fallback_models or []
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._tracer: TracingAdapter = tracer or StdoutTracingAdapter()
        self._circuit_breakers: dict[str, _CircuitBreaker] = {}
        self._api_key = api_key  # passed to acompletion for OpenRouter models

        if not _LITELLM_AVAILABLE:
            log.warning(
                "litellm is not installed — LiteLLMGateway will raise ImportError "
                "at call time.  Install it with: pip install litellm"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_model(self, model: str) -> str:
        return self._model_map.get(model, model)

    def _cb_for(self, model: str) -> _CircuitBreaker:
        if model not in self._circuit_breakers:
            self._circuit_breakers[model] = _CircuitBreaker()
        return self._circuit_breakers[model]

    def _deadline_budget_ms(self, deadline: DeadlineProfile) -> float:
        return (
            _DEADLINE_BUDGETS_S.get(
                str(deadline.value) if hasattr(deadline, "value") else str(deadline),
                30.0,
            )
            * 1000
        )

    def _deadline_timeout_s(self, deadline: DeadlineProfile) -> float:
        return _DEADLINE_BUDGETS_S.get(
            str(deadline.value) if hasattr(deadline, "value") else str(deadline), 30.0
        )

    @staticmethod
    def _extract_provider(model: str) -> str:
        """Extract provider prefix from a LiteLLM model string like ``openai/gpt-4o``."""
        if "/" in model:
            return model.split("/", 1)[0]
        return "unknown"

    @staticmethod
    def _extract_cost(response: Any) -> float:
        """Extract cost_usd from a LiteLLM response, returning 0.0 for local models."""
        try:
            cost = getattr(response, "_hidden_params", {}).get("response_cost")
            if cost is not None:
                return float(cost)
            # litellm.completion_cost may be available
            cost = litellm.completion_cost(completion_response=response)
            if cost is not None:
                return float(cost)
        except Exception:
            pass
        return 0.0

    async def _call_model(
        self,
        model: str,
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int | None,
        response_format: dict[str, Any] | None,
        timeout_s: float,
    ) -> tuple[str, int, int, float, str]:
        """Call LiteLLM and return (content, input_tokens, output_tokens, cost_usd, used_model)."""
        if not _LITELLM_AVAILABLE:
            raise ImportError("litellm is not installed")

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout_s,
            "num_retries": 0,  # we manage retries ourselves
        }
        if self._api_key is not None and model.startswith("openrouter/"):
            kwargs["api_key"] = self._api_key
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format

        response = await acompletion(**kwargs)

        content = response.choices[0].message.content or ""
        usage = response.usage
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost_usd = self._extract_cost(response)
        used_model = getattr(response, "model", model) or model

        return content, input_tokens, output_tokens, cost_usd, used_model

    # ------------------------------------------------------------------
    # Public interface (AIGateway protocol)
    # ------------------------------------------------------------------

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        deadline: DeadlineProfile = DeadlineProfile.INTERACTIVE,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> CompletionResult:
        resolved = self._resolve_model(model)
        budget_ms = self._deadline_budget_ms(deadline)
        timeout_s = self._deadline_timeout_s(deadline)

        # Cap per-call timeout to deadline budget
        call_timeout_s = min(self._timeout_seconds, timeout_s)

        trace_id: UUID | None = None
        try:
            trace_id = self._tracer.start_trace(
                "ai_complete",
                metadata={"model": resolved, "deadline": str(deadline)},
            )
        except Exception:
            pass

        wall_start = time.monotonic()

        # Build candidate list: primary + fallbacks
        candidates = [resolved] + [
            self._resolve_model(m) for m in self._fallback_models
        ]
        last_exc: Exception | None = None

        for candidate in candidates:
            cb = self._cb_for(candidate)
            if cb.is_open:
                log.info("circuit_breaker open for %r, skipping", candidate)
                continue

            try:
                content, in_tok, out_tok, cost, used = await _with_retry(
                    lambda m=candidate: self._call_model(
                        m,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                        timeout_s=call_timeout_s,
                    ),
                    max_retries=self._max_retries,
                )
                cb.record_success()

                elapsed_ms = (time.monotonic() - wall_start) * 1000
                if elapsed_ms > budget_ms:
                    raise DeadlineExceeded(deadline.value, elapsed_ms, budget_ms)

                provider = self._extract_provider(used)

                try:
                    self._tracer.record_completion(
                        trace_id=trace_id,  # type: ignore[arg-type]
                        model=used,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cost_usd=cost,
                        latency_ms=elapsed_ms,
                        provider=provider,
                    )
                    self._tracer.end_trace(trace_id)  # type: ignore[arg-type]
                except Exception:
                    pass

                return CompletionResult(
                    content=content,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    model=used,
                    provider=provider,
                    latency_ms=elapsed_ms,
                    cost_usd=cost,
                )

            except DeadlineExceeded:
                raise

            except Exception as exc:
                cb.record_failure()
                last_exc = exc
                log.warning(
                    "Model %r failed: %s — trying next fallback", candidate, exc
                )
                continue

        # All candidates exhausted
        try:
            if trace_id is not None:
                self._tracer.end_trace(trace_id, error=str(last_exc))
        except Exception:
            pass

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("All model candidates skipped (circuit breakers open)")

    async def embed(
        self,
        *,
        model: str,
        texts: list[str],
    ) -> list[list[float]]:
        """Delegate to ``embeddings.py``-style batched embedding.

        Kept on the gateway so that ``AIGateway`` protocol callers have a
        single object.  Heavy batching logic lives in
        ``mindforge/infrastructure/ai/embeddings.py``.
        """
        resolved = self._resolve_model(model)
        return await embed_batched(resolved, texts, timeout_s=self._timeout_seconds)
