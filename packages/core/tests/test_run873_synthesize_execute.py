"""
Failing tests for RUN-873: SynthesizeBlock — use runner.execute() and budgeted.instruction.

SynthesizeBlock must stop using Task entirely and call runner.execute() with string args
(instruction, context) derived from budgeted.instruction / budgeted.context.

Tests cover:
- AC1: synthesize.py has no 'from runsight_core.primitives import Task' import
- AC2: synthesize.py source has no 'Task(' instantiation
- AC3: SynthesizeBlock calls runner.execute() (not execute_task()) for the LLM call
- AC4: runner.execute() receives string instruction, not a Task object
- AC5: runner.execute() receives string context, not a Task object
- AC6: SynthesizeBlock still produces correct synthesis output
"""

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
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


def _make_soul(soul_id: str = "synth_soul") -> Soul:
    return Soul(
        id=soul_id,
        kind="soul",
        name="Synthesizer Soul",
        role="Synthesizer",
        system_prompt="Synthesize the outputs",
    )


def _make_synthesize(
    block_id: str = "synth1",
    input_block_ids: list[str] | None = None,
    **kwargs,
):
    """Create a SynthesizeBlock with sensible defaults."""
    from runsight_core.blocks.synthesize import SynthesizeBlock

    soul = kwargs.pop("soul", _make_soul())
    runner = kwargs.pop("runner", _mock_runner("Synthesized result"))
    if input_block_ids is None:
        input_block_ids = ["block_a", "block_b"]
    return SynthesizeBlock(
        block_id=block_id,
        input_block_ids=input_block_ids,
        synthesizer_soul=soul,
        runner=runner,
        **kwargs,
    )


def _make_state(block_ids: list[str] | None = None) -> WorkflowState:
    """Create a WorkflowState with results for the given block IDs."""
    if block_ids is None:
        block_ids = ["block_a", "block_b"]
    results = {bid: BlockResult(output=f"Output from {bid}") for bid in block_ids}
    return WorkflowState(results=results)


# ==============================================================================
# AC1: synthesize.py must NOT import Task from primitives
# ==============================================================================


class TestNoTaskImport:
    """synthesize.py must have no 'from runsight_core.primitives import Task' import."""

    def test_synthesize_source_has_no_task_import(self):
        """synthesize.py source must not import Task from primitives in any form."""
        import runsight_core.blocks.synthesize as synth_mod

        source = inspect.getsource(synth_mod)
        import_lines_with_task = [
            line
            for line in source.splitlines()
            if "import" in line and "primitives" in line and "Task" in line
        ]
        assert import_lines_with_task == [], (
            f"synthesize.py still imports Task from primitives — must be removed (RUN-873): "
            f"{import_lines_with_task}"
        )

    def test_synthesize_source_has_no_task_in_import_line(self):
        """synthesize.py import of Soul must not include Task on the same line."""
        import runsight_core.blocks.synthesize as synth_mod

        source = inspect.getsource(synth_mod)
        for line in source.splitlines():
            if "import" in line and "primitives" in line:
                assert "Task" not in line, (
                    f"synthesize.py still references Task in import line: {line!r}"
                )

    def test_task_not_importable_from_synthesize(self):
        """Task must not be accessible as an attribute of the synthesize module."""
        import runsight_core.blocks.synthesize as synth_mod

        assert not hasattr(synth_mod, "Task"), (
            "Task is still accessible from the synthesize module namespace — remove the import"
        )


# ==============================================================================
# AC2: synthesize.py source must have no Task( instantiation
# ==============================================================================


class TestNoTaskInstantiation:
    """synthesize.py must contain no 'Task(' call anywhere in its source."""

    def test_synthesize_source_has_no_task_instantiation(self):
        """synthesize.py must not contain 'Task(' — Task object creation must be removed."""
        import runsight_core.blocks.synthesize as synth_mod

        source = inspect.getsource(synth_mod)
        assert "Task(" not in source, (
            "synthesize.py still instantiates Task — the synthesis_task = Task(...) block must be "
            "removed (RUN-873)"
        )

    def test_synthesize_source_has_no_synthesis_task_variable(self):
        """synthesize.py must not contain 'synthesis_task' variable anywhere."""
        import runsight_core.blocks.synthesize as synth_mod

        source = inspect.getsource(synth_mod)
        assert "synthesis_task" not in source, (
            "synthesize.py still uses synthesis_task variable — it must be removed (RUN-873)"
        )


# ==============================================================================
# AC3: SynthesizeBlock calls runner.execute() not execute_task()
# ==============================================================================


class TestRunnerExecuteCalled:
    """SynthesizeBlock must call runner.execute() instead of runner.execute_task()."""

    @pytest.mark.asyncio
    async def test_runner_execute_called(self):
        """runner.execute() must be called (not execute_task)."""
        runner = _mock_runner("Synthesized output")
        block = _make_synthesize(block_id="synth_exec1", runner=runner)
        state = _make_state()

        await block.execute(state)

        runner.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_runner_execute_task_not_called(self):
        """runner.execute_task() must NOT be called — SynthesizeBlock uses runner.execute() now."""
        runner = _mock_runner("Synthesized output")
        block = _make_synthesize(block_id="synth_exec2", runner=runner)
        state = _make_state()

        await block.execute(state)

        runner.execute_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_runner_execute_called_with_three_inputs(self):
        """runner.execute() must be called even when synthesizing three inputs."""
        runner = _mock_runner("Unified synthesis")
        block = _make_synthesize(
            block_id="synth_exec3",
            input_block_ids=["a", "b", "c"],
            runner=runner,
        )
        state = WorkflowState(
            results={
                "a": BlockResult(output="Output A"),
                "b": BlockResult(output="Output B"),
                "c": BlockResult(output="Output C"),
            }
        )

        await block.execute(state)

        runner.execute.assert_called_once()
        runner.execute_task.assert_not_called()


# ==============================================================================
# AC4: runner.execute() receives string instruction (not a Task object)
# ==============================================================================


class TestRunnerExecuteReceivesStringInstruction:
    """The first positional arg to runner.execute() must be a str, not a Task."""

    @pytest.mark.asyncio
    async def test_execute_first_arg_is_string(self):
        """runner.execute() first arg (instruction) must be a plain string."""
        runner = _mock_runner("Synthesized output")
        block = _make_synthesize(block_id="synth_str1", runner=runner)
        state = _make_state()

        await block.execute(state)

        args, _kwargs = runner.execute.call_args
        instruction_arg = args[0]
        assert isinstance(instruction_arg, str), (
            f"runner.execute() first arg must be str, got {type(instruction_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_execute_first_arg_is_not_task(self):
        """runner.execute() must not receive a Task object as first arg — must be a string."""
        runner = _mock_runner("Synthesized output")
        block = _make_synthesize(block_id="synth_str2", runner=runner)
        state = _make_state()

        await block.execute(state)

        args, _kwargs = runner.execute.call_args
        instruction_arg = args[0]
        assert isinstance(instruction_arg, str), (
            f"runner.execute() first arg must be a string instruction, got {type(instruction_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_execute_instruction_contains_synthesis_directive(self):
        """The instruction string passed to runner.execute() must contain synthesis-related text."""
        runner = _mock_runner("Synthesized output")
        block = _make_synthesize(block_id="synth_str3", runner=runner)
        state = _make_state()

        await block.execute(state)

        args, _kwargs = runner.execute.call_args
        instruction_arg = args[0]
        assert len(instruction_arg) > 0, "Instruction string must not be empty"


# ==============================================================================
# AC5: runner.execute() receives string context (not a Task object)
# ==============================================================================


class TestRunnerExecuteReceivesStringContext:
    """The second positional arg to runner.execute() must be str or None, not a Task."""

    @pytest.mark.asyncio
    async def test_execute_second_arg_is_string_or_none(self):
        """runner.execute() second arg (context) must be str or None."""
        runner = _mock_runner("Synthesized output")
        block = _make_synthesize(block_id="synth_ctx1", runner=runner)
        state = _make_state()

        await block.execute(state)

        args, _kwargs = runner.execute.call_args
        assert len(args) >= 2, "runner.execute() must be called with at least 2 positional args"
        context_arg = args[1]
        assert isinstance(context_arg, (str, type(None))), (
            f"runner.execute() second arg must be str or None, got {type(context_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_execute_second_arg_is_not_task(self):
        """runner.execute() second arg must be str or None, not a Task object."""
        runner = _mock_runner("Synthesized output")
        block = _make_synthesize(block_id="synth_ctx2", runner=runner)
        state = _make_state()

        await block.execute(state)

        args, _kwargs = runner.execute.call_args
        assert len(args) >= 2, "runner.execute() must have at least 2 positional args"
        context_arg = args[1]
        assert isinstance(context_arg, (str, type(None))), (
            f"runner.execute() context arg must be str or None, got {type(context_arg).__name__}"
        )

    @pytest.mark.asyncio
    async def test_execute_third_arg_is_soul(self):
        """runner.execute() third arg must be the synthesizer_soul (a Soul instance)."""
        runner = _mock_runner("Synthesized output")
        soul = _make_soul("my_synth_soul")
        block = _make_synthesize(block_id="synth_ctx3", soul=soul, runner=runner)
        state = _make_state()

        await block.execute(state)

        args, _kwargs = runner.execute.call_args
        assert len(args) >= 3, "runner.execute() must be called with (instruction, context, soul)"
        soul_arg = args[2]
        assert isinstance(soul_arg, Soul), (
            f"runner.execute() third arg must be Soul, got {type(soul_arg).__name__}"
        )
        assert soul_arg.id == "my_synth_soul"


# ==============================================================================
# AC6: SynthesizeBlock still produces correct synthesis results
# ==============================================================================


class TestSynthesizeResultsCorrect:
    """SynthesizeBlock must still produce correct BlockResult output."""

    @pytest.mark.asyncio
    async def test_synthesize_output_stored_in_state(self):
        """SynthesizeBlock must store runner output in state.results[block_id]."""
        runner = _mock_runner("Final synthesized report")
        block = _make_synthesize(block_id="synth_res1", runner=runner)
        state = _make_state()

        result_state = await block.execute(state)

        assert "synth_res1" in result_state.results
        assert result_state.results["synth_res1"].output == "Final synthesized report"

    @pytest.mark.asyncio
    async def test_synthesize_cost_propagated(self):
        """Cost from runner.execute() result must be added to state.total_cost_usd."""
        runner = _mock_runner("Result", cost=0.07, tokens=300)
        block = _make_synthesize(block_id="synth_res2", runner=runner)
        state = WorkflowState(
            results={
                "block_a": BlockResult(output="Output A"),
                "block_b": BlockResult(output="Output B"),
            },
            total_cost_usd=1.0,
            total_tokens=500,
        )

        result_state = await block.execute(state)

        assert result_state.total_cost_usd == pytest.approx(1.07)
        assert result_state.total_tokens == 800

    @pytest.mark.asyncio
    async def test_synthesize_tokens_propagated(self):
        """Token count from runner.execute() result must be added to state.total_tokens."""
        runner = _mock_runner("Result", cost=0.0, tokens=250)
        block = _make_synthesize(block_id="synth_res3", runner=runner)
        state = WorkflowState(
            results={
                "block_a": BlockResult(output="Output A"),
                "block_b": BlockResult(output="Output B"),
            },
            total_cost_usd=0.0,
            total_tokens=100,
        )

        result_state = await block.execute(state)

        assert result_state.total_tokens == 350

    @pytest.mark.asyncio
    async def test_missing_input_block_raises(self):
        """SynthesizeBlock must raise ValueError when an input_block_id is not in state.results."""
        runner = _mock_runner("Result")
        block = _make_synthesize(
            block_id="synth_res4",
            input_block_ids=["block_a", "missing_block"],
            runner=runner,
        )
        state = WorkflowState(results={"block_a": BlockResult(output="Output A")})

        with pytest.raises(ValueError, match="missing_block"):
            await block.execute(state)

    @pytest.mark.asyncio
    async def test_context_contains_all_input_outputs(self):
        """The context passed to runner.execute() must include text from all input blocks."""
        runner = _mock_runner("Synthesis")
        block = _make_synthesize(
            block_id="synth_res5",
            input_block_ids=["alpha", "beta"],
            runner=runner,
        )
        state = WorkflowState(
            results={
                "alpha": BlockResult(output="Alpha output text"),
                "beta": BlockResult(output="Beta output text"),
            }
        )

        await block.execute(state)

        args, _kwargs = runner.execute.call_args
        # context is second positional arg
        context_arg = args[1] if len(args) >= 2 else _kwargs.get("context", "")
        assert "Alpha output text" in (context_arg or ""), (
            "Context passed to runner.execute() must include output from 'alpha' block"
        )
        assert "Beta output text" in (context_arg or ""), (
            "Context passed to runner.execute() must include output from 'beta' block"
        )
