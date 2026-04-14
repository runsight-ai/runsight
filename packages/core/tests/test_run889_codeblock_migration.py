"""
RUN-889: Failing tests for CodeBlock migration to BlockContext/BlockOutput.

Tests verify that after migration:
AC-1: CodeBlock.execute accepts BlockContext and returns BlockOutput (not WorkflowState)
AC-2: stdin_data to subprocess is byte-identical to current path
AC-3: Error cases produce correct BlockOutput with exit_handle="error"
AC-4: exit_handle extraction from dict results still works
AC-5: build_block_context detects CodeBlock (has `code` attribute) and populates
      ctx.inputs with full state snapshot: results, metadata, shared_memory
AC-6: End-to-end via execute_block dispatches CodeBlock through new path
"""

import json
import textwrap
from unittest.mock import patch

import pytest
from runsight_core.block_io import (
    BlockContext,
    BlockOutput,
    apply_block_output,
    build_block_context,
)
from runsight_core.blocks.code import CodeBlock
from runsight_core.primitives import Task
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, execute_block

# ---------------------------------------------------------------------------
# Test code snippets
# ---------------------------------------------------------------------------

SIMPLE_CODE = textwrap.dedent("""\
def main(data):
    return {'result': 'ok'}
""")

ECHO_DATA_CODE = textwrap.dedent("""\
def main(data):
    return data
""")

ERROR_CODE = textwrap.dedent("""\
def main(data):
    raise ValueError('boom')
""")

EXIT_HANDLE_CODE = textwrap.dedent("""\
def main(data):
    return {'exit_handle': 'custom_exit', 'data': 'value'}
""")

EXIT_HANDLE_EMPTY_CODE = textwrap.dedent("""\
def main(data):
    return {'exit_handle': '', 'data': 'value'}
""")

NO_EXIT_HANDLE_CODE = textwrap.dedent("""\
def main(data):
    return {'data': 'value'}
""")

TIMEOUT_CODE = textwrap.dedent("""\
def main(data):
    while True:
        pass
""")

NON_JSON_CODE = textwrap.dedent("""\
def main(data):
    return object()
""")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> WorkflowState:
    defaults: dict = {
        "results": {},
        "metadata": {},
        "shared_memory": {},
        "execution_log": [],
        "current_task": Task(id="t1", instruction="run code"),
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


def _make_code_block_context(block: CodeBlock, state: WorkflowState) -> BlockContext:
    """Helper: build a BlockContext for CodeBlock directly (no build_block_context)."""
    return BlockContext(
        block_id=block.block_id,
        instruction="run code",
        context=None,
        inputs={
            "results": {
                k: v.output if isinstance(v, BlockResult) else v for k, v in state.results.items()
            },
            "metadata": state.metadata,
            "shared_memory": state.shared_memory,
        },
        conversation_history=[],
        soul=None,
        model_name=None,
        state_snapshot=state,
    )


# ===========================================================================
# AC-1: CodeBlock.execute accepts BlockContext and returns BlockOutput
# ===========================================================================


class TestAC1AcceptsBlockContextReturnsBlockOutput:
    @pytest.mark.asyncio
    async def test_execute_accepts_block_context_returns_block_output(self):
        """CodeBlock.execute must accept a BlockContext and return BlockOutput."""
        block = CodeBlock("cb1", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput), (
            f"Expected BlockOutput but got {type(result).__name__}. "
            "CodeBlock.execute must return BlockOutput after RUN-889 migration."
        )

    @pytest.mark.asyncio
    async def test_block_output_contains_code_return_value(self):
        """BlockOutput.output must contain the JSON-encoded return value of main()."""
        block = CodeBlock("cb1", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        parsed = json.loads(result.output)
        assert parsed == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_block_output_cost_is_zero(self):
        """CodeBlock makes no LLM calls — cost_usd must be exactly 0."""
        block = CodeBlock("cb_cost", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.cost_usd == 0.0, (
            f"CodeBlock cost_usd must be 0.0 (no LLM calls), got {result.cost_usd}"
        )

    @pytest.mark.asyncio
    async def test_block_output_tokens_is_zero(self):
        """CodeBlock makes no LLM calls — total_tokens must be exactly 0."""
        block = CodeBlock("cb_tokens", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.total_tokens == 0, (
            f"CodeBlock total_tokens must be 0 (no LLM calls), got {result.total_tokens}"
        )

    @pytest.mark.asyncio
    async def test_block_output_log_entries_contain_success_message(self):
        """BlockOutput.log_entries must contain a success message referencing the block_id."""
        block = CodeBlock("cb_log", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert len(result.log_entries) >= 1
        assert any(
            "executed successfully" in entry.get("content", "") for entry in result.log_entries
        ), "Expected log_entries to contain 'executed successfully' for CodeBlock success path"

    @pytest.mark.asyncio
    async def test_execute_does_not_return_workflow_state(self):
        """After migration, CodeBlock.execute(BlockContext) must NOT return WorkflowState."""
        block = CodeBlock("cb2", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert not isinstance(result, WorkflowState), (
            "CodeBlock.execute(BlockContext) must return BlockOutput, not WorkflowState"
        )

    @pytest.mark.asyncio
    async def test_execute_still_accepts_workflow_state_legacy_path(self):
        """Legacy path: CodeBlock.execute(WorkflowState) must still work for backward compat."""
        block = CodeBlock("cb_legacy", SIMPLE_CODE)
        state = _make_state()

        result = await block.execute(state)

        # Legacy path returns WorkflowState
        assert isinstance(result, WorkflowState)
        assert "cb_legacy" in result.results


# ===========================================================================
# AC-2: stdin_data byte-identical to current path
# ===========================================================================


class TestAC2StdinDataByteIdentical:
    @pytest.mark.asyncio
    async def test_stdin_data_structure_matches_current_path(self):
        """ctx.inputs must produce the same JSON structure as the current stdin_data."""
        prior_result = BlockResult(output="prior output")
        state = _make_state(
            results={"prior_block": prior_result},
            metadata={"run_id": "abc"},
            shared_memory={"key": "value"},
        )
        block = CodeBlock("cb_stdin", ECHO_DATA_CODE)
        ctx = _make_code_block_context(block, state)

        # The ctx.inputs must be structured exactly as the current code builds stdin_data:
        # {"results": {k: v.output}, "metadata": {...}, "shared_memory": {...}}
        assert "results" in ctx.inputs
        assert "metadata" in ctx.inputs
        assert "shared_memory" in ctx.inputs

    @pytest.mark.asyncio
    async def test_stdin_results_values_are_unwrapped_output_strings(self):
        """Results values in ctx.inputs must be unwrapped .output strings, not BlockResult."""
        prior_result = BlockResult(output="prior output string")
        state = _make_state(results={"prior_block": prior_result})
        block = CodeBlock("cb_unwrap", ECHO_DATA_CODE)
        ctx = _make_code_block_context(block, state)

        results_in_inputs = ctx.inputs["results"]
        assert isinstance(results_in_inputs["prior_block"], str), (
            "Results values in ctx.inputs must be unwrapped to .output strings, "
            f"got {type(results_in_inputs['prior_block']).__name__}"
        )
        assert results_in_inputs["prior_block"] == "prior output string"

    @pytest.mark.asyncio
    async def test_stdin_data_round_trips_through_subprocess(self):
        """The data passed to main() in the subprocess must contain results, metadata, shared_memory."""
        state = _make_state(
            results={"prev": BlockResult(output="prev_out")},
            metadata={"wf": "test"},
            shared_memory={"sm_key": "sm_val"},
        )
        block = CodeBlock("cb_echo", ECHO_DATA_CODE)
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        parsed = json.loads(result.output)
        # data passed to main() must contain all three keys
        assert "results" in parsed
        assert "metadata" in parsed
        assert "shared_memory" in parsed
        assert parsed["results"]["prev"] == "prev_out"
        assert parsed["metadata"]["wf"] == "test"
        assert parsed["shared_memory"]["sm_key"] == "sm_val"

    @pytest.mark.asyncio
    async def test_stdin_metadata_matches_state_metadata(self):
        """ctx.inputs['metadata'] must be identical to state.metadata."""
        state = _make_state(metadata={"blueprint": "test_wf", "run_id": "run-123"})
        block = CodeBlock("cb_meta", SIMPLE_CODE)
        ctx = _make_code_block_context(block, state)

        assert ctx.inputs["metadata"] == {"blueprint": "test_wf", "run_id": "run-123"}

    @pytest.mark.asyncio
    async def test_stdin_shared_memory_matches_state_shared_memory(self):
        """ctx.inputs['shared_memory'] must be identical to state.shared_memory."""
        state = _make_state(shared_memory={"counter": 42, "flag": True})
        block = CodeBlock("cb_sm", SIMPLE_CODE)
        ctx = _make_code_block_context(block, state)

        assert ctx.inputs["shared_memory"] == {"counter": 42, "flag": True}


# ===========================================================================
# AC-3: Error cases produce correct BlockOutput with exit_handle="error"
# ===========================================================================


class TestAC3ErrorCases:
    @pytest.mark.asyncio
    async def test_nonzero_exit_code_returns_block_output_with_error_exit_handle(self):
        """Non-zero subprocess exit → BlockOutput with exit_handle='error'."""
        block = CodeBlock("cb_err", ERROR_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput), f"Expected BlockOutput, got {type(result).__name__}"
        assert result.exit_handle == "error", (
            f"Non-zero exit must produce exit_handle='error', got {result.exit_handle!r}"
        )

    @pytest.mark.asyncio
    async def test_nonzero_exit_code_output_contains_error_prefix(self):
        """Non-zero exit → BlockOutput.output must start with 'Error:'."""
        block = CodeBlock("cb_err2", ERROR_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.output.startswith("Error:"), (
            f"Error output must start with 'Error:', got {result.output!r}"
        )

    @pytest.mark.asyncio
    async def test_nonzero_exit_code_output_contains_error_message(self):
        """Non-zero exit → BlockOutput.output must contain the error message."""
        block = CodeBlock("cb_err3", ERROR_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert "boom" in result.output, f"Error output must contain 'boom', got {result.output!r}"

    @pytest.mark.asyncio
    async def test_invalid_json_stdout_returns_block_output_with_error(self):
        """Non-JSON stdout → BlockOutput with error message (no exit_handle='error' required)."""
        block = CodeBlock("cb_nonjson", NON_JSON_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert "Error" in result.output, (
            f"Non-JSON stdout must produce error output, got {result.output!r}"
        )

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self):
        """Timeout → TimeoutError raised (same as current behaviour, not swallowed)."""
        block = CodeBlock("cb_timeout", TIMEOUT_CODE, timeout_seconds=1)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        with pytest.raises(TimeoutError, match="timed out"):
            await block.execute(ctx)

    @pytest.mark.asyncio
    async def test_error_log_entries_contain_block_id(self):
        """Error BlockOutput.log_entries must reference the block_id."""
        block = CodeBlock("cb_errlog", ERROR_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert len(result.log_entries) >= 1
        assert any("cb_errlog" in entry.get("content", "") for entry in result.log_entries), (
            "log_entries must reference the block_id for error cases"
        )


# ===========================================================================
# AC-4: exit_handle extraction from dict results
# ===========================================================================


class TestAC4ExitHandleExtraction:
    @pytest.mark.asyncio
    async def test_dict_with_exit_handle_extracts_handle(self):
        """Code returns dict with 'exit_handle' key → extracted as exit_handle, popped from output."""
        block = CodeBlock("cb_exit", EXIT_HANDLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.exit_handle == "custom_exit", (
            f"exit_handle must be 'custom_exit', got {result.exit_handle!r}"
        )

    @pytest.mark.asyncio
    async def test_dict_with_exit_handle_removes_key_from_output(self):
        """When exit_handle is extracted, the 'exit_handle' key must not appear in the output."""
        block = CodeBlock("cb_exit2", EXIT_HANDLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        parsed = json.loads(result.output)
        assert "exit_handle" not in parsed, (
            "'exit_handle' key must be popped from dict before storing as output"
        )
        assert parsed == {"data": "value"}

    @pytest.mark.asyncio
    async def test_dict_with_empty_exit_handle_yields_none(self):
        """Code returns dict with 'exit_handle': '' → exit_handle=None (empty string is falsy)."""
        block = CodeBlock("cb_empty_exit", EXIT_HANDLE_EMPTY_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.exit_handle is None, (
            f"Empty exit_handle string must produce exit_handle=None, got {result.exit_handle!r}"
        )

    @pytest.mark.asyncio
    async def test_dict_without_exit_handle_yields_none(self):
        """Code returns dict without 'exit_handle' key → exit_handle=None."""
        block = CodeBlock("cb_no_exit", NO_EXIT_HANDLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.exit_handle is None, (
            f"Dict without exit_handle must produce exit_handle=None, got {result.exit_handle!r}"
        )

    @pytest.mark.asyncio
    async def test_dict_without_exit_handle_preserves_output(self):
        """Code returns dict without exit_handle → full dict in output."""
        block = CodeBlock("cb_no_exit2", NO_EXIT_HANDLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        parsed = json.loads(result.output)
        assert parsed == {"data": "value"}


# ===========================================================================
# AC-5: build_block_context "access: all" pattern for CodeBlock
# ===========================================================================


class TestAC5BuildBlockContext:
    def test_build_block_context_detects_code_attribute(self):
        """build_block_context must detect CodeBlock (has 'code' attr) and use 'access: all'."""
        block = CodeBlock("cb_ctx", SIMPLE_CODE)
        state = _make_state(
            results={"prev": BlockResult(output="some result")},
            metadata={"wf": "test"},
            shared_memory={"key": "val"},
        )

        ctx = build_block_context(block, state)

        assert isinstance(ctx, BlockContext), (
            f"build_block_context must return BlockContext for CodeBlock, got {type(ctx).__name__}"
        )

    def test_build_block_context_inputs_contain_results(self):
        """ctx.inputs must contain 'results' key with full state snapshot."""
        block = CodeBlock("cb_ctx", SIMPLE_CODE)
        state = _make_state(
            results={"prev": BlockResult(output="some result")},
        )

        ctx = build_block_context(block, state)

        assert "results" in ctx.inputs, (
            "build_block_context for CodeBlock must populate ctx.inputs['results']"
        )

    def test_build_block_context_inputs_contain_metadata(self):
        """ctx.inputs must contain 'metadata' key from state."""
        block = CodeBlock("cb_ctx", SIMPLE_CODE)
        state = _make_state(metadata={"wf": "test_workflow"})

        ctx = build_block_context(block, state)

        assert "metadata" in ctx.inputs, (
            "build_block_context for CodeBlock must populate ctx.inputs['metadata']"
        )
        assert ctx.inputs["metadata"] == {"wf": "test_workflow"}

    def test_build_block_context_inputs_contain_shared_memory(self):
        """ctx.inputs must contain 'shared_memory' key from state."""
        block = CodeBlock("cb_ctx", SIMPLE_CODE)
        state = _make_state(shared_memory={"sm": "data"})

        ctx = build_block_context(block, state)

        assert "shared_memory" in ctx.inputs, (
            "build_block_context for CodeBlock must populate ctx.inputs['shared_memory']"
        )
        assert ctx.inputs["shared_memory"] == {"sm": "data"}

    def test_build_block_context_results_values_are_unwrapped(self):
        """Results in ctx.inputs must be unwrapped BlockResult.output strings."""
        block = CodeBlock("cb_ctx", SIMPLE_CODE)
        state = _make_state(results={"prev": BlockResult(output="output str")})

        ctx = build_block_context(block, state)

        results_in_inputs = ctx.inputs["results"]
        assert isinstance(results_in_inputs["prev"], str), (
            "Results values must be unwrapped to strings (BlockResult.output), "
            f"got {type(results_in_inputs['prev']).__name__}"
        )
        assert results_in_inputs["prev"] == "output str"

    def test_build_block_context_block_id_matches(self):
        """ctx.block_id must match the block's block_id."""
        block = CodeBlock("my_code_block", SIMPLE_CODE)
        state = _make_state()

        ctx = build_block_context(block, state)

        assert ctx.block_id == "my_code_block"

    def test_build_block_context_soul_is_none(self):
        """CodeBlock has no soul — ctx.soul must be None."""
        block = CodeBlock("cb_ctx", SIMPLE_CODE)
        state = _make_state()

        ctx = build_block_context(block, state)

        assert ctx.soul is None, f"CodeBlock ctx.soul must be None (no LLM), got {ctx.soul!r}"

    def test_build_block_context_no_current_task_required(self):
        """CodeBlock does NOT need state.current_task — build_block_context must not raise."""
        block = CodeBlock("cb_ctx", SIMPLE_CODE)
        # Deliberately omit current_task
        state = WorkflowState(results={}, metadata={}, shared_memory={})

        # Must NOT raise ValueError about current_task being None
        ctx = build_block_context(block, state)

        assert isinstance(ctx, BlockContext)


# ===========================================================================
# AC-6: E2E via execute_block
# ===========================================================================


class TestAC6ExecuteBlockDispatch:
    @pytest.mark.asyncio
    async def test_execute_block_calls_build_block_context_for_codeblock(self):
        """execute_block must route CodeBlock through build_block_context (new dispatch path)."""
        block = CodeBlock("cb_dispatch", SIMPLE_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="test_workflow",
            blocks={"cb_dispatch": block},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        with patch(
            "runsight_core.workflow.build_block_context",
            wraps=build_block_context,
        ) as mock_build_ctx:
            result_state = await execute_block(block, state, block_exec_ctx)

        assert mock_build_ctx.called, (
            "execute_block must call build_block_context for CodeBlock (new dispatch path)"
        )
        assert isinstance(result_state, WorkflowState)

    @pytest.mark.asyncio
    async def test_execute_block_calls_apply_block_output_for_codeblock(self):
        """execute_block must call apply_block_output for CodeBlock."""
        block = CodeBlock("cb_apply", SIMPLE_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="test_workflow",
            blocks={"cb_apply": block},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        apply_calls = []
        original_apply = apply_block_output

        def tracking_apply(s, block_id, output):
            apply_calls.append(block_id)
            return original_apply(s, block_id, output)

        with patch("runsight_core.workflow.apply_block_output", side_effect=tracking_apply):
            result_state = await execute_block(block, state, block_exec_ctx)

        assert "cb_apply" in apply_calls, (
            "execute_block must call apply_block_output for CodeBlock (new dispatch path)"
        )
        assert isinstance(result_state, WorkflowState)

    @pytest.mark.asyncio
    async def test_execute_block_result_stored_in_state(self):
        """After execute_block, the CodeBlock result must be in state.results."""
        block = CodeBlock("cb_e2e", SIMPLE_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="test_workflow",
            blocks={"cb_e2e": block},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        result_state = await execute_block(block, state, block_exec_ctx)

        assert isinstance(result_state, WorkflowState)
        assert "cb_e2e" in result_state.results, (
            "execute_block must store CodeBlock result in state.results['cb_e2e']"
        )

    @pytest.mark.asyncio
    async def test_execute_block_cost_not_accumulated_for_codeblock(self):
        """CodeBlock adds no cost — state.total_cost_usd must be unchanged after execute_block."""
        block = CodeBlock("cb_cost_e2e", SIMPLE_CODE)
        state = _make_state()
        state = state.model_copy(update={"total_cost_usd": 2.50, "total_tokens": 300})
        block_exec_ctx = BlockExecutionContext(
            workflow_name="test_workflow",
            blocks={"cb_cost_e2e": block},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        result_state = await execute_block(block, state, block_exec_ctx)

        assert isinstance(result_state, WorkflowState)
        assert result_state.total_cost_usd == pytest.approx(2.50), (
            "CodeBlock must not add cost to state.total_cost_usd"
        )
        assert result_state.total_tokens == 300, (
            "CodeBlock must not add tokens to state.total_tokens"
        )

    @pytest.mark.asyncio
    async def test_execute_block_error_path_sets_exit_handle_in_state(self):
        """execute_block with error code → state.results[block_id].exit_handle='error'."""
        block = CodeBlock("cb_err_e2e", ERROR_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="test_workflow",
            blocks={"cb_err_e2e": block},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        result_state = await execute_block(block, state, block_exec_ctx)

        assert isinstance(result_state, WorkflowState)
        assert "cb_err_e2e" in result_state.results
        assert result_state.results["cb_err_e2e"].exit_handle == "error", (
            "Error path must store exit_handle='error' in state.results"
        )

    @pytest.mark.asyncio
    async def test_execute_block_custom_exit_handle_stored_in_state(self):
        """execute_block with custom exit_handle code → state.results[block_id].exit_handle='custom_exit'."""
        block = CodeBlock("cb_custom_exit_e2e", EXIT_HANDLE_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="test_workflow",
            blocks={"cb_custom_exit_e2e": block},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        result_state = await execute_block(block, state, block_exec_ctx)

        assert isinstance(result_state, WorkflowState)
        assert "cb_custom_exit_e2e" in result_state.results
        assert result_state.results["cb_custom_exit_e2e"].exit_handle == "custom_exit"
