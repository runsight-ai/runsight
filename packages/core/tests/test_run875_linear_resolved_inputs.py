"""
Failing tests for RUN-875: LinearBlock — build user message from _resolved_inputs.

Acceptance Criteria:
- LinearBlock no longer reads state.current_task
- LinearBlock builds its instruction from state.shared_memory["_resolved_inputs"]
- LinearBlock works when _resolved_inputs is empty (produces empty user message)
- LinearBlock works when _resolved_inputs has content from upstream blocks

Issues being fixed (all must be verified by these tests):
1. `if state.current_task is None: raise ValueError(...)` — must be removed
2. `task = state.current_task` — must be removed
3. Reads `task.instruction` and `task.context` — must read from _resolved_inputs
4. Stateful path: calls runner.execute_task(budgeted.task, soul, messages=...) — must use runner.execute()
5. Stateful path: calls runner._build_prompt(budgeted.task) — must build from strings
6. Stateless path: calls runner.execute_task(task, soul) — must use runner.execute()

After fix:
- Read `_resolved_inputs = state.shared_memory.get("_resolved_inputs", {})`
- If _resolved_inputs has content, serialize as instruction string
- If empty, instruction is empty string ""
- Context is None (no current_task to read context from)
- Use runner.execute() in both paths
- No Task import needed
"""

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exec_result(task_id, soul_id, output, cost=0.0, tokens=0):
    return ExecutionResult(
        task_id=task_id,
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_soul():
    from runsight_core.primitives import Soul

    return Soul(
        id="test_soul",
        role="Tester",
        system_prompt="You test things.",
        model_name="gpt-4o",
        provider="openai",
    )


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner with runner.execute (not execute_task)."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = "gpt-4o"
    return runner


def _make_linear_block(block_id, soul, runner):
    from runsight_core.blocks.linear import LinearBlock

    return LinearBlock(block_id, soul, runner)


# ===========================================================================
# 1. Source-level: no Task import in linear.py
# ===========================================================================


class TestNoTaskImportInSource:
    """linear.py must not import Task from runsight_core.primitives."""

    def test_linear_module_source_does_not_import_task(self):
        """linear.py source text must not contain 'Task' in its import lines."""
        import runsight_core.blocks.linear as linear_module

        source = inspect.getsource(linear_module)
        import_lines = [
            line
            for line in source.splitlines()
            if line.startswith("from ") or line.startswith("import ")
        ]
        task_import_lines = [line for line in import_lines if "Task" in line]
        assert task_import_lines == [], f"linear.py still imports Task. Found: {task_import_lines}"

    def test_linear_module_does_not_have_task_in_module_namespace(self):
        """After import, 'Task' must not appear in the linear module's namespace."""
        import runsight_core.blocks.linear as linear_module

        assert not hasattr(linear_module, "Task"), (
            "linear.py exports 'Task' — it must not import it"
        )


# ===========================================================================
# 2. Source-level: no current_task read in linear.py
# ===========================================================================


class TestNoCurrentTaskReadInSource:
    """linear.py must not reference state.current_task anywhere."""

    def test_linear_source_does_not_reference_current_task(self):
        """linear.py source must not contain the string 'current_task'."""
        import runsight_core.blocks.linear as linear_module

        source = inspect.getsource(linear_module)
        assert "current_task" not in source, (
            "linear.py still references 'current_task'. Remove all usages."
        )

    def test_linear_source_does_not_raise_on_none_task(self):
        """linear.py source must not contain the 'current_task is None' guard."""
        import runsight_core.blocks.linear as linear_module

        source = inspect.getsource(linear_module)
        assert "current_task is None" not in source, (
            "linear.py still has the 'current_task is None' ValueError guard. Remove it."
        )


# ===========================================================================
# 3. LinearBlock does NOT raise when state.current_task is None
# ===========================================================================


class TestNoRaiseOnNoneCurrentTask:
    """LinearBlock must not raise ValueError when state.current_task is None."""

    @pytest.mark.asyncio
    async def test_does_not_raise_when_current_task_is_none(self, sample_soul, mock_runner):
        """LinearBlock executes successfully even when current_task is None."""
        mock_runner.execute = AsyncMock(return_value=_make_exec_result("x", "test_soul", "output"))

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState(current_task=None)

        # Must not raise — should execute normally
        result_state = await block.execute(state)
        assert "linear1" in result_state.results

    @pytest.mark.asyncio
    async def test_does_not_raise_when_state_has_no_current_task_at_all(
        self, sample_soul, mock_runner
    ):
        """LinearBlock works on a default WorkflowState (current_task defaults to None)."""
        mock_runner.execute = AsyncMock(return_value=_make_exec_result("x", "test_soul", "output"))

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState()  # current_task=None by default

        result_state = await block.execute(state)
        assert "linear1" in result_state.results


# ===========================================================================
# 4. LinearBlock reads _resolved_inputs from shared_memory
# ===========================================================================


class TestReadsResolvedInputsFromSharedMemory:
    """LinearBlock must read _resolved_inputs from state.shared_memory, not current_task."""

    @pytest.mark.asyncio
    async def test_empty_resolved_inputs_produces_empty_instruction(self, sample_soul, mock_runner):
        """When _resolved_inputs is empty dict, instruction passed to runner.execute is ''."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"instruction": instruction, "context": context})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState(shared_memory={"_resolved_inputs": {}})

        await block.execute(state)

        assert len(captured_calls) == 1
        assert captured_calls[0]["instruction"] == "", (
            f"Expected empty string when _resolved_inputs is empty, "
            f"got {captured_calls[0]['instruction']!r}"
        )

    @pytest.mark.asyncio
    async def test_no_resolved_inputs_key_produces_empty_instruction(
        self, sample_soul, mock_runner
    ):
        """When shared_memory has no '_resolved_inputs' key, instruction is ''."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"instruction": instruction})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState()  # no shared_memory at all

        await block.execute(state)

        assert len(captured_calls) == 1
        assert captured_calls[0]["instruction"] == "", (
            f"Expected empty string when no _resolved_inputs, "
            f"got {captured_calls[0]['instruction']!r}"
        )

    @pytest.mark.asyncio
    async def test_resolved_inputs_with_data_is_passed_as_instruction(
        self, sample_soul, mock_runner
    ):
        """When _resolved_inputs has content, it is serialized into the instruction string."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"instruction": instruction})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState(
            shared_memory={"_resolved_inputs": {"step1": "upstream result", "step2": "more data"}}
        )

        await block.execute(state)

        assert len(captured_calls) == 1
        instruction = captured_calls[0]["instruction"]
        assert isinstance(instruction, str), (
            f"instruction must be a string, got {type(instruction)}"
        )
        # Instruction must contain the upstream data in some form
        assert "upstream result" in instruction or "step1" in instruction, (
            f"instruction must contain _resolved_inputs data, got {instruction!r}"
        )

    @pytest.mark.asyncio
    async def test_context_is_none_when_no_current_task(self, sample_soul, mock_runner):
        """Context passed to runner.execute is None (no current_task to read context from)."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"context": context})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState()

        await block.execute(state)

        assert captured_calls[0]["context"] is None, (
            f"Expected context=None, got {captured_calls[0]['context']!r}"
        )


# ===========================================================================
# 5. runner.execute() called — not execute_task()
# ===========================================================================


class TestRunnerExecuteCalledNotExecuteTask:
    """LinearBlock must call runner.execute(), never runner.execute_task()."""

    @pytest.mark.asyncio
    async def test_stateless_path_calls_runner_execute_not_execute_task(
        self, sample_soul, mock_runner
    ):
        """Stateless path uses runner.execute(), not runner.execute_task()."""
        mock_runner.execute = AsyncMock(return_value=_make_exec_result("x", "test_soul", "output"))
        mock_runner.execute_task = AsyncMock()  # must NOT be called

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState()
        await block.execute(state)

        assert mock_runner.execute.called, "runner.execute() was never called"
        mock_runner.execute_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_stateful_path_calls_runner_execute_not_execute_task(
        self, sample_soul, mock_runner
    ):
        """Stateful path uses runner.execute(), not runner.execute_task()."""
        mock_runner.execute = AsyncMock(return_value=_make_exec_result("x", "test_soul", "output"))
        mock_runner.execute_task = AsyncMock()  # must NOT be called

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        block.stateful = True
        state = WorkflowState()
        await block.execute(state)

        assert mock_runner.execute.called, "runner.execute() was never called in stateful path"
        mock_runner.execute_task.assert_not_called()


# ===========================================================================
# 6. runner.execute() receives string args, not Task objects
# ===========================================================================


class TestRunnerExecuteReceivesStringArgs:
    """runner.execute(instruction, context, soul, ...) must receive strings, not Task objects."""

    @pytest.mark.asyncio
    async def test_stateless_execute_receives_instruction_string(self, sample_soul, mock_runner):
        """Stateless: runner.execute first positional arg is a string, not a Task."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"instruction": instruction, "context": context, "soul": soul})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState(shared_memory={"_resolved_inputs": {"input_block": "some data"}})
        await block.execute(state)

        assert len(captured_calls) == 1
        assert isinstance(captured_calls[0]["instruction"], str), (
            f"Expected instruction to be str, got {type(captured_calls[0]['instruction'])}"
        )

    @pytest.mark.asyncio
    async def test_stateful_execute_receives_instruction_string(self, sample_soul, mock_runner):
        """Stateful: runner.execute first positional arg is a string, not a Task."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"instruction": instruction, "context": context})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        block.stateful = True
        state = WorkflowState(shared_memory={"_resolved_inputs": {"block_a": "upstream output"}})
        await block.execute(state)

        assert len(captured_calls) == 1
        assert isinstance(captured_calls[0]["instruction"], str), (
            f"Stateful: instruction must be str, got {type(captured_calls[0]['instruction'])}"
        )

    @pytest.mark.asyncio
    async def test_execute_receives_soul_arg(self, sample_soul, mock_runner):
        """runner.execute must receive the block's soul as third arg."""
        captured_souls = []

        async def _capture(instruction, context, soul, **kw):
            captured_souls.append(soul)
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState()
        await block.execute(state)

        assert len(captured_souls) == 1
        assert captured_souls[0].id == "test_soul"


# ===========================================================================
# 7. Stateful path: conversation history built from strings (no _build_prompt with Task)
# ===========================================================================


class TestStatefulHistoryBuiltFromStrings:
    """Stateful path must build conversation history using string instruction, not Task objects."""

    @pytest.mark.asyncio
    async def test_stateful_path_builds_history_with_user_message(self, sample_soul, mock_runner):
        """After stateful execution, conversation_histories has a user message with string content."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, "response from linear"
            )
        )

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        block.stateful = True
        state = WorkflowState()
        new_state = await block.execute(state)

        history_key = "linear1_test_soul"
        assert history_key in new_state.conversation_histories, (
            f"Expected history key '{history_key}' in conversation_histories. "
            f"Found keys: {list(new_state.conversation_histories.keys())}"
        )
        history = new_state.conversation_histories[history_key]
        assert len(history) > 0

        user_msgs = [m for m in history if m.get("role") == "user"]
        assert len(user_msgs) >= 1, "Expected at least one user message in history"
        user_content = user_msgs[-1]["content"]
        assert isinstance(user_content, str), (
            f"User message content must be a string, got {type(user_content)}"
        )

    @pytest.mark.asyncio
    async def test_stateful_path_history_contains_assistant_response(
        self, sample_soul, mock_runner
    ):
        """After stateful execution, history has an assistant message with the LLM response."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, "LLM response text"
            )
        )

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        block.stateful = True
        state = WorkflowState()
        new_state = await block.execute(state)

        history = new_state.conversation_histories.get("linear1_test_soul", [])
        assistant_msgs = [m for m in history if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1, "Expected at least one assistant message in history"
        assert assistant_msgs[-1]["content"] == "LLM response text"

    @pytest.mark.asyncio
    async def test_stateful_path_does_not_call_build_prompt_with_task(
        self, sample_soul, mock_runner
    ):
        """Stateful path must not call runner._build_prompt(task) — Task object must not be passed."""
        build_prompt_calls = []
        mock_runner._build_prompt = MagicMock(
            side_effect=lambda arg: build_prompt_calls.append(arg)
        )
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, "output"
            )
        )

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        block.stateful = True
        state = WorkflowState()
        await block.execute(state)

        # If _build_prompt is called at all, it must not receive a Task object
        from runsight_core.primitives import Task

        for call_arg in build_prompt_calls:
            assert not isinstance(call_arg, Task), (
                f"_build_prompt was called with a Task object: {call_arg!r}. "
                "Stateful path must build prompt from strings."
            )


# ===========================================================================
# 8. Result stored correctly in state.results
# ===========================================================================


class TestResultStoredCorrectly:
    """BlockResult must still be stored at state.results[block_id]."""

    @pytest.mark.asyncio
    async def test_result_stored_in_state_results(self, sample_soul, mock_runner):
        """Output from runner.execute is stored at state.results[block_id]."""
        mock_runner.execute = AsyncMock(
            return_value=_make_exec_result("x", "test_soul", "Linear output text")
        )

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState()
        new_state = await block.execute(state)

        assert "linear1" in new_state.results
        assert new_state.results["linear1"].output == "Linear output text"

    @pytest.mark.asyncio
    async def test_preserves_existing_results(self, sample_soul, mock_runner):
        """LinearBlock preserves previously stored results when adding new one."""
        mock_runner.execute = AsyncMock(
            return_value=_make_exec_result("x", "test_soul", "New output")
        )

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState(results={"previous_block": BlockResult(output="Previous output")})
        new_state = await block.execute(state)

        assert new_state.results["previous_block"].output == "Previous output"
        assert new_state.results["linear1"].output == "New output"

    @pytest.mark.asyncio
    async def test_execution_log_appended(self, sample_soul, mock_runner):
        """Execution log entry still added with block id."""
        mock_runner.execute = AsyncMock(return_value=_make_exec_result("x", "test_soul", "Output"))

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState()
        new_state = await block.execute(state)

        assert len(new_state.execution_log) == 1
        assert "[Block linear1]" in new_state.execution_log[0]["content"]

    @pytest.mark.asyncio
    async def test_cost_and_tokens_aggregated(self, sample_soul, mock_runner):
        """total_cost_usd and total_tokens are accumulated from runner.execute result."""
        mock_runner.execute = AsyncMock(
            return_value=_make_exec_result("x", "test_soul", "Output", cost=0.25, tokens=500)
        )

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState(total_cost_usd=0.10, total_tokens=100)
        new_state = await block.execute(state)

        assert new_state.total_cost_usd == pytest.approx(0.35)
        assert new_state.total_tokens == 600


# ===========================================================================
# 9. _resolved_inputs with multiple keys — content all present in instruction
# ===========================================================================


class TestResolvedInputsMultipleKeys:
    """When _resolved_inputs has multiple upstream entries, all data appears in instruction."""

    @pytest.mark.asyncio
    async def test_multiple_resolved_inputs_all_in_instruction(self, sample_soul, mock_runner):
        """Instruction string includes data from all entries in _resolved_inputs."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"instruction": instruction})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState(
            shared_memory={
                "_resolved_inputs": {
                    "block_a": "result from A",
                    "block_b": "result from B",
                    "block_c": "result from C",
                }
            }
        )
        await block.execute(state)

        assert len(captured_calls) == 1
        instruction = captured_calls[0]["instruction"]
        assert isinstance(instruction, str)
        # All upstream data must be reachable in the instruction
        assert "result from A" in instruction or "block_a" in instruction, (
            f"block_a data missing from instruction: {instruction!r}"
        )
        assert "result from B" in instruction or "block_b" in instruction, (
            f"block_b data missing from instruction: {instruction!r}"
        )
        assert "result from C" in instruction or "block_c" in instruction, (
            f"block_c data missing from instruction: {instruction!r}"
        )

    @pytest.mark.asyncio
    async def test_single_resolved_input_in_instruction(self, sample_soul, mock_runner):
        """Instruction string contains data from single entry in _resolved_inputs."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"instruction": instruction})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        block = _make_linear_block("linear1", sample_soul, mock_runner)
        state = WorkflowState(
            shared_memory={"_resolved_inputs": {"research_block": "deep research output"}}
        )
        await block.execute(state)

        instruction = captured_calls[0]["instruction"]
        assert "deep research output" in instruction or "research_block" in instruction, (
            f"Single _resolved_inputs entry data missing from instruction: {instruction!r}"
        )
