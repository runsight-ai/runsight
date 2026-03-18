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
from runsight_core.state import WorkflowState
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner

if TYPE_CHECKING:
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

        result = await self.runner.execute_task(state.current_task, self.soul)

        # Truncate output for message log (prevent state size explosion)
        truncated = result.output[:200] + "..." if len(result.output) > 200 else result.output

        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: result.output},
                "messages": state.messages
                + [
                    {"role": "system", "content": f"[Block {self.block_id}] Completed: {truncated}"}
                ],
                "total_cost_usd": state.total_cost_usd + result.cost_usd,
                "total_tokens": state.total_tokens + result.total_tokens,
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

        # Execute all souls in parallel (preserves order)
        tasks = [self.runner.execute_task(state.current_task, soul) for soul in self.souls]
        results = await asyncio.gather(*tasks)  # Raises on first failure

        # Aggregate outputs as JSON
        outputs = [{"soul_id": result.soul_id, "output": result.output} for result in results]

        # Aggregate costs and tokens
        total_cost = sum(result.cost_usd for result in results)
        total_tokens = sum(result.total_tokens for result in results)

        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: json.dumps(outputs, indent=2)},
                "messages": state.messages
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] FanOut completed with {len(self.souls)} agents",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + total_cost,
                "total_tokens": state.total_tokens + total_tokens,
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
            [f"=== Output from {bid} ===\n{state.results[bid]}" for bid in self.input_block_ids]
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
                "results": {**state.results, self.block_id: result.output},
                "messages": state.messages
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


class DebateBlock(BaseBlock):
    """
    Runs iterative debate between two agents, storing transcript and conclusion.

    Typical Use: Adversarial review (agent A proposes, agent B critiques, iterate).
    Output Format: JSON transcript + conclusion in shared_memory.
    """

    def __init__(
        self,
        block_id: str,
        soul_a: Soul,
        soul_b: Soul,
        iterations: int,
        runner: RunsightTeamRunner,
    ):
        """
        Args:
            block_id: Unique block identifier.
            soul_a: First debater (starts each round).
            soul_b: Second debater (responds to soul_a).
            iterations: Number of debate rounds (must be >= 1).
            runner: Execution engine for running tasks.

        Raises:
            ValueError: If block_id is empty or iterations < 1.
        """
        super().__init__(block_id)
        if iterations < 1:
            raise ValueError(f"DebateBlock {block_id}: iterations must be >= 1, got {iterations}")
        self.soul_a = soul_a
        self.soul_b = soul_b
        self.iterations = iterations
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Run debate for N iterations, alternating between soul_a and soul_b.

        Args:
            state: Must have state.current_task set (the debate topic).

        Returns:
            New state with:
            - results[block_id] = JSON transcript: [{"round": 1, "soul_a": "...", "soul_b": "..."}, ...]
            - shared_memory[f"{block_id}_conclusion"] = final soul_b response
            - messages appended with debate summary
            - total_cost_usd and total_tokens updated with all execution results

        Raises:
            ValueError: If state.current_task is None.
        """
        if state.current_task is None:
            raise ValueError(f"DebateBlock {self.block_id}: state.current_task is None")

        transcript: List[Dict[str, Any]] = []
        previous_b_output: str = ""
        total_cost = 0.0
        total_tokens = 0

        original_context = state.current_task.context or ""

        for round_num in range(1, self.iterations + 1):
            # Soul A: include original task context (may contain retry feedback) + prior B output
            task_a_context_parts = []
            if original_context:
                task_a_context_parts.append(original_context)
            if previous_b_output:
                task_a_context_parts.append(
                    f"Previous response from {self.soul_b.role}: {previous_b_output}"
                )
            task_a_context = "\n\n".join(task_a_context_parts) if task_a_context_parts else None
            task_a = Task(
                id=f"{self.block_id}_round{round_num}_a",
                instruction=state.current_task.instruction,
                context=task_a_context,
            )
            result_a = await self.runner.execute_task(task_a, self.soul_a)
            total_cost += result_a.cost_usd
            total_tokens += result_a.total_tokens

            # Soul B: include original task context + A's response
            task_b_context_parts = []
            if original_context:
                task_b_context_parts.append(original_context)
            task_b_context_parts.append(f"Response from {self.soul_a.role}: {result_a.output}")
            task_b = Task(
                id=f"{self.block_id}_round{round_num}_b",
                instruction=state.current_task.instruction,
                context="\n\n".join(task_b_context_parts),
            )
            result_b = await self.runner.execute_task(task_b, self.soul_b)
            total_cost += result_b.cost_usd
            total_tokens += result_b.total_tokens

            transcript.append(
                {"round": round_num, "soul_a": result_a.output, "soul_b": result_b.output}
            )
            previous_b_output = result_b.output

        # Final conclusion is last soul_b response
        conclusion = transcript[-1]["soul_b"]

        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: json.dumps(transcript, indent=2)},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_conclusion": conclusion,
                },
                "messages": state.messages
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] Debate completed: {self.iterations} rounds",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + total_cost,
                "total_tokens": state.total_tokens + total_tokens,
            }
        )


class RetryBlock(BaseBlock):
    """
    Wrap any BaseBlock with retry logic on exceptions.

    Typical Use: Wrap flaky API blocks or unreliable operations.
    Example: RetryBlock wraps APICallBlock, retries on ConnectionError.
    """

    def __init__(
        self,
        block_id: str,
        inner_block: BaseBlock,
        max_retries: int = 3,
        provide_error_context: bool = False,
    ) -> None:
        """
        Args:
            block_id: Unique identifier for this block instance.
            inner_block: The block to wrap with retry logic.
            max_retries: Maximum number of retries after initial attempt (default: 3).
                        Total attempts = 1 initial + max_retries.
            provide_error_context: If True, store error messages in shared_memory.

        Raises:
            ValueError: If block_id is empty (from BaseBlock).
            ValueError: If max_retries < 0.
        """
        super().__init__(block_id)
        if max_retries < 0:
            raise ValueError(f"RetryBlock {block_id}: max_retries must be >= 0, got {max_retries}")
        self.inner_block = inner_block
        self.max_retries = max_retries
        self.provide_error_context = provide_error_context

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Execute inner block with retry logic on exceptions.

        Args:
            state: Passed to inner_block.execute().
            **kwargs: Forwarded to inner_block.execute() (e.g. call_stack, workflow_registry).

        Returns:
            New state with:
            - results[block_id] = results[inner_block.block_id] (if success)
            - shared_memory[f"{block_id}_retry_errors"] = List[str] (if provide_error_context=True)
            - messages appended with retry summary

        Raises:
            Exception: If all retries exhausted, raises the last exception from inner_block.
        """
        errors: List[str] = []
        attempts = 0  # Starts at 0, will increment to 1, 2, 3, ...
        last_exception: Optional[Exception] = None

        # Total attempts = 1 initial + max_retries retries
        for attempt_num in range(self.max_retries + 1):
            attempts += 1  # attempts now = 1, 2, 3, ... up to max_retries+1

            try:
                # Attempt execution
                result_state = await self.inner_block.execute(state, **kwargs)

                # Success! Store inner block's result under THIS block's ID
                final_state = result_state.model_copy(
                    update={
                        "results": {
                            **result_state.results,
                            self.block_id: result_state.results.get(self.inner_block.block_id, ""),
                        },
                        "messages": result_state.messages
                        + [
                            {
                                "role": "system",
                                "content": f"[Block {self.block_id}] RetryBlock succeeded after {attempts} attempt(s)",
                            }
                        ],
                    }
                )

                # Optionally store error context even on success (shows what was overcome)
                if self.provide_error_context and errors:
                    final_state = final_state.model_copy(
                        update={
                            "shared_memory": {
                                **final_state.shared_memory,
                                f"{self.block_id}_retry_errors": errors,
                            }
                        }
                    )

                return final_state

            except Exception as e:
                last_exception = e
                error_msg = (
                    f"Attempt {attempts}/{self.max_retries + 1}: {type(e).__name__}: {str(e)}"
                )
                errors.append(error_msg)

                # Inject error feedback into state for next retry attempt
                if self.provide_error_context:
                    feedback = "\n".join(errors)
                    updates: Dict[str, Any] = {
                        "shared_memory": {
                            **state.shared_memory,
                            f"{self.block_id}_retry_errors": errors.copy(),
                        },
                    }
                    if state.current_task is not None:
                        existing_ctx = state.current_task.context or ""
                        updates["current_task"] = state.current_task.model_copy(
                            update={
                                "context": (
                                    f"{existing_ctx}\n\n"
                                    f"--- RETRY FEEDBACK (attempt {attempts}) ---\n"
                                    f"{feedback}\n"
                                    f"Address these issues."
                                )
                            }
                        )
                    state = state.model_copy(update=updates)

                # If this was the last attempt, don't continue loop
                if attempt_num == self.max_retries:
                    break
                # Otherwise, continue to next retry

        # All retries exhausted - store error context and re-raise
        if self.provide_error_context:
            state = state.model_copy(
                update={
                    "shared_memory": {
                        **state.shared_memory,
                        f"{self.block_id}_retry_errors": errors,
                    }
                }
            )

        # Re-raise last exception
        if last_exception is not None:
            raise last_exception
        else:
            # This should never happen, but satisfy type checker
            raise RuntimeError(f"RetryBlock {self.block_id}: unexpected error state")


class TeamLeadBlock(BaseBlock):
    """
    Analyze failure context from shared_memory and produce recommendations.

    Typical Use: After RetryBlock exhausts retries, analyze errors and recommend fixes.
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
                "results": {**state.results, self.block_id: result.output},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_recommendation": result.output,
                },
                "messages": state.messages
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
                "results": {**state.results, self.block_id: text_plan},
                "metadata": {
                    **state.metadata,
                    f"{self.block_id}_new_steps": structured_steps,
                },
                "messages": state.messages
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


class MessageBusBlock(BaseBlock):
    """
    Orchestrate N-agent round-robin message exchange with structured transcript output.

    Typical Use: Multi-agent brainstorming with context passing between agents.
    Example: 4 agents collaborate for 3 rounds, each agent sees prior contributions in their round.
    Output Format: JSON transcript with rounds and contributions, consensus in shared_memory.
    """

    def __init__(
        self,
        block_id: str,
        souls: List[Soul],
        iterations: int,
        runner: RunsightTeamRunner,
    ):
        """
        Args:
            block_id: Unique block identifier.
            souls: List of agents participating in message exchange (must be non-empty).
            iterations: Number of rounds to execute (must be >= 1).
            runner: Execution engine for running tasks.

        Raises:
            ValueError: If block_id is empty (from BaseBlock).
            ValueError: If souls list is empty.
            ValueError: If iterations < 1.
        """
        super().__init__(block_id)
        if not souls:
            raise ValueError(f"MessageBusBlock {block_id}: souls list cannot be empty")
        if iterations < 1:
            raise ValueError(
                f"MessageBusBlock {block_id}: iterations must be >= 1, got {iterations}"
            )
        self.souls = souls
        self.iterations = iterations
        self.runner = runner

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Execute N-agent round-robin message exchange.

        Args:
            state: Must have state.current_task set (the discussion topic).

        Returns:
            New state with:
            - results[block_id] = JSON transcript: [{"round": int, "contributions": [{"soul_id": str, "output": str}]}]
            - shared_memory[f"{block_id}_consensus"] = final agent output from last round
            - messages appended with message bus summary
            - total_cost_usd and total_tokens updated with all execution results

        Raises:
            ValueError: If state.current_task is None.
        """
        # Step 1: Validate current_task
        if state.current_task is None:
            raise ValueError(f"MessageBusBlock {self.block_id}: state.current_task is None")

        # Step 2: Initialize transcript
        transcript: List[Dict[str, Any]] = []
        total_cost = 0.0
        total_tokens = 0

        # Step 3: Execute iterations
        for round_num in range(1, self.iterations + 1):
            round_contributions: List[Dict[str, str]] = []

            # Step 4: Sequential contributions within round
            for soul in self.souls:
                # Context passing mechanism
                # Construct task by appending formatted contributions to current_task.instruction
                if round_contributions:
                    # Format prior contributions in THIS round
                    formatted_context = "\n\n".join(
                        [f"[{c['soul_id']}]: {c['output']}" for c in round_contributions]
                    )
                    context_str = f"Prior contributions in this round:\n{formatted_context}"
                else:
                    context_str = None

                # Create task with context
                task = Task(
                    id=f"{self.block_id}_r{round_num}_{soul.id}",
                    instruction=state.current_task.instruction,
                    context=context_str,
                )

                # Execute task
                result = await self.runner.execute_task(task, soul)
                total_cost += result.cost_usd
                total_tokens += result.total_tokens

                # Record contribution
                round_contributions.append({"soul_id": soul.id, "output": result.output})

            # Step 5: Append round to transcript
            transcript.append({"round": round_num, "contributions": round_contributions})

        # Step 6: Extract consensus (last agent's output in last round)
        # Note: "consensus" refers to the last agent's output, not necessarily true consensus
        final_output = transcript[-1]["contributions"][-1]["output"]

        # Step 7: Return updated state
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: json.dumps(transcript, indent=2)},
                "shared_memory": {
                    **state.shared_memory,
                    f"{self.block_id}_consensus": final_output,
                },
                "messages": state.messages
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] MessageBus completed: {len(self.souls)} agents × {self.iterations} rounds",
                    }
                ],
                "total_cost_usd": state.total_cost_usd + total_cost,
                "total_tokens": state.total_tokens + total_tokens,
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
                "results": {**state.results, self.block_id: decision},
                "metadata": {
                    **state.metadata,
                    f"{self.block_id}_decision": decision,
                },
                "messages": state.messages
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


class PlaceholderBlock(BaseBlock):
    """
    Echo block for dynamic injection fallback.

    Stores description in state.results[block_id] and appends one system
    message. Requires no current_task. Does not modify shared_memory or metadata.

    Typical Use: Fallback when BlockRegistry has no factory for an injected step_id.
    """

    def __init__(self, block_id: str, description: str) -> None:
        """
        Args:
            block_id: Unique block identifier (used as results key).
            description: Human-readable description, echoed to state.results.

        Raises:
            ValueError: If block_id is empty (from BaseBlock).
        """
        super().__init__(block_id)
        self.description = description

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        """
        Store description in results and append system message.

        Args:
            state: Current workflow state. current_task NOT required.

        Returns:
            New state with:
            - results[block_id] = self.description
            - messages appended with one system entry

        Raises:
            Nothing (pure echo operation).
        """
        return state.model_copy(
            update={
                "results": {**state.results, self.block_id: self.description},
                "messages": state.messages
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] PlaceholderBlock: {self.description}",
                    }
                ],
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
                    self.block_id: f"WorkflowBlock '{self.child_workflow.name}' completed",
                },
                "messages": new_parent_state.messages
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
        child_state = WorkflowState()

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
    On FAIL: raises ValueError with feedback, enabling RetryBlock to catch and retry.

    Supports optional content extraction from JSON data (e.g., debate transcripts)
    via the extract_field parameter — extracts the named field from the last entry
    of a JSON array stored in results[eval_key].
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

        content = state.results[self.eval_key]

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
                    "results": {**state.results, self.block_id: pass_through},
                    "metadata": {
                        **state.metadata,
                        f"{self.block_id}_decision": "pass",
                    },
                    "messages": state.messages
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

        content = state.results[self.content_key]
        output = Path(self.output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")

        char_count = len(content)
        return state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: f"Written {char_count} chars to {self.output_path}",
                },
                "messages": state.messages
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
                "results": state.results,
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
                        self.block_id: f"Error: {error_msg}",
                    },
                    "messages": state.messages
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
                        self.block_id: f"Error: output is not valid JSON: {stdout!r}",
                    },
                    "messages": state.messages
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
                    self.block_id: json.dumps(result) if not isinstance(result, str) else result,
                },
                "messages": state.messages
                + [
                    {
                        "role": "system",
                        "content": f"[Block {self.block_id}] CodeBlock: executed successfully",
                    }
                ],
            }
        )
