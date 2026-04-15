"""IsolatedBlockWrapper — wraps LLM blocks for subprocess execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from runsight_core.blocks.base import BaseBlock
from runsight_core.budget_enforcement import budget_killed_exception_from_message
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    PromptEnvelope,
    ResultEnvelope,
    SoulEnvelope,
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
LLM_BLOCK_TYPES = frozenset({"linear", "gate", "synthesize", "dispatch"})


_BLOCK_TYPE_MAP = {
    "LinearBlock": "linear",
    "GateBlock": "gate",
    "SynthesizeBlock": "synthesize",
    "DispatchBlock": "dispatch",
}


def _get_soul(inner_block: BaseBlock) -> Any:
    """Extract the soul from an inner block, handling different attribute names."""
    if type(inner_block).__name__ == "DispatchBlock":
        branches = getattr(inner_block, "branches", [])
        if branches:
            return getattr(branches[0], "soul", None)
    attr_name = _SOUL_ATTR_MAP.get(type(inner_block).__name__, "soul")
    return getattr(inner_block, attr_name, None)


def _collect_resolved_tools(inner_block: BaseBlock, soul: Any) -> list[Any]:
    if type(inner_block).__name__ == "DispatchBlock":
        tools_by_name: dict[str, Any] = {}
        for branch in getattr(inner_block, "branches", []):
            branch_soul = getattr(branch, "soul", None)
            for tool in getattr(branch_soul, "resolved_tools", None) or []:
                tools_by_name[tool.name] = tool
        return list(tools_by_name.values())
    return list(getattr(soul, "resolved_tools", None) or [])


def _build_tool_envelopes_from_tools(resolved_tools: list[Any]) -> list[ToolDefEnvelope]:
    """Serialize resolved tool metadata for the worker-side tool loop."""
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


def _build_tool_envelopes(soul: Any) -> list[ToolDefEnvelope]:
    return _build_tool_envelopes_from_tools(list(getattr(soul, "resolved_tools", None) or []))


def _serialize_scoped_results(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize workflow results for the subprocess envelope.

    WorkflowBlock output mappings may write plain strings/dicts back into
    ``state.results`` instead of BlockResult instances. The isolation envelope
    still needs a uniform object shape for worker-side reconstruction.
    """
    serialized: dict[str, dict[str, Any]] = {}
    for key, value in results.items():
        if isinstance(value, BlockResult):
            serialized[key] = value.model_dump()
        else:
            serialized[key] = {"output": value}
    return serialized


def _serialize_soul_summary(soul: Any) -> dict[str, Any]:
    return {
        "id": getattr(soul, "id", ""),
        "role": getattr(soul, "role", ""),
        "system_prompt": getattr(soul, "system_prompt", ""),
        "model_name": getattr(soul, "model_name", ""),
        "provider": getattr(soul, "provider", "") or "",
        "temperature": getattr(soul, "temperature", None),
        "max_tokens": getattr(soul, "max_tokens", None),
        "required_tool_calls": list(getattr(soul, "required_tool_calls", None) or []),
        "max_tool_iterations": getattr(soul, "max_tool_iterations", 5),
    }


def _build_block_metadata(inner_block: BaseBlock) -> tuple[str, dict[str, Any]]:
    block_class_name = type(inner_block).__name__
    block_type = _BLOCK_TYPE_MAP.get(
        block_class_name, block_class_name.removesuffix("Block").lower()
    )
    block_config: dict[str, Any] = {}
    limits = getattr(inner_block, "limits", None)
    if limits is not None:
        block_config["limits"] = (
            limits.model_dump(exclude_none=True) if hasattr(limits, "model_dump") else limits
        )

    if block_type == "gate":
        block_config.update(
            {
                "eval_key": getattr(inner_block, "eval_key", ""),
                "extract_field": getattr(inner_block, "extract_field", None),
            }
        )
    elif block_type == "synthesize":
        block_config.update(
            {
                "input_block_ids": list(getattr(inner_block, "input_block_ids", [])),
                "synthesizer_soul": _serialize_soul_summary(
                    getattr(inner_block, "synthesizer_soul", None)
                ),
            }
        )
    elif block_type == "dispatch" and hasattr(inner_block, "branches"):
        block_config["branches"] = [
            {
                "exit_id": branch.exit_id,
                "label": branch.label,
                "task_instruction": branch.task_instruction,
                "soul": _serialize_soul_summary(branch.soul),
            }
            for branch in inner_block.branches
        ]

    return block_type, block_config


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
        harness: Any | None = None,
        harness_factory: Callable[[], Any] | None = None,
        retry_config: Optional[Any] = None,
    ):
        super().__init__(block_id, retry_config=retry_config)
        self.inner_block = inner_block
        self.soul = _get_soul(inner_block)
        self.harness = harness
        self._harness_factory = harness_factory

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the inner block for attributes not on the wrapper."""
        return getattr(self.inner_block, name)

    async def _run_in_subprocess(self, envelope: ContextEnvelope) -> ResultEnvelope:
        """Run the inner block in a subprocess via SubprocessHarness."""
        if self.harness is None:
            if self._harness_factory is None:
                raise NotImplementedError(
                    "SubprocessHarness is not configured on IsolatedBlockWrapper"
                )
            self.harness = self._harness_factory()
        return await self.harness.run(envelope)

    async def execute(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        """Execute the inner block through the subprocess isolation boundary.

        Builds a ContextEnvelope, executes the subprocess path, and maps the
        ResultEnvelope back to WorkflowState.
        """
        # Build the context envelope
        soul = self.soul
        soul_envelope = SoulEnvelope(
            id=soul.id if soul else "",
            role=soul.role if soul else "",
            name=soul.name if soul else None,
            system_prompt=soul.system_prompt if soul else "",
            model_name=soul.model_name or "" if soul else "",
            provider=soul.provider or "" if soul else "",
            temperature=soul.temperature if soul else None,
            max_tokens=soul.max_tokens if soul else None,
            required_tool_calls=list(soul.required_tool_calls or []) if soul else [],
            max_tool_iterations=soul.max_tool_iterations
            if soul and hasattr(soul, "max_tool_iterations")
            else 5,
        )

        task_envelope = PromptEnvelope(
            id="",
            instruction="",
            context={},
        )

        # Gather conversation history for stateful blocks
        history_key = f"{self.block_id}_{soul.id}" if soul else self.block_id
        conversation_history = (
            state.conversation_histories.get(history_key, []) if self.inner_block.stateful else []
        )

        block_type, block_config = _build_block_metadata(self.inner_block)
        resolved_tools = _collect_resolved_tools(self.inner_block, soul)

        if (
            self.harness is not None
            and soul is not None
            and hasattr(self.harness, "_resolved_tools")
        ):
            self.harness._resolved_tools = {tool.name: tool for tool in resolved_tools}

        envelope = ContextEnvelope(
            block_id=self.block_id,
            block_type=block_type,
            block_config=block_config,
            soul=soul_envelope,
            tools=_build_tool_envelopes_from_tools(resolved_tools),
            prompt=task_envelope,
            scoped_results=_serialize_scoped_results(state.results),
            scoped_shared_memory=dict(state.shared_memory),
            conversation_history=conversation_history,
            timeout_seconds=300,
            max_output_bytes=1_000_000,
        )

        result = await self._run_in_subprocess(envelope)

        # Handle errors from the subprocess
        if result.error is not None:
            error_type = result.error_type or "BlockExecutionError"
            if error_type == "BudgetKilledException":
                budget_exc = budget_killed_exception_from_message(result.error)
                if budget_exc is not None:
                    raise budget_exc
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

        # Route delegate artifacts to per-port state results for dispatch blocks
        for port, artifact in result.delegate_artifacts.items():
            updated_results[f"{self.block_id}.{port}"] = BlockResult(
                output=artifact.prompt,
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
