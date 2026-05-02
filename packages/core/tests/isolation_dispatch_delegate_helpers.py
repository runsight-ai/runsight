"""DispatchBlock isolation and delegate artifact routing tests.

The suite verifies one subprocess envelope is used for dispatch coordination,
delegate artifacts are routed to per-port state results, missing ports are
skipped, collapsed artifact values are routed, and the subprocess pool
concurrency limit is enforced.
"""

import asyncio
from unittest.mock import MagicMock

from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.blocks.dispatch import DispatchBlock
from runsight_core.isolation.envelope import ResultEnvelope
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState

# Shared fixtures


def _make_soul(soul_id: str = "coordinator") -> Soul:
    return Soul(
        id=soul_id if len(soul_id) >= 3 else f"soul-{soul_id}",
        kind="soul",
        name="Coordinator",
        role="Coordinator",
        system_prompt="You coordinate parallel dispatch tasks.",
        model_name="gpt-4o-mini",
    )


def _make_state(task_instruction: str = "Coordinate work") -> WorkflowState:
    return WorkflowState()


def _make_result_envelope(
    block_id: str = "research_dispatch",
    delegate_artifacts: dict | None = None,
    output: str = "coordination complete",
    exit_handle: str = "done",
) -> ResultEnvelope:
    return ResultEnvelope(
        block_id=block_id,
        output=output,
        exit_handle=exit_handle,
        cost_usd=0.005,
        total_tokens=200,
        tool_calls_made=len(delegate_artifacts) if delegate_artifacts else 0,
        delegate_artifacts=delegate_artifacts or {},
        conversation_history=[],
        error=None,
        error_type=None,
    )


def _execute_wrapper(wrapper, state):
    """Run wrapper.execute synchronously."""

    async def _run():
        ctx = build_block_context(wrapper, state)
        output = await wrapper.execute(ctx)
        return apply_block_output(state, wrapper.block_id, output)

    return asyncio.get_event_loop().run_until_complete(_run())


def _make_wrapped_dispatch(branches):
    """Create a DispatchBlock wrapped in IsolatedBlockWrapper."""
    from runsight_core.isolation.wrapper import IsolatedBlockWrapper

    runner = MagicMock()
    inner = DispatchBlock("research_dispatch", branches, runner)
    return IsolatedBlockWrapper("research_dispatch", inner)


# ==============================================================================
# Dispatch sends one subprocess envelope with all branch metadata
# ==============================================================================
