"""
Shared test infrastructure for runsight_core tests.
"""

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from runsight_core.primitives import Soul


# Python 3.14 removed the implicit event-loop creation in get_event_loop().
# Ensure a loop exists so legacy sync tests that call
# ``asyncio.get_event_loop().run_until_complete(...)`` still work.
@pytest.fixture(autouse=True)
def _ensure_event_loop():
    """Guarantee an asyncio event loop is set for every test."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


async def execute_block_for_test(block, state, *, inputs=None, step=None):
    """Execute a block through the BlockContext contract and return WorkflowState.

    Several older unit tests exercise concrete blocks directly.  Keeping that
    adapter in tests lets production code stay on execute(ctx) -> BlockOutput.
    """
    from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context

    ctx = build_block_context(block, state, step=step)
    if inputs:
        ctx = ctx.model_copy(update={"inputs": {**ctx.inputs, **inputs}})

    output = await block.execute(ctx)
    if not isinstance(output, BlockOutput):
        raise TypeError(
            f"{type(block).__name__}.execute returned {type(output).__name__}; expected BlockOutput"
        )
    return apply_block_output(state, block.block_id, output)


async def execute_loop_for_test(loop, state, *, blocks, ctx=None):
    """Execute a LoopBlock through BlockContext with a minimal workflow context."""
    from runsight_core.workflow import BlockExecutionContext

    loop_ctx = ctx or BlockExecutionContext(
        workflow_name="loop_helper_workflow",
        blocks=blocks,
        call_stack=[],
        workflow_registry=None,
        observer=None,
    )
    return await execute_block_for_test(
        loop,
        state,
        inputs={
            "blocks": blocks,
            "ctx": loop_ctx,
        },
    )


def block_output_from_state(block_id, before, after):
    """Convert a test-built WorkflowState diff into a BlockOutput."""
    from runsight_core.block_io import BlockOutput
    from runsight_core.state import BlockResult

    raw_result = after.results.get(block_id, BlockResult(output=""))
    if isinstance(raw_result, BlockResult):
        output = raw_result.output
        exit_handle = raw_result.exit_handle
        artifact_ref = raw_result.artifact_ref
        artifact_type = raw_result.artifact_type
        metadata = raw_result.metadata or {}
    else:
        output = str(raw_result)
        exit_handle = None
        artifact_ref = None
        artifact_type = None
        metadata = {}

    extra_results = {
        key: value
        for key, value in after.results.items()
        if key != block_id and before.results.get(key) != value
    }
    shared_memory_updates = {
        key: value
        for key, value in after.shared_memory.items()
        if before.shared_memory.get(key) != value
    }
    metadata_updates = {
        key: value for key, value in after.metadata.items() if before.metadata.get(key) != value
    }

    return BlockOutput(
        output=output,
        exit_handle=exit_handle,
        artifact_ref=artifact_ref,
        artifact_type=artifact_type,
        metadata=metadata,
        cost_usd=after.total_cost_usd - before.total_cost_usd,
        total_tokens=after.total_tokens - before.total_tokens,
        log_entries=after.execution_log[len(before.execution_log) :],
        extra_results=extra_results or None,
        shared_memory_updates=shared_memory_updates or None,
        metadata_updates=metadata_updates or None,
    )


_ISOLATION_TEST_PREFIXES = (
    "test_isolation_",
    "test_worker_proxies_extract",
    "test_worker_support_extract",
    "test_assertion_isolation",
    "test_tool_builtin_http_pipeline",
    "test_tool_custom_executor_pipeline",
    "test_tool_custom_request_resolution",
    "test_tool_delegate_behavior",
    "test_tool_ipc_tool_calls",
    "test_tool_isolated_execution_envelope",
    "test_tool_parse_validation",
    "test_tool_pipeline_execution",
    "test_tool_request_executor_pipeline",
    "test_tool_runner_behaviors",
    "test_tool_workflow_fixtures",
)


@pytest.fixture(autouse=True)
def _bypass_subprocess_isolation(request, monkeypatch):
    """Keep block execution in-process so litellm mocks are visible.

    Production code spawns a real subprocess via SubprocessHarness where
    parent-process mocks are invisible.  This patches SubprocessHarness.run
    so the wrapper's real execute() path (envelope construction, result
    mapping) is exercised while the subprocess spawn is replaced with an
    in-process call to the inner block.

    Isolation-specific tests are excluded so they exercise the real path.
    """
    if request.fspath.basename.startswith(_ISOLATION_TEST_PREFIXES):
        return

    try:
        from runsight_core.isolation.envelope import (
            ContextEnvelope,
            DelegateArtifact,
            ResultEnvelope,
        )
        from runsight_core.isolation.harness import SubprocessHarness
        from runsight_core.isolation.wrapper import IsolatedBlockWrapper
    except ImportError:
        return

    async def _in_process_harness_run(self, envelope: ContextEnvelope) -> ResultEnvelope:
        """No-op replacement for SubprocessHarness.run.

        Real execution is handled by the patched _run_in_subprocess which
        calls the inner block directly when the harness is a SubprocessHarness.
        This stub exists so that SubprocessHarness.run is patched away from
        the real socket/subprocess implementation, satisfying the harness-boundary invariant.
        """
        return ResultEnvelope(
            block_id=envelope.block_id,
            output="",
            exit_handle="default",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

    async def _patched_run_in_subprocess(
        self: IsolatedBlockWrapper, envelope: ContextEnvelope
    ) -> ResultEnvelope:
        """Execute in-process when harness is real, forward when harness is a test mock.

        When the wrapper's harness is a real SubprocessHarness, this calls the
        inner block directly — litellm mocks in the parent process are visible.
        When the harness is a test-supplied mock (e.g. AsyncMock), it forwards
        to harness.run so test assertions on the mock work correctly.
        """
        if self.harness is None:
            if self._harness_factory is None:
                raise NotImplementedError(
                    "SubprocessHarness is not configured on IsolatedBlockWrapper"
                )
            self.harness = self._harness_factory()

        if type(self.harness).__name__ in ("MagicMock", "AsyncMock"):
            return await self.harness.run(envelope)

        from runsight_core.block_io import BlockOutput, apply_block_output, build_block_context
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.state import BlockResult, WorkflowState

        results: dict[str, BlockResult] = {}
        for key, val in envelope.scoped_results.items():
            if isinstance(val, dict):
                results[key] = BlockResult(
                    output=val.get("output", ""),
                    exit_handle=val.get("exit_handle"),
                )
            else:
                results[key] = BlockResult(output=str(val))

        state = WorkflowState(
            results=results,
            shared_memory=dict(envelope.scoped_shared_memory),
        )

        active_budget = _active_budget.get(None)
        if isinstance(active_budget, BudgetSession):
            active_budget.check_or_raise(block_id=envelope.block_id)

        budget_token = _active_budget.set(None)
        try:
            block_ctx = build_block_context(self.inner_block, state)
            block_ctx = block_ctx.model_copy(
                update={"inputs": {**block_ctx.inputs, **dict(envelope.inputs)}}
            )
            raw_output = await self.inner_block.execute(block_ctx)
            if isinstance(raw_output, WorkflowState):
                result_state = raw_output
            elif isinstance(raw_output, BlockOutput):
                result_state = apply_block_output(state, self.inner_block.block_id, raw_output)
            else:
                result_state = state
        finally:
            _active_budget.reset(budget_token)

        if isinstance(active_budget, BudgetSession):
            active_budget.accrue(
                cost_usd=result_state.total_cost_usd,
                tokens=result_state.total_tokens,
            )

        block_result = result_state.results.get(self.inner_block.block_id, BlockResult(output=""))

        # Extract delegate artifacts (dispatch block per-port results).
        delegate_artifacts: dict[str, DelegateArtifact] = {}
        port_prefix = f"{self.inner_block.block_id}."
        for key, val in result_state.results.items():
            if key.startswith(port_prefix):
                port = key[len(port_prefix) :]
                output_text = val.output if isinstance(val, BlockResult) else str(val)
                delegate_artifacts[port] = DelegateArtifact(prompt=output_text)

        # Mirror the real worker: successful isolated blocks default to "done"
        # when the inner block does not emit an explicit exit handle.
        return SimpleNamespace(
            block_id=envelope.block_id,
            output=block_result.output,
            exit_handle=block_result.exit_handle or "done",
            cost_usd=result_state.total_cost_usd,
            total_tokens=result_state.total_tokens,
            tool_calls_made=0,
            delegate_artifacts=delegate_artifacts,
            conversation_history=[],
            error=None,
            error_type=None,
        )

    monkeypatch.setattr(SubprocessHarness, "run", _in_process_harness_run)
    monkeypatch.setattr(IsolatedBlockWrapper, "_run_in_subprocess", _patched_run_in_subprocess)


def make_test_yaml(steps_yaml: str) -> str:
    """Wrap step YAML with a standard souls section containing a helper analyst.

    Args:
        steps_yaml: Block definitions YAML (indented with 2 spaces per block).

    Returns:
        Full workflow YAML string that includes a helper analyst soul definition,
        so that ``parse_workflow_yaml`` can resolve ``soul_ref: helper_analyst``.
    """
    # Extract block names from the steps_yaml for transitions
    import re

    block_names = re.findall(r"^  (\w+):", steps_yaml, re.MULTILINE)
    entry = block_names[0] if block_names else "my_block"

    # Build transitions: chain blocks linearly, last one is terminal
    transitions = ""
    for i, name in enumerate(block_names):
        if i < len(block_names) - 1:
            transitions += f"    - from: {name}\n      to: {block_names[i + 1]}\n"
        else:
            transitions += f"    - from: {name}\n      to: null\n"

    return f"""\
version: "1.0"
id: inline-helper-workflow
kind: workflow
souls:
  helper_analyst:
    id: helper_analyst
    kind: soul
    name: Helper Analyst
    role: Analyst
    system_prompt: Analyze the workflow step.
blocks:
{steps_yaml}
workflow:
  name: inline_helper_workflow
  entry: {entry}
  transitions:
{transitions}"""


@pytest.fixture
def tmp_path(request):
    """Override tmp_path with a shorter base to avoid AF_UNIX path length limits on macOS."""
    with tempfile.TemporaryDirectory(prefix="rs_") as d:
        yield Path(d)


@pytest.fixture
def helper_souls_map():
    """Provide a souls map with a helper analyst for tests that construct blocks directly."""
    return {
        "helper_analyst": Soul(
            id="helper_analyst",
            kind="soul",
            name="Helper Analyst",
            role="Analyst",
            system_prompt="Analyze the workflow step.",
        )
    }
