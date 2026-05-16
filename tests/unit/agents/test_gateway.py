"""Unit tests for Phase 3 — AI Gateway."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from mindforge.domain.models import CompletionResult, DeadlineProfile, DeadlineExceeded
from mindforge.infrastructure.ai.infra.gateway import (
    LiteLLMGateway,
    _CircuitBreaker,
    _CBState,
)
from mindforge.infrastructure.tracing.stdout_adapter import StdoutTracingAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    model: str = "openai/gpt-4o-mini", content: str = "hello"
) -> CompletionResult:
    return CompletionResult(
        content=content,
        input_tokens=10,
        output_tokens=5,
        model=model,
        provider="openai",
        latency_ms=50.0,
        cost_usd=0.0001,
    )


def _mock_litellm_response(
    content: str, model: str = "openai/gpt-4o-mini"
) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.model = model
    response.usage = MagicMock()
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 5
    response._hidden_params = {"response_cost": 0.0001}
    return response


# ---------------------------------------------------------------------------
# 3.5.1 — Model name resolution
# ---------------------------------------------------------------------------


class TestModelResolution:
    def test_logical_name_resolved(self):
        gw = LiteLLMGateway(
            model_map={"small": "openai/gpt-4o-mini", "large": "openai/gpt-4o"}
        )
        assert gw._resolve_model("small") == "openai/gpt-4o-mini"
        assert gw._resolve_model("large") == "openai/gpt-4o"

    def test_unknown_name_passed_through(self):
        gw = LiteLLMGateway(model_map={"small": "openai/gpt-4o-mini"})
        assert (
            gw._resolve_model("anthropic/claude-3-haiku-20240307")
            == "anthropic/claude-3-haiku-20240307"
        )

    def test_empty_map_passthrough(self):
        gw = LiteLLMGateway()
        assert gw._resolve_model("openai/gpt-4o") == "openai/gpt-4o"

    def test_provider_extraction(self):
        assert LiteLLMGateway._extract_provider("openai/gpt-4o") == "openai"
        assert (
            LiteLLMGateway._extract_provider("anthropic/claude-3-haiku-20240307")
            == "anthropic"
        )
        assert LiteLLMGateway._extract_provider("gpt-4o") == "unknown"


# ---------------------------------------------------------------------------
# 3.5.2 — CompletionResult construction
# ---------------------------------------------------------------------------


class TestCompletionResult:
    @pytest.mark.asyncio
    async def test_completion_result_all_fields(self):
        gw = LiteLLMGateway(
            model_map={"small": "openai/gpt-4o-mini"},
            max_retries=0,
        )
        mock_resp = _mock_litellm_response("Answer text")

        with patch(
            "mindforge.infrastructure.ai.infra.gateway.acompletion",
            new=AsyncMock(return_value=mock_resp),
            create=True,
        ):
            result = await gw.complete(
                model="small",
                messages=[{"role": "user", "content": "Q?"}],
            )

        assert result.content == "Answer text"
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.model == "openai/gpt-4o-mini"
        assert result.provider == "openai"
        assert result.cost_usd >= 0.0
        assert result.latency_ms >= 0.0
        assert result.total_tokens == 15

    @pytest.mark.asyncio
    async def test_completion_result_records_actual_model_on_fallback(self):
        """The actually-used fallback model must appear in CompletionResult.model."""
        primary_model = "openai/gpt-4o"
        fallback_model = "anthropic/claude-3-haiku-20240307"
        fallback_resp = _mock_litellm_response("Fallback answer", model=fallback_model)

        async def fake_completion(**kwargs):
            if kwargs["model"] == primary_model:
                raise OSError("primary unavailable")
            return fallback_resp

        gw = LiteLLMGateway(
            default_model=primary_model,
            fallback_models=[fallback_model],
            max_retries=0,
        )
        with patch(
            "mindforge.infrastructure.ai.infra.gateway.acompletion",
            side_effect=fake_completion,
            create=True,
        ):
            result = await gw.complete(
                model=primary_model,
                messages=[{"role": "user", "content": "Q?"}],
            )

        assert result.model == fallback_model
        assert result.provider == "anthropic"


# ---------------------------------------------------------------------------
# 3.5.3 — Deadline enforcement
# ---------------------------------------------------------------------------


class TestDeadlineEnforcement:
    def test_deadline_budget_interactive(self):
        gw = LiteLLMGateway()
        budget = gw._deadline_budget_ms(DeadlineProfile.INTERACTIVE)
        assert budget == 15_000.0

    def test_deadline_budget_batch(self):
        gw = LiteLLMGateway()
        budget = gw._deadline_budget_ms(DeadlineProfile.BATCH)
        assert budget == 180_000.0

    def test_deadline_budget_background(self):
        gw = LiteLLMGateway()
        budget = gw._deadline_budget_ms(DeadlineProfile.BACKGROUND)
        assert budget == 300_000.0

    @pytest.mark.asyncio
    async def test_deadline_exceeded_raised_when_over_budget(self):
        """If wall-clock time exceeds deadline after completion, raise DeadlineExceeded."""
        import time as _time

        mock_resp = _mock_litellm_response("slow answer")

        async def slow_completion(**kwargs):
            return mock_resp

        gw = LiteLLMGateway(max_retries=0)

        original_monotonic = _time.monotonic
        call_count = 0

        def patched_monotonic():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 0.0
            # Return a time far past the INTERACTIVE budget of 15s
            return 20.0

        with patch(
            "mindforge.infrastructure.ai.infra.gateway.time.monotonic",
            side_effect=patched_monotonic,
        ):
            with patch(
                "mindforge.infrastructure.ai.infra.gateway.acompletion",
                new=AsyncMock(return_value=mock_resp),
                create=True,
            ):
                with pytest.raises(DeadlineExceeded) as exc_info:
                    await gw.complete(
                        model="openai/gpt-4o-mini",
                        messages=[{"role": "user", "content": "Q?"}],
                        deadline=DeadlineProfile.INTERACTIVE,
                    )

        assert exc_info.value.deadline_profile in (
            "INTERACTIVE",
            DeadlineProfile.INTERACTIVE,
        )
        assert exc_info.value.elapsed_ms > 15_000.0


# ---------------------------------------------------------------------------
# 3.5.4 — Circuit breaker state transitions
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = _CircuitBreaker()
        assert cb._state == _CBState.CLOSED
        assert not cb.is_open

    def test_opens_after_threshold_failures(self):
        cb = _CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
            assert not cb.is_open
        cb.record_failure()  # 5th failure
        assert cb._state == _CBState.OPEN
        assert cb.is_open

    def test_success_resets_failures(self):
        cb = _CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._consecutive_failures == 0
        assert cb._state == _CBState.CLOSED

    def test_half_open_after_cooldown(self):
        import time as _time

        cb = _CircuitBreaker(failure_threshold=1, cooldown_s=60.0)
        cb.record_failure()
        assert cb.is_open

        # Simulate 61 seconds passing
        with patch(
            "mindforge.infrastructure.ai.infra.gateway.time.monotonic",
            return_value=cb._opened_at + 61.0,
        ):
            assert not cb.is_open  # transitions to HALF_OPEN → not open
            assert cb._state == _CBState.HALF_OPEN

    def test_circuit_open_skips_model(self):
        """When a circuit is open, the gateway should skip that model."""
        cb = _CircuitBreaker(failure_threshold=1)
        cb.record_failure()
        assert cb.is_open

    @pytest.mark.asyncio
    async def test_gateway_skips_open_circuit(self):
        """Gateway skips primary model if its circuit is open and uses fallback."""
        primary = "openai/gpt-4o"
        fallback = "anthropic/claude-3-haiku-20240307"

        fallback_resp = _mock_litellm_response("fallback!", model=fallback)

        async def fake_completion(**kwargs):
            if kwargs["model"] == primary:
                raise AssertionError("primary should have been skipped")
            return fallback_resp

        gw = LiteLLMGateway(
            default_model=primary, fallback_models=[fallback], max_retries=0
        )
        # Open primary circuit
        gw._cb_for(primary)
        for _ in range(5):
            gw._cb_for(primary).record_failure()

        with patch(
            "mindforge.infrastructure.ai.infra.gateway.acompletion",
            side_effect=fake_completion,
            create=True,
        ):
            result = await gw.complete(
                model=primary, messages=[{"role": "user", "content": "Q?"}]
            )

        assert result.model == fallback


# ---------------------------------------------------------------------------
# 3.5.5 — Fallback chain
# ---------------------------------------------------------------------------


class TestFallbackChain:
    @pytest.mark.asyncio
    async def test_fallback_invoked_on_primary_failure(self):
        primary = "openai/gpt-4o"
        fallback = "anthropic/claude-3-haiku-20240307"
        fallback_resp = _mock_litellm_response("from fallback", model=fallback)

        async def fake_completion(**kwargs):
            if kwargs["model"] == primary:
                raise OSError("primary down")
            return fallback_resp

        gw = LiteLLMGateway(fallback_models=[fallback], max_retries=0)
        with patch(
            "mindforge.infrastructure.ai.infra.gateway.acompletion",
            side_effect=fake_completion,
            create=True,
        ):
            result = await gw.complete(
                model=primary, messages=[{"role": "user", "content": "Q?"}]
            )

        assert result.content == "from fallback"
        assert result.model == fallback

    @pytest.mark.asyncio
    async def test_all_fallbacks_fail_raises(self):
        primary = "openai/gpt-4o"
        fallback = "anthropic/claude-3-haiku-20240307"

        gw = LiteLLMGateway(fallback_models=[fallback], max_retries=0)
        with patch(
            "mindforge.infrastructure.ai.infra.gateway.acompletion",
            side_effect=OSError("all down"),
            create=True,
        ):
            with pytest.raises(OSError):
                await gw.complete(
                    model=primary, messages=[{"role": "user", "content": "Q?"}]
                )

    @pytest.mark.asyncio
    async def test_second_fallback_used_when_first_also_fails(self):
        primary = "openai/gpt-4o"
        fb1 = "anthropic/claude-3-haiku-20240307"
        fb2 = "openai/gpt-4o-mini"
        final_resp = _mock_litellm_response("from fb2", model=fb2)

        async def fake_completion(**kwargs):
            if kwargs["model"] in (primary, fb1):
                raise OSError("unavailable")
            return final_resp

        gw = LiteLLMGateway(fallback_models=[fb1, fb2], max_retries=0)
        with patch(
            "mindforge.infrastructure.ai.infra.gateway.acompletion",
            side_effect=fake_completion,
            create=True,
        ):
            result = await gw.complete(
                model=primary, messages=[{"role": "user", "content": "Q?"}]
            )

        assert result.model == fb2


# ---------------------------------------------------------------------------
# StubAIGateway tests
# ---------------------------------------------------------------------------


class TestStubAIGateway:
    @pytest.mark.asyncio
    async def test_stub_returns_configured_response(self, mock_gateway):
        expected = _make_result(content="configured answer")
        mock_gateway.set_response("small", expected)
        result = await mock_gateway.complete(
            model="small", messages=[{"role": "user", "content": "?"}]
        )
        assert result.content == "configured answer"

    @pytest.mark.asyncio
    async def test_stub_tracks_calls(self, mock_gateway):
        await mock_gateway.complete(
            model="small", messages=[{"role": "user", "content": "Q"}]
        )
        await mock_gateway.complete(
            model="large", messages=[{"role": "user", "content": "Q2"}]
        )
        assert len(mock_gateway.calls) == 2
        assert mock_gateway.calls[0]["model"] == "small"

    @pytest.mark.asyncio
    async def test_stub_wildcard_response(self, mock_gateway):
        expected = _make_result(content="catch-all")
        mock_gateway.set_response("*", expected)
        result = await mock_gateway.complete(model="any-model", messages=[])
        assert result.content == "catch-all"

    @pytest.mark.asyncio
    async def test_stub_default_response(self, mock_gateway):
        result = await mock_gateway.complete(
            model="fallback", messages=[{"role": "user", "content": "hello"}]
        )
        assert "[stub]" in result.content

    @pytest.mark.asyncio
    async def test_stub_embed_returns_vectors(self, mock_gateway):
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        mock_gateway.set_embed_response("*", vectors)
        result = await mock_gateway.embed(model="embedding", texts=["a", "b"])
        assert result == vectors

    @pytest.mark.asyncio
    async def test_stub_embed_default_zero_vectors(self, mock_gateway):
        result = await mock_gateway.embed(model="embedding", texts=["a", "b", "c"])
        assert len(result) == 3
        assert all(v == [0.0, 0.0, 0.0, 0.0] for v in result)


# ---------------------------------------------------------------------------
# StdoutTracingAdapter smoke test
# ---------------------------------------------------------------------------


class TestStdoutTracingAdapter:
    def test_start_trace_returns_uuid(self):
        adapter = StdoutTracingAdapter()
        tid = adapter.start_trace("test")
        from uuid import UUID

        assert isinstance(tid, UUID)

    def test_record_completion_does_not_raise(self):
        adapter = StdoutTracingAdapter()
        tid = adapter.start_trace("test")
        adapter.record_completion(
            trace_id=tid,
            model="openai/gpt-4o-mini",
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.001,
            latency_ms=42.0,
            provider="openai",
        )
        adapter.end_trace(tid)
