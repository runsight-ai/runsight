"""Smoke coverage for the real workspace isolation boundary."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.blocks.linear import LinearBlock
from runsight_core.budget_enforcement import BudgetSession, _active_budget
from runsight_core.isolation import IsolatedBlockWrapper, UnixLocalHarness, UnixSocketIPCTransport
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState
from runsight_core.yaml.schema import BlockLimitsDef

pytestmark = pytest.mark.real_subprocess_isolation


def _soul(soul_id: str = "soul-integration") -> Soul:
    return Soul(
        id=soul_id,
        kind="soul",
        name="Tester",
        role="Tester",
        system_prompt="You are an integration test soul.",
        model_name="gpt-4o-mini",
        provider="openai",
        temperature=0.0,
    )


def _patch_llm_stream(
    monkeypatch: pytest.MonkeyPatch,
    responder: Callable[[dict[str, Any], int], dict[str, Any]],
) -> dict[str, Any]:
    import runsight_core.isolation.handlers as handlers_module

    captured: dict[str, Any] = {"api_keys": None, "payloads": []}

    def fake_make_llm_call_handler(api_keys: dict[str, str]):
        captured["api_keys"] = dict(api_keys)

        def _handler(payload: dict[str, Any]):
            captured["payloads"].append(payload)
            call_number = len(captured["payloads"])
            response = responder(payload, call_number)

            async def _stream():
                yield response

            return _stream()

        return _handler

    monkeypatch.setattr(handlers_module, "make_llm_call_handler", fake_make_llm_call_handler)
    return captured


@pytest.mark.asyncio
async def test_linear_wrapper_real_subprocess_routes_llm_and_reconciles_budget(
    monkeypatch: pytest.MonkeyPatch,
):
    captured = _patch_llm_stream(
        monkeypatch,
        lambda _payload, _call_number: {
            "content": "linear subprocess output",
            "cost_usd": 0.03,
            "prompt_tokens": 4,
            "completion_tokens": 8,
            "total_tokens": 12,
            "tool_calls": [],
            "finish_reason": "stop",
        },
    )
    workflow_budget = BudgetSession(
        scope_name="workflow:isolated-linear-block",
        cost_cap_usd=1.0,
        token_cap=1000,
        on_exceed="fail",
    )
    token = _active_budget.set(workflow_budget)
    soul = _soul("linear-soul")
    inner = LinearBlock("isolated-linear-block", soul, MagicMock())
    inner.limits = BlockLimitsDef(cost_cap_usd=1.0, token_cap=100)
    harness = UnixLocalHarness(ipc_transport=UnixSocketIPCTransport(socket_dir=Path("/tmp")))
    wrapper = IsolatedBlockWrapper(
        "isolated-linear-block",
        inner,
        harness=harness,
        api_keys={"openai": "sk-test-openai"},
    )
    state = WorkflowState()

    try:
        ctx = build_block_context(wrapper, state)
        output = await wrapper.execute(ctx)
        next_state = apply_block_output(state, wrapper.block_id, output)
    finally:
        _active_budget.reset(token)

    assert captured["api_keys"] == {"openai": "sk-test-openai"}
    assert captured["payloads"][0]["model"] == "gpt-4o-mini"
    assert next_state.results["isolated-linear-block"].output == "linear subprocess output"
    assert next_state.results["isolated-linear-block"].exit_handle == "done"
    assert next_state.total_cost_usd == pytest.approx(0.03)
    assert next_state.total_tokens == 12
    assert workflow_budget.cost_usd == pytest.approx(0.03)
    assert workflow_budget.tokens == 12
