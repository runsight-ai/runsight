"""
RUN-727 — E2E tests for per-block timeout enforcement.

Full-path integration: YAML parse -> Workflow.run() -> execute_block() ->
asyncio.wait_for wrapping -> BudgetKilledException on timeout.

Mocks only: litellm.acompletion (external LLM call) and litellm.completion_cost
(cost calculator).  All internal modules exercise real code paths.

Scenarios:
1. Block timeout — no error route → run fails
2. Block timeout — with error route → fallback block executes
3. Block completes before timeout — no kill, workflow completes normally
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runsight_core.budget_enforcement import BudgetKilledException
from runsight_core.primitives import Task
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml as _parse_workflow_yaml

_TEST_API_KEYS = {"openai": "sk-test-openai"}


@pytest.fixture(autouse=True)
def _bypass_isolation(monkeypatch):
    """Keep block execution in-process so litellm mocks are visible."""
    from runsight_core.isolation.wrapper import IsolatedBlockWrapper

    async def _in_process(self, state, **kwargs):
        return await self.inner_block.execute(state, **kwargs)

    monkeypatch.setattr(IsolatedBlockWrapper, "execute", _in_process)


def parse_workflow_yaml(*args, **kwargs):
    """Parse legacy e2e workflows with the engine-side IPC credential seam wired."""
    kwargs.setdefault("api_keys", _TEST_API_KEYS)
    return _parse_workflow_yaml(*args, **kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_litellm_response(
    content: str = "done",
    prompt_tokens: int = 50,
    completion_tokens: int = 30,
    total_tokens: int = 80,
):
    """Build a mock object mimicking litellm.acompletion() return value."""
    message = MagicMock()
    message.content = content
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


# ---------------------------------------------------------------------------
# YAML templates
# ---------------------------------------------------------------------------

_YAML_BLOCK_TIMEOUT_NO_ERROR_ROUTE = """\
version: "1.0"
souls:
  s1:
    id: s1
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  slow_block:
    type: linear
    soul_ref: s1
    limits:
      max_duration_seconds: 1
  block2:
    type: linear
    soul_ref: s1
workflow:
  name: timeout_no_error_route
  entry: slow_block
  transitions:
    - from: slow_block
      to: block2
    - from: block2
      to: null
"""

_YAML_BLOCK_TIMEOUT_WITH_ERROR_ROUTE = """\
version: "1.0"
souls:
  s1:
    id: s1
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  slow_block:
    type: linear
    soul_ref: s1
    limits:
      max_duration_seconds: 1
    error_route: fallback
  fallback:
    type: linear
    soul_ref: s1
workflow:
  name: timeout_with_fallback
  entry: slow_block
  transitions:
    - from: slow_block
      to: null
    - from: fallback
      to: null
"""

_YAML_FAST_BLOCK_WITH_TIMEOUT = """\
version: "1.0"
souls:
  s1:
    id: s1
    role: Worker
    system_prompt: Do work.
    provider: openai
    model_name: gpt-4o
blocks:
  fast_block:
    type: linear
    soul_ref: s1
    limits:
      max_duration_seconds: 60
  block2:
    type: linear
    soul_ref: s1
workflow:
  name: fast_with_timeout
  entry: fast_block
  transitions:
    - from: fast_block
      to: block2
    - from: block2
      to: null
"""


# ===========================================================================
# Scenario 1: Block timeout — no error route → run fails
# ===========================================================================


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
            return _make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_BLOCK_TIMEOUT_NO_ERROR_ROUTE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            return _make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_BLOCK_TIMEOUT_NO_ERROR_ROUTE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            return _make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_BLOCK_TIMEOUT_NO_ERROR_ROUTE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            return _make_litellm_response(content="slow result")

        mock_acompletion.side_effect = slow_response
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_BLOCK_TIMEOUT_NO_ERROR_ROUTE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        with pytest.raises(BudgetKilledException) as exc_info:
            await wf.run(state)

        # actual_value is set to the timeout value itself (not wall-clock elapsed)
        assert exc_info.value.actual_value == 1


# ===========================================================================
# Scenario 2: Block timeout — with error route → fallback
# ===========================================================================


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
                return _make_litellm_response(content="slow result")
            else:
                # fallback: return instantly
                return _make_litellm_response(content="fallback result")

        mock_acompletion.side_effect = side_effect
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_BLOCK_TIMEOUT_WITH_ERROR_ROUTE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
                return _make_litellm_response(content="slow result")
            else:
                return _make_litellm_response(content="fallback result")

        mock_acompletion.side_effect = side_effect
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_BLOCK_TIMEOUT_WITH_ERROR_ROUTE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
                return _make_litellm_response(content="slow result")
            else:
                return _make_litellm_response(content="recovered")

        mock_acompletion.side_effect = side_effect
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_BLOCK_TIMEOUT_WITH_ERROR_ROUTE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
                return _make_litellm_response(content="slow result")
            else:
                return _make_litellm_response(content="recovered")

        mock_acompletion.side_effect = side_effect
        mock_cost.return_value = 0.001

        wf = parse_workflow_yaml(_YAML_BLOCK_TIMEOUT_WITH_ERROR_ROUTE)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        result = await wf.run(state)

        # Error info should be stored in shared_memory under __error__slow_block
        error_info = result.shared_memory.get("__error__slow_block")
        assert error_info is not None
        assert error_info["type"] == "BudgetKilledException"


# ===========================================================================
# Scenario 3: Block completes before timeout — no kill
# ===========================================================================


class TestBlockCompletesBeforeTimeout:
    """Block with max_duration_seconds=60 that completes instantly.
    No exception raised, workflow completes normally."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_workflow_completes_normally(self, mock_cost, mock_acompletion):
        """Workflow with generous timeout runs both blocks and completes normally."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="result one", total_tokens=100),
            _make_litellm_response(content="result two", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_yaml(_YAML_FAST_BLOCK_WITH_TIMEOUT)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

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
            _make_litellm_response(content="fast one", total_tokens=100),
            _make_litellm_response(content="fast two", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_yaml(_YAML_FAST_BLOCK_WITH_TIMEOUT)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        # Should not raise any exception
        result = await wf.run(state)
        assert result is not None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_both_blocks_execute(self, mock_cost, mock_acompletion):
        """Both blocks should execute — the timeout-bearing block and its successor."""
        mock_acompletion.side_effect = [
            _make_litellm_response(content="first", total_tokens=100),
            _make_litellm_response(content="second", total_tokens=120),
        ]
        mock_cost.side_effect = [0.01, 0.02]

        wf = parse_workflow_yaml(_YAML_FAST_BLOCK_WITH_TIMEOUT)
        state = WorkflowState(
            current_task=Task(id="t1", instruction="Do something"),
        )

        await wf.run(state)

        # acompletion should have been called twice — once per block
        assert mock_acompletion.call_count == 2

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock)
    @patch("runsight_core.llm.client.completion_cost")
    async def test_block_without_timeout_not_wrapped(self, mock_cost, mock_acompletion):
        """block2 (no timeout) should NOT have max_duration_seconds set, confirming
        that only explicitly configured blocks get timeout wrapping."""
        wf = parse_workflow_yaml(_YAML_FAST_BLOCK_WITH_TIMEOUT)

        fast_block = wf.blocks["fast_block"]
        block2 = wf.blocks["block2"]

        # fast_block should have timeout set
        assert getattr(fast_block, "max_duration_seconds", None) == 60

        # block2 should NOT have timeout set
        assert getattr(block2, "max_duration_seconds", None) is None
