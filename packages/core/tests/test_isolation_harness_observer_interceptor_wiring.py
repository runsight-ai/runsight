"""Subprocess harness observer interceptor wiring behavior."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from isolation_harness_helpers import (
    _make_context_envelope,
    _make_result_envelope,
    _patch_harness_subprocess_result,
)
from runsight_core.isolation import (
    ResultEnvelope,
)


class TestHarnessObserverInterceptorWiring:
    """SubprocessHarness registers ObserverInterceptor in IPC registry."""

    @pytest.mark.asyncio
    async def test_run_registers_observer_interceptor_for_ipc_trace_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module
        from runsight_core.yaml.schema import BlockLimitsDef

        workflow_budget = BudgetSession(
            scope_name="workflow:harness-observer-parent",
            cost_cap_usd=5.0,
            token_cap=5_000,
            on_exceed="fail",
        )
        active_token = _active_budget.set(workflow_budget)
        captured: dict[str, Any] = {
            "observer_inits": 0,
            "final_engine_context": None,
        }

        class FakeObserverInterceptor:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured["observer_inits"] += 1

            async def on_request(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                engine_context["trace_id"] = "observer-trace"
                engine_context["span_id"] = "observer-span"
                return engine_context

            async def on_response(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

            async def on_stream_chunk(
                self, action: str, chunk: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

        class FakeIPCServer:
            def __init__(
                self,
                *,
                sock,
                handlers: dict[str, Any],
                registry=None,
                grant_token=None,
            ) -> None:
                self._registry = registry
                captured["registry"] = registry

            async def serve(self) -> None:
                if self._registry is not None:
                    request_ctx = await self._registry.run_on_request(
                        "llm_call",
                        {"model": "gpt-4o-mini"},
                        {"trace.parent_id": "observer-parent-span"},
                    )
                    final_ctx = await self._registry.run_on_response(
                        "llm_call",
                        {"cost_usd": 0.01, "total_tokens": 11},
                        request_ctx,
                    )
                    captured["final_engine_context"] = final_ctx
                await asyncio.sleep(0)

            async def shutdown(self) -> None:
                return None

        monkeypatch.setattr(
            harness_module, "ObserverInterceptor", FakeObserverInterceptor, raising=False
        )
        monkeypatch.setattr(harness_module, "IPCServer", FakeIPCServer)
        _patch_harness_subprocess_result(
            monkeypatch,
            harness_module,
            _make_result_envelope(block_id="observed-linear-block", output="ok"),
        )

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))

        envelope = _make_context_envelope(block_id="observed-linear-block", block_type="linear")
        envelope.block_config = {
            "block_id": "observed-linear-block",
            "block_type": "linear",
            "limits": BlockLimitsDef(cost_cap_usd=1.0, token_cap=200).model_dump(),
        }

        try:
            result = await harness.run(envelope)
        finally:
            _active_budget.reset(active_token)

        assert isinstance(result, ResultEnvelope)
        assert captured["registry"] is not None
        assert captured["observer_inits"] >= 1
        assert captured["final_engine_context"]["trace.parent_id"] == "observer-parent-span"
        assert captured["final_engine_context"]["trace_id"] == "observer-trace"
        assert captured["final_engine_context"]["span_id"] == "observer-span"
