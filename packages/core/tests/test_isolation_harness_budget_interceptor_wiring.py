"""Subprocess harness budget interceptor wiring behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path
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

pytestmark = pytest.mark.real_subprocess_isolation


class TestHarnessBudgetInterceptorWiring:
    """SubprocessHarness wires BudgetInterceptor into IPC execution."""

    @pytest.mark.asyncio
    async def test_run_builds_block_budget_interceptor_with_workflow_parent(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ):
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module
        from runsight_core.yaml.schema import BlockLimitsDef

        workflow_budget = BudgetSession(
            scope_name="workflow:harness-budget-parent",
            cost_cap_usd=5.0,
            token_cap=5_000,
            on_exceed="fail",
        )
        active_token = _active_budget.set(workflow_budget)
        captured: dict[str, Any] = {}

        class FakeBudgetInterceptor:
            def __init__(self, *args: Any, **kwargs: Any):
                session = kwargs.get("session") or kwargs.get("budget_session")
                if session is None:
                    for arg in args:
                        if isinstance(arg, BudgetSession):
                            session = arg
                            break
                captured["child_session"] = session

            async def on_request(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

            async def on_response(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                session = captured.get("child_session")
                if session is not None:
                    session.accrue(
                        cost_usd=float(payload.get("cost_usd", 0.0)),
                        tokens=int(payload.get("total_tokens", 0)),
                    )
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
                captured["registry"] = registry
                captured["grant_token"] = grant_token
                self._registry = registry

            async def serve(self) -> None:
                if self._registry is not None:
                    request_ctx = await self._registry.run_on_request(
                        "llm_call",
                        {"model": "gpt-4o-mini"},
                        {},
                    )
                    await self._registry.run_on_response(
                        "llm_call",
                        {"cost_usd": 0.10, "total_tokens": 15},
                        request_ctx,
                    )
                await asyncio.sleep(0)

            async def shutdown(self) -> None:
                return None

        monkeypatch.setattr(
            harness_module, "BudgetInterceptor", FakeBudgetInterceptor, raising=False
        )
        monkeypatch.setattr(harness_module, "IPCServer", FakeIPCServer)
        _patch_harness_subprocess_result(
            monkeypatch,
            harness_module,
            _make_result_envelope(block_id="budgeted-linear-block", output="ok"),
        )

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))

        envelope = _make_context_envelope(block_id="budgeted-linear-block", block_type="linear")
        block_limits = BlockLimitsDef(cost_cap_usd=1.0, token_cap=200)
        envelope.block_config = {
            "block_id": "budgeted-linear-block",
            "block_type": "linear",
            "limits": block_limits.model_dump(),
        }

        try:
            result = await harness.run(envelope)
        finally:
            _active_budget.reset(active_token)

        assert isinstance(result, ResultEnvelope)
        assert captured.get("registry") is not None
        assert captured.get("child_session") is not None
        assert captured["child_session"] is not workflow_budget
        assert captured["child_session"].parent is workflow_budget
        assert captured["child_session"].cost_cap_usd == pytest.approx(1.0)
        assert workflow_budget.cost_usd == pytest.approx(0.10)
        assert workflow_budget.tokens == 15

    @pytest.mark.asyncio
    async def test_run_registers_workflow_budget_when_block_has_no_own_limits(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation import SubprocessHarness
        from runsight_core.isolation import harness as harness_module

        workflow_budget = BudgetSession(
            scope_name="workflow:harness-budget-parent",
            cost_cap_usd=5.0,
            token_cap=5_000,
            on_exceed="fail",
        )
        active_token = _active_budget.set(workflow_budget)
        captured: dict[str, Any] = {}

        class FakeBudgetInterceptor:
            def __init__(self, *args: Any, **kwargs: Any):
                captured["session"] = kwargs.get("session") or kwargs.get("budget_session")

            async def on_request(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                return engine_context

            async def on_response(
                self, action: str, payload: dict[str, Any], engine_context: dict[str, Any]
            ) -> dict[str, Any]:
                session = captured.get("session")
                if session is not None:
                    session.accrue(
                        cost_usd=float(payload.get("cost_usd", 0.0)),
                        tokens=int(payload.get("total_tokens", 0)),
                    )
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

            async def serve(self) -> None:
                if self._registry is not None:
                    request_ctx = await self._registry.run_on_request(
                        "llm_call",
                        {"model": "gpt-4o-mini"},
                        {},
                    )
                    await self._registry.run_on_response(
                        "llm_call",
                        {"cost_usd": 0.10, "total_tokens": 15},
                        request_ctx,
                    )
                await asyncio.sleep(0)

            async def shutdown(self) -> None:
                return None

        monkeypatch.setattr(
            harness_module, "BudgetInterceptor", FakeBudgetInterceptor, raising=False
        )
        monkeypatch.setattr(harness_module, "IPCServer", FakeIPCServer)
        _patch_harness_subprocess_result(
            monkeypatch,
            harness_module,
            _make_result_envelope(block_id="budgeted-linear-block", output="ok"),
        )

        harness = SubprocessHarness(api_keys={"openai": "dummy-openai-key"})
        monkeypatch.setattr(harness, "_monitor_heartbeats", AsyncMock(return_value=False))
        envelope = _make_context_envelope(block_id="budgeted-linear-block", block_type="linear")

        try:
            result = await harness.run(envelope)
        finally:
            _active_budget.reset(active_token)

        assert isinstance(result, ResultEnvelope)
        assert captured["session"] is workflow_budget
        assert workflow_budget.cost_usd == pytest.approx(0.10)
        assert workflow_budget.tokens == 15
