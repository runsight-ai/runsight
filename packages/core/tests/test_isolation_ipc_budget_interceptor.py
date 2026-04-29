"""ISO-002 IPC budget interceptor tests."""

from __future__ import annotations

import asyncio
import socket
from pathlib import Path
from typing import Any

import pytest
from isolation_ipc_helpers import (
    _make_budget_interceptor,
    _make_grant_token,
    _send_raw_authenticated_request_and_collect_frames,
)


class TestBudgetInterceptorContract:
    """RUN-810: BudgetInterceptor budget checks, accrual, and IPC short-circuit behavior."""

    @pytest.mark.asyncio
    async def test_on_response_accrues_cost_and_updates_remaining_budget_context(self):
        from runsight_core.budget_enforcement import BudgetSession
        from runsight_core.isolation import interceptors as interceptors_module

        budget_session = BudgetSession(
            scope_name="block:run810",
            cost_cap_usd=0.50,
            token_cap=100,
            on_exceed="fail",
        )
        interceptor = _make_budget_interceptor(
            interceptors_module,
            session=budget_session,
            block_id="run810-block",
        )

        engine_context: dict[str, Any] = {}
        engine_context = await interceptor.on_request(
            "llm_call", {"model": "gpt-4o-mini"}, engine_context
        )
        engine_context = await interceptor.on_response(
            "llm_call",
            {"cost_usd": 0.10, "total_tokens": 12},
            engine_context,
        )

        assert budget_session.cost_usd == pytest.approx(0.10)
        assert budget_session.tokens == 12
        assert engine_context["budget_remaining_usd"] == pytest.approx(0.40)
        assert engine_context["budget_remaining_tokens"] == 88

    @pytest.mark.asyncio
    async def test_on_response_over_cap_reports_negative_remaining_then_next_request_kills(self):
        from runsight_core.budget_enforcement import BudgetKilledException, BudgetSession
        from runsight_core.isolation import interceptors as interceptors_module

        budget_session = BudgetSession(
            scope_name="block:run810-over-response",
            cost_cap_usd=0.04,
            token_cap=100,
            on_exceed="fail",
        )
        interceptor = _make_budget_interceptor(
            interceptors_module,
            session=budget_session,
            block_id="run810-over-response",
        )

        engine_context: dict[str, Any] = {}
        engine_context = await interceptor.on_request(
            "llm_call", {"model": "gpt-4o-mini"}, engine_context
        )
        engine_context = await interceptor.on_response(
            "llm_call",
            {"cost_usd": 0.05, "total_tokens": 12},
            engine_context,
        )

        assert budget_session.cost_usd == pytest.approx(0.05)
        assert engine_context["budget_remaining_usd"] == pytest.approx(-0.01)
        with pytest.raises(BudgetKilledException):
            await interceptor.on_request("llm_call", {"model": "gpt-4o-mini"}, engine_context)

    @pytest.mark.asyncio
    async def test_on_stream_chunk_accrues_partial_tokens_incrementally(self):
        from runsight_core.budget_enforcement import BudgetSession
        from runsight_core.isolation import interceptors as interceptors_module

        budget_session = BudgetSession(
            scope_name="block:run810-stream",
            cost_cap_usd=5.0,
            token_cap=100,
            on_exceed="fail",
        )
        interceptor = _make_budget_interceptor(
            interceptors_module,
            session=budget_session,
            block_id="run810-stream",
        )

        engine_context: dict[str, Any] = {}
        engine_context = await interceptor.on_request(
            "llm_call", {"model": "gpt-4o-mini"}, engine_context
        )
        engine_context = await interceptor.on_stream_chunk(
            "llm_call",
            {"total_tokens": 3, "tokens": 3},
            engine_context,
        )
        engine_context = await interceptor.on_stream_chunk(
            "llm_call",
            {"total_tokens": 4, "tokens": 4},
            engine_context,
        )

        assert budget_session.tokens == 7
        assert engine_context["budget_remaining_tokens"] == 93

    @pytest.mark.asyncio
    async def test_streaming_terminal_on_response_does_not_double_count_chunk_usage(self):
        from runsight_core.budget_enforcement import BudgetSession
        from runsight_core.isolation import interceptors as interceptors_module

        budget_session = BudgetSession(
            scope_name="block:run810-stream-final",
            cost_cap_usd=1.0,
            token_cap=100,
            on_exceed="fail",
        )
        interceptor = _make_budget_interceptor(
            interceptors_module,
            session=budget_session,
            block_id="run810-stream-final",
        )

        engine_context: dict[str, Any] = {}
        engine_context = await interceptor.on_request(
            "llm_call", {"model": "gpt-4o-mini"}, engine_context
        )
        engine_context = await interceptor.on_stream_chunk(
            "llm_call",
            {"cost_usd": 0.03, "total_tokens": 7},
            engine_context,
        )
        engine_context = await interceptor.on_response("llm_call", {}, engine_context)

        assert budget_session.cost_usd == pytest.approx(0.03)
        assert budget_session.tokens == 7
        assert engine_context["budget_remaining_usd"] == pytest.approx(0.97)

    @pytest.mark.asyncio
    async def test_stream_chunk_over_cap_reports_negative_remaining_then_next_request_kills(self):
        from runsight_core.budget_enforcement import BudgetKilledException, BudgetSession
        from runsight_core.isolation import interceptors as interceptors_module

        budget_session = BudgetSession(
            scope_name="block:run810-stream-over",
            cost_cap_usd=5.0,
            token_cap=5,
            on_exceed="fail",
        )
        interceptor = _make_budget_interceptor(
            interceptors_module,
            session=budget_session,
            block_id="run810-stream-over",
        )

        engine_context: dict[str, Any] = {}
        engine_context = await interceptor.on_request(
            "llm_call", {"model": "gpt-4o-mini"}, engine_context
        )
        engine_context = await interceptor.on_stream_chunk(
            "llm_call",
            {"total_tokens": 7, "tokens": 7},
            engine_context,
        )

        assert budget_session.tokens == 7
        assert engine_context["budget_remaining_tokens"] == -2
        with pytest.raises(BudgetKilledException):
            await interceptor.on_request("llm_call", {"model": "gpt-4o-mini"}, engine_context)

    @pytest.mark.asyncio
    async def test_budget_interceptor_kills_request_before_handler_when_budget_exhausted(
        self, tmp_path: Path
    ):
        from runsight_core.budget_enforcement import BudgetSession
        from runsight_core.isolation import IPCServer
        from runsight_core.isolation import interceptors as interceptors_module

        InterceptorRegistry = getattr(interceptors_module, "InterceptorRegistry", None)
        assert InterceptorRegistry is not None
        registry = InterceptorRegistry()

        budget_session = BudgetSession(
            scope_name="block:run810-exhausted",
            cost_cap_usd=0.01,
            token_cap=100,
            on_exceed="fail",
        )
        budget_session.accrue(cost_usd=0.02, tokens=0)
        registry.register(
            _make_budget_interceptor(
                interceptors_module,
                session=budget_session,
                block_id="run810-exhausted",
            )
        )

        sock_path = tmp_path / "run810-exhausted.sock"
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(str(sock_path))
        server_sock.listen(1)

        handler_called = False

        async def should_not_run(_payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal handler_called
            handler_called = True
            return {"status": "unexpected"}

        grant_token = _make_grant_token(block_id="run810-exhausted")
        server = IPCServer(
            sock=server_sock,
            handlers={"simple": should_not_run},
            registry=registry,
            grant_token=grant_token,
        )
        server_task = asyncio.create_task(server.serve())

        try:
            frames = await _send_raw_authenticated_request_and_collect_frames(
                sock_path,
                grant_token,
                {
                    "id": "req-810-kill-1",
                    "action": "simple",
                    "payload": {"value": "blocked"},
                },
            )
            assert handler_called is False
            assert len(frames) == 1
            assert frames[0]["done"] is True
            assert frames[0]["payload"]["error_type"] == "BudgetKilledException"
            assert frames[0]["payload"]["block_id"] == "run810-exhausted"
            assert frames[0]["payload"]["limit_kind"] == "cost_usd"
            assert "budget" in (frames[0]["error"] or "").lower()
        finally:
            await server.shutdown()
            server_task.cancel()
            server_sock.close()
            sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# RUN-393: InterceptorRegistry chain-of-responsibility for IPC messages
# ---------------------------------------------------------------------------
