"""
Failing tests for RUN-874: DispatchBlock — stop reading state.current_task.context.

Acceptance Criteria:
- DispatchBlock no longer imports Task or reads state.current_task
- Per-exit branch instructions still work correctly
- Context inheritance works via shared_memory or explicit parameter
- Existing dispatch tests pass

Issues being fixed (all must be verified by these tests):
1. `from runsight_core.primitives import ... Task` — import must go
2. `context = state.current_task.context if state.current_task is not None else None` — reads current_task
3. Stateful path: creates Task(...) using budgeted.task.instruction/context (budgeted.task gone after RUN-870)
4. Stateful path: calls runner.execute_task() — should use runner.execute()
5. Stateful path: calls runner._build_prompt(budgeted.task) — needs strings
6. Stateless path: creates Task(...) and calls runner.execute_task() — same fix

After fix:
- No Task import, no current_task read
- Context comes from state.shared_memory.get("_resolved_inputs", {}) or is None
- Both paths call runner.execute(instruction, context, soul, messages=...)
- History prompt built from strings (instruction + context) directly
"""

import inspect
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from runsight_core.runner import ExecutionResult
from runsight_core.state import WorkflowState

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
def soul_alpha():
    from runsight_core.primitives import Soul

    return Soul(
        id="alpha",
        role="Alpha",
        system_prompt="You are alpha.",
        model_name="gpt-4o",
        provider="openai",
    )


@pytest.fixture
def soul_beta():
    from runsight_core.primitives import Soul

    return Soul(
        id="beta",
        role="Beta",
        system_prompt="You are beta.",
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


def _make_dispatch_block(block_id, branches, runner):
    from runsight_core.blocks.dispatch import DispatchBlock

    return DispatchBlock(block_id, branches, runner)


def _make_branch(exit_id, soul, instruction):
    from runsight_core.blocks.dispatch import DispatchBranch

    return DispatchBranch(exit_id=exit_id, label=exit_id, soul=soul, task_instruction=instruction)


# ===========================================================================
# 1. Source-level: no Task import in dispatch.py
# ===========================================================================


class TestNoTaskImportInSource:
    """dispatch.py must not import Task from runsight_core.primitives."""

    def test_dispatch_module_source_does_not_import_task(self):
        """dispatch.py source text must not contain 'Task' in its import lines."""
        import runsight_core.blocks.dispatch as dispatch_module

        source = inspect.getsource(dispatch_module)
        import_lines = [
            line
            for line in source.splitlines()
            if line.startswith("from ") or line.startswith("import ")
        ]
        task_import_lines = [line for line in import_lines if "Task" in line]
        assert task_import_lines == [], (
            f"dispatch.py still imports Task. Found: {task_import_lines}"
        )

    def test_dispatch_module_does_not_have_task_in_module_namespace(self):
        """After import, 'Task' must not appear in the dispatch module's namespace."""
        import runsight_core.blocks.dispatch as dispatch_module

        assert not hasattr(dispatch_module, "Task"), (
            "dispatch.py exports 'Task' — it must not import it"
        )


# ===========================================================================
# 2. Source-level: no current_task read in dispatch.py
# ===========================================================================


class TestNoCurrentTaskReadInSource:
    """dispatch.py must not reference state.current_task anywhere."""

    def test_dispatch_source_does_not_reference_current_task(self):
        """dispatch.py source must not contain the string 'current_task'."""
        import runsight_core.blocks.dispatch as dispatch_module

        source = inspect.getsource(dispatch_module)
        assert "current_task" not in source, (
            "dispatch.py still references 'current_task'. Remove all usages."
        )

    def test_dispatch_source_does_not_instantiate_task(self):
        """dispatch.py source must not contain 'Task(' — no Task instantiation."""
        import runsight_core.blocks.dispatch as dispatch_module

        source = inspect.getsource(dispatch_module)
        assert "Task(" not in source, (
            "dispatch.py still instantiates Task objects. All Task(...) calls must be removed."
        )


# ===========================================================================
# 3. runner.execute() called — not execute_task()
# ===========================================================================


class TestRunnerExecuteCalledNotExecuteTask:
    """DispatchBlock must call runner.execute(), never runner.execute_task()."""

    @pytest.mark.asyncio
    async def test_stateless_path_calls_runner_execute_not_execute_task(
        self, soul_alpha, soul_beta, mock_runner
    ):
        """Stateless path uses runner.execute(), not runner.execute_task()."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, f"out_{soul.id}"
            )
        )
        mock_runner.execute_task = AsyncMock()  # must NOT be called

        branches = [
            _make_branch("exit_a", soul_alpha, "Instruct alpha"),
            _make_branch("exit_b", soul_beta, "Instruct beta"),
        ]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState()
        await block.execute(state)

        assert mock_runner.execute.called, "runner.execute() was never called"
        mock_runner.execute_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_stateful_path_calls_runner_execute_not_execute_task(
        self, soul_alpha, soul_beta, mock_runner
    ):
        """Stateful path uses runner.execute(), not runner.execute_task()."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, f"out_{soul.id}"
            )
        )
        mock_runner.execute_task = AsyncMock()  # must NOT be called

        branches = [
            _make_branch("exit_a", soul_alpha, "Instruct alpha"),
            _make_branch("exit_b", soul_beta, "Instruct beta"),
        ]
        block = _make_dispatch_block("d1", branches, mock_runner)
        block.stateful = True
        state = WorkflowState()
        await block.execute(state)

        assert mock_runner.execute.called, "runner.execute() was never called in stateful path"
        mock_runner.execute_task.assert_not_called()


# ===========================================================================
# 4. runner.execute() receives string args, not Task objects
# ===========================================================================


class TestRunnerExecuteReceivesStringArgs:
    """runner.execute(instruction, context, soul, ...) must receive strings, not Task objects."""

    @pytest.mark.asyncio
    async def test_stateless_execute_receives_instruction_string(self, soul_alpha, mock_runner):
        """runner.execute first positional arg is a string instruction, not a Task."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"instruction": instruction, "context": context, "soul": soul})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        branches = [_make_branch("exit_a", soul_alpha, "Do the thing")]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState()
        await block.execute(state)

        assert len(captured_calls) == 1
        call = captured_calls[0]
        assert isinstance(call["instruction"], str), (
            f"Expected instruction to be str, got {type(call['instruction'])}"
        )
        assert call["instruction"] == "Do the thing"

    @pytest.mark.asyncio
    async def test_stateless_execute_receives_context_string_or_none(self, soul_alpha, mock_runner):
        """runner.execute context arg is a string or None, not a Task or object."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"context": context})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        branches = [_make_branch("exit_a", soul_alpha, "Instruct")]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState()
        await block.execute(state)

        context_val = captured_calls[0]["context"]
        assert context_val is None or isinstance(context_val, str), (
            f"Expected context to be str or None, got {type(context_val)}: {context_val!r}"
        )

    @pytest.mark.asyncio
    async def test_stateful_execute_receives_instruction_string(self, soul_alpha, mock_runner):
        """Stateful path: runner.execute first arg is a string instruction."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"instruction": instruction, "context": context})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        branches = [_make_branch("exit_a", soul_alpha, "Stateful instruction")]
        block = _make_dispatch_block("d1", branches, mock_runner)
        block.stateful = True
        state = WorkflowState()
        await block.execute(state)

        assert len(captured_calls) == 1
        assert isinstance(captured_calls[0]["instruction"], str), (
            f"Stateful: instruction must be str, got {type(captured_calls[0]['instruction'])}"
        )
        assert captured_calls[0]["instruction"] == "Stateful instruction"


# ===========================================================================
# 5. Context inheritance: shared_memory["_resolved_inputs"] or None
# ===========================================================================


class TestContextInheritanceViaSharedMemory:
    """Context must come from state.shared_memory['_resolved_inputs'], not current_task."""

    @pytest.mark.asyncio
    async def test_context_from_shared_memory_resolved_inputs(self, soul_alpha, mock_runner):
        """When shared_memory has '_resolved_inputs', context value is passed to runner.execute."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"context": context})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        branches = [_make_branch("exit_a", soul_alpha, "Do it")]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState(
            shared_memory={"_resolved_inputs": {"context": "Shared context value"}}
        )
        await block.execute(state)

        assert len(captured_calls) == 1
        assert captured_calls[0]["context"] == "Shared context value", (
            f"Expected 'Shared context value' from shared_memory, got {captured_calls[0]['context']!r}"
        )

    @pytest.mark.asyncio
    async def test_no_shared_memory_context_is_none(self, soul_alpha, mock_runner):
        """When shared_memory has no '_resolved_inputs', context passed to runner.execute is None."""
        captured_calls = []

        async def _capture(instruction, context, soul, **kw):
            captured_calls.append({"context": context})
            return _make_exec_result("x", soul.id, "output")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        branches = [_make_branch("exit_a", soul_alpha, "Do it")]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState()  # no shared_memory
        await block.execute(state)

        assert captured_calls[0]["context"] is None, (
            f"Expected context=None when no shared_memory, got {captured_calls[0]['context']!r}"
        )

    @pytest.mark.asyncio
    async def test_does_not_crash_without_current_task_on_state(self, soul_alpha, mock_runner):
        """Block runs without current_task set — must not raise AttributeError."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, "output"
            )
        )

        branches = [_make_branch("exit_a", soul_alpha, "Instruction")]
        block = _make_dispatch_block("d1", branches, mock_runner)
        # WorkflowState without current_task — the new code must not touch it
        state = WorkflowState()

        # Must not raise
        new_state = await block.execute(state)
        assert "d1.exit_a" in new_state.results


# ===========================================================================
# 6. Per-exit branch instructions still work correctly
# ===========================================================================


class TestPerExitBranchInstructionsWork:
    """Each branch receives its own unique instruction string after the fix."""

    @pytest.mark.asyncio
    async def test_each_branch_receives_its_own_instruction(
        self, soul_alpha, soul_beta, mock_runner
    ):
        """Each branch's task_instruction is forwarded as the instruction string."""
        captured = {}

        async def _capture(instruction, context, soul, **kw):
            captured[soul.id] = instruction
            return _make_exec_result("x", soul.id, f"out_{soul.id}")

        mock_runner.execute = AsyncMock(side_effect=_capture)

        branches = [
            _make_branch("exit_a", soul_alpha, "Alpha instruction"),
            _make_branch("exit_b", soul_beta, "Beta instruction"),
        ]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState()
        await block.execute(state)

        assert captured["alpha"] == "Alpha instruction"
        assert captured["beta"] == "Beta instruction"

    @pytest.mark.asyncio
    async def test_per_exit_results_still_keyed_correctly(self, soul_alpha, soul_beta, mock_runner):
        """Results are still stored at state.results['{block_id}.{exit_id}']."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, f"out_{soul.id}"
            )
        )

        branches = [
            _make_branch("exit_a", soul_alpha, "Alpha instruction"),
            _make_branch("exit_b", soul_beta, "Beta instruction"),
        ]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState()
        new_state = await block.execute(state)

        assert "d1.exit_a" in new_state.results
        assert "d1.exit_b" in new_state.results
        assert new_state.results["d1.exit_a"].output == "out_alpha"
        assert new_state.results["d1.exit_b"].output == "out_beta"

    @pytest.mark.asyncio
    async def test_per_exit_result_exit_handle_set_correctly(
        self, soul_alpha, soul_beta, mock_runner
    ):
        """Per-exit BlockResult.exit_handle is set to the branch exit_id."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, f"out_{soul.id}"
            )
        )

        branches = [
            _make_branch("exit_a", soul_alpha, "Alpha"),
            _make_branch("exit_b", soul_beta, "Beta"),
        ]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState()
        new_state = await block.execute(state)

        assert new_state.results["d1.exit_a"].exit_handle == "exit_a"
        assert new_state.results["d1.exit_b"].exit_handle == "exit_b"

    @pytest.mark.asyncio
    async def test_combined_result_still_present(self, soul_alpha, soul_beta, mock_runner):
        """Combined result at state.results[block_id] is still a JSON list."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, f"out_{soul.id}"
            )
        )

        branches = [
            _make_branch("exit_a", soul_alpha, "Alpha"),
            _make_branch("exit_b", soul_beta, "Beta"),
        ]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState()
        new_state = await block.execute(state)

        assert "d1" in new_state.results
        parsed = json.loads(new_state.results["d1"].output)
        assert isinstance(parsed, list)
        assert len(parsed) == 2


# ===========================================================================
# 7. Stateful path: conversation history built from strings (not Task)
# ===========================================================================


class TestStatefulHistoryBuiltFromStrings:
    """Stateful path must build conversation history using string instruction/context."""

    @pytest.mark.asyncio
    async def test_stateful_path_builds_history_entry_with_strings(self, soul_alpha, mock_runner):
        """After stateful execution, conversation_histories contains a user message with string content."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, "response from alpha"
            )
        )

        branches = [_make_branch("exit_a", soul_alpha, "Do stateful work")]
        block = _make_dispatch_block("d1", branches, mock_runner)
        block.stateful = True
        state = WorkflowState()
        new_state = await block.execute(state)

        history_key = "d1_exit_a"
        assert history_key in new_state.conversation_histories, (
            f"Expected history key '{history_key}' in conversation_histories"
        )
        history = new_state.conversation_histories[history_key]
        assert len(history) > 0

        # Find the user message — it must have string content
        user_msgs = [m for m in history if m.get("role") == "user"]
        assert len(user_msgs) >= 1, "Expected at least one user message in history"
        user_content = user_msgs[-1]["content"]
        assert isinstance(user_content, str), (
            f"User message content must be a string, got {type(user_content)}"
        )
        # Must NOT be a Task repr
        assert "Task" not in user_content or "task" not in user_content.lower()[:10], (
            f"User message content looks like a Task object repr: {user_content!r}"
        )

    @pytest.mark.asyncio
    async def test_stateful_path_history_contains_assistant_response(self, soul_alpha, mock_runner):
        """After stateful execution, history has an assistant message with the LLM response."""
        mock_runner.execute = AsyncMock(
            side_effect=lambda instruction, context, soul, **kw: _make_exec_result(
                "x", soul.id, "LLM response text"
            )
        )

        branches = [_make_branch("exit_a", soul_alpha, "Do stateful work")]
        block = _make_dispatch_block("d1", branches, mock_runner)
        block.stateful = True
        state = WorkflowState()
        new_state = await block.execute(state)

        history = new_state.conversation_histories.get("d1_exit_a", [])
        assistant_msgs = [m for m in history if m.get("role") == "assistant"]
        assert len(assistant_msgs) >= 1, "Expected at least one assistant message in history"
        assert assistant_msgs[-1]["content"] == "LLM response text"

    @pytest.mark.asyncio
    async def test_stateful_path_does_not_call_build_prompt_with_task(
        self, soul_alpha, mock_runner
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

        branches = [_make_branch("exit_a", soul_alpha, "Do it")]
        block = _make_dispatch_block("d1", branches, mock_runner)
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
# 8. Cost/token aggregation still works
# ===========================================================================


class TestCostTokenAggregationAfterFix:
    """Cost and token aggregation still functions correctly after removing Task."""

    @pytest.mark.asyncio
    async def test_cost_aggregation_stateless(self, soul_alpha, soul_beta, mock_runner):
        """total_cost_usd and total_tokens are summed across branches."""

        async def _side_effect(instruction, context, soul, **kw):
            if soul.id == "alpha":
                return _make_exec_result("x", soul.id, "out", cost=0.05, tokens=200)
            return _make_exec_result("x", soul.id, "out", cost=0.03, tokens=150)

        mock_runner.execute = AsyncMock(side_effect=_side_effect)

        branches = [
            _make_branch("exit_a", soul_alpha, "Alpha"),
            _make_branch("exit_b", soul_beta, "Beta"),
        ]
        block = _make_dispatch_block("d1", branches, mock_runner)
        state = WorkflowState(total_cost_usd=0.10, total_tokens=50)
        new_state = await block.execute(state)

        assert new_state.total_cost_usd == pytest.approx(0.18)
        assert new_state.total_tokens == 400
