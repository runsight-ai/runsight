"""
Shared test infrastructure for runsight_core tests.
"""

import asyncio
import tempfile
from pathlib import Path

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


_REAL_WORKSPACE_RUNTIME_MARKER = "real_workspace_runtime"
_LEGACY_REAL_SUBPROCESS_ISOLATION_MARKER = "real_subprocess_isolation"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_workspace_runtime: tests that must exercise the real Unix-local workspace runtime",
    )


def _uses_real_workspace_runtime(request: pytest.FixtureRequest) -> bool:
    """Return whether a test explicitly opts into the real workspace runtime."""
    return (
        request.node.get_closest_marker(_REAL_WORKSPACE_RUNTIME_MARKER) is not None
        or request.node.get_closest_marker(_LEGACY_REAL_SUBPROCESS_ISOLATION_MARKER) is not None
    )


def _uses_real_subprocess_isolation(request: pytest.FixtureRequest) -> bool:
    """Compatibility alias for older real-boundary tests."""
    return _uses_real_workspace_runtime(request)


@pytest.fixture(autouse=True)
def _bypass_subprocess_isolation(request, monkeypatch):
    """Keep block execution in-process so litellm mocks are visible.

    Production code spawns a real worker via the workspace harness where
    parent-process mocks are invisible.  This patches UnixLocalHarness.run so
    the wrapper's real execute() and _run_in_subprocess paths (request
    construction, harness delegation, result mapping) are exercised while the
    worker launch is replaced with an in-process worker simulation.

    Tests that must exercise the real workspace runtime opt out with the
    real_workspace_runtime marker.
    """
    if _uses_real_workspace_runtime(request):
        return

    try:
        from runsight_core.isolation.envelope import (
            DelegateArtifact,
            ResultEnvelope,
        )
        from runsight_core.isolation.workspace import (
            UnixLocalHarness,
            WorkspaceMaterializer,
            WorkspaceRunRequest,
        )
    except ImportError:
        return

    class _InProcessIPCClient:
        """Tiny IPC client facade backed by the harness's host-side handlers."""

        def __init__(self, handlers):
            self._handlers = handlers

        async def request(self, name, payload):
            handler = self._handlers[name]
            result = handler(payload)
            if hasattr(result, "__await__"):
                return await result
            return result

        async def request_stream(self, name, payload):
            handler = self._handlers[name]
            stream = handler(payload)
            if hasattr(stream, "__await__"):
                stream = await stream
            async for chunk in stream:
                yield chunk

        async def connect(self):
            return {"accepted": True, "error": None}

        async def close(self):
            return None

    async def _in_process_workspace_run(self: UnixLocalHarness, request: WorkspaceRunRequest):
        """Run the worker logic in-process at the workspace harness boundary."""
        from runsight_core.block_io import BlockContext, BlockOutput, build_block_context
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation import worker_proxies as _proxies
        from runsight_core.isolation import worker_support as _support
        from runsight_core.state import BlockResult

        session = self._session_factory.create(request.manifest, request.policy)
        session = WorkspaceMaterializer(session).materialize(
            request.manifest,
            policy=request.policy,
        )
        envelope = self._worker_envelope(request)
        ipc_client = _InProcessIPCClient(self._build_ipc_handlers(request=request, session=session))

        try:
            resolved_tools = _proxies.create_tool_stubs(envelope.tools, ipc_client=ipc_client)
            soul = _support.reconstruct_soul(envelope.soul, resolved_tools=resolved_tools)
            runner = _proxies.create_runner(
                model_name=envelope.soul.model_name,
                ipc_client=ipc_client,
            )
            state = _support.build_scoped_state(envelope)

            history_key = f"{envelope.block_id}_{envelope.soul.id}"
            history = state.conversation_histories.get(history_key, [])
            budgeted_history = history
            if history:
                budgeted_history = _support.build_budgeted_history(
                    model=envelope.soul.model_name,
                    system_prompt=soul.system_prompt,
                    instruction=envelope.prompt.instruction,
                    conversation_history=history,
                )

            active_budget = _active_budget.get(None)
            if isinstance(active_budget, BudgetSession):
                active_budget.check_or_raise(block_id=envelope.block_id)

            budget_token = _active_budget.set(None)
            try:
                block = _support._create_block(envelope, soul, runner)
                block_type = _support._BLOCK_TYPE_MAP.get(
                    envelope.block_type.lower(),
                    envelope.block_type.lower(),
                )
                if block_type == "assertion":
                    raw_context = envelope.prompt.context
                    context_text = (
                        raw_context.get("text") if isinstance(raw_context, dict) else None
                    )
                    block_ctx = BlockContext(
                        block_id=envelope.block_id,
                        instruction=envelope.prompt.instruction,
                        context=context_text,
                        inputs=dict(envelope.inputs),
                        conversation_history=budgeted_history,
                        soul=soul,
                        model_name=envelope.soul.model_name,
                        state_snapshot=state,
                    )
                else:
                    base_ctx = build_block_context(block, state)
                    block_ctx = base_ctx.model_copy(
                        update={
                            "inputs": {**base_ctx.inputs, **dict(envelope.inputs)},
                            "conversation_history": budgeted_history,
                        }
                    )
                block_output = await block.execute(block_ctx)
            finally:
                _active_budget.reset(budget_token)

            if not isinstance(block_output, BlockOutput):
                return ResultEnvelope(
                    block_id=envelope.block_id,
                    output=None,
                    exit_handle="error",
                    cost_usd=0.0,
                    total_tokens=0,
                    tool_calls_made=0,
                    delegate_artifacts={},
                    conversation_history=[],
                    error=f"worker block returned {type(block_output).__name__}",
                    error_type="TypeError",
                )

            if isinstance(active_budget, BudgetSession):
                active_budget.accrue(
                    cost_usd=block_output.cost_usd,
                    tokens=block_output.total_tokens,
                )

            delegate_artifacts: dict[str, DelegateArtifact] = {}
            if block_type == "dispatch" and block_output.extra_results:
                port_prefix = f"{envelope.block_id}."
                for key, val in block_output.extra_results.items():
                    if key.startswith(port_prefix):
                        port = key[len(port_prefix) :]
                        output_text = val.output if isinstance(val, BlockResult) else str(val)
                        delegate_artifacts[port] = DelegateArtifact(prompt=output_text)

            conversation_history = list(budgeted_history)
            if (
                block_output.conversation_updates
                and history_key in block_output.conversation_updates
            ):
                conversation_history += block_output.conversation_updates[history_key]
            elif (
                block_output.conversation_replacements
                and history_key in block_output.conversation_replacements
            ):
                conversation_history = block_output.conversation_replacements[history_key]

            return ResultEnvelope(
                block_id=envelope.block_id,
                output=block_output.output if block_output.output else None,
                exit_handle=block_output.exit_handle or "done",
                cost_usd=block_output.cost_usd,
                total_tokens=block_output.total_tokens,
                tool_calls_made=0,
                delegate_artifacts=delegate_artifacts,
                conversation_history=conversation_history,
                error=None,
                error_type=None,
            )
        finally:
            if self._should_cleanup(succeeded=True):
                try:
                    session.host_root.rmdir()
                except OSError:
                    pass

    monkeypatch.setattr(UnixLocalHarness, "run", _in_process_workspace_run)


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
