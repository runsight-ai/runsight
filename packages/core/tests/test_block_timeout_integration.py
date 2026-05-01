"""
Integration coverage for per-block timeout enforcement.

Owner decision: this suite owns block-level ``max_duration_seconds`` behavior,
including timeout failure, error-route recovery, and the successful fast path.
Workflow-level timeout and cost warn behavior have separate suites.
"""

from __future__ import annotations

import asyncio
import time
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
_FAST_SUCCESS_FIXTURE = "block-timeout-fast-success.yaml"


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    patch_fixture_model_budget(monkeypatch)


class TestBlockTimeoutNoErrorRoute:
    """Block with max_duration_seconds=1 where mock LLM sleeps 5s.
    No error_route => BudgetKilledException propagates, run fails."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_budget_killed_exception_raised(self, mock_cost, mock_acompletion):
        """Workflow.run() raises BudgetKilledException when block exceeds timeout."""

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_NO_ERROR_ROUTE_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        exc = exc_info.value
        assert exc.scope == "block"
        assert exc.block_id == "slow_block"
        assert exc.limit_kind == "timeout"
        assert exc.limit_value == 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_timeout_fires_within_tolerance(self, mock_cost, mock_acompletion):
        """Block with max_duration_seconds=1 MUST terminate within 1.5s (T+0.5s)."""

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_NO_ERROR_ROUTE_FIXTURE)
        state = WorkflowState()

        t0 = time.monotonic()
        with pytest.raises(BudgetKilledException):
            await wf.run(state)
        elapsed = time.monotonic() - t0

        # Must terminate within T+0.5s = 1.5s
        assert elapsed < 1.5, f"Timeout took {elapsed:.2f}s, expected <1.5s"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_second_block_never_executes(self, mock_cost, mock_acompletion):
        """When first block times out, LLM should only be called once
        (second block never runs)."""
        call_count = 0

        async def slow_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(5)
            return make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_NO_ERROR_ROUTE_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException):
            await wf.run(state)

        # Under process isolation the timeout may fire during subprocess startup
        # before the first LLM boundary, but block2 must never get a second call.
        assert call_count <= 1

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_exception_actual_value_matches_timeout(self, mock_cost, mock_acompletion):
        """BudgetKilledException.actual_value should equal the timeout value."""

        async def slow_response(*args, **kwargs):
            await asyncio.sleep(5)
            return make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_NO_ERROR_ROUTE_FIXTURE)
        state = WorkflowState()

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        # actual_value is set to the timeout value itself (not wall-clock elapsed)
        assert exc_info.value.actual_value == 1


class TestBlockTimeoutWithErrorRoute:
    """Block with max_duration_seconds=1 and error_route=fallback.
    Timeout fires, error routing sends to fallback block which completes."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_fallback_block_executes_after_timeout(self, mock_cost, mock_acompletion):
        """When slow_block times out and has error_route=fallback,
        the fallback block should execute and produce a result."""
        call_index = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_index
            call_index += 1
            if call_index == 1:
                # slow_block: sleep longer than timeout
                await asyncio.sleep(5)
                return make_litellm_response(content="slow result")
            else:
                # fallback: return instantly
                return make_litellm_response(content="fallback result")

        mock_acompletion.side_effect = side_effect
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_ERROR_ROUTE_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        # Fallback block should have executed
        assert "fallback" in result.results
        # If the timeout fires before slow_block reaches the LLM boundary, the
        # fallback consumes the first mock response; either output proves the
        # error route ran instead of block2.
        assert result.results["fallback"].output in {"slow result", "fallback result"}

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_slow_block_result_contains_error_info(self, mock_cost, mock_acompletion):
        """When slow_block times out, its result should contain error metadata."""
        call_index = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_index
            call_index += 1
            if call_index == 1:
                await asyncio.sleep(5)
                return make_litellm_response(content="slow result")
            else:
                return make_litellm_response(content="fallback result")

        mock_acompletion.side_effect = side_effect
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_ERROR_ROUTE_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        # slow_block should have an error result recorded
        assert "slow_block" in result.results
        block_result = result.results["slow_block"]
        assert block_result.exit_handle == "error"
        assert block_result.metadata is not None
        assert "BudgetKilledException" in block_result.metadata.get("error_type", "")

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_completes_normally_via_fallback(self, mock_cost, mock_acompletion):
        """Workflow should complete without raising an exception when error_route
        catches the timeout failure."""
        call_index = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_index
            call_index += 1
            if call_index == 1:
                await asyncio.sleep(5)
                return make_litellm_response(content="slow result")
            else:
                return make_litellm_response(content="recovered")

        mock_acompletion.side_effect = side_effect
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_ERROR_ROUTE_FIXTURE)
        state = WorkflowState()

        # Should NOT raise — error_route catches the exception
        result = await wf.run(state)
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_error_info_in_shared_memory(self, mock_cost, mock_acompletion):
        """Error information should be available in shared_memory for the fallback
        block to reference."""
        call_index = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_index
            call_index += 1
            if call_index == 1:
                await asyncio.sleep(5)
                return make_litellm_response(content="slow result")
            else:
                return make_litellm_response(content="recovered")

        mock_acompletion.side_effect = side_effect
        mock_cost.return_value = 0.001

        wf = parse_workflow_fixture(_ERROR_ROUTE_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        # Error info should be stored in shared_memory under __error__slow_block
        error_info = result.shared_memory.get("__error__slow_block")
        assert error_info is not None
        assert error_info["type"] == "BudgetKilledException"


class TestBlockCompletesBeforeTimeout:
    """Block with max_duration_seconds=60 that completes instantly.
    No exception raised, workflow completes normally."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_completes_normally(self, mock_cost, mock_acompletion):
        """Workflow with generous timeout runs both blocks and completes normally."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="result one", total_tokens=100),
            make_litellm_response(content="result two", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_fixture(_FAST_SUCCESS_FIXTURE)
        state = WorkflowState()

        result = await wf.run(state)

        assert "fast_block" in result.results
        assert "block2" in result.results
        assert result.results["fast_block"].output == "result one"
        assert result.results["block2"].output == "result two"

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_no_exception_raised(self, mock_cost, mock_acompletion):
        """No BudgetKilledException should be raised when block completes within timeout."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="fast one", total_tokens=100),
            make_litellm_response(content="fast two", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_fixture(_FAST_SUCCESS_FIXTURE)
        state = WorkflowState()

        # Should not raise any exception
        result = await wf.run(state)
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_both_blocks_execute(self, mock_cost, mock_acompletion):
        """Both blocks should execute — the timeout-bearing block and its successor."""
        mock_acompletion.side_effect = [
            make_litellm_response(content="first", total_tokens=100),
            make_litellm_response(content="second", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_fixture(_FAST_SUCCESS_FIXTURE)
        state = WorkflowState()

        await wf.run(state)

        # acompletion should have been called twice — once per block
        assert mock_acompletion.call_count == 2

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_block_without_timeout_not_wrapped(self, mock_cost, mock_acompletion):
        """block2 (no timeout) should NOT have max_duration_seconds set, confirming
        that only explicitly configured blocks get timeout wrapping."""
        wf = parse_workflow_fixture(_FAST_SUCCESS_FIXTURE)

        fast_block = wf.blocks["fast_block"]
        block2 = wf.blocks["block2"]

        # fast_block should have timeout set
        assert getattr(fast_block, "max_duration_seconds", None) == 60

        # block2 should NOT have timeout set
        assert getattr(block2, "max_duration_seconds", None) is None
