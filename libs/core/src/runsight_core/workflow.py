"""
Workflow state machine for orchestrating block execution.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Deque, Dict, List, Optional, Tuple

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.implementations import PlaceholderBlock
from runsight_core.conditions.engine import Case, evaluate_output_conditions
from runsight_core.state import WorkflowState

if TYPE_CHECKING:
    from runsight_core.blocks.registry import BlockRegistry
    from runsight_core.observer import WorkflowObserver
    from runsight_core.yaml.registry import WorkflowRegistry

logger = logging.getLogger(__name__)


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
        self._blocks: Dict[str, BaseBlock] = {}
        self._transitions: Dict[str, str] = {}  # from_block_id -> to_block_id
        self._entry_block_id: Optional[str] = None
        self._conditional_transitions: Dict[
            str, Dict[str, str]
        ] = {}  # from_block_id -> {decision_str -> to_block_id}
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
        the block's result. The winning case_id (or the default) is written to
        state.metadata[f"{block_id}_decision"] so that conditional_transitions
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

        # Check 4: Cycle detection (DFS)
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
        1. If current_block_id has a conditional transition:
           a. Read state.metadata.get("router_decision") (global key)
           b. Fallback: state.metadata.get(f"{current_block_id}_decision") (block-scoped)
           c. Look up decision in condition_map
           d. Fallback: condition_map.get("default")
           e. Raise KeyError if neither found
        2. Otherwise: return self._transitions.get(current_block_id) (plain or terminal)

        Args:
            current_block_id: ID of block that just executed.
            state: State returned by block.execute() (contains fresh metadata).

        Returns:
            Next block ID string, or None if terminal.

        Raises:
            KeyError: If conditional transition resolution fails (no matching key, no default).
        """
        # Evaluate output_conditions first (if present), writing decision to metadata
        if current_block_id in self._output_conditions:
            cases, default_decision = self._output_conditions[current_block_id]
            decision_oc, warnings_oc = evaluate_output_conditions(
                cases, state.results.get(current_block_id, ""), default_decision
            )
            state.metadata[f"{current_block_id}_decision"] = decision_oc
            if warnings_oc:
                state.metadata[f"{current_block_id}_warnings"] = warnings_oc

        if current_block_id in self._conditional_transitions:
            condition_map = self._conditional_transitions[current_block_id]

            # Read decision: global key first, block-scoped fallback
            decision: Any = state.metadata.get("router_decision")
            if decision is None:
                decision = state.metadata.get(f"{current_block_id}_decision")

            # Look up in condition_map; fallback to "default"
            next_id = condition_map.get(str(decision)) if decision is not None else None
            if next_id is None:
                next_id = condition_map.get("default")

            if next_id is None:
                raise KeyError(
                    f"Conditional transition from '{current_block_id}': "
                    f"decision {decision!r} not found in condition_map "
                    f"and no 'default' key present. "
                    f"condition_map keys: {list(condition_map.keys())}"
                )
            return next_id

        # Plain transition (or terminal if absent)
        return self._transitions.get(current_block_id)

    async def run(
        self,
        initial_state: WorkflowState,
        *,
        registry: Optional["BlockRegistry"] = None,
        call_stack: Optional[List[str]] = None,
        workflow_registry: Optional["WorkflowRegistry"] = None,
        observer: Optional["WorkflowObserver"] = None,
    ) -> WorkflowState:
        """
        Execute workflow starting from entry block, following transitions until terminal.

        Supports:
        - Plain transitions (existing behaviour, unchanged)
        - Conditional transitions: reads decision from state.metadata, branches accordingly
        - Dynamic step injection: splices injected blocks into live queue after each block
        - WorkflowBlock execution: propagates call_stack and workflow_registry to child workflows

        Args:
            initial_state: Starting workflow state.
            registry: Optional block factory registry. Used to resolve injected step_ids.
                      If None or step_id not found, PlaceholderBlock is used as fallback.
            call_stack: Workflow name stack for recursion tracking (default: []).
                       Used by WorkflowBlock to detect cycles and enforce depth limits.
            workflow_registry: Optional WorkflowRegistry for resolving child workflows.
                              Required when workflow contains WorkflowBlock instances.

        Returns:
            Final workflow state after all blocks (static + injected) execute.

        Raises:
            ValueError: If workflow fails validation.
            ValueError: If an injected step item is missing 'step_id' or 'description' keys.
            KeyError:   If a conditional transition has no matching key and no 'default' key.
            RecursionError: If WorkflowBlock detects cycle or depth limit exceeded.
            Exception:  If any block execution fails (propagates from block.execute()).
        """
        if call_stack is None:
            call_stack = []

        # Step 1: Validate static graph before any execution
        errors = self.validate()
        if errors:
            raise ValueError(f"Cannot run invalid workflow '{self.name}': {errors}")

        # Step 2: Initialise execution queue with (block_id, block_instance) pairs
        QueueEntry = Tuple[str, BaseBlock]
        queue: Deque[QueueEntry] = deque()

        # Seed queue with entry block
        assert self._entry_block_id is not None  # guaranteed by validate()
        queue.append((self._entry_block_id, self._blocks[self._entry_block_id]))

        state = initial_state

        wf_start_time = time.time()
        if observer:
            try:
                observer.on_workflow_start(self.name, state)
            except Exception:
                logger.warning("Observer.on_workflow_start failed", exc_info=True)

        try:
            while queue:
                current_block_id, block = queue.popleft()

                block_type = type(block).__name__
                if observer:
                    try:
                        observer.on_block_start(self.name, current_block_id, block_type)
                    except Exception:
                        logger.warning("Observer.on_block_start failed", exc_info=True)

                block_start_time = time.time()

                # Step 3: Execute block with context propagation for WorkflowBlock and RetryBlock
                from runsight_core.blocks.implementations import RetryBlock, WorkflowBlock

                try:
                    kwargs_for_context = {
                        "call_stack": call_stack + [self.name],
                        "workflow_registry": workflow_registry,
                        "observer": observer,
                    }
                    if isinstance(block, WorkflowBlock):
                        state = await block.execute(state, **kwargs_for_context)
                    elif isinstance(block, RetryBlock):
                        # RetryBlock may wrap WorkflowBlock; forward kwargs so cycle/depth work
                        state = await block.execute(state, **kwargs_for_context)
                    else:
                        state = await block.execute(state)

                    block_duration = time.time() - block_start_time
                    if observer:
                        try:
                            observer.on_block_complete(
                                self.name, current_block_id, block_type, block_duration, state
                            )
                        except Exception:
                            logger.warning("Observer.on_block_complete failed", exc_info=True)

                except Exception as e:
                    block_duration = time.time() - block_start_time
                    if observer:
                        try:
                            observer.on_block_error(
                                self.name, current_block_id, block_type, block_duration, e
                            )
                        except Exception:
                            logger.warning("Observer.on_block_error failed", exc_info=True)
                    raise

                # Step 4: Resolve successor BEFORE checking injection
                next_block_id = self._resolve_next(current_block_id, state)

                # Step 5: Check for dynamic step injection
                injected_raw = state.metadata.get(f"{current_block_id}_new_steps")
                if injected_raw and isinstance(injected_raw, list) and len(injected_raw) > 0:
                    # Build injected block list (validates each item)
                    injected_blocks: List[QueueEntry] = []
                    for item in injected_raw:
                        if not isinstance(item, dict):
                            raise ValueError(
                                f"Injected step item must be a dict, got {type(item).__name__!r}: {item!r}"
                            )
                        if "step_id" not in item or "description" not in item:
                            raise ValueError(
                                f"Injected step item missing 'step_id' or 'description': {item!r}"
                            )
                        step_id: str = item["step_id"]
                        description: str = item["description"]

                        # Resolve factory from registry, fallback to PlaceholderBlock
                        injected_block: BaseBlock
                        if registry is not None:
                            factory = registry.get(step_id)
                            if factory is not None:
                                injected_block = factory(step_id, description)
                            else:
                                injected_block = PlaceholderBlock(step_id, description)
                        else:
                            injected_block = PlaceholderBlock(step_id, description)

                        injected_blocks.append((step_id, injected_block))

                    # Splice injected blocks at front of queue
                    # Original next_block_id becomes successor of last injected block
                    # Queue state after splice: [inj_0, inj_1, ..., inj_n, original_next, ...]

                    # Save remaining queue (everything after current position)
                    remaining = list(queue)
                    queue.clear()

                    # Add injected blocks first
                    for entry in injected_blocks:
                        queue.append(entry)

                    # Add original next (if any)
                    if next_block_id is not None:
                        queue.append((next_block_id, self._blocks[next_block_id]))

                    # Re-add remaining (blocks already queued before this point)
                    for entry in remaining:
                        queue.append(entry)

                else:
                    # No injection: simply queue the resolved next block
                    if next_block_id is not None:
                        queue.append((next_block_id, self._blocks[next_block_id]))

            wf_duration = time.time() - wf_start_time
            if observer:
                try:
                    observer.on_workflow_complete(self.name, state, wf_duration)
                except Exception:
                    logger.warning("Observer.on_workflow_complete failed", exc_info=True)

            return state

        except Exception as e:
            wf_duration = time.time() - wf_start_time
            if observer:
                try:
                    observer.on_workflow_error(self.name, e, wf_duration)
                except Exception:
                    logger.warning("Observer.on_workflow_error failed", exc_info=True)
            raise
