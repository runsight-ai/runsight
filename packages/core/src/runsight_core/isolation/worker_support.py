"""Support functions for the subprocess worker (ISO-004).

Extracted from worker.py (RUN-820) to reduce module size. Contains:
- Envelope parsing and primitive reconstruction
- Budget-aware history trimming
- State scoping
- Block type mapping and block instantiation
"""

from __future__ import annotations

import json
from typing import Any

from runsight_core.block_io import BlockContext, BlockOutput
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    SoulEnvelope,
)
from runsight_core.memory.budget import ContextBudgetRequest, fit_to_budget
from runsight_core.memory.token_counting import litellm_token_counter
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.tools import ToolInstance

# ---------------------------------------------------------------------------
# Public helper functions (importable by tests)
# ---------------------------------------------------------------------------


def parse_context_envelope(json_str: str) -> ContextEnvelope:
    """Parse a JSON string into a ContextEnvelope."""
    return ContextEnvelope.model_validate_json(json_str)


def reconstruct_soul(
    soul_envelope: SoulEnvelope,
    *,
    resolved_tools: list[ToolInstance] | None = None,
) -> Soul:
    """Convert a SoulEnvelope into a runsight_core.primitives.Soul."""
    return Soul(
        id=soul_envelope.id,
        kind="soul",
        name=soul_envelope.name,
        role=soul_envelope.role,
        system_prompt=soul_envelope.system_prompt,
        model_name=soul_envelope.model_name,
        provider=soul_envelope.provider or None,
        temperature=soul_envelope.temperature,
        max_tokens=soul_envelope.max_tokens,
        required_tool_calls=list(soul_envelope.required_tool_calls),
        max_tool_iterations=soul_envelope.max_tool_iterations,
        resolved_tools=resolved_tools,
    )


def build_budgeted_history(
    model: str,
    system_prompt: str,
    instruction: str,
    conversation_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply fit_to_budget locally to trim conversation history.

    Uses a conservative budget_ratio (0.5) to leave room for the block's
    own output, tool calls, and instruction within the worker subprocess.
    """
    budgeted = fit_to_budget(
        ContextBudgetRequest(
            model=model,
            system_prompt=system_prompt,
            instruction=instruction,
            context="",
            conversation_history=conversation_history,
            budget_ratio=0.5,
        ),
        counter=litellm_token_counter,
    )
    return budgeted.messages


def build_scoped_state(envelope: ContextEnvelope) -> WorkflowState:
    """Construct a scoped WorkflowState from envelope data."""
    results: dict[str, BlockResult] = {}
    for block_id, result_data in envelope.scoped_results.items():
        if isinstance(result_data, dict):
            results[block_id] = BlockResult(**result_data)
        else:
            results[block_id] = BlockResult(output=str(result_data))

    history_key = f"{envelope.block_id}_{envelope.soul.id}"

    return WorkflowState(
        shared_memory=dict(envelope.scoped_shared_memory),
        results=results,
        conversation_histories={history_key: list(envelope.conversation_history)},
    )


# ---------------------------------------------------------------------------
# Block type mapping and block instantiation
# ---------------------------------------------------------------------------

_BLOCK_TYPE_MAP = {
    "linear": "linear",
    "linearblock": "linear",
    "gate": "gate",
    "gateblock": "gate",
    "synthesize": "synthesize",
    "synthesizeblock": "synthesize",
    "dispatch": "dispatch",
    "dispatchblock": "dispatch",
    "assertion": "assertion",
    "assertionblock": "assertion",
}


def _resolve_block_soul(block_soul: Any, fallback_soul: Soul) -> Soul:
    if not isinstance(block_soul, dict):
        return fallback_soul
    payload = fallback_soul.model_dump(exclude={"resolved_tools"})
    payload.update(block_soul)
    payload.setdefault("required_tool_calls", fallback_soul.required_tool_calls or [])
    payload.setdefault("max_tool_iterations", fallback_soul.max_tool_iterations)
    payload["resolved_tools"] = fallback_soul.resolved_tools
    return Soul.model_validate(payload)


def _create_block(envelope: ContextEnvelope, soul: Soul, runner: RunsightTeamRunner):
    """Instantiate the correct block based on envelope.block_type."""
    block_type = _BLOCK_TYPE_MAP.get(envelope.block_type.lower(), envelope.block_type.lower())

    if block_type == "linear":
        from runsight_core.blocks.linear import LinearBlock

        block = LinearBlock(
            block_id=envelope.block_id,
            soul=soul,
            runner=runner,
        )
        block.stateful = True
        return block

    if block_type == "gate":
        from runsight_core.blocks.gate import GateBlock

        gate_soul = _resolve_block_soul(envelope.block_config.get("gate_soul"), soul)
        block = GateBlock(
            block_id=envelope.block_id,
            gate_soul=gate_soul,
            eval_key=str(envelope.block_config.get("eval_key", "")),
            extract_field=envelope.block_config.get("extract_field"),
            runner=runner,
        )
        block.stateful = True
        return block

    if block_type == "synthesize":
        from runsight_core.blocks.synthesize import SynthesizeBlock

        synthesizer_soul = _resolve_block_soul(envelope.block_config.get("synthesizer_soul"), soul)
        input_block_ids = list(envelope.block_config.get("input_block_ids", []))
        block = SynthesizeBlock(
            block_id=envelope.block_id,
            input_block_ids=input_block_ids,
            synthesizer_soul=synthesizer_soul,
            runner=runner,
        )
        block.stateful = True
        return block

    if block_type == "dispatch":
        from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch

        raw_branches = list(envelope.block_config.get("branches", []))
        branches = [
            DispatchBranch(
                exit_id=str(branch.get("exit_id", "")),
                label=str(branch.get("label", "")),
                soul=_resolve_block_soul(branch.get("soul"), soul),
                task_instruction=str(branch.get("task_instruction", "")),
            )
            for branch in raw_branches
            if isinstance(branch, dict)
        ]
        block = DispatchBlock(block_id=envelope.block_id, branches=branches, runner=runner)
        block.stateful = True
        return block

    if block_type == "assertion":
        from runsight_core.assertions.base import (
            AssertionContext,
            TokenUsage,
            grading_result_from_data,
            grading_result_to_data,
        )
        from runsight_core.assertions.registry import run_assertions

        assertion_payload = envelope.block_config.get("assertion")
        if not isinstance(assertion_payload, dict):
            raise ValueError("assertion block requires a dict assertion payload")
        output_to_grade = str(envelope.block_config.get("output_to_grade", ""))
        judge_soul_raw = envelope.block_config.get("judge_soul")
        judge_soul_payload = judge_soul_raw if isinstance(judge_soul_raw, dict) else {}
        judge_soul = _resolve_block_soul(judge_soul_payload, soul)
        usage_totals = {"cost_usd": 0.0, "total_tokens": 0}

        class AssertionBlockAdapter:
            def __init__(self, block_id: str) -> None:
                self._block_id = block_id

            async def execute(self, ctx: BlockContext) -> BlockOutput:
                async def _run_worker_llm_judge(
                    cfg: dict[str, Any],
                    assertion_output: str,
                    _assertion_context: AssertionContext,
                ):
                    client = runner._get_client(judge_soul)
                    config_payload = cfg.get("config")
                    llm_config = config_payload if isinstance(config_payload, dict) else {}
                    rubric = str(llm_config.get("rubric", ""))
                    user_prompt = (
                        "Grade the candidate output against the rubric and return JSON with fields "
                        "'passed' (bool), 'score' (0..1), 'reason' (str), optional 'named_scores', "
                        "'tokens_used', 'component_results', 'assertion_type', and 'metadata'.\n\n"
                        f"Rubric:\n{rubric}\n\nCandidate output:\n{assertion_output}"
                    )

                    response = await client.achat(
                        messages=[{"role": "user", "content": user_prompt}],
                        system_prompt=judge_soul.system_prompt,
                        temperature=judge_soul.temperature,
                    )

                    content = response.get("content")
                    if not isinstance(content, str):
                        raise ValueError("llm_judge response content must be a string")

                    try:
                        grading_payload = json.loads(content)
                    except json.JSONDecodeError as exc:
                        raise ValueError("llm_judge response must be valid JSON") from exc

                    grading = grading_result_from_data(grading_payload)
                    if grading.assertion_type is None:
                        grading.assertion_type = "llm_judge"
                    grading.metadata.setdefault("judge_model", judge_soul.model_name)

                    prompt_tokens = int(response.get("prompt_tokens", 0) or 0)
                    completion_tokens = int(response.get("completion_tokens", 0) or 0)
                    total_tokens = int(
                        response.get("total_tokens", prompt_tokens + completion_tokens) or 0
                    )
                    cost_usd = float(response.get("cost_usd", 0.0) or 0.0)
                    usage_totals["cost_usd"] += cost_usd
                    usage_totals["total_tokens"] += total_tokens

                    if grading.tokens_used is None and total_tokens > 0:
                        grading.tokens_used = TokenUsage(
                            prompt=prompt_tokens,
                            completion=completion_tokens,
                            total=total_tokens,
                        )
                    return grading

                # Use state snapshot for metadata when available
                state = ctx.state_snapshot
                cost_usd_base = state.total_cost_usd if state is not None else 0.0
                total_tokens_base = state.total_tokens if state is not None else 0
                shared_memory = dict(state.shared_memory) if state is not None else {}
                run_id = str(state.metadata.get("run_id", "")) if state is not None else ""
                workflow_id = (
                    str(state.metadata.get("workflow_id", "")) if state is not None else ""
                )

                assertion_context = AssertionContext(
                    output=output_to_grade,
                    prompt=envelope.prompt.instruction,
                    prompt_hash="",
                    soul_id=judge_soul.id,
                    soul_version="",
                    block_id=self._block_id,
                    block_type="assertion",
                    cost_usd=cost_usd_base,
                    total_tokens=total_tokens_base,
                    latency_ms=0.0,
                    variables=shared_memory,
                    run_id=run_id,
                    workflow_id=workflow_id,
                )
                assertions_result = await run_assertions(
                    [assertion_payload],
                    output=output_to_grade,
                    context=assertion_context,
                    llm_judge_runner=_run_worker_llm_judge,
                )
                if not assertions_result.results:
                    raise ValueError("assertion block produced no grading result")
                serialized = json.dumps(grading_result_to_data(assertions_result.results[0]))
                return BlockOutput(
                    output=serialized,
                    exit_handle="done",
                    cost_usd=usage_totals["cost_usd"],
                    total_tokens=usage_totals["total_tokens"],
                )

        return AssertionBlockAdapter(envelope.block_id)

    raise ValueError(f"Unsupported block_type: {block_type!r}")
