"""
Failing tests for RUN-872: GateBlock — use runner.execute() and budgeted.instruction.

GateBlock must stop using Task entirely and call runner.execute() with string args
(instruction, context) derived from budgeted.instruction / budgeted.context.

Tests cover:
- AC1: gate.py has no 'from runsight_core.primitives import Task' import
- AC2: gate.py source has no 'Task(' instantiation
- AC3: GateBlock calls runner.execute() (not execute_task()) for the LLM call
- AC4: runner.execute() receives string instruction, not a Task object
- AC5: runner.execute() receives string context, not a Task object
- AC6: GateBlock still produces PASS result with correct exit_handle
- AC7: GateBlock still produces FAIL result with correct exit_handle and feedback
"""

import inspect
from unittest.mock import AsyncMock, MagicMock

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
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    runner.execute_task = AsyncMock(
        return_value=ExecutionResult(
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    return runner


def _make_soul(soul_id: str = "gate_soul") -> Soul:
    return Soul(
        id=soul_id, kind="soul", name="Gate Soul", role="Gate", system_prompt="Evaluate quality"
    )


def _make_gate(block_id: str = "gate1", eval_key: str = "content", **kwargs):
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
# AC1: gate.py must NOT import Task from primitives
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
            f"gate.py still imports Task from primitives — must be removed (RUN-872): "
            f"{import_lines_with_task}"
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

        assert not hasattr(gate_mod, "Task"), (
            "Task is still accessible from the gate module namespace — remove the import"
        )


# ==============================================================================
# AC2: gate.py source must have no Task( instantiation
# ==============================================================================


class TestNoTaskInstantiation:
    """gate.py must contain no 'Task(' call anywhere in its source."""

    def test_gate_source_has_no_task_instantiation(self):
        """gate.py must not contain 'Task(' — Task object creation must be removed."""
        import runsight_core.blocks.gate as gate_mod

        source = inspect.getsource(gate_mod)
        assert "Task(" not in source, (
            "gate.py still instantiates Task — the gate_task = Task(...) block must be removed (RUN-872)"
        )

    def test_gate_source_has_no_gate_task_variable(self):
        """gate.py must not contain 'gate_task' variable anywhere."""
        import runsight_core.blocks.gate as gate_mod

        source = inspect.getsource(gate_mod)
        assert "gate_task" not in source, (
            "gate.py still uses gate_task variable — it must be removed (RUN-872)"
        )


# ==============================================================================
# AC3: GateBlock calls runner.execute() not execute_task()
# ==============================================================================


class TestRunnerExecuteCalled:
    """GateBlock must call runner.execute() instead of runner.execute_task()."""

    @pytest.mark.asyncio
    async def test_runner_execute_called_on_pass(self):
        """On PASS path, runner.execute() must be called (not execute_task)."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_exec1", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Good content")})

        await execute_block_for_test(block, state)

        runner.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_runner_execute_called_on_fail(self):
        """On FAIL path, runner.execute() must be called (not execute_task)."""
        runner = _mock_runner("FAIL: needs improvement")
        block = _make_gate(block_id="gate_exec2", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft content")})

        await execute_block_for_test(block, state)

        runner.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_runner_execute_task_not_called(self):
        """runner.execute_task() must NOT be called — GateBlock uses runner.execute() now."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_exec3", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content")})

        await execute_block_for_test(block, state)

        runner.execute_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_runner_execute_task_not_called_on_fail(self):
        """execute_task() must NOT be called on FAIL path either."""
        runner = _mock_runner("FAIL: poor quality")
        block = _make_gate(block_id="gate_exec4", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft")})

        await execute_block_for_test(block, state)

        runner.execute_task.assert_not_called()


# ==============================================================================
# AC4: runner.execute() receives string instruction (not a Task object)
# ==============================================================================


class TestRunnerExecuteReceivesStringInstruction:
    """The first positional arg to runner.execute() must be a str, not a Task."""

    @pytest.mark.asyncio
    async def test_execute_first_arg_is_string(self):
        """runner.execute() first arg (instruction) must be a plain string."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_str1", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Some content")})

        await execute_block_for_test(block, state)

        args, _kwargs = runner.execute.call_args
        instruction_arg = args[0]
        assert isinstance(instruction_arg, str), (
            f"runner.execute() first arg must be str, got {type(instruction_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_execute_first_arg_is_not_task(self):
        """runner.execute() must not receive a Task object as first arg — must be a string."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_str2", runner=runner)
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
        block = _make_gate(block_id="gate_str3", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content to evaluate")})

        await execute_block_for_test(block, state)

        args, _kwargs = runner.execute.call_args
        instruction_arg = args[0]
        # The instruction should contain some gate-related evaluation text
        assert len(instruction_arg) > 0, "Instruction string must not be empty"


# ==============================================================================
# AC5: runner.execute() receives string context (not a Task object)
# ==============================================================================


class TestRunnerExecuteReceivesStringContext:
    """The second positional arg to runner.execute() must be str or None, not a Task."""

    @pytest.mark.asyncio
    async def test_execute_second_arg_is_string_or_none(self):
        """runner.execute() second arg (context) must be str or None."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_ctx1", runner=runner)
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
        block = _make_gate(block_id="gate_ctx2", runner=runner)
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
        block = _make_gate(block_id="gate_ctx3", soul=soul, runner=runner)
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
# AC6 & AC7: GateBlock still produces correct PASS/FAIL results
# ==============================================================================


class TestGateResultsCorrect:
    """GateBlock must still produce correct BlockResult on both PASS and FAIL paths."""

    @pytest.mark.asyncio
    async def test_pass_exit_handle_is_pass(self):
        """On PASS response, BlockResult must have exit_handle='pass'."""
        runner = _mock_runner("PASS")
        block = _make_gate(block_id="gate_res1", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="High quality content")})

        result_state = await execute_block_for_test(block, state)

        assert result_state.results["gate_res1"].exit_handle == "pass"

    @pytest.mark.asyncio
    async def test_fail_exit_handle_is_fail(self):
        """On FAIL response, BlockResult must have exit_handle='fail'."""
        runner = _mock_runner("FAIL: missing citations")
        block = _make_gate(block_id="gate_res2", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft text")})

        result_state = await execute_block_for_test(block, state)

        assert result_state.results["gate_res2"].exit_handle == "fail"

    @pytest.mark.asyncio
    async def test_fail_output_contains_feedback(self):
        """On FAIL, BlockResult output must contain the feedback reason."""
        runner = _mock_runner("FAIL: incomplete argument")
        block = _make_gate(block_id="gate_res3", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Draft")})

        result_state = await execute_block_for_test(block, state)

        assert "incomplete argument" in result_state.results["gate_res3"].output

    @pytest.mark.asyncio
    async def test_pass_cost_propagated(self):
        """On PASS, cost from runner.execute() result must be added to state."""
        runner = _mock_runner("PASS", cost=0.05, tokens=200)
        block = _make_gate(block_id="gate_res4", runner=runner)
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
        block = _make_gate(block_id="gate_res5", runner=runner)
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
        block = _make_gate(block_id="gate_res6", eval_key="missing_key", runner=runner)
        state = WorkflowState(results={"content": BlockResult(output="Content")})

        with pytest.raises(ValueError, match="missing_key"):
            await execute_block_for_test(block, state)
