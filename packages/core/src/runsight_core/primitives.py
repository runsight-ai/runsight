"""
Core primitives for Runsight Agent OS.
"""

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from runsight_core.identity import EntityKind, validate_entity_id

if TYPE_CHECKING:
    from runsight_core.blocks.base import BaseBlock
    from runsight_core.state import WorkflowState


class Soul(BaseModel):
    """
    Represents an agent's persona, capabilities, and expected output schema.
    """

    id: str = Field(..., description="Unique identifier for the soul (e.g., 'researcher_v1')")
    kind: Literal["soul"] = Field(..., description="Entity kind for a soul primitive")
    name: str = Field(..., description="Display name for the soul")
    role: str = Field(..., description="The role of the agent (e.g., 'Senior Researcher')")
    system_prompt: str = Field(
        ..., description="The system instructions defining the agent's behavior and constraints"
    )
    tools: Optional[List[str]] = Field(
        default=None, description="Optional list of tool name references"
    )
    required_tool_calls: Optional[List[str]] = Field(
        default=None,
        description="Optional list of LLM-facing tool function names that must be called before completion",
    )
    max_tool_iterations: int = Field(
        default=5, description="Maximum number of tool-use iterations per execution"
    )
    model_name: Optional[str] = Field(
        default=None, description="Optional model override (uses runner default if None)"
    )
    provider: Optional[str] = Field(
        default=None, description="Optional provider override for the selected model"
    )
    temperature: Optional[float] = Field(
        default=None, description="Optional sampling temperature override"
    )
    max_tokens: Optional[int] = Field(
        default=None, description="Optional output token limit override"
    )
    avatar_color: Optional[str] = Field(
        default=None, description="Optional UI color hint for displaying the soul"
    )
    resolved_tools: Optional[List[Any]] = Field(
        default=None,
        exclude=True,
        description="Resolved tool objects (excluded from serialization)",
    )

    @field_validator("id")
    @classmethod
    def _validate_identity(cls, value: str) -> str:
        validate_entity_id(value, EntityKind.SOUL)
        return value


class Step:
    """
    Wrapper for BaseBlock with pre/post hook execution.

    Use Case: Add logging, validation, or state transformation around blocks.
    Example: pre_hook = log start time, post_hook = log end time + duration.

    declared_inputs: Maps local names to 'source_block.field.path' references.
    Resolution happens in build_block_context (block_io.py) when the step is
    passed as the step parameter. Step.execute does not resolve or inject inputs.

    Note: Hooks must be synchronous. For async operations, use a block instead.
    """

    def __init__(
        self,
        block: "BaseBlock",
        pre_hook: Optional[Callable[["WorkflowState"], "WorkflowState"]] = None,
        post_hook: Optional[Callable[["WorkflowState"], "WorkflowState"]] = None,
        declared_inputs: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Args:
            block: The block to wrap.
            pre_hook: Optional function to run before block execution.
                     Receives state, returns modified state (or same state).
                     MUST be synchronous (not async).
            post_hook: Optional function to run after block execution.
                      Receives state (output from block), returns modified state.
                      MUST be synchronous (not async).
            declared_inputs: Optional mapping of {local_name: "source_block_id.field.path"}.
                            Passed to build_block_context for resolution; not resolved here.
        """
        self.block = block
        self.pre_hook = pre_hook
        self.post_hook = post_hook
        self.declared_inputs: Dict[str, str] = declared_inputs or {}

    @property
    def block_id(self) -> str:
        """Delegate block_id to the wrapped block."""
        return self.block.block_id

    @property
    def assertions(self) -> Optional[List[Any]]:
        """Delegate assertions to the wrapped block."""
        return getattr(self.block, "assertions", None)

    async def execute(self, state: "WorkflowState", **kwargs: Any) -> "WorkflowState":
        """
        Execute pre_hook → block → post_hook in sequence.

        Input resolution is not performed here. Callers that need declared_inputs
        resolved should use build_block_context(block, state, step=self) before
        dispatching.

        Args:
            state: Initial workflow state.

        Returns:
            Final state after all phases.

        Raises:
            Exception: Propagates any exception from hooks or block.
        """
        from runsight_core.block_io import apply_block_output, build_block_context

        # Phase 1: Pre-hook (optional)
        if self.pre_hook is not None:
            state = self.pre_hook(state)

        # Phase 2: Resolve declared inputs (if any) — inject into shared_memory for block access
        from runsight_core.state import WorkflowState as _WorkflowState  # for isinstance check

        if self.declared_inputs:
            resolved_inputs: Dict[str, Any] = {}
            for name, from_ref in self.declared_inputs.items():
                resolved_inputs[name] = self._resolve_from_ref(from_ref, state)
            state = state.model_copy(
                update={
                    "shared_memory": {**state.shared_memory, "_resolved_inputs": resolved_inputs}
                }
            )
        else:
            # Clear stale resolved inputs from previous step
            if "_resolved_inputs" in state.shared_memory:
                new_sm = {k: v for k, v in state.shared_memory.items() if k != "_resolved_inputs"}
                state = state.model_copy(update={"shared_memory": new_sm})

        ctx = build_block_context(self.block, state, step=self)
        try:
            output = await self.block.execute(ctx)
        except AttributeError as exc:
            # Backward compat: non-BaseBlock old-style blocks access WorkflowState
            # attributes on the BlockContext. Fall back to direct state dispatch.
            if "'BlockContext' object has no attribute" in str(exc):
                output = await self.block.execute(state)
            else:
                raise
        # Backward compat: old-style blocks may return WorkflowState directly.
        if isinstance(output, _WorkflowState):
            return output
        state = apply_block_output(state, self.block.block_id, output)

        # Phase 3: Post-hook (optional)
        if self.post_hook is not None:
            state = self.post_hook(state)

        return state

    def _resolve_from_ref(self, from_ref: str, state: "WorkflowState") -> Any:
        """Resolve 'step_id.field.path' against state.results."""
        import json

        parts = from_ref.split(".", 1)
        source_id = parts[0]
        if source_id not in state.results:
            raise ValueError(
                f"Input resolution failed: source block '{source_id}' not found in state.results. "
                f"Available: {sorted(state.results.keys())}"
            )
        raw = state.results[source_id]
        # Unwrap BlockResult to its output string for resolution
        from runsight_core.state import BlockResult

        if isinstance(raw, BlockResult):
            raw = raw.output
        if len(parts) == 1:
            return raw

        # JSON auto-parse
        parsed = raw
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                # Raw string that isn't JSON — return as-is (field path is informational)
                return raw

        # If parsed is still a plain string (JSON string literal), return as-is
        if isinstance(parsed, str):
            return parsed

        # Dot-path resolution for dict/list structures
        field_path = parts[1]
        from runsight_core.conditions.engine import resolve_dotted_path

        value = resolve_dotted_path(parsed, field_path)
        if value is None and not (isinstance(parsed, dict) and field_path in parsed):
            if source_id == "workflow":
                return None
            raise ValueError(
                f"Input resolution failed: field path '{field_path}' not found in output of '{source_id}'"
            )
        return value
