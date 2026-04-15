"""
BaseBlock abstract interface for workflow blocks.
"""

import asyncio
import functools
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from runsight_core.state import WorkflowState

if TYPE_CHECKING:
    from runsight_core.block_io import BlockContext, BlockOutput


class NodeKilledException(Exception):
    """Raised when a block is killed during execution."""

    def __init__(self, block_id: str):
        super().__init__(f"Node '{block_id}' was killed")
        self.block_id = block_id


class BaseBlock(ABC):
    """
    Abstract base for workflow blocks. All concrete blocks must implement execute().

    Constructor contract: All subclasses MUST accept block_id as first parameter.
    """

    def __init__(self, block_id: str, *, retry_config=None):
        """
        Args:
            block_id: Unique identifier for this block instance within a blueprint.
                     Used as the key in state.results.
            retry_config: Optional RetryConfig for retry execution in workflow runner.

        Raises:
            ValueError: If block_id is empty string.
        """
        if not block_id:
            raise ValueError("block_id cannot be empty")
        self.block_id = block_id
        self.assertions = None
        self.exit_conditions = None
        self.retry_config = retry_config
        self.stateful = False
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()  # not paused by default
        self._kill_flag: bool = False

    async def _check_pause(self) -> None:
        """
        Check pause/kill status. Blocks if paused; raises NodeKilledException if killed.

        Call at LLM boundaries to enable cooperative pause/kill.

        Raises:
            NodeKilledException: If the kill flag is set after the pause event is signaled.
        """
        await self._pause_event.wait()
        if self._kill_flag:
            raise NodeKilledException(self.block_id)

    async def write_artifact(
        self, state: WorkflowState, key: str, content: str, metadata: dict | None = None
    ) -> str:
        """Write an artifact via the state's artifact store.

        Args:
            state: Current workflow state (must have an artifact_store attached).
            key: Artifact key/name.
            content: String content to persist.
            metadata: Optional metadata dict to attach to the artifact.

        Returns:
            The ref string produced by the store.

        Raises:
            RuntimeError: If state.artifact_store is None.
        """
        if state.artifact_store is None:
            raise RuntimeError(
                "No ArtifactStore attached to WorkflowState. "
                "Provide an artifact_store when constructing the state."
            )
        return await state.artifact_store.write(key, content, metadata=metadata)

    async def read_artifact(self, state: WorkflowState, ref: str) -> str:
        """Read an artifact by ref via the state's artifact store.

        Args:
            state: Current workflow state (must have an artifact_store attached).
            ref: The artifact reference string returned by a previous write.

        Returns:
            The artifact content string.

        Raises:
            RuntimeError: If state.artifact_store is None.
        """
        if state.artifact_store is None:
            raise RuntimeError(
                "No ArtifactStore attached to WorkflowState. "
                "Provide an artifact_store when constructing the state."
            )
        return await state.artifact_store.read(ref)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Wrap each subclass's execute with a WorkflowState compat shim.

        This allows isolation/worker.py (RUN-906) to keep calling block.execute(state)
        without modification. When the argument is a WorkflowState, the shim builds a
        BlockContext, runs the real execute, and applies the output back to state.
        Any extra kwargs are merged into ctx.inputs so callers like LoopBlock tests
        that pass blocks=blocks still work.

        Backward-compat: if build_block_context raises (e.g. no current_task) or if
        the original execute returns a WorkflowState directly (old-style test helpers),
        the shim falls back to the legacy direct-passthrough path.
        """
        super().__init_subclass__(**kwargs)
        if "execute" in cls.__dict__:
            original = cls.__dict__["execute"]

            # Detect if original is new-style (BlockContext -> BlockOutput) by checking
            # the annotation of the first non-self parameter. New-style blocks use
            # 'BlockContext' or a forward ref to it; old-style use 'WorkflowState' or Any.
            import inspect as _inspect

            _sig = _inspect.signature(original)
            _params = list(_sig.parameters.values())
            _first_param = _params[1] if len(_params) > 1 else None
            _annotation = (
                getattr(_first_param, "annotation", _inspect.Parameter.empty)
                if _first_param is not None
                else _inspect.Parameter.empty
            )
            # Check if the annotation references BlockContext (string or type).
            _ann_str = str(_annotation)
            # Capture _is_new_style in closure via default arg on inner helper.
            _is_new_style: bool = "BlockContext" in _ann_str and "WorkflowState" not in _ann_str

            # If no annotation, inherit new-style status from parent classes.
            # This handles subclasses like `class Foo(LinearBlock): async def execute(self, ctx): ...`
            # that don't re-annotate but are clearly new-style because their parent is.
            # Skip abstract methods (e.g. BaseBlock.execute itself is abstract + BlockContext-annotated,
            # but that doesn't mean concrete old-style subclasses should be classified as new-style).
            if not _is_new_style and _annotation is _inspect.Parameter.empty:
                for _base in cls.__mro__[1:]:
                    _base_execute = _base.__dict__.get("execute")
                    if _base_execute is not None:
                        # Skip abstract methods — they don't represent a concrete implementation style.
                        if getattr(_base_execute, "__isabstractmethod__", False):
                            continue
                        _base_sig = _inspect.signature(_base_execute)
                        _base_params = list(_base_sig.parameters.values())
                        _base_first = _base_params[1] if len(_base_params) > 1 else None
                        _base_ann = (
                            getattr(_base_first, "annotation", _inspect.Parameter.empty)
                            if _base_first is not None
                            else _inspect.Parameter.empty
                        )
                        _base_ann_str = str(_base_ann)
                        if "BlockContext" in _base_ann_str and "WorkflowState" not in _base_ann_str:
                            _is_new_style = True
                        break

            def _make_shim(orig: Any, is_new_style: bool) -> Any:
                @functools.wraps(orig)
                async def _shim(self: "BaseBlock", ctx_or_state: Any, **extra_kwargs: Any) -> Any:
                    if isinstance(ctx_or_state, WorkflowState):
                        # Temporary shim for isolation/worker.py (RUN-906 will remove this call).
                        from runsight_core.block_io import (
                            apply_block_output,
                            build_block_context,
                        )

                        try:
                            ctx = build_block_context(self, ctx_or_state)
                        except ValueError:
                            # Legitimate business error (eval_key missing, inputs missing, etc.)
                            # — re-raise instead of falling back to the old-style path.
                            raise
                        except Exception:
                            # Old-style block with no matching context strategy; call directly.
                            return await orig(self, ctx_or_state, **extra_kwargs)

                        if extra_kwargs:
                            ctx = ctx.model_copy(update={"inputs": {**ctx.inputs, **extra_kwargs}})
                        try:
                            output = await orig(self, ctx)
                        except AttributeError as exc:
                            # Old-style block tried to access WorkflowState attributes on ctx.
                            # Only fall back for known old-style attribute access patterns AND
                            # only for old-style blocks — new-style blocks propagate the error.
                            if is_new_style or "'BlockContext' object has no attribute" not in str(
                                exc
                            ):
                                raise
                            return await orig(self, ctx_or_state, **extra_kwargs)
                        if isinstance(output, WorkflowState):
                            # Old-style block returned WorkflowState directly.
                            return output
                        return apply_block_output(ctx_or_state, self.block_id, output)
                    # ctx_or_state is a BlockContext — pass through directly.
                    # New-style blocks: no exception handling needed.
                    if is_new_style:
                        return await orig(self, ctx_or_state)
                    # Old-style blocks: use state_snapshot directly to avoid double-call.
                    # Trying block_ctx first would invoke orig once with a BlockContext
                    # (capturing {}) and again with snapshot when AttributeError fires.
                    snapshot = getattr(ctx_or_state, "state_snapshot", None)
                    if snapshot is not None and isinstance(snapshot, WorkflowState):
                        # Forward any non-empty inputs from the BlockContext as kwargs
                        # so that old-style blocks (e.g. inside LoopBlock) receive
                        # forwarded kwargs such as 'blocks', 'call_stack', 'observer'.
                        fwd_kwargs = dict(getattr(ctx_or_state, "inputs", {}) or {})
                        return await orig(self, snapshot, **fwd_kwargs)
                    # No snapshot available: try passing BlockContext and let any
                    # AttributeError propagate naturally.
                    return await orig(self, ctx_or_state)

                return _shim

            setattr(cls, "execute", _make_shim(original, _is_new_style))

    @abstractmethod
    async def execute(self, ctx: "BlockContext") -> "BlockOutput":
        """
        Execute this block's logic.

        Args:
            ctx: BlockContext containing instruction, inputs, soul, model, etc.

        Returns:
            BlockOutput with output, exit_handle, cost, tokens, and optional updates.

        Raises:
            ValueError: If required inputs are missing.
            Exception: If execution fails (propagates to Workflow.run() caller).
        """
        pass
