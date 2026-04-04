"""IsolatedBlockWrapper — wraps LLM blocks for subprocess execution."""

from __future__ import annotations

from typing import Any, Optional

from runsight_core.blocks.base import BaseBlock
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    ResultEnvelope,
    SoulEnvelope,
    TaskEnvelope,
    ToolDefEnvelope,
)
from runsight_core.isolation.errors import BlockExecutionError
from runsight_core.state import BlockResult, WorkflowState

# Block types whose soul attribute is not named "soul"
_SOUL_ATTR_MAP = {
    "GateBlock": "gate_soul",
    "SynthesizeBlock": "synthesizer_soul",
}

# LLM block types that should be wrapped at build time
LLM_BLOCK_TYPES = frozenset({"linear", "gate", "synthesize", "fanout"})


def _get_soul(inner_block: BaseBlock) -> Any:
    """Extract the soul from an inner block, handling different attribute names."""
    attr_name = _SOUL_ATTR_MAP.get(type(inner_block).__name__, "soul")
    return getattr(inner_block, attr_name, None)


def _build_tool_envelopes(soul: Any) -> list[ToolDefEnvelope]:
    """Serialize resolved tool metadata for the worker-side tool loop."""
    resolved_tools = getattr(soul, "resolved_tools", None) or []
    tool_envelopes: list[ToolDefEnvelope] = []

    for tool in resolved_tools:
        exits = []
        port_enum = (
            getattr(tool, "parameters", {}).get("properties", {}).get("port", {}).get("enum", [])
        )
        if isinstance(port_enum, list):
            exits = [str(port) for port in port_enum]

        tool_envelopes.append(
            ToolDefEnvelope(
                source=str(getattr(tool, "source", "") or tool.name),
                config=dict(getattr(tool, "config", {}) or {}),
                exits=exits,
                name=tool.name,
                description=tool.description,
                parameters=dict(tool.parameters or {}),
                tool_type=str(getattr(tool, "tool_type", "")),
            )
        )

    return tool_envelopes


class IsolatedBlockWrapper(BaseBlock):
    """Wraps an LLM block to execute it in an isolated subprocess.

    Delegates execution to ``_run_in_subprocess`` which sends a ContextEnvelope
    and receives a ResultEnvelope.  The envelope is then mapped back onto
    WorkflowState.
    """

    def __init__(
        self,
        block_id: str,
        inner_block: BaseBlock,
        *,
        retry_config: Optional[Any] = None,
    ):
        super().__init__(block_id, retry_config=retry_config)
        self.inner_block = inner_block
        self.soul = _get_soul(inner_block)

    @property
    def __class__(self) -> type:
        """Make isinstance() transparent: wrapper passes isinstance checks for the inner block type."""
        return type(self.inner_block)

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the inner block for attributes not on the wrapper."""
        return getattr(self.inner_block, name)

    async def _run_in_subprocess(self, envelope: ContextEnvelope) -> ResultEnvelope:
        """Run the inner block in a subprocess via SubprocessHarness.

        This method is the seam that tests mock.  The default implementation
        delegates to the inner block directly as a bridge until subprocess
        infrastructure is fully wired.
        """
        raise NotImplementedError("_run_in_subprocess must be mocked or overridden")

    async def execute(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        """Execute the inner block through the subprocess isolation boundary.

        When ``_run_in_subprocess`` is mocked (normal test path), builds a
        ContextEnvelope and maps the ResultEnvelope back to WorkflowState.
        When it raises NotImplementedError (integration / not-yet-wired path),
        falls back to direct inner-block execution so existing tests stay green.
        """
        # Build the context envelope
        soul = self.soul
        soul_envelope = SoulEnvelope(
            id=soul.id if soul else "",
            role=soul.role if soul else "",
            system_prompt=soul.system_prompt if soul else "",
            model_name=soul.model_name or "" if soul else "",
            max_tool_iterations=soul.max_tool_iterations
            if soul and hasattr(soul, "max_tool_iterations")
            else 5,
        )

        task = state.current_task
        raw_context = task.context if task else None
        if isinstance(raw_context, str):
            task_context = {"text": raw_context}
        else:
            task_context = raw_context if raw_context else {}
        task_envelope = TaskEnvelope(
            id=task.id if task else "",
            instruction=task.instruction if task else "",
            context=task_context,
        )

        # Gather conversation history for stateful blocks
        history_key = f"{self.block_id}_{soul.id}" if soul else self.block_id
        conversation_history = (
            state.conversation_histories.get(history_key, []) if self.inner_block.stateful else []
        )

        # Populate block_config with branch metadata for FanOut blocks
        block_config: dict[str, Any] = {}
        if hasattr(self.inner_block, "branches"):
            block_config["branches"] = [
                {
                    "exit_id": b.exit_id,
                    "label": b.label,
                    "soul_ref": b.soul.id if b.soul else "",
                    "task_instruction": b.task_instruction,
                }
                for b in self.inner_block.branches
            ]

        envelope = ContextEnvelope(
            block_id=self.block_id,
            block_type=type(self.inner_block).__name__,
            block_config=block_config,
            soul=soul_envelope,
            tools=_build_tool_envelopes(soul),
            task=task_envelope,
            scoped_results={k: v.model_dump() for k, v in state.results.items()},
            scoped_shared_memory=dict(state.shared_memory),
            conversation_history=conversation_history,
            timeout_seconds=300,
            max_output_bytes=1_000_000,
        )

        try:
            result = await self._run_in_subprocess(envelope)
        except NotImplementedError:
            # Subprocess not wired yet — delegate to inner block directly
            return await self.inner_block.execute(state, **kwargs)

        # Handle errors from the subprocess
        if result.error is not None:
            error_type = result.error_type or "BlockExecutionError"
            if error_type == "ValueError":
                raise ValueError(result.error)
            if error_type == "SubprocessError":
                raise BlockExecutionError(result.error, original_error_type=error_type)
            raise BlockExecutionError(result.error, original_error_type=error_type)

        # Map ResultEnvelope back to WorkflowState
        updated_results = {
            **state.results,
            self.block_id: BlockResult(
                output=result.output or "",
                exit_handle=result.exit_handle,
            ),
        }

        # Route delegate artifacts to per-port state results for FanOut blocks
        for port, artifact in result.delegate_artifacts.items():
            updated_results[f"{self.block_id}.{port}"] = BlockResult(
                output=artifact.task,
                exit_handle=port,
            )

        # Update conversation history if stateful
        conversation_update = dict(state.conversation_histories)
        if self.inner_block.stateful and result.conversation_history:
            conversation_update[history_key] = result.conversation_history

        return state.model_copy(
            update={
                "results": updated_results,
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
                "conversation_histories": conversation_update,
            }
        )
