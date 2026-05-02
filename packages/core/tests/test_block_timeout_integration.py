"""
Smoke coverage for parsed workflow block timeout wiring.

Detailed timeout precision, successful fast paths, and error-route metadata are
owned by the timeout enforcement and workflow error-routing suites. This file
keeps only the parsed YAML -> Workflow.run() -> block timeout integration paths.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.state import WorkflowState
from workflow_limit_helpers import (
    make_litellm_response,
    parse_workflow_fixture,
    patch_fixture_model_budget,
)

_NO_ERROR_ROUTE_FIXTURE = "block-timeout-no-error-route.yaml"
_ERROR_ROUTE_FIXTURE = "block-timeout-with-error-route.yaml"


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    patch_fixture_model_budget(monkeypatch)


@pytest.mark.asyncio
@patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
@patch("runsight_core.llm.client.completion_cost")
async def test_parsed_workflow_raises_block_timeout_without_error_route(
    mock_cost, mock_acompletion
):
    async def slow_response(*args, **kwargs):
        await asyncio.sleep(2)
        return make_litellm_response(content="slow result")

    mock_acompletion.side_effect = slow_response
    mock_cost.return_value = 0.001

    wf = parse_workflow_fixture(_NO_ERROR_ROUTE_FIXTURE)

    with pytest.raises(BudgetKilledException) as exc_info:
        await wf.run(WorkflowState())

    exc = exc_info.value
    assert exc.scope == "block"
    assert exc.block_id == "slow_block"
    assert exc.limit_kind == "timeout"
    assert exc.limit_value == 1


@pytest.mark.asyncio
@patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
@patch("runsight_core.llm.client.completion_cost")
async def test_parsed_workflow_routes_timed_out_block_to_fallback(mock_cost, mock_acompletion):
    call_index = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            await asyncio.sleep(2)
            return make_litellm_response(content="slow result")
        return make_litellm_response(content="fallback result")

    mock_acompletion.side_effect = side_effect
    mock_cost.return_value = 0.001

    wf = parse_workflow_fixture(_ERROR_ROUTE_FIXTURE)
    result = await wf.run(WorkflowState())

    assert result.results["slow_block"].exit_handle == "error"
    assert "fallback" in result.results
    assert result.results["fallback"].output in {"slow result", "fallback result"}
    assert result.shared_memory["__error__slow_block"]["type"] == "BudgetKilledException"
