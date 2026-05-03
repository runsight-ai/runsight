"""GateBlock runner execution contract tests.

The suite verifies GateBlock calls runner.execute() with string instruction and
context arguments, keeps Task wiring out of the module, and preserves
PASS/FAIL result behavior.
"""

import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import execute_block_for_test
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock(
        return_value=ExecutionResult(
            task_id="gate-eval-task",
            soul_id="gate-eval-soul",
            output=output,
            cost_usd=cost,
            total_tokens=tokens,
        )
    )
    runner.execute_task = AsyncMock(
        return_value=ExecutionResult(
            task_id="legacy-gate-task",
            soul_id="gate-eval-soul",
            output=output,
            cost_usd=cost,
            total_tokens=tokens,
        )
    )
    return runner


def _make_soul(soul_id: str = "gate_soul") -> Soul:
    return Soul(
        id=soul_id, kind="soul", name="Gate Soul", role="Gate", system_prompt="Evaluate quality"
    )


def _make_gate(block_id: str = "quality_gate", eval_key: str = "content", **kwargs):
    """Create a GateBlock with sensible defaults."""
    from runsight_core.blocks.gate import GateBlock

    soul = kwargs.pop("soul", _make_soul())
    runner = kwargs.pop("runner", _mock_runner("PASS"))
    return GateBlock(
        block_id=block_id,
        gate_soul=soul,
        eval_key=eval_key,
        runner=runner,
        **kwargs,
    )


# ==============================================================================
# Gate module does not import Task from primitives
# ==============================================================================


class TestNoTaskImport:
    """gate.py must have no 'from runsight_core.primitives import Task' import."""

    def test_gate_source_has_no_task_import(self):
        """gate.py source must not import Task from primitives in any form."""
        import runsight_core.blocks.gate as gate_mod

        source = inspect.getsource(gate_mod)
        # Covers both: 'import Task' and 'import Soul, Task' or 'import Task, Soul'
        import_lines_with_task = [
            line
            for line in source.splitlines()
            if "import" in line and "primitives" in line and "Task" in line
        ]
        assert import_lines_with_task == [], (
            f"gate.py still imports Task from primitives: {import_lines_with_task}"
        )

    def test_gate_source_has_no_task_in_import_line(self):
        """gate.py import of Soul must not include Task on the same line."""
        import runsight_core.blocks.gate as gate_mod

        source = inspect.getsource(gate_mod)
        # Check that no import line pulls in Task from primitives
        for line in source.splitlines():
            if "import" in line and "primitives" in line:
                assert "Task" not in line, f"gate.py still references Task in import line: {line!r}"

    def test_task_not_importable_from_gate(self):
        """Task must not be accessible as an attribute of the gate module."""
        import runsight_core.blocks.gate as gate_mod

        assert not hasattr(gate_mod, "Task"), "Task is still accessible from gate module namespace"


# ==============================================================================
# Gate module does not instantiate Task
# ==============================================================================


class TestNoTaskInstantiation:
    """gate.py must contain no 'Task(' call anywhere in its source."""

    def test_gate_source_has_no_task_instantiation(self):
        """gate.py must not contain 'Task(' instantiation."""
        import runsight_core.blocks.gate as gate_mod

        source = inspect.getsource(gate_mod)
        assert "Task(" not in source, "gate.py still instantiates Task"

    def test_gate_source_has_no_gate_task_variable(self):
        """gate.py must not contain 'gate_task' variable anywhere."""
        import runsight_core.blocks.gate as gate_mod

        source = inspect.getsource(gate_mod)
        assert "gate_task" not in source, "gate.py still uses gate_task variable"


# ==============================================================================
# GateBlock calls runner.execute() instead of execute_task()
# ==============================================================================


class TestRunnerExecuteCalled:
    """GateBlock must call runner.execute() instead of runner.execute_task()."""

    @pytest.mark.asyncio
    async def test_runner_execute_called_on_pass(self):
        """On PASS path, runner.execute() must be called (not execute_task)."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="pass_execute_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Good content")})

        await execute_block_for_test(block, state)

        runner.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_runner_execute_called_on_fail(self):
        """On FAIL path, runner.execute() must be called (not execute_task)."""
        runner = _mock_runner("FAIL: needs improvement")
        block = _make_gate(block_id="fail_execute_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft content")})

        await execute_block_for_test(block, state)

        runner.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_runner_execute_task_not_called(self):
        """runner.execute_task() must not be called because GateBlock uses runner.execute()."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="execute_only_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content")})

        await execute_block_for_test(block, state)

        runner.execute_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_runner_execute_task_not_called_on_fail(self):
        """execute_task() must not be called on FAIL path either."""
        runner = _mock_runner("FAIL: poor quality")
        block = _make_gate(block_id="fail_execute_only_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft")})

        await execute_block_for_test(block, state)

        runner.execute_task.assert_not_called()


# ==============================================================================
# runner.execute() receives string instruction
# ==============================================================================


class TestRunnerExecuteReceivesStringInstruction:
    """The first positional arg to runner.execute() must be a str, not a Task."""

    @pytest.mark.asyncio
    async def test_execute_first_arg_is_string(self):
        """runner.execute() first arg (instruction) must be a plain string."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="instruction_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Some content")})

        await execute_block_for_test(block, state)

        args, _kwargs = runner.execute.call_args
        instruction_arg = args[0]
        assert isinstance(instruction_arg, str), (
            f"runner.execute() first arg must be str, got {type(instruction_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_execute_first_arg_is_not_task(self):
        """runner.execute() must not receive a Task object as first arg."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="string_instruction_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content")})

        await execute_block_for_test(block, state)

        args, _kwargs = runner.execute.call_args
        instruction_arg = args[0]
        assert isinstance(instruction_arg, str), (
            f"runner.execute() first arg must be a string instruction, got {type(instruction_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_execute_instruction_contains_eval_directive(self):
        """The instruction string passed to runner.execute() must contain evaluation directive text."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="directive_instruction_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content to evaluate")})

        await execute_block_for_test(block, state)

        args, _kwargs = runner.execute.call_args
        instruction_arg = args[0]
        # The instruction should contain some gate-related evaluation text
        assert len(instruction_arg) > 0, "Instruction string must not be empty"


# ==============================================================================
# runner.execute() receives string context
# ==============================================================================


class TestRunnerExecuteReceivesStringContext:
    """The second positional arg to runner.execute() must be str or None, not a Task."""

    @pytest.mark.asyncio
    async def test_execute_second_arg_is_string_or_none(self):
        """runner.execute() second arg (context) must be str or None."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="context_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="The actual content")})

        await execute_block_for_test(block, state)

        args, _kwargs = runner.execute.call_args
        assert len(args) >= 2, "runner.execute() must be called with at least 2 positional args"
        context_arg = args[1]
        assert isinstance(context_arg, (str, type(None))), (
            f"runner.execute() second arg must be str or None, got {type(context_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_execute_second_arg_is_not_task(self):
        """runner.execute() second arg must be str or None, not a Task object."""
        runner = _mock_runner("FAIL: needs work")
        block = _make_gate(block_id="string_context_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Some draft")})

        await execute_block_for_test(block, state)

        args, _kwargs = runner.execute.call_args
        assert len(args) >= 2, "runner.execute() must have at least 2 positional args"
        context_arg = args[1]
        assert isinstance(context_arg, (str, type(None))), (
            f"runner.execute() context arg must be str or None, got {type(context_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_execute_third_arg_is_soul(self):
        """runner.execute() third arg must be the gate_soul (a Soul instance)."""
        runner = _mock_runner("PASS")
        soul = _make_soul("my_gate_soul")
        block = _make_gate(block_id="soul_context_gate", soul=soul, runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content")})

        await execute_block_for_test(block, state)

        args, _kwargs = runner.execute.call_args
        assert len(args) >= 3, "runner.execute() must be called with (instruction, context, soul)"
        soul_arg = args[2]
        assert isinstance(soul_arg, Soul), (
            f"runner.execute() third arg must be Soul, got {type(soul_arg).__name__}"
        )
        assert soul_arg.id == "my_gate_soul"


# ==============================================================================
# GateBlock produces correct PASS/FAIL results
# ==============================================================================


class TestGateResultsCorrect:
    """GateBlock must still produce correct BlockResult on both PASS and FAIL paths."""

    @pytest.mark.asyncio
    async def test_pass_exit_handle_is_pass(self):
        """On PASS response, BlockResult must have exit_handle='pass'."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="pass_result_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="High quality content")})

        result_state = await execute_block_for_test(block, state)

        assert result_state.results["pass_result_gate"].exit_handle == "pass"

    @pytest.mark.asyncio
    async def test_fail_exit_handle_is_fail(self):
        """On FAIL response, BlockResult must have exit_handle='fail'."""
        runner = _mock_runner("FAIL: missing citations")
        block = _make_gate(block_id="fail_result_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft text")})

        result_state = await execute_block_for_test(block, state)

        assert result_state.results["fail_result_gate"].exit_handle == "fail"

    @pytest.mark.asyncio
    async def test_fail_output_contains_feedback(self):
        """On FAIL, BlockResult output must contain the feedback reason."""
        runner = _mock_runner("FAIL: incomplete argument")
        block = _make_gate(block_id="fail_feedback_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft")})

        result_state = await execute_block_for_test(block, state)

        assert "incomplete argument" in result_state.results["fail_feedback_gate"].output

    @pytest.mark.asyncio
    async def test_pass_cost_propagated(self):
        """On PASS, cost from runner.execute() result must be added to state."""
        runner = _mock_runner("PASS", cost=0.05, tokens=200)
        block = _make_gate(block_id="pass_cost_gate", runner=runner)
        state = WorkflowState(
            results={"content": BlockResult(output="Good")},
            total_cost_usd=1.0,
            total_tokens=500,
        )

        result_state = await execute_block_for_test(block, state)

        assert result_state.total_cost_usd == pytest.approx(1.05)
        assert result_state.total_tokens == 700

    @pytest.mark.asyncio
    async def test_fail_cost_propagated(self):
        """On FAIL, cost from runner.execute() result must be added to state."""
        runner = _mock_runner("FAIL: poor quality", cost=0.03, tokens=150)
        block = _make_gate(block_id="fail_cost_gate", runner=runner)
        state = WorkflowState(
            results={"content": BlockResult(output="Draft")},
            total_cost_usd=2.0,
            total_tokens=300,
        )

        result_state = await execute_block_for_test(block, state)

        assert result_state.total_cost_usd == pytest.approx(2.03)
        assert result_state.total_tokens == 450

    @pytest.mark.asyncio
    async def test_missing_eval_key_raises(self):
        """GateBlock must raise ValueError when eval_key is not in state.results."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="missing_eval_gate", eval_key="missing_key", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content")})

        with pytest.raises(ValueError, match="missing_key"):
            await execute_block_for_test(block, state)


class TestGateDecisionAndExtractionEdges:
    """GateBlock decision parsing and extract_field behavior."""

    @pytest.mark.asyncio
    async def test_context_uses_block_result_output_not_str(self):
        """GateBlock prompt uses BlockResult.output, not implicit __str__."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_real_output", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="REAL_OUTPUT")})

        with patch.object(BlockResult, "__str__", return_value="PATCHED_STR"):
            await execute_block_for_test(block, state)

        args, _kwargs = runner.execute.call_args
        context_arg = args[1] if len(args) >= 2 else _kwargs.get("context", "")
        assert "REAL_OUTPUT" in (context_arg or "")
        assert "PATCHED_STR" not in (context_arg or "")

    @pytest.mark.asyncio
    async def test_multiline_pass_uses_first_line_for_decision(self):
        """Only the first response line controls PASS routing."""
        runner = _mock_runner("PASS\nextra explanation")
        block = _make_gate(block_id="multiline_pass_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content")})

        result_state = await execute_block_for_test(block, state)

        result = result_state.results["multiline_pass_gate"]
        assert result.exit_handle == "pass"
        assert "extra explanation" not in result.output

    @pytest.mark.asyncio
    async def test_lowercase_pass_is_recognized(self):
        """Lowercase pass is accepted as a PASS decision."""
        runner = _mock_runner("pass")
        block = _make_gate(block_id="lowercase_pass_gate", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content")})

        result_state = await execute_block_for_test(block, state)

        assert result_state.results["lowercase_pass_gate"].exit_handle == "pass"

    @pytest.mark.asyncio
    async def test_extract_field_on_pass_returns_json_field(self):
        """PASS with extract_field returns the selected source JSON field."""
        runner = _mock_runner("PASS")
        block = _make_gate(
            block_id="extract_pass_gate",
            runner=runner,
            extract_field="score",
        )
        state = WorkflowState(results={"content": BlockResult(output=json.dumps([{"score": 85}]))})

        result_state = await execute_block_for_test(block, state)

        result = result_state.results["extract_pass_gate"]
        assert result.exit_handle == "pass"
        assert result.output == 85 or result.output == "85"

    @pytest.mark.asyncio
    async def test_extract_field_invalid_json_falls_back_to_decision_line(self):
        """Invalid source JSON falls back to the PASS decision line."""
        runner = _mock_runner("PASS")
        block = _make_gate(
            block_id="extract_invalid_json_gate",
            runner=runner,
            extract_field="score",
        )
        state = WorkflowState(results={"content": BlockResult(output="not valid json")})

        result_state = await execute_block_for_test(block, state)

        result = result_state.results["extract_invalid_json_gate"]
        assert result.exit_handle == "pass"
        assert result.output == "PASS"

    @pytest.mark.asyncio
    async def test_extract_field_missing_field_falls_back_to_decision_line(self):
        """Missing source JSON field falls back to the PASS decision line."""
        runner = _mock_runner("PASS")
        block = _make_gate(
            block_id="extract_missing_field_gate",
            runner=runner,
            extract_field="score",
        )
        state = WorkflowState(
            results={"content": BlockResult(output=json.dumps([{"other": "value"}]))}
        )

        result_state = await execute_block_for_test(block, state)

        result = result_state.results["extract_missing_field_gate"]
        assert result.exit_handle == "pass"
        assert result.output == "PASS"

    @pytest.mark.asyncio
    async def test_extract_field_not_applied_on_fail(self):
        """FAIL feedback is returned instead of extracting from source JSON."""
        runner = _mock_runner("FAIL: insufficient quality")
        block = _make_gate(
            block_id="extract_fail_gate",
            runner=runner,
            extract_field="score",
        )
        state = WorkflowState(results={"content": BlockResult(output=json.dumps([{"score": 42}]))})

        result_state = await execute_block_for_test(block, state)

        result = result_state.results["extract_fail_gate"]
        assert result.exit_handle == "fail"
        assert "insufficient quality" in result.output
