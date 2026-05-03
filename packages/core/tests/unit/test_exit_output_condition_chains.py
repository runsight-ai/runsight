"""Exit-port output-condition chain integration coverage."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import block_output_from_state
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow

# ---------------------------------------------------------------------------
# Helpers: mock runner and blocks
# ---------------------------------------------------------------------------


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock(
        return_value=ExecutionResult(
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    return runner


def _make_soul(soul_id: str = "test_soul") -> Soul:
    return Soul(id=soul_id, kind="soul", name="Test", role="Test", system_prompt="Test prompt")


class StubBlock(BaseBlock):
    """Minimal block that stores a fixed output."""

    def __init__(self, block_id: str, output: str = "done"):
        super().__init__(block_id)
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self._output),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class ExitHandleBlock(BaseBlock):
    """Block whose execute() stores a BlockResult with a specific exit_handle."""

    def __init__(self, block_id: str, exit_handle: str, output: str = "done"):
        super().__init__(block_id)
        self._exit_handle = exit_handle
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=self._output,
                        exit_handle=self._exit_handle,
                    ),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class JsonOutputBlock(BaseBlock):
    """Block that stores a JSON-string BlockResult (no exit_handle set)."""

    def __init__(self, block_id: str, data: dict):
        super().__init__(block_id)
        self._data = data

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=json.dumps(self._data)),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


def _fresh_state(**kwargs) -> WorkflowState:
    return WorkflowState(**kwargs)


class TestOutputConditionsExitHandleChainIntegration:
    """Code/linear block output_conditions feed conditional routing."""

    @pytest.mark.asyncio
    async def test_output_conditions_match_routes_correctly(self):
        """Block produces JSON output -> output_conditions match a case ->
        exit_handle set -> conditional_transition routes to correct block."""
        from runsight_core.conditions.engine import Case, Condition, ConditionGroup

        wf = Workflow(name="oc_chain")

        producer = JsonOutputBlock("producer", {"status": "approved", "score": 85})
        on_approved = StubBlock("on_approved", output="approved_path")
        on_rejected = StubBlock("on_rejected", output="rejected_path")

        wf.add_block(producer)
        wf.add_block(on_approved)
        wf.add_block(on_rejected)
        wf.set_entry("producer")

        # output_conditions: if status == "approved" -> case_id "approved"
        cases = [
            Case(
                case_id="approved",
                condition_group=ConditionGroup(
                    conditions=[
                        Condition(eval_key="status", operator="equals", value="approved"),
                    ],
                    combinator="and",
                ),
            ),
        ]
        wf.set_output_conditions("producer", cases, default="rejected")

        wf.add_conditional_transition(
            "producer",
            {"approved": "on_approved", "rejected": "on_rejected", "default": "on_rejected"},
        )
        wf.add_transition("on_approved", None)
        wf.add_transition("on_rejected", None)

        final = await wf.run(_fresh_state())

        # output_conditions should match "approved" and set exit_handle
        assert final.results["producer"].exit_handle == "approved"
        assert "on_approved" in final.results, (
            "Should route to on_approved via output_conditions -> exit_handle -> conditional_transition"
        )
        assert "on_rejected" not in final.results

    @pytest.mark.asyncio
    async def test_output_conditions_no_match_uses_default(self):
        """Block output doesn't match any case -> default decision used ->
        exit_handle set to default -> routes to fallback block."""
        from runsight_core.conditions.engine import Case, Condition, ConditionGroup

        wf = Workflow(name="oc_default_chain")

        producer = JsonOutputBlock("producer", {"status": "pending", "score": 50})
        on_approved = StubBlock("on_approved", output="approved_path")
        on_fallback = StubBlock("on_fallback", output="fallback_path")

        wf.add_block(producer)
        wf.add_block(on_approved)
        wf.add_block(on_fallback)
        wf.set_entry("producer")

        # output_conditions: if status == "approved" -> case_id "approved"
        # No case for "pending" -> falls to default="rejected"
        cases = [
            Case(
                case_id="approved",
                condition_group=ConditionGroup(
                    conditions=[
                        Condition(eval_key="status", operator="equals", value="approved"),
                    ],
                    combinator="and",
                ),
            ),
        ]
        wf.set_output_conditions("producer", cases, default="rejected")

        wf.add_conditional_transition(
            "producer",
            {"approved": "on_approved", "rejected": "on_fallback", "default": "on_fallback"},
        )
        wf.add_transition("on_approved", None)
        wf.add_transition("on_fallback", None)

        final = await wf.run(_fresh_state())

        assert final.results["producer"].exit_handle == "rejected"
        assert "on_fallback" in final.results
        assert "on_approved" not in final.results

    @pytest.mark.asyncio
    async def test_block_with_exit_handle_and_output_conditions(self):
        """When a block already has exit_handle set, output_conditions preserve it."""
        from runsight_core.conditions.engine import Case, Condition, ConditionGroup

        wf = Workflow(name="exit_handle_priority")

        # This block has exit_handle already set
        producer = ExitHandleBlock(
            "producer", exit_handle="custom_exit", output='{"status": "approved"}'
        )
        on_custom = StubBlock("on_custom", output="custom_path")
        on_approved = StubBlock("on_approved", output="approved_path")

        wf.add_block(producer)
        wf.add_block(on_custom)
        wf.add_block(on_approved)
        wf.set_entry("producer")

        # Even though output_conditions would match "approved",
        # the pre-set exit_handle="custom_exit" should take priority
        cases = [
            Case(
                case_id="approved",
                condition_group=ConditionGroup(
                    conditions=[
                        Condition(eval_key="status", operator="equals", value="approved"),
                    ],
                    combinator="and",
                ),
            ),
        ]
        wf.set_output_conditions("producer", cases, default="default")

        wf.add_conditional_transition(
            "producer",
            {
                "custom_exit": "on_custom",
                "approved": "on_approved",
                "default": "on_approved",
            },
        )
        wf.add_transition("on_custom", None)
        wf.add_transition("on_approved", None)

        final = await wf.run(_fresh_state())

        assert final.results["producer"].exit_handle == "custom_exit"
        assert "on_custom" in final.results, (
            "exit_handle should take priority over output_conditions"
        )
        assert "on_approved" not in final.results


# ==============================================================================
# Validation catches invalid exit configurations
# ==============================================================================
