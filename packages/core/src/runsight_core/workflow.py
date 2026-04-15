"""
Workflow state machine for orchestrating block execution.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import re
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Deque, Dict, List, Optional, Tuple

from runsight_core.blocks.base import BaseBlock
from runsight_core.conditions.engine import Case, evaluate_output_conditions
from runsight_core.state import BlockResult, WorkflowState

if TYPE_CHECKING:
    from runsight_core.blocks.registry import BlockRegistry
    from runsight_core.observer import WorkflowObserver
    from runsight_core.yaml.registry import WorkflowRegistry

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True, slots=True)
class BlockExecutionContext:
    """Execution context shared across block dispatch within a workflow run."""

    workflow_name: str
    blocks: Dict[str, BaseBlock]
    call_stack: List[str]
    workflow_registry: Optional["WorkflowRegistry"]
    observer: Optional["WorkflowObserver"]
    passthrough_kwargs: Dict[str, Any] = dataclasses.field(default_factory=dict)


async def _execute_with_retry(
    block: BaseBlock,
    state: WorkflowState,
    retry_cfg: Any,
    execute_fn: Callable[[BaseBlock, WorkflowState], Awaitable[WorkflowState]],
) -> WorkflowState:
    """Wrap block execution with retry logic based on retry_config."""
    max_attempts = retry_cfg.max_attempts
    last_exc: Optional[BaseException] = None
    last_error_type = ""

    for attempt in range(1, max_attempts + 1):
        try:
            # Pass the same pre-retry `state` on every attempt so stateful blocks
            # start from a clean history — failed-attempt messages are never carried over.
            result_state = await execute_fn(block, state)
            if attempt > 1:
                result_state.shared_memory = {
                    **result_state.shared_memory,
                    f"__retry__{block.block_id}": {
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "last_error": str(last_exc),
                        "last_error_type": last_error_type,
                        "total_retries": attempt - 1,
                    },
                }
            return result_state
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            last_exc = exc
            last_error_type = type(exc).__name__

            if retry_cfg.non_retryable_errors and last_error_type in retry_cfg.non_retryable_errors:
                raise

            if attempt >= max_attempts:
                raise

            if retry_cfg.backoff == "exponential":
                sleep_duration = retry_cfg.backoff_base_seconds * (2 ** (attempt - 1))
            else:
                sleep_duration = retry_cfg.backoff_base_seconds
            await asyncio.sleep(sleep_duration)

    assert last_exc is not None
    raise last_exc  # pragma: no cover


def _matches_exit_condition(cond: object, output: str) -> bool:
    """Check if a single exit condition matches the block output."""
    if getattr(cond, "contains", None) is not None and cond.contains in output:
        return True
    if getattr(cond, "regex", None) is not None and re.search(cond.regex, output):
        return True
    return False


async def execute_block(
    block: BaseBlock,
    state: WorkflowState,
    ctx: BlockExecutionContext,
) -> WorkflowState:
    """Execute a workflow block with observer notifications and retry behavior."""
    from runsight_core.blocks.loop import LoopBlock
    from runsight_core.blocks.workflow_block import WorkflowBlock

    block_id = block.block_id
    block_type = type(block).__name__
    soul = getattr(block, "soul", None)
    start_kwargs = {"soul": soul} if soul is not None else {}
    observer = ctx.observer

    if observer:
        try:
            if isinstance(block, WorkflowBlock):
                child_workflow_id = getattr(block, "workflow_ref", None)
                if child_workflow_id:
                    start_kwargs["child_workflow_id"] = child_workflow_id
                start_kwargs["child_workflow_name"] = block.child_workflow.name
            observer.on_block_start(ctx.workflow_name, block_id, block_type, **start_kwargs)
        except Exception:
            logger.warning("Observer.on_block_start failed", exc_info=True)

    block_start_time = time.time()
    passthrough_kwargs = dict(ctx.passthrough_kwargs)
    kwargs_for_context = dict(passthrough_kwargs)
    kwargs_for_context.update(
        {
            "call_stack": ctx.call_stack + [ctx.workflow_name],
            "workflow_registry": ctx.workflow_registry,
            "observer": observer,
        }
    )

    async def _dispatch(blk: BaseBlock, current_state: WorkflowState) -> WorkflowState:
        if isinstance(blk, WorkflowBlock):
            return await blk.execute(current_state, **kwargs_for_context)
        if isinstance(blk, LoopBlock):
            loop_kwargs = dict(kwargs_for_context)
            loop_kwargs.update({"blocks": ctx.blocks, "ctx": ctx})
            return await blk.execute(current_state, **loop_kwargs)
        if passthrough_kwargs:
            return await blk.execute(current_state, **passthrough_kwargs)
        return await blk.execute(current_state)

    # Block-level budget session swap
    from runsight_core.budget_enforcement import (
        BudgetKilledException,
        BudgetSession,
        _active_budget,
    )

    block_limits = getattr(block, "limits", None)
    block_budget_token = None
    if block_limits is not None:
        current_session = _active_budget.get(None)
        block_session = BudgetSession.from_block_limits(
            block_limits, block_id, parent=current_session
        )
        block_budget_token = _active_budget.set(block_session)

    try:
        timeout = getattr(block, "max_duration_seconds", None)
        retry_cfg = getattr(block, "retry_config", None)
        if retry_cfg is not None:
            dispatch_coro = _execute_with_retry(block, state, retry_cfg, _dispatch)
        else:
            dispatch_coro = _dispatch(block, state)

        try:
            if timeout is not None:
                state = await asyncio.wait_for(dispatch_coro, timeout=timeout)
            else:
                state = await dispatch_coro
        except asyncio.TimeoutError:
            raise BudgetKilledException(
                scope="block",
                block_id=block_id,
                limit_kind="timeout",
                limit_value=timeout,
                actual_value=timeout,
            )

        if getattr(block, "exit_conditions", None):
            br = state.results.get(block_id)
            if br and br.exit_handle is None:
                for cond in block.exit_conditions:
                    if _matches_exit_condition(cond, br.output):
                        state = state.model_copy(
                            update={
                                "results": {
                                    **state.results,
                                    block_id: br.model_copy(
                                        update={"exit_handle": cond.exit_handle}
                                    ),
                                }
                            }
                        )
                        break

        block_duration = time.time() - block_start_time
        if observer:
            try:
                observer.on_block_complete(
                    ctx.workflow_name,
                    block_id,
                    block_type,
                    block_duration,
                    state,
                    **({"soul": soul} if soul is not None else {}),
                )
            except Exception:
                logger.warning("Observer.on_block_complete failed", exc_info=True)

        return state
    except Exception as exc:
        block_duration = time.time() - block_start_time
        if observer:
            try:
                observer.on_block_error(
                    ctx.workflow_name, block_id, block_type, block_duration, exc
                )
            except Exception:
                logger.warning("Observer.on_block_error failed", exc_info=True)
        raise
    finally:
        if block_budget_token is not None:
            _active_budget.reset(block_budget_token)


class Workflow:
    """
    Orchestrates block execution following a transition graph.

    Execution Model: Sequential (one block at a time), single-path transitions.
    Validation: Topology checks (entry exists, no dangling refs, acyclic).

    Example:
        wf = Workflow(name="research_pipeline")
        wf.add_block(research_block)
        wf.add_block(code_block)
        wf.add_transition("research", "code")  # research -> code
        wf.set_entry("research")
        errors = wf.validate()
        if errors:
            raise ValueError(f"Invalid workflow: {errors}")
        final_state = await wf.run(initial_state)
    """

    def __init__(self, name: str):
        """
        Args:
            name: Workflow identifier (for logging/debugging).

        Raises:
            ValueError: If name is empty.
        """
        if not name:
            raise ValueError("Workflow name cannot be empty")
        self.name = name
        self.identity: Optional[str] = None
        self._blocks: Dict[str, BaseBlock] = {}
        self._transitions: Dict[str, str] = {}  # from_block_id -> to_block_id
        self._entry_block_id: Optional[str] = None
        self._conditional_transitions: Dict[
            str, Dict[str, str]
        ] = {}  # from_block_id -> {decision_str -> to_block_id}
        self._error_routes: Dict[str, str] = {}
        self._output_conditions: Dict[str, Tuple[List[Case], str]] = {}

    @property
    def blocks(self) -> Dict[str, BaseBlock]:
        """Read-only access to the block registry keyed by block_id."""
        return self._blocks

    def add_block(self, block: BaseBlock) -> "Workflow":
        """
        Register a block in this workflow.

        Args:
            block: Block instance to add.

        Returns:
            Self (for fluent API chaining).

        Raises:
            ValueError: If block.block_id already registered.
        """
        if block.block_id in self._blocks:
            raise ValueError(
                f"Block ID '{block.block_id}' already exists in blueprint '{self.name}'"
            )
        self._blocks[block.block_id] = block
        return self

    def add_transition(self, from_block_id: str, to_block_id: Optional[str]) -> "Workflow":
        """
        Define transition from one block to another.

        TERMINAL SEMANTICS: Use to_block_id=None to mark a block as terminal (no outgoing transition).

        Args:
            from_block_id: Source block ID.
            to_block_id: Destination block ID, or None for terminal blocks.

        Returns:
            Self (for fluent API chaining).

        Raises:
            ValueError: If from_block_id already has a transition defined.
            ValueError: If from_block_id already has a conditional transition defined.

        Note: Validation of block existence is deferred to validate() method.
              This allows building workflows in any order (add blocks after transitions).
        """
        if from_block_id in self._transitions:
            raise ValueError(
                f"Block '{from_block_id}' already has transition to '{self._transitions[from_block_id]}'. "
                "Only single-path transitions are supported."
            )
        if from_block_id in self._conditional_transitions:
            raise ValueError(
                f"Block '{from_block_id}' already has a conditional transition. "
                "Cannot add both plain and conditional transitions for the same block."
            )
        if to_block_id is not None:
            self._transitions[from_block_id] = to_block_id
        # If to_block_id is None, do NOT add entry to _transitions (terminal block)
        return self

    def add_conditional_transition(
        self,
        from_step_id: str,
        condition_map: Dict[str, str],
    ) -> "Workflow":
        """
        Register a conditional (multi-path) transition from from_step_id.

        After from_step_id executes, the engine reads a decision string from
        state.metadata and selects the next block using condition_map.

        Args:
            from_step_id: Source block ID. Must be registered via add_block() before
                          validate() is called (registration order is flexible).
            condition_map: Mapping of decision strings to successor block IDs.
                           Reserved key: "default" — used when decision string has
                           no explicit entry in condition_map.
                           Example: {"approved": "approve_block", "rejected": "reject_block",
                                     "default": "reject_block"}

        Returns:
            Self (for fluent API chaining).

        Raises:
            ValueError: If from_step_id already has a plain transition (add_transition).
            ValueError: If from_step_id already has a conditional transition.

        Note:
            Block existence is validated lazily via validate(), not here.
            This mirrors the existing add_transition() deferred-validation pattern.
        """
        if from_step_id in self._transitions:
            raise ValueError(
                f"Block '{from_step_id}' already has a plain transition. "
                "Cannot add both plain and conditional transitions for the same block."
            )
        if from_step_id in self._conditional_transitions:
            raise ValueError(
                f"Block '{from_step_id}' already has a conditional transition defined."
            )
        self._conditional_transitions[from_step_id] = condition_map
        return self

    def set_entry(self, block_id: str) -> "Workflow":
        """
        Set the starting block for execution.

        Args:
            block_id: ID of entry block.

        Returns:
            Self (for fluent API chaining).

        Note: Validation of block existence is deferred to validate().
        """
        self._entry_block_id = block_id
        return self

    def set_output_conditions(
        self, block_id: str, cases: list, default: str = "default"
    ) -> "Workflow":
        """Store output_conditions for a block.

        When _resolve_next runs for this block, the cases are evaluated against
        the block's result. The winning case_id (or the default) is persisted
        as exit_handle on the BlockResult so that conditional_transitions
        can consume it.

        Args:
            block_id: The block whose result should be evaluated.
            cases: Ordered list of Case objects.
            default: Fallback decision string if no case matches.

        Returns:
            Self for fluent API chaining.
        """
        self._output_conditions[block_id] = (cases, default)
        return self

    def set_error_route(self, block_id: str, target_block_id: str) -> "Workflow":
        """Store an error_route mapping for later runtime handling."""
        self._error_routes[block_id] = target_block_id
        return self

    def validate(self) -> List[str]:
        """
        Validate workflow topology. Returns list of error messages (empty if valid).

        Checks:
        1. Entry block is set and exists in _blocks
        2. All transition references point to registered blocks
        3. All conditional transition references point to registered blocks
        4. No cycles (DFS-based cycle detection)

        Returns:
            List of error strings. Empty list means workflow is valid.

        Example:
            errors = workflow.validate()
            if errors:
                raise ValueError(f"Workflow invalid: {errors}")
        """
        errors: List[str] = []

        # Check 1: Entry block exists
        if self._entry_block_id is None:
            errors.append("No entry block set. Call set_entry(block_id) before validation.")
        elif self._entry_block_id not in self._blocks:
            errors.append(
                f"Entry block '{self._entry_block_id}' not found. "
                f"Available blocks: {list(self._blocks.keys())}"
            )

        # Check 2: All plain transitions reference valid blocks
        for from_id, to_id in self._transitions.items():
            if from_id not in self._blocks:
                errors.append(f"Transition from unknown block '{from_id}' to '{to_id}'")
            if to_id not in self._blocks:
                errors.append(f"Transition from '{from_id}' to unknown block '{to_id}'")

        # Check 3: All conditional transition references point to valid blocks
        for from_id, cmap in self._conditional_transitions.items():
            if from_id not in self._blocks:
                errors.append(f"Conditional transition from unknown block '{from_id}'")
            # Check conditional transition targets
            for decision_key, to_id in cmap.items():
                if to_id not in self._blocks:
                    errors.append(
                        f"Conditional transition from '{from_id}' "
                        f"(decision='{decision_key}') to unknown block '{to_id}'"
                    )

        # Check 4: Exit validation — transition keys must match declared exits
        for from_id, cmap in self._conditional_transitions.items():
            block = self._blocks.get(from_id)
            declared_exits = getattr(block, "_declared_exits", None)
            if declared_exits is not None:
                declared_ids = {e.id for e in declared_exits} | {"default"}
                for key in cmap.keys():
                    if key not in declared_ids:
                        errors.append(
                            f"'{from_id}': transition key '{key}' not in declared exits {sorted(declared_ids)}"
                        )

        # Check 5: All error routes reference valid blocks
        for from_id, to_id in self._error_routes.items():
            if from_id not in self._blocks:
                errors.append(f"error_route from unknown block '{from_id}' to '{to_id}'")
            if to_id not in self._blocks:
                errors.append(f"error_route from '{from_id}' to '{to_id}' unknown block")

        # Check 6: Cycle detection (DFS)
        if not errors:  # Only check cycles if structure is valid
            cycle = self._detect_cycle()
            if cycle:
                errors.append(f"Cycle detected: {' -> '.join(cycle)}")

        return errors

    def _detect_cycle(self) -> Optional[List[str]]:
        """
        DFS-based cycle detection. Returns cycle path if found, None otherwise.

        Algorithm: Track visiting (grey) and visited (black) nodes. If we encounter
        a grey node, we have a cycle. Traverses both plain and conditional transitions.
        """
        WHITE, GREY, BLACK = 0, 1, 2
        color: Dict[str, int] = {bid: WHITE for bid in self._blocks}
        parent: Dict[str, Optional[str]] = {bid: None for bid in self._blocks}

        def dfs(node: str) -> Optional[List[str]]:
            color[node] = GREY

            # Collect all successors: plain transition + all conditional targets
            successors: List[str] = []
            if node in self._transitions:
                successors.append(self._transitions[node])
            if node in self._conditional_transitions:
                successors.extend(self._conditional_transitions[node].values())

            for neighbor in successors:
                if neighbor not in color:
                    continue  # Skip unknown block IDs (already caught by validate)
                if color[neighbor] == GREY:
                    # Cycle detected, reconstruct path
                    cycle_path = [neighbor]
                    current = node
                    while current != neighbor:
                        cycle_path.append(current)
                        parent_node = parent[current]
                        assert parent_node is not None, "Parent must exist in cycle path"
                        current = parent_node
                    cycle_path.append(neighbor)
                    return list(reversed(cycle_path))
                elif color[neighbor] == WHITE:
                    parent[neighbor] = node
                    result = dfs(neighbor)
                    if result:
                        return result

            color[node] = BLACK
            return None

        # Start DFS from entry block
        if self._entry_block_id and self._entry_block_id in self._blocks:
            result = dfs(self._entry_block_id)
            if result:
                return result

        # Check unreachable components (could have cycles not reachable from entry)
        for block_id in self._blocks:
            if color[block_id] == WHITE:
                result = dfs(block_id)
                if result:
                    return result

        return None

    def _resolve_next(self, current_block_id: str, state: WorkflowState) -> Optional[str]:
        """
        Determine the next block ID after current_block_id executes.

        Resolution order:
        1. Read exit_handle from state.results[block_id].exit_handle (if present)
        2. If no exit_handle, evaluate output_conditions (if present) and persist
           the computed exit_handle on the BlockResult
        3. If conditional_transitions exist: use exit_handle as lookup key
        4. Fallback to "default" key in condition_map
        5. Fallback to plain transition

        Args:
            current_block_id: ID of block that just executed.
            state: State returned by block.execute() (contains fresh results).

        Returns:
            Next block ID string, or None if terminal.

        Raises:
            KeyError: If conditional transition resolution fails (no matching key, no default).
        """
        # Step 1: Read exit_handle from BlockResult (if present)
        exit_handle: Optional[str] = None
        block_result = state.results.get(current_block_id)
        if block_result is not None and hasattr(block_result, "exit_handle"):
            exit_handle = block_result.exit_handle

        # Step 2: If no exit_handle, evaluate output_conditions (if present)
        if exit_handle is None and current_block_id in self._output_conditions:
            cases, default_decision = self._output_conditions[current_block_id]
            _output = (
                block_result.output
                if block_result is not None and hasattr(block_result, "output")
                else (block_result if isinstance(block_result, str) else "")
            )
            decision_oc, warnings_oc = evaluate_output_conditions(cases, _output, default_decision)
            # Persist exit_handle on the BlockResult (not metadata)
            if block_result is not None and hasattr(block_result, "exit_handle"):
                state.results[current_block_id].exit_handle = decision_oc
            exit_handle = decision_oc
            if warnings_oc:
                state.metadata[f"{current_block_id}_warnings"] = warnings_oc

        # Step 3: If conditional_transitions exist, use exit_handle as lookup key
        if current_block_id in self._conditional_transitions:
            condition_map = self._conditional_transitions[current_block_id]

            next_id = condition_map.get(str(exit_handle)) if exit_handle is not None else None
            # Step 4: Fallback to "default" key
            if next_id is None:
                next_id = condition_map.get("default")

            if next_id is None:
                raise KeyError(
                    f"Conditional transition from '{current_block_id}': "
                    f"exit_handle {exit_handle!r} not found in condition_map "
                    f"and no 'default' key present. "
                    f"condition_map keys: {list(condition_map.keys())}"
                )
            return next_id

        # Step 5: Plain transition (or terminal if absent)
        return self._transitions.get(current_block_id)

    def _notify_observers(
        self,
        observer: Optional["WorkflowObserver"],
        event_name: str,
        *args: Any,
    ) -> None:
        """Call a named observer method, swallowing and logging any exception."""
        if observer is None:
            return
        method = getattr(observer, event_name, None)
        if method is None:
            return
        try:
            method(*args)
        except Exception:
            logger.warning("Observer.%s failed", event_name, exc_info=True)

    async def _handle_block_error(
        self,
        current_block_id: str,
        exc: Exception,
        state: WorkflowState,
        queue: "Deque[Tuple[str, BaseBlock]]",
    ) -> WorkflowState:
        """Route a block exception through the error_route, or re-raise if none configured."""
        error_target_id = self._error_routes.get(current_block_id)
        if error_target_id is None:
            raise exc
        if error_target_id not in self._blocks:
            raise ValueError(
                f"error_route from '{current_block_id}' to unknown block '{error_target_id}'"
            ) from exc

        error_type = type(exc).__name__
        error_message = str(exc)
        state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    current_block_id: BlockResult(
                        output=error_message,
                        exit_handle="error",
                        metadata={
                            "error_type": error_type,
                            "error_message": error_message,
                            "block_id": current_block_id,
                        },
                    ),
                },
                "shared_memory": {
                    **state.shared_memory,
                    f"__error__{current_block_id}": {"type": error_type, "message": error_message},
                },
            }
        )
        queue.clear()
        queue.append((error_target_id, self._blocks[error_target_id]))
        return state

    async def _run_main_loop(
        self,
        queue: "Deque[Tuple[str, BaseBlock]]",
        ctx: BlockExecutionContext,
        state: WorkflowState,
        registry: Optional["BlockRegistry"],
    ) -> WorkflowState:
        """Execute blocks from queue until empty, handling error routes and injection."""
        runtime_blocks = ctx.blocks
        while queue:
            current_block_id, block = queue.popleft()
            try:
                state = await execute_block(block, state, ctx)
            except Exception as e:
                state = await self._handle_block_error(current_block_id, e, state, queue)
                continue

            # Soft-error routing: block exited normally with exit_handle=="error"
            block_result = state.results.get(current_block_id)
            if (
                block_result is not None
                and getattr(block_result, "exit_handle", None) == "error"
                and current_block_id in self._error_routes
            ):
                error_target_id = self._error_routes[current_block_id]
                queue.clear()
                queue.append((error_target_id, self._blocks[error_target_id]))
                continue

            next_block_id = self._resolve_next(current_block_id, state)
            injected_raw = state.metadata.get(f"{current_block_id}_new_steps")

            if injected_raw and isinstance(injected_raw, list) and len(injected_raw) > 0:
                injected_entries = self._resolve_injected_steps(
                    injected_raw, registry, runtime_blocks
                )
                remaining = list(queue)
                queue.clear()
                for entry in injected_entries:
                    queue.append(entry)
                if next_block_id is not None:
                    queue.append((next_block_id, runtime_blocks[next_block_id]))
                for entry in remaining:
                    queue.append(entry)
            else:
                if next_block_id is not None:
                    queue.append((next_block_id, runtime_blocks[next_block_id]))

        return state

    def _resolve_injected_steps(
        self,
        injected_raw: list,
        registry: Optional["BlockRegistry"],
        runtime_blocks: Dict[str, BaseBlock],
    ) -> "List[Tuple[str, BaseBlock]]":
        """Validate and instantiate dynamically injected step items."""
        injected_entries: List[Tuple[str, BaseBlock]] = []
        for item in injected_raw:
            if not isinstance(item, dict):
                raise ValueError(
                    f"Injected step item must be a dict, got {type(item).__name__!r}: {item!r}"
                )
            if "step_id" not in item or "description" not in item:
                raise ValueError(f"Injected step item missing 'step_id' or 'description': {item!r}")
            step_id: str = item["step_id"]
            description: str = item["description"]
            if registry is None or registry.get(step_id) is None:
                raise ValueError(f"No factory registered for injected step '{step_id}'")
            factory = registry.get(step_id)
            injected_block: BaseBlock = factory(step_id, description)  # type: ignore[misc]
            runtime_blocks[step_id] = injected_block
            injected_entries.append((step_id, injected_block))
        return injected_entries

    async def _run_with_timeout(
        self,
        loop_coro: Any,
        flow_timeout: Optional[float],
    ) -> WorkflowState:
        """Await loop_coro, converting TimeoutError to BudgetKilledException."""
        from runsight_core.budget_enforcement import BudgetKilledException

        try:
            if flow_timeout is not None:
                return await asyncio.wait_for(loop_coro, timeout=flow_timeout)
            return await loop_coro
        except asyncio.TimeoutError:
            raise BudgetKilledException(
                scope="workflow",
                block_id=None,
                limit_kind="timeout",
                limit_value=flow_timeout,
                actual_value=flow_timeout,
            )

    def _seed_inputs(self, state: WorkflowState, inputs: Optional[Dict[str, Any]]) -> WorkflowState:
        """Return a copy of state with inputs serialised into results['workflow']."""
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    "workflow": BlockResult(output=json.dumps(inputs or {})),
                }
            }
        )

    async def run(
        self,
        initial_state: WorkflowState,
        *,
        inputs: Optional[Dict[str, Any]] = None,
        registry: Optional["BlockRegistry"] = None,
        call_stack: Optional[List[str]] = None,
        workflow_registry: Optional["WorkflowRegistry"] = None,
        observer: Optional["WorkflowObserver"] = None,
    ) -> WorkflowState:
        """Validate, initialise budget/observer lifecycle, then delegate to _run_main_loop."""
        from runsight_core.budget_enforcement import BudgetSession, _active_budget

        if call_stack is None:
            call_stack = []
        if errors := self.validate():
            raise ValueError(f"Cannot run invalid workflow '{self.name}': {errors}")

        runtime_blocks: Dict[str, BaseBlock] = dict(self._blocks)
        assert self._entry_block_id is not None  # guaranteed by validate()
        queue: Deque[Tuple[str, BaseBlock]] = deque(
            [(self._entry_block_id, runtime_blocks[self._entry_block_id])]
        )
        state = self._seed_inputs(initial_state, inputs)

        flow_limits = getattr(self, "limits", None)
        budget_token = (
            _active_budget.set(BudgetSession.from_workflow_limits(flow_limits, self.name))
            if flow_limits is not None
            else None
        )
        flow_timeout = getattr(flow_limits, "max_duration_seconds", None)
        wf_start_time = time.time()
        observer_workflow_name = self.identity or self.name
        self._notify_observers(observer, "on_workflow_start", observer_workflow_name, state)

        ctx = BlockExecutionContext(
            workflow_name=observer_workflow_name,
            blocks=runtime_blocks,
            call_stack=call_stack,
            workflow_registry=workflow_registry,
            observer=observer,
        )
        try:
            state = await self._run_with_timeout(
                self._run_main_loop(queue, ctx, state, registry),
                flow_timeout,
            )
            wf_duration = time.time() - wf_start_time
            self._notify_observers(
                observer, "on_workflow_complete", observer_workflow_name, state, wf_duration
            )
            return state
        except Exception as e:
            wf_duration = time.time() - wf_start_time
            self._notify_observers(
                observer, "on_workflow_error", observer_workflow_name, e, wf_duration
            )
            raise
        finally:
            if budget_token is not None:
                _active_budget.reset(budget_token)
