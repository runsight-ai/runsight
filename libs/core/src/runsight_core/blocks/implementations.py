"""
Concrete block implementations for workflow composition.
"""

import ast
import asyncio
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

from runsight_core.blocks.base import BaseBlock
from runsight_core.memory.windowing import get_max_tokens, prune_messages
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner

if TYPE_CHECKING:
    from runsight_core.conditions.engine import Condition, ConditionGroup
    from runsight_core.workflow import Workflow
    from runsight_core.yaml.registry import WorkflowRegistry


class LinearBlock(BaseBlock):
    """
    Executes the current task with a single agent.

    Typical Use: Sequential processing where one agent completes a task.
    Example: Research block → writes research report to results.
    """

    def __init__(self, block_id: str, soul: Soul, runner: RunsightTeamRunner):
        """
        Args:
            block_id: Unique block identifier.
            soul: The agent that will execute the task.
            runner: Execution engine for running tasks.

        Raises:
            ValueError: If block_id is empty (from BaseBlock).
        """
        super().__init__(block_id)
        self.soul = soul
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Execute state.current_task using self.soul.

        Args:
            state: Must have state.current_task set.

        Returns:
            New state with:
            - results[block_id] = execution output string
            - messages appended with execution summary
            - total_cost_usd and total_tokens updated with execution result

        Raises:
            ValueError: If state.current_task is None.
        """
        if state.current_task is None:
            raise ValueError(f"LinearBlock {self.block_id}: state.current_task is None")

        if self.stateful:
            # Retry-safe: _execute_with_retry passes the same input state per attempt,
            # so `history` here never contains messages from a failed attempt.
            history_key = f"{self.block_id}_{self.soul.id}"
            history = state.conversation_histories.get(history_key, [])
            result = await self.runner.execute_task(state.current_task, self.soul, messages=history)
            prompt = self.runner._build_prompt(state.current_task)
            updated_history = history + [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": result.output},
            ]
            model = self.soul.model_name or self.runner.model_name
            updated_history = prune_messages(updated_history, get_max_tokens(model), model)
            conversation_update = {**state.conversation_histories, history_key: updated_history}
        else:
            result = await self.runner.execute_task(state.current_task, self.soul)
            conversation_update = state.conversation_histories

        # Truncate output for message log (prevent state size explosion)
        truncated = result.output[:200] + "..." if len(result.output) > 200 else result.output

        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=result.output)},
                "execution_log": state.execution_log
                + [
                    {"role": "system", "content": f"[Block {self.block_id}] Completed: {truncated}"}
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
                "conversation_histories": conversation_update,
            }
        )


class FanOutBlock(BaseBlock):
    """
    Executes the current task with multiple agents in parallel.

    Typical Use: Gather diverse perspectives (3 reviewers critique a proposal).
    Output Format: JSON list [{"soul_id": "...", "output": "..."}, ...]
    """

    def __init__(self, block_id: str, souls: List[Soul], runner: RunsightTeamRunner):
        """
        Args:
            block_id: Unique block identifier.
            souls: List of agents to run in parallel (must be non-empty).
            runner: Execution engine for running tasks.

        Raises:
            ValueError: If block_id is empty or souls list is empty.
        """
        super().__init__(block_id)
        if not souls:
            raise ValueError(f"FanOutBlock {block_id}: souls list cannot be empty")
        self.souls = souls
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Execute state.current_task in parallel across all souls.

        Args:
            state: Must have state.current_task set.

        Returns:
            New state with:
            - results[block_id] = JSON list of {"soul_id": str, "output": str}
            - messages appended with fanout summary
            - total_cost_usd and total_tokens updated with all execution results

        Raises:
            ValueError: If state.current_task is None.
            Exception: If ANY soul execution fails, entire block fails (all-or-nothing).
        """
        if state.current_task is None:
            raise ValueError(f"FanOutBlock {self.block_id}: state.current_task is None")

        if self.stateful:
            # Pre-read per-soul histories
            histories = {
                soul.id: state.conversation_histories.get(f"{self.block_id}_{soul.id}", [])
                for soul in self.souls
            }

            # Execute all souls in parallel, passing each soul's history
            gather_tasks = [
                self.runner.execute_task(state.current_task, soul, messages=histories[soul.id])
                for soul in self.souls
            ]
            results = await asyncio.gather(*gather_tasks)  # Raises on first failure

            # Build per-soul updated histories
            prompt = self.runner._build_prompt(state.current_task)
            updated_histories = {**state.conversation_histories}
            for soul, result in zip(self.souls, results):
                history_key = f"{self.block_id}_{soul.id}"
                updated = histories[soul.id] + [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": result.output},
                ]
                model = soul.model_name or self.runner.model_name
                updated_histories[history_key] = prune_messages(
                    updated, get_max_tokens(model), model
                )

            conversation_update = updated_histories
        else:
            # Execute all souls in parallel (preserves order)
            gather_tasks = [
                self.runner.execute_task(state.current_task, soul) for soul in self.souls
            ]
            results = await asyncio.gather(*gather_tasks)  # Raises on first failure
            conversation_update = state.conversation_histories

        # Aggregate outputs as JSON
        outputs = [{"soul_id": result.soul_id, "output": result.output} for result in results]

        # Aggregate costs and tokens
        total_cost = sum(result.cost_usd for result in results)
        total_tokens = sum(result.total_tokens for result in results)

        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=json.dumps(outputs, indent=2)),
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] FanOut completed with {len(self.souls)} agents",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + total_cost,
                "total_tokens": state.total_tokens + total_tokens,
                "conversation_histories": conversation_update,
            }
        )


class SynthesizeBlock(BaseBlock):
    """
    Reads outputs from multiple input blocks and synthesizes them into a cohesive result.

    Typical Use: Combine research + code + review into final report.
    """

    def __init__(
        self,
        block_id: str,
        input_block_ids: List[str],
        synthesizer_soul: Soul,
        runner: RunsightTeamRunner,
    ):
        """
        Args:
            block_id: Unique block identifier.
            input_block_ids: Block IDs whose outputs to synthesize (must be non-empty).
            synthesizer_soul: Agent that performs synthesis.
            runner: Execution engine for running tasks.

        Raises:
            ValueError: If block_id is empty or input_block_ids is empty.
        """
        super().__init__(block_id)
        if not input_block_ids:
            raise ValueError(f"SynthesizeBlock {block_id}: input_block_ids cannot be empty")
        self.input_block_ids = input_block_ids
        self.synthesizer_soul = synthesizer_soul
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Read inputs, construct synthesis task, execute with synthesizer.

        Args:
            state: Must have all input_block_ids present in state.results.

        Returns:
            New state with:
            - results[block_id] = synthesized output string
            - messages appended with synthesis summary
            - total_cost_usd and total_tokens updated with execution result

        Raises:
            ValueError: If any input_block_id missing from state.results.
        """
        # Validate all inputs exist
        missing = [bid for bid in self.input_block_ids if bid not in state.results]
        if missing:
            raise ValueError(
                f"SynthesizeBlock {self.block_id}: missing inputs: {missing}. "
                f"Available: {list(state.results.keys())}"
            )

        # Gather inputs
        combined_outputs = "\n\n".join(
            [
                f"=== Output from {bid} ===\n{state.results[bid].output if hasattr(state.results[bid], 'output') else state.results[bid]}"
                for bid in self.input_block_ids
            ]
        )

        # Construct synthesis task
        synthesis_instruction = (
            "Synthesize the following outputs into a cohesive, unified result. "
            "Identify common themes, resolve conflicts, and provide a comprehensive summary.\n\n"
            f"{combined_outputs}"
        )
        synthesis_task = Task(id=f"{self.block_id}_synthesis", instruction=synthesis_instruction)

        # Execute synthesis
        result = await self.runner.execute_task(synthesis_task, self.synthesizer_soul)

        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=result.output)},
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] Synthesized {len(self.input_block_ids)} inputs",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
            }
        )


class LoopBlock(BaseBlock):
    """
    Execute inner blocks sequentially for multiple rounds via flat-ref resolution.

    Typical Use: Writer + critic pattern where multiple blocks iterate in a loop.
    Example: LoopBlock runs [writer, critic] for 3 rounds.
    """

    def __init__(
        self,
        block_id: str,
        inner_block_refs: List[str],
        max_rounds: int = 5,
        break_condition: Optional[Union["Condition", "ConditionGroup"]] = None,
        carry_context: Optional[Any] = None,
    ) -> None:
        """
        Args:
            block_id: Unique identifier for this block instance.
            inner_block_refs: List of block IDs to execute sequentially each round.
            max_rounds: Number of rounds to execute (default: 5).
            break_condition: Optional condition evaluated after each round against
                the last inner block's output. If met, the loop exits early.
            carry_context: Optional CarryContextConfig for passing context between rounds.

        Raises:
            ValueError: If block_id is empty (from BaseBlock).
            ValueError: If inner_block_refs is empty.
            ValueError: If block_id is in inner_block_refs (self-reference).
            ValueError: If carry_context.source_blocks references blocks not in inner_block_refs.
        """
        super().__init__(block_id)
        if not inner_block_refs:
            raise ValueError(f"LoopBlock '{block_id}': inner_block_refs must not be empty")
        if block_id in inner_block_refs:
            raise ValueError(f"LoopBlock '{block_id}': self-reference detected in inner_block_refs")
        if carry_context is not None and carry_context.source_blocks is not None:
            invalid = [sb for sb in carry_context.source_blocks if sb not in inner_block_refs]
            if invalid:
                raise ValueError(
                    f"LoopBlock '{block_id}': carry_context.source_blocks references "
                    f"blocks not in inner_block_refs: {invalid}"
                )
        self.inner_block_refs = inner_block_refs
        self.max_rounds = max_rounds
        self.break_condition = break_condition
        self.carry_context = carry_context

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Execute inner blocks sequentially for max_rounds rounds.

        Args:
            state: Current workflow state.
            **kwargs: Must include blocks=Dict[str, BaseBlock] for flat-ref resolution.

        Returns:
            Updated state with round counter, inner block results, and loop metadata.

        Raises:
            ValueError: If a referenced block ID is not found in the blocks dict.
        """
        from runsight_core.conditions.engine import (
            ConditionGroup,
            evaluate_condition,
            evaluate_condition_group,
        )

        blocks: Dict[str, BaseBlock] = kwargs.get("blocks", {})
        broke_early = False
        rounds_completed = 0
        carry_history: List[Dict[str, Any]] = []

        for round_num in range(1, self.max_rounds + 1):
            # Set round counter in shared_memory before executing inner blocks
            state = state.model_copy(
                update={
                    "shared_memory": {
                        **state.shared_memory,
                        f"{self.block_id}_round": round_num,
                    },
                }
            )

            for ref in self.inner_block_refs:
                inner_block = blocks.get(ref)
                if inner_block is None:
                    raise ValueError(
                        f"LoopBlock '{self.block_id}': inner block ref '{ref}' "
                        f"not found in blocks dict. "
                        f"Available blocks: {sorted(blocks.keys())}"
                    )
                state = await inner_block.execute(state, **kwargs)

            rounds_completed = round_num

            # Carry context: collect outputs and inject into shared_memory for next round
            if self.carry_context is not None and self.carry_context.enabled:
                source_ids = self.carry_context.source_blocks or self.inner_block_refs
                round_outputs: Dict[str, Any] = {
                    sid: (result.output if hasattr(result, "output") else result)
                    if (result := state.results.get(sid)) is not None
                    else None
                    for sid in source_ids
                }
                carry_history.append(round_outputs)

                if self.carry_context.mode == "last":
                    inject_value: Any = round_outputs
                else:  # mode == "all"
                    inject_value = list(carry_history)

                state = state.model_copy(
                    update={
                        "shared_memory": {
                            **state.shared_memory,
                            self.carry_context.inject_as: inject_value,
                        },
                    }
                )

            # Evaluate break condition against the last inner block's output
            if self.break_condition is not None:
                last_ref = self.inner_block_refs[-1]
                _last_result = state.results.get(last_ref)
                last_output = (
                    _last_result.output if hasattr(_last_result, "output") else _last_result
                )
                if isinstance(self.break_condition, ConditionGroup):
                    should_break = evaluate_condition_group(self.break_condition, last_output)
                else:
                    should_break = evaluate_condition(self.break_condition, last_output)
                if should_break:
                    broke_early = True
                    break

        # Store loop metadata in shared_memory
        if broke_early:
            break_reason = "condition met"
        else:
            break_reason = "max_rounds reached"

        meta_key = f"__loop__{self.block_id}"
        state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=f"completed_{rounds_completed}_rounds"),
                },
                "shared_memory": {
                    **state.shared_memory,
                    meta_key: {
                        "rounds_completed": rounds_completed,
                        "broke_early": broke_early,
                        "break_reason": break_reason,
                    },
                },
            }
        )

        return state


class TeamLeadBlock(BaseBlock):
    """
    Analyze failure context from shared_memory and produce recommendations.

    Typical Use: After LoopBlock exhausts retries, analyze errors and recommend fixes.
    Example: TeamLeadBlock reads retry_errors and produces actionable recommendation.
    """

    def __init__(
        self,
        block_id: str,
        failure_context_keys: List[str],
        team_lead_soul: Soul,
        runner: RunsightTeamRunner,
    ):
        """
        Args:
            block_id: Unique block identifier.
            failure_context_keys: Keys to read from state.shared_memory for analysis.
            team_lead_soul: Agent that performs failure analysis.
            runner: Execution engine for running tasks.

        Raises:
            ValueError: If block_id is empty or failure_context_keys is empty.
        """
        super().__init__(block_id)
        if not failure_context_keys:
            raise ValueError(f"TeamLeadBlock {block_id}: failure_context_keys cannot be empty")
        self.failure_context_keys = failure_context_keys
        self.team_lead_soul = team_lead_soul
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Analyze failure context and produce recommendations.

        Args:
            state: Must have all failure_context_keys present in shared_memory.

        Returns:
            New state with:
            - results[block_id] = recommendation text
            - shared_memory[f"{block_id}_recommendation"] = recommendation text
            - messages appended with advisor summary
            - total_cost_usd and total_tokens updated with execution result

        Raises:
            ValueError: If any failure_context_key missing from state.shared_memory.
        """
        # Step 1: Validate all context keys exist
        missing_keys = [key for key in self.failure_context_keys if key not in state.shared_memory]
        if missing_keys:
            raise ValueError(
                f"TeamLeadBlock {self.block_id}: missing failure context keys: {missing_keys}. "
                f"Available keys: {list(state.shared_memory.keys())}"
            )

        # Step 2: Gather error context
        error_contexts = []
        for key in self.failure_context_keys:
            context_value = state.shared_memory[key]
            # Handle both list and string values
            if isinstance(context_value, list):
                formatted = "\n".join([f"  - {item}" for item in context_value])
            else:
                formatted = str(context_value)
            error_contexts.append(f"Context from '{key}':\n{formatted}")

        combined_context = "\n\n".join(error_contexts)

        # Step 3: Construct analysis task
        analysis_instruction = f"""You are analyzing a workflow failure. Review the error context below and provide:
1. Root cause analysis
2. Recommended remediation steps
3. Prevention strategies for future runs

Error Context:
{combined_context}

Provide your analysis and recommendations in a structured format."""

        analysis_task = Task(id=f"{self.block_id}_analysis", instruction=analysis_instruction)

        # Step 4: Execute analysis
        result = await self.runner.execute_task(analysis_task, self.team_lead_soul)

        # Step 5: Return updated state
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=result.output)},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_recommendation": result.output,
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] TeamLeadBlock analyzed {len(self.failure_context_keys)} context(s)",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
            }
        )


class EngineeringManagerBlock(BaseBlock):
    """
    Generate alternative execution plan using LLM, parse into structured steps.

    Typical Use: After workflow failure, generate new plan with structured steps.
    Example: EngineeringManagerBlock reads current task and failure context, produces plan + JSON steps.
    """

    def __init__(
        self,
        block_id: str,
        engineering_manager_soul: Soul,
        runner: RunsightTeamRunner,
    ):
        """
        Args:
            block_id: Unique block identifier.
            engineering_manager_soul: Agent that generates execution plans.
            runner: Execution engine for running tasks.

        Raises:
            ValueError: If block_id is empty (from BaseBlock).
        """
        super().__init__(block_id)
        self.engineering_manager_soul = engineering_manager_soul
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Generate alternative execution plan based on current context.

        Args:
            state: Must have state.current_task set. Optionally reads failure context from shared_memory.

        Returns:
            New state with:
            - results[block_id] = text plan from LLM
            - metadata[f"{block_id}_new_steps"] = List[Dict[str, str]] with keys: step_id, description
            - messages appended with replanner summary
            - total_cost_usd and total_tokens updated with execution result

        Raises:
            ValueError: If state.current_task is None.
        """
        # Step 1: Validate current_task
        if state.current_task is None:
            raise ValueError(f"EngineeringManagerBlock {self.block_id}: state.current_task is None")

        # Step 2: Gather context (current task + any failure info in shared_memory)
        context_parts = [f"Original Goal: {state.current_task.instruction}"]

        # Check for common failure context keys
        if f"{self.block_id}_previous_errors" in state.shared_memory:
            context_parts.append(
                f"Previous Errors:\n{state.shared_memory[f'{self.block_id}_previous_errors']}"
            )

        combined_context = "\n\n".join(context_parts)

        # Step 3: Construct planning task
        planning_instruction = f"""You are a workflow planner. Given the context below, create a detailed execution plan.

{combined_context}

Provide your plan as a numbered list where each step follows this format:
<step_number>. <step_id>: <description>

Example:
1. research_phase: Gather requirements and analyze constraints
2. design_phase: Create technical architecture
3. implementation_phase: Implement core features

Your plan:"""

        planning_task = Task(id=f"{self.block_id}_planning", instruction=planning_instruction)

        # Step 4: Execute planning task
        result = await self.runner.execute_task(planning_task, self.engineering_manager_soul)
        text_plan = result.output

        # Step 5: Parse plan to extract structured steps
        # Regex pattern: ^\d+\.\s+([^:]+):\s+(.+)$
        # Matches: "1. step_id: description"
        step_pattern = re.compile(r"^\d+\.\s+([^:]+):\s+(.+)$", re.MULTILINE)
        matches = step_pattern.findall(text_plan)

        structured_steps: List[Dict[str, str]] = []
        if matches:
            # Successfully parsed structured format
            for step_id, description in matches:
                structured_steps.append(
                    {"step_id": step_id.strip(), "description": description.strip()}
                )
        else:
            # Fallback: LLM didn't follow format, create single generic step
            structured_steps = [
                {
                    "step_id": "replanned_execution",
                    "description": text_plan[:200] + "..." if len(text_plan) > 200 else text_plan,
                }
            ]

        # Step 6: Return updated state
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=text_plan)},
                "metadata": {
                    **state.metadata,
                    f"{self.block_id}_new_steps": structured_steps,
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] EngineeringManagerBlock generated {len(structured_steps)} step(s)",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
            }
        )


class RouterBlock(BaseBlock):
    """
    Evaluate routing condition using Soul (LLM) or Callable (function).

    Supports two evaluation modes:
    1. Soul evaluator: LLM decides based on current_task
    2. Callable evaluator: Function evaluates state programmatically

    Typical Use: Decision points in workflows (approve/reject, route selection).
    Output: Decision string stored in results and metadata.
    """

    def __init__(
        self,
        block_id: str,
        condition_evaluator: Union[Soul, Callable[[WorkflowState], str]],
        runner: Optional[RunsightTeamRunner] = None,
    ) -> None:
        """
        Args:
            block_id: Unique block identifier.
            condition_evaluator: Either a Soul (LLM evaluates) or Callable (function evaluates).
            runner: Required if condition_evaluator is Soul, optional otherwise.

        Raises:
            ValueError: If block_id is empty (from BaseBlock).
            ValueError: If condition_evaluator is Soul but runner is None.
        """
        super().__init__(block_id)

        # Validation: runner required for Soul evaluator
        if isinstance(condition_evaluator, Soul) and runner is None:
            raise ValueError(
                f"RouterBlock {block_id}: runner is required when condition_evaluator is Soul"
            )

        self.condition_evaluator = condition_evaluator
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Evaluate routing condition and store decision.

        Args:
            state: If condition_evaluator is Soul, must have state.current_task set.

        Returns:
            New state with:
            - results[block_id] = decision string (e.g., "approved", "rejected")
            - metadata[f"{block_id}_decision"] = decision string
            - messages appended with routing decision summary
            - total_cost_usd and total_tokens updated with execution result (if Soul evaluator)

        Raises:
            ValueError: If condition_evaluator is Soul but current_task is None.
        """
        # Step 1: Evaluate condition based on type
        additional_cost = 0.0
        additional_tokens = 0
        if isinstance(self.condition_evaluator, Soul):
            # Soul-based evaluation (LLM decides)
            if state.current_task is None:
                raise ValueError(
                    f"RouterBlock {self.block_id}: state.current_task is None (required for Soul evaluator)"
                )

            # Execute routing task with Soul
            # Type narrowing: runner is guaranteed non-None when condition_evaluator is Soul (validated in __init__)
            assert self.runner is not None, "Runner must be provided for Soul evaluator"
            result = await self.runner.execute_task(state.current_task, self.condition_evaluator)
            decision = result.output.strip()
            additional_cost = result.cost_usd
            additional_tokens = result.total_tokens
        else:
            # Callable-based evaluation (function decides)
            decision = self.condition_evaluator(state)

        # Step 2: Return updated state with decision
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: BlockResult(output=decision)},
                "metadata": {
                    **state.metadata,
                    f"{self.block_id}_decision": decision,
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] RouterBlock decision: {decision}",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + additional_cost,
                "total_tokens": state.total_tokens + additional_tokens,
            }
        )


class WorkflowBlock(BaseBlock):
    """
    Execute entire child workflow as a single block step.

    Implements Hierarchical State Machine (HSM) pattern with:
    - Isolated child state (clean WorkflowState passed to child)
    - Explicit input/output mapping (dotted path resolution)
    - Cycle detection (call_stack tracking)
    - Depth limits (max_depth enforcement)
    - Cost propagation (child metrics added to parent)

    Typical Use: Workflow composition where parent delegates complex
                 sub-task to a self-contained child workflow.

    Example YAML:
        sub_analysis:
          type: workflow
          workflow_ref: analysis_pipeline
          inputs:
            shared_memory.topic: shared_memory.research_topic
            context: results.research
          outputs:
            results.analysis_result: results.final
            shared_memory.insights: shared_memory.key_insights
          max_depth: 5
    """

    def __init__(
        self,
        block_id: str,
        child_workflow: "Workflow",
        inputs: Dict[str, str],
        outputs: Dict[str, str],
        max_depth: int = 10,
    ):
        """
        Args:
            block_id: Unique identifier for this block instance.
            child_workflow: The workflow to execute as a sub-step.
            inputs: Mapping of child state keys → parent dotted paths.
                   Format: {"child.dotted.path": "parent.dotted.path"}
                   Example: {"shared_memory.topic": "shared_memory.research_topic"}
            outputs: Mapping of parent dotted paths → child dotted paths.
                    Format: {"parent.dotted.path": "child.dotted.path"}
                    Example: {"results.analysis": "results.final"}
            max_depth: Maximum recursion depth (default: 10).

        Raises:
            ValueError: If block_id is empty (from BaseBlock.__init__).
        """
        super().__init__(block_id)
        self.child_workflow = child_workflow
        self.inputs = inputs
        self.outputs = outputs
        self.max_depth = max_depth

    async def execute(
        self,
        state: WorkflowState,
        *,
        call_stack: List[str] = [],
        workflow_registry: Optional["WorkflowRegistry"] = None,
        **kwargs,
    ) -> WorkflowState:
        """
        Execute child workflow with isolated state and map outputs back to parent.

        Execution Flow (6 steps):
        1. Cycle detection: Check if child_workflow.name in call_stack
        2. Depth check: Verify len(call_stack) < max_depth
        3. Map inputs: Create clean child state from parent state via inputs mapping
        4. Run child: Execute child_workflow.run() with extended call_stack
        5. Map outputs: Write child results back to parent state via outputs mapping
        6. Propagate costs: Add child costs/tokens to parent, append system message

        Args:
            state: Parent workflow state (read-only).
            call_stack: Workflow name stack (prevents cycles). Default: empty list.
                       Format: ["parent_wf", "intermediate_wf", ...]
            workflow_registry: Workflow resolution registry (passed through to child).
            **kwargs: Additional keyword arguments (ignored by this block).

        Returns:
            New parent state with:
            - results[block_id] = f"WorkflowBlock '{child_workflow.name}' completed"
            - Mapped outputs written to parent state fields
            - total_cost_usd += child_final_state.total_cost_usd
            - total_tokens += child_final_state.total_tokens
            - messages appended with system message

        Raises:
            RecursionError: If cycle detected (child_workflow.name in call_stack).
            RecursionError: If depth limit exceeded (len(call_stack) >= max_depth).
            KeyError: If input mapping references non-existent parent key at runtime.
            KeyError: If output mapping references non-existent child key at runtime.
            Exception: Any exception from child_workflow.run() propagates immediately.
        """
        # Step 1: Cycle detection
        if self.child_workflow.name in call_stack:
            raise RecursionError(
                f"WorkflowBlock '{self.block_id}': cycle detected. "
                f"Workflow '{self.child_workflow.name}' is already in call stack. "
                f"Call stack: {' -> '.join(call_stack)} -> {self.child_workflow.name}"
            )

        # Step 2: Depth check
        if len(call_stack) >= self.max_depth:
            raise RecursionError(
                f"WorkflowBlock '{self.block_id}': maximum depth {self.max_depth} exceeded. "
                f"Call stack depth: {len(call_stack)}. "
                f"Call stack: {' -> '.join(call_stack)}"
            )

        # Step 3: Map inputs (parent → child)
        child_state = self._map_inputs(state, self.inputs)

        # Step 4: Run child workflow (propagate observer for monitoring)
        observer = kwargs.get("observer")
        child_final_state = await self.child_workflow.run(
            child_state,
            call_stack=call_stack + [self.child_workflow.name],
            workflow_registry=workflow_registry,
            observer=observer,
        )

        # Step 5: Map outputs (child → parent)
        new_parent_state = self._map_outputs(state, child_final_state, self.outputs)

        # Step 6: Propagate costs and add system message
        return new_parent_state.model_copy(
            update={
                "results": {
                    **new_parent_state.results,
                    self.block_id: BlockResult(
                        output=f"WorkflowBlock '{self.child_workflow.name}' completed"
                    ),
                },
                "execution_log": new_parent_state.execution_log
                + [
                    {
                        "role": "system",
                        "content": (
                            f"[Block {self.block_id}] WorkflowBlock '{self.child_workflow.name}' "
                            f"completed (cost: ${child_final_state.total_cost_usd:.4f}, "
                            f"tokens: {child_final_state.total_tokens})"
                        ),
                    }
                ],
                "total_cost_usd": new_parent_state.total_cost_usd
                + child_final_state.total_cost_usd,
                "total_tokens": new_parent_state.total_tokens + child_final_state.total_tokens,
            }
        )

    def _resolve_dotted(self, state: WorkflowState, path: str, *, context: str = "state") -> Any:
        """
        Resolve dotted path to value in WorkflowState.

        Supported path formats:
        - "current_task" → state.current_task
        - "results.block_id" → state.results["block_id"]
        - "shared_memory.key" → state.shared_memory["key"]
        - "metadata.key" → state.metadata["key"]

        Args:
            state: WorkflowState to read from.
            path: Dotted path string.
            context: Context string for error messages (e.g. "parent state", "child state").

        Returns:
            Resolved value (any JSON-serializable type).

        Raises:
            KeyError: If key not found in dict at runtime. Error message includes:
                     - block_id
                     - full path
                     - context (parent/child state)
                     - available keys in that field
        """
        parts = path.split(".", 1)
        field = parts[0]

        if field == "current_task":
            if len(parts) > 1:
                raise ValueError(
                    f"WorkflowBlock '{self.block_id}': invalid path '{path}'. "
                    f"current_task does not support nested access."
                )
            return state.current_task

        elif field in ("results", "shared_memory", "metadata"):
            if len(parts) != 2:
                raise ValueError(
                    f"WorkflowBlock '{self.block_id}': invalid path '{path}'. "
                    f"Expected format: '{field}.key', got '{path}'."
                )
            key = parts[1]
            field_dict = getattr(state, field)

            if key not in field_dict:
                raise KeyError(
                    f"WorkflowBlock '{self.block_id}': path '{path}' not found in {context}. "
                    f"Available {field} keys: {sorted(field_dict.keys())}"
                )
            return field_dict[key]

        else:
            raise ValueError(
                f"WorkflowBlock '{self.block_id}': invalid path prefix '{field}'. "
                f"Supported prefixes: current_task, results, shared_memory, metadata."
            )

    def _write_dotted(self, state: WorkflowState, path: str, value: Any) -> WorkflowState:
        """
        Write value to dotted path in WorkflowState, returning new state.

        Supported path formats:
        - "current_task" → state.current_task = value
        - "results.block_id" → state.results["block_id"] = value
        - "shared_memory.key" → state.shared_memory["key"] = value
        - "metadata.key" → state.metadata["key"] = value

        Args:
            state: WorkflowState to write to (not mutated).
            path: Dotted path string.
            value: Value to write (any JSON-serializable type).

        Returns:
            New WorkflowState with value written to path.

        Raises:
            ValueError: If path format is invalid (bad prefix or missing key part).
        """
        parts = path.split(".", 1)
        field = parts[0]

        if field == "current_task":
            if len(parts) > 1:
                raise ValueError(
                    f"WorkflowBlock '{self.block_id}': invalid path '{path}'. "
                    f"current_task does not support nested access."
                )
            return state.model_copy(update={"current_task": value})

        elif field in ("results", "shared_memory", "metadata"):
            if len(parts) != 2:
                raise ValueError(
                    f"WorkflowBlock '{self.block_id}': invalid path '{path}'. "
                    f"Expected format: '{field}.key', got '{path}'."
                )
            key = parts[1]
            field_dict = getattr(state, field)
            new_dict = {**field_dict, key: value}
            return state.model_copy(update={field: new_dict})

        else:
            raise ValueError(
                f"WorkflowBlock '{self.block_id}': invalid path prefix '{field}'. "
                f"Supported prefixes: current_task, results, shared_memory, metadata."
            )

    def _map_inputs(
        self,
        parent_state: WorkflowState,
        inputs: Dict[str, str],
    ) -> WorkflowState:
        """
        Create clean child state by mapping parent values to child state fields.

        Algorithm:
        1. Start with empty WorkflowState (all fields at defaults)
        2. For each (child_key, parent_path) in inputs:
           a. Resolve parent_path in parent_state using _resolve_dotted()
           b. Write to child_key in child_state using _write_dotted()
        3. Return populated child_state

        Args:
            parent_state: Parent workflow state (read-only).
            inputs: Mapping of child state keys → parent dotted paths.
                   Example: {"shared_memory.topic": "shared_memory.research_topic"}

        Returns:
            New WorkflowState with only mapped inputs populated.
            All other fields remain at defaults (empty dicts, 0 costs, etc.).

        Raises:
            KeyError: If any parent_path not found in parent_state (via _resolve_dotted).
        """
        child_state = WorkflowState(artifact_store=parent_state.artifact_store)

        for child_key, parent_path in inputs.items():
            # Resolve value from parent
            value = self._resolve_dotted(parent_state, parent_path, context="parent state")

            # Write to child state
            child_state = self._write_dotted(child_state, child_key, value)

        return child_state

    def _map_outputs(
        self,
        parent_state: WorkflowState,
        child_final_state: WorkflowState,
        outputs: Dict[str, str],
    ) -> WorkflowState:
        """
        Write child workflow results back to parent state via output mapping.

        Algorithm:
        1. Start with parent_state as base
        2. For each (parent_path, child_path) in outputs:
           a. Resolve child_path in child_final_state using _resolve_dotted()
           b. Write to parent_path in parent_state using _write_dotted()
        3. Return updated parent_state

        Args:
            parent_state: Parent workflow state (read-only).
            child_final_state: Final state from child workflow execution (read-only).
            outputs: Mapping of parent dotted paths → child dotted paths.
                    Example: {"results.analysis": "results.final"}

        Returns:
            New parent WorkflowState with mapped outputs written.
            Original parent fields preserved unless explicitly overwritten.

        Raises:
            KeyError: If any child_path not found in child_final_state (via _resolve_dotted).
        """
        new_parent = parent_state

        for parent_path, child_path in outputs.items():
            # Resolve value from child
            value = self._resolve_dotted(child_final_state, child_path, context="child state")

            # Write to parent state
            new_parent = self._write_dotted(new_parent, parent_path, value)

        return new_parent


class GateBlock(BaseBlock):
    """
    Quality gate that evaluates content and either passes or fails the workflow.

    On PASS: stores result (or extracted content) and continues execution.
    On FAIL: raises ValueError with feedback, enabling LoopBlock to catch and retry.

    Supports optional content extraction from JSON data via the extract_field
    parameter — extracts the named field from the last entry of a JSON array
    stored in results[eval_key].
    """

    def __init__(
        self,
        block_id: str,
        gate_soul: Soul,
        eval_key: str,
        runner: RunsightTeamRunner,
        extract_field: Optional[str] = None,
    ):
        super().__init__(block_id)
        self.gate_soul = gate_soul
        self.eval_key = eval_key
        self.runner = runner
        self.extract_field = extract_field

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        if self.eval_key not in state.results:
            raise ValueError(
                f"GateBlock '{self.block_id}': eval_key '{self.eval_key}' not found in state.results. "
                f"Available keys: {sorted(state.results.keys())}"
            )

        content = (
            state.results[self.eval_key].output
            if hasattr(state.results[self.eval_key], "output")
            else str(state.results[self.eval_key])
        )

        gate_task = Task(
            id=f"{self.block_id}_eval",
            instruction=(
                "Evaluate the following content and decide if it meets quality standards.\n\n"
                f"{content}\n\n"
                "Respond with EXACTLY one of:\n"
                "PASS - if the content meets quality standards\n"
                "FAIL: <detailed reason> - if the content needs improvement"
            ),
        )
        result = await self.runner.execute_task(gate_task, self.gate_soul)
        decision_line = result.output.strip().split("\n")[0]
        is_pass = decision_line.upper().startswith("PASS")

        if is_pass:
            pass_through = decision_line
            if self.extract_field:
                try:
                    data = json.loads(content)
                    if isinstance(data, list) and data:
                        pass_through = data[-1].get(self.extract_field, decision_line)
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    pass_through = decision_line

            return state.model_copy(
                update={
                    "results": {**state.results, self.block_id: BlockResult(output=pass_through)},
                    "metadata": {
                        **state.metadata,
                        f"{self.block_id}_decision": "pass",
                    },
                    "execution_log": state.execution_log
                    + [
                        {
                            "role": "system",
                            "content": f"[Block {self.block_id}] Gate: PASS",
                        }
                    ],
                    "total_cost_usd": state.total_cost_usd + result.cost_usd,
                    "total_tokens": state.total_tokens + result.total_tokens,
                }
            )
        else:
            feedback = decision_line[5:].strip() if ":" in decision_line else decision_line
            error = ValueError(f"GateBlock '{self.block_id}' FAILED: {feedback}")
            error.state = state.model_copy(
                update={
                    "total_cost_usd": state.total_cost_usd + result.cost_usd,
                    "total_tokens": state.total_tokens + result.total_tokens,
                    "metadata": {
                        **state.metadata,
                        f"{self.block_id}_decision": "fail",
                    },
                }
            )
            raise error


class FileWriterBlock(BaseBlock):
    """
    Write content from workflow state to a file on disk.

    Reads state.results[content_key] and writes it to output_path.
    Creates parent directories if they don't exist.
    No LLM calls — pure I/O operation.
    """

    def __init__(self, block_id: str, output_path: str, content_key: str):
        super().__init__(block_id)
        self.output_path = output_path
        self.content_key = content_key

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        if self.content_key not in state.results:
            raise ValueError(
                f"FileWriterBlock '{self.block_id}': content_key '{self.content_key}' "
                f"not found in state.results. Available keys: {sorted(state.results.keys())}"
            )

        _raw = state.results[self.content_key]
        content = _raw.output if hasattr(_raw, "output") else str(_raw)
        output = Path(self.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")

        char_count = len(content)
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=f"Written {char_count} chars to {self.output_path}"
                    ),
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] FileWriter: wrote {char_count} chars to {self.output_path}",
                    }
                ],
            }
        )


# ---------------------------------------------------------------------------
# CodeBlock — sandboxed Python code execution
# ---------------------------------------------------------------------------

DEFAULT_ALLOWED_IMPORTS: List[str] = [
    "json",
    "re",
    "math",
    "datetime",
    "collections",
    "itertools",
    "hashlib",
    "base64",
    "time",
    "urllib.parse",
]

BLOCKED_BUILTINS: set = {
    "__import__",
    "open",
    "exec",
    "eval",
    "compile",
    "globals",
    "locals",
    "breakpoint",
}

BLOCKED_MODULES: set = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "importlib",
}


def _validate_code_ast(code: str, allowed_imports: List[str]) -> None:
    """
    Parse *code* with :func:`ast.parse` and reject dangerous constructs.

    Raises:
        ValueError: If the code contains forbidden imports, builtins, or
            is missing a ``def main(data)`` function.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Code has a syntax error: {exc}") from exc

    has_main = False

    for node in ast.walk(tree):
        # --- import <module> ---
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in BLOCKED_MODULES:
                    raise ValueError(f"Import of '{alias.name}' is not allowed")
                if top not in allowed_imports:
                    raise ValueError(f"Import of '{alias.name}' is not in the allowed list")

        # --- from <module> import ... ---
        if isinstance(node, ast.ImportFrom):
            if node.module is not None:
                top = node.module.split(".")[0]
                if top in BLOCKED_MODULES:
                    raise ValueError(f"Import from '{node.module}' is not allowed")
                if top not in allowed_imports:
                    raise ValueError(f"Import from '{node.module}' is not in the allowed list")

        # --- function calls: __import__, open, eval, exec, compile, etc. ---
        if isinstance(node, ast.Call):
            func = node.func
            name: Optional[str] = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name and name in BLOCKED_BUILTINS:
                raise ValueError(f"Call to '{name}()' is not allowed")

        # --- detect def main ---
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            has_main = True

    if not has_main:
        raise ValueError("Code must define a 'def main(data)' function")


_HARNESS_TEMPLATE = textwrap.dedent(
    """\
import sys, json

# --- user code ---
{user_code}
# --- end user code ---

_input = json.loads(sys.stdin.read())
_result = main(_input)
sys.stdout.write(json.dumps(_result))
"""
)


class CodeBlock(BaseBlock):
    """
    Execute user-provided Python code in an isolated subprocess.

    The code MUST define ``def main(data) -> <json-serializable>``.
    ``data`` is a dict with keys ``results``, ``metadata``, ``shared_memory``
    from the current :class:`WorkflowState`.

    Security:
        * AST validation rejects dangerous imports / builtins at init time.
        * Execution happens in a subprocess with a minimal environment.
        * A configurable timeout (default 30 s) kills runaway processes.

    No LLM calls — cost and tokens are unchanged.
    """

    def __init__(
        self,
        block_id: str,
        code: str,
        timeout_seconds: int = 30,
        allowed_imports: Optional[List[str]] = None,
    ):
        super().__init__(block_id)
        if not code or not code.strip():
            raise ValueError("Code cannot be empty")
        self.code = code
        self.timeout_seconds = timeout_seconds
        self.allowed_imports = (
            allowed_imports if allowed_imports is not None else list(DEFAULT_ALLOWED_IMPORTS)
        )
        self._validate_code()

    def _validate_code(self) -> None:
        """Validate user code via AST analysis."""
        _validate_code_ast(self.code, self.allowed_imports)

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """Run user code in a subprocess and return updated state."""
        harness = _HARNESS_TEMPLATE.format(user_code=self.code)

        stdin_data = json.dumps(
            {
                "results": {
                    k: v.output if hasattr(v, "output") else v for k, v in state.results.items()
                },
                "metadata": state.metadata,
                "shared_memory": state.shared_memory,
            }
        ).encode()

        import os

        minimal_env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")}
        # On macOS, include DYLD_LIBRARY_PATH if present
        for key in ("HOME", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
            if key in os.environ:
                minimal_env[key] = os.environ[key]

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                harness,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=minimal_env,
            )

            async def _communicate():
                return await proc.communicate(input=stdin_data)

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                _communicate(), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            # Kill the process on timeout
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise TimeoutError(
                f"CodeBlock '{self.block_id}': execution timed out after {self.timeout_seconds}s"
            )

        if proc.returncode != 0:
            error_msg = stderr_bytes.decode(errors="replace").strip()
            return state.model_copy(
                update={
                    "results": {
                        **state.results,
                        self.block_id: BlockResult(output=f"Error: {error_msg}"),
                    },
                    "execution_log": state.execution_log
                    + [
                        {
                            "role": "system",
                            "content": f"[Block {self.block_id}] CodeBlock: error — {error_msg}",
                        }
                    ],
                }
            )

        stdout = stdout_bytes.decode(errors="replace").strip()
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            return state.model_copy(
                update={
                    "results": {
                        **state.results,
                        self.block_id: BlockResult(
                            output=f"Error: output is not valid JSON: {stdout!r}"
                        ),
                    },
                    "execution_log": state.execution_log
                    + [
                        {
                            "role": "system",
                            "content": f"[Block {self.block_id}] CodeBlock: non-JSON output",
                        }
                    ],
                }
            )

        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=json.dumps(result) if not isinstance(result, str) else result
                    ),
                },
                "execution_log": state.execution_log
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] CodeBlock: executed successfully",
                    }
                ],
            }
        )
