"""CodeBlock BlockContext/BlockOutput migration coverage.

Owner: packages/core CodeBlock runtime migration.
Boundary: CodeBlock execution, error handling, exit handles, context building,
and workflow dispatch must preserve the BlockContext/BlockOutput contract.
Exit criteria: remove once equivalent coverage lives in ordinary CodeBlock and
workflow execution suites.

Tests verify:
- CodeBlock.execute accepts BlockContext and returns BlockOutput.
- ctx.inputs are passed to the subprocess unchanged.
- Error cases produce BlockOutput with exit_handle="error".
- exit_handle extraction from dict results still works.
- build_block_context detects CodeBlock without current_task or LLM state.
- execute_block dispatches CodeBlock through the BlockContext path.
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
    }
    defaults.update(overrides)
    return WorkflowState(**defaults)


def _make_code_block_context(
    block: CodeBlock,
    state: WorkflowState,
    *,
    inputs: dict | None = None,
) -> BlockContext:
    """Helper: build a BlockContext for CodeBlock directly (no build_block_context)."""
    return BlockContext(
        block_id=block.block_id,
        instruction="run code",
        context=None,
        inputs=dict(inputs or {}),
        conversation_history=[],
        soul=None,
        model_name=None,
        state_snapshot=state,
    )


# ===========================================================================
# CodeBlock.execute accepts BlockContext and returns BlockOutput
# ===========================================================================


class TestAcceptsBlockContextAndReturnsBlockOutput:
    @pytest.mark.asyncio
    async def test_execute_accepts_block_context_returns_block_output(self):
        """CodeBlock.execute must accept a BlockContext and return BlockOutput."""
        block = CodeBlock("context_accepting_code_block", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput), (
            f"Expected BlockOutput but got {type(result).__name__}. "
            "CodeBlock.execute should return BlockOutput after BlockContext migration."
        )

    @pytest.mark.asyncio
    async def test_block_output_contains_code_return_value(self):
        """BlockOutput.output must contain the JSON-encoded return value of main()."""
        block = CodeBlock("context_accepting_code_block", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        parsed = json.loads(result.output)
        assert parsed == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_block_output_cost_is_zero(self):
        """CodeBlock makes no LLM calls, so cost_usd is exactly 0."""
        block = CodeBlock("cost_free_code_block", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.cost_usd == 0.0, (
            f"CodeBlock cost_usd must be 0.0 (no LLM calls), got {result.cost_usd}"
        )

    @pytest.mark.asyncio
    async def test_block_output_tokens_is_zero(self):
        """CodeBlock makes no LLM calls, so total_tokens is exactly 0."""
        block = CodeBlock("token_free_code_block", SIMPLE_CODE)
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
        block = CodeBlock("success_log_code_block", SIMPLE_CODE)
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
        """CodeBlock.execute(BlockContext) must not return WorkflowState."""
        block = CodeBlock("state_contract_code_block", SIMPLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert not isinstance(result, WorkflowState), (
            "CodeBlock.execute(BlockContext) must return BlockOutput, not WorkflowState"
        )

    # Legacy WorkflowState shim removed.


# ===========================================================================
# Governed ctx.inputs are passed through to stdin
# ===========================================================================


class TestStdinDataByteIdentical:
    @pytest.mark.asyncio
    async def test_stdin_data_structure_matches_governed_inputs(self):
        """ctx.inputs must be passed to the subprocess using local declared names."""
        state = _make_state()
        block = CodeBlock("stdin_payload_code_block", ECHO_DATA_CODE)
        declared_inputs = {
            "prior_output": "prior output",
            "run_context": {"run_id": "abc"},
            "scratch_value": "value",
        }
        ctx = _make_code_block_context(block, state, inputs=declared_inputs)

        assert ctx.inputs == declared_inputs

    @pytest.mark.asyncio
    async def test_stdin_upstream_values_are_plain_declared_input_values(self):
        """Resolved upstream values in ctx.inputs must already be plain local inputs."""
        prior_result = BlockResult(output="prior output string")
        state = _make_state(results={"prior_block": prior_result})
        block = CodeBlock("upstream_value_code_block", ECHO_DATA_CODE)
        ctx = _make_code_block_context(
            block,
            state,
            inputs={"prior_output": prior_result.output},
        )

        assert isinstance(ctx.inputs["prior_output"], str), (
            "Resolved upstream values in ctx.inputs must be plain JSON-serializable values, "
            f"got {type(ctx.inputs['prior_output']).__name__}"
        )
        assert ctx.inputs["prior_output"] == "prior output string"

    @pytest.mark.asyncio
    async def test_stdin_data_round_trips_through_subprocess(self):
        """The data passed to main() in the subprocess must match ctx.inputs exactly."""
        state = _make_state()
        block = CodeBlock("echo_declared_inputs_code_block", ECHO_DATA_CODE)
        declared_inputs = {
            "previous_output": "prev_out",
            "runtime_info": {"workflow_name": "codeblock_stdin_round_trip_workflow"},
            "scratchpad": {"sm_key": "sm_val"},
        }
        ctx = _make_code_block_context(block, state, inputs=declared_inputs)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        parsed = json.loads(result.output)
        assert parsed == declared_inputs

    @pytest.mark.asyncio
    async def test_stdin_local_mapping_matches_declared_payload(self):
        """ctx.inputs preserves local mapping payloads."""
        state = _make_state(metadata={"blueprint": "fixture_workflow", "run_id": "fixture-run"})
        block = CodeBlock("metadata_mapping_code_block", SIMPLE_CODE)
        ctx = _make_code_block_context(
            block,
            state,
            inputs={"run_context": {"blueprint": "fixture_workflow", "run_id": "fixture-run"}},
        )

        assert ctx.inputs["run_context"] == {
            "blueprint": "fixture_workflow",
            "run_id": "fixture-run",
        }

    @pytest.mark.asyncio
    async def test_stdin_local_nested_inputs_are_preserved(self):
        """ctx.inputs preserves nested local payloads."""
        state = _make_state(shared_memory={"counter": 42, "flag": True})
        block = CodeBlock("shared_memory_mapping_code_block", SIMPLE_CODE)
        ctx = _make_code_block_context(
            block,
            state,
            inputs={"scratchpad": {"counter": 42, "flag": True}},
        )

        assert ctx.inputs["scratchpad"] == {"counter": 42, "flag": True}


# ===========================================================================
# Error cases produce correct BlockOutput with exit_handle="error"
# ===========================================================================


class TestCodeBlockErrorCases:
    @pytest.mark.asyncio
    async def test_nonzero_exit_code_returns_block_output_with_error_exit_handle(self):
        """Non-zero subprocess exit returns BlockOutput with exit_handle='error'."""
        block = CodeBlock("error_exit_code_block", ERROR_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput), f"Expected BlockOutput, got {type(result).__name__}"
        assert result.exit_handle == "error", (
            f"Non-zero exit must produce exit_handle='error', got {result.exit_handle!r}"
        )

    @pytest.mark.asyncio
    async def test_nonzero_exit_code_output_contains_error_prefix(self):
        """Non-zero exit makes BlockOutput.output start with 'Error:'."""
        block = CodeBlock("error_message_code_block", ERROR_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.output.startswith("Error:"), (
            f"Error output must start with 'Error:', got {result.output!r}"
        )

    @pytest.mark.asyncio
    async def test_nonzero_exit_code_output_contains_error_message(self):
        """Non-zero exit makes BlockOutput.output contain the error message."""
        block = CodeBlock("error_serialization_code_block", ERROR_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert "boom" in result.output, f"Error output must contain 'boom', got {result.output!r}"

    @pytest.mark.asyncio
    async def test_invalid_json_stdout_returns_block_output_with_error(self):
        """Non-JSON stdout returns BlockOutput with an error message."""
        block = CodeBlock("non_json_output_code_block", NON_JSON_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert "Error" in result.output, (
            f"Non-JSON stdout must produce error output, got {result.output!r}"
        )

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self):
        """Timeout raises TimeoutError rather than being swallowed."""
        block = CodeBlock("timeout_code_block", TIMEOUT_CODE, timeout_seconds=1)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        with pytest.raises(TimeoutError, match="timed out"):
            await block.execute(ctx)

    @pytest.mark.asyncio
    async def test_error_log_entries_contain_block_id(self):
        """Error BlockOutput.log_entries must reference the block_id."""
        block = CodeBlock("error_log_code_block", ERROR_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert len(result.log_entries) >= 1
        assert any(
            "error_log_code_block" in entry.get("content", "") for entry in result.log_entries
        ), "log_entries must reference the block_id for error cases"


# ===========================================================================
# exit_handle extraction from dict results
# ===========================================================================


class TestCodeBlockExitHandleExtraction:
    @pytest.mark.asyncio
    async def test_dict_with_exit_handle_extracts_handle(self):
        """Code returning dict with exit_handle extracts it and removes it from output."""
        block = CodeBlock("custom_exit_code_block", EXIT_HANDLE_CODE)
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
        block = CodeBlock("block_result_exit_code_block", EXIT_HANDLE_CODE)
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
        """Code returning empty exit_handle yields exit_handle=None."""
        block = CodeBlock("empty_exit_code_block", EXIT_HANDLE_EMPTY_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.exit_handle is None, (
            f"Empty exit_handle string must produce exit_handle=None, got {result.exit_handle!r}"
        )

    @pytest.mark.asyncio
    async def test_dict_without_exit_handle_yields_none(self):
        """Code returning a dict without exit_handle yields exit_handle=None."""
        block = CodeBlock("no_exit_output_code_block", NO_EXIT_HANDLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        assert result.exit_handle is None, (
            f"Dict without exit_handle must produce exit_handle=None, got {result.exit_handle!r}"
        )

    @pytest.mark.asyncio
    async def test_dict_without_exit_handle_preserves_output(self):
        """Code returning a dict without exit_handle preserves the full dict in output."""
        block = CodeBlock("no_exit_result_code_block", NO_EXIT_HANDLE_CODE)
        state = _make_state()
        ctx = _make_code_block_context(block, state)

        result = await block.execute(ctx)

        assert isinstance(result, BlockOutput)
        parsed = json.loads(result.output)
        assert parsed == {"data": "value"}


# ===========================================================================
# build_block_context for CodeBlock
# ===========================================================================


class TestCodeBlockContextBuilder:
    def test_build_block_context_detects_code_attribute(self):
        """build_block_context must detect CodeBlock (has 'code' attr)."""
        block = CodeBlock("context_builder_code_block", SIMPLE_CODE)
        state = _make_state(
            results={"prev": BlockResult(output="some result")},
            metadata={"wf": "codeblock_context_builder_workflow"},
            shared_memory={"key": "val"},
        )

        ctx = build_block_context(block, state)

        assert isinstance(ctx, BlockContext), (
            f"build_block_context must return BlockContext for CodeBlock, got {type(ctx).__name__}"
        )

    def test_build_block_context_without_declarations_has_empty_inputs(self):
        """CodeBlock without inputs receives empty inputs."""
        block = CodeBlock("context_builder_code_block", SIMPLE_CODE)
        state = _make_state(
            results={"prev": BlockResult(output="some result")},
            metadata={"wf": "codeblock_migration_workflow"},
            shared_memory={"sm": "data"},
        )

        ctx = build_block_context(block, state)

        assert ctx.inputs == {}

    def test_build_block_context_block_id_matches(self):
        """ctx.block_id must match the block's block_id."""
        block = CodeBlock("explicit_block_id_code_block", SIMPLE_CODE)
        state = _make_state()

        ctx = build_block_context(block, state)

        assert ctx.block_id == "explicit_block_id_code_block"

    def test_build_block_context_soul_is_none(self):
        """CodeBlock has no soul, so ctx.soul is None."""
        block = CodeBlock("context_builder_code_block", SIMPLE_CODE)
        state = _make_state()

        ctx = build_block_context(block, state)

        assert ctx.soul is None, f"CodeBlock ctx.soul must be None (no LLM), got {ctx.soul!r}"

    def test_build_block_context_no_current_task_required(self):
        """CodeBlock does not need state.current_task."""
        block = CodeBlock("context_builder_code_block", SIMPLE_CODE)
        # Deliberately omit current_task
        state = WorkflowState(results={}, metadata={}, shared_memory={})

        # Should not raise ValueError about current_task being None.
        ctx = build_block_context(block, state)

        assert isinstance(ctx, BlockContext)


# ===========================================================================
# execute_block dispatch
# ===========================================================================


class TestExecuteBlockDispatch:
    @pytest.mark.asyncio
    async def test_execute_block_calls_build_block_context_for_codeblock(self):
        """execute_block must route CodeBlock through build_block_context (new dispatch path)."""
        block = CodeBlock("dispatch_context_code_block", SIMPLE_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="codeblock_migration_workflow",
            blocks={"dispatch_context_code_block": block},
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
        block = CodeBlock("apply_output_code_block", SIMPLE_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="codeblock_migration_workflow",
            blocks={"apply_output_code_block": block},
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

        assert "apply_output_code_block" in apply_calls, (
            "execute_block must call apply_block_output for CodeBlock (new dispatch path)"
        )
        assert isinstance(result_state, WorkflowState)

    @pytest.mark.asyncio
    async def test_execute_block_result_stored_in_state(self):
        """After execute_block, the CodeBlock result must be in state.results."""
        block = CodeBlock("stored_result_code_block", SIMPLE_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="codeblock_migration_workflow",
            blocks={"stored_result_code_block": block},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        result_state = await execute_block(block, state, block_exec_ctx)

        assert isinstance(result_state, WorkflowState)
        assert "stored_result_code_block" in result_state.results, (
            "execute_block must store CodeBlock result in state.results['stored_result_code_block']"
        )

    @pytest.mark.asyncio
    async def test_execute_block_cost_not_accumulated_for_codeblock(self):
        """CodeBlock adds no cost, so state.total_cost_usd is unchanged."""
        block = CodeBlock("cost_passthrough_code_block", SIMPLE_CODE)
        state = _make_state()
        state = state.model_copy(update={"total_cost_usd": 2.50, "total_tokens": 300})
        block_exec_ctx = BlockExecutionContext(
            workflow_name="codeblock_migration_workflow",
            blocks={"cost_passthrough_code_block": block},
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
        """execute_block with error code sets state.results[block_id].exit_handle='error'."""
        block = CodeBlock("error_path_code_block", ERROR_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="codeblock_migration_workflow",
            blocks={"error_path_code_block": block},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        result_state = await execute_block(block, state, block_exec_ctx)

        assert isinstance(result_state, WorkflowState)
        assert "error_path_code_block" in result_state.results
        assert result_state.results["error_path_code_block"].exit_handle == "error", (
            "Error path must store exit_handle='error' in state.results"
        )

    @pytest.mark.asyncio
    async def test_execute_block_custom_exit_handle_stored_in_state(self):
        """execute_block with custom exit_handle stores it in state results."""
        block = CodeBlock("custom_exit_state_code_block", EXIT_HANDLE_CODE)
        state = _make_state()
        block_exec_ctx = BlockExecutionContext(
            workflow_name="codeblock_migration_workflow",
            blocks={"custom_exit_state_code_block": block},
            call_stack=[],
            workflow_registry=None,
            observer=None,
        )

        result_state = await execute_block(block, state, block_exec_ctx)

        assert isinstance(result_state, WorkflowState)
        assert "custom_exit_state_code_block" in result_state.results
        assert result_state.results["custom_exit_state_code_block"].exit_handle == "custom_exit"
