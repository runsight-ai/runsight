"""
YAML workflow parser for Runsight.
Exports: parse_workflow_yaml, parse_task_yaml, BUILT_IN_SOULS, BLOCK_TYPE_REGISTRY
"""

from __future__ import annotations

import yaml
from typing import Any, Callable, Dict, Union, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from runsight_core.yaml.registry import WorkflowRegistry

from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.implementations import (
    LinearBlock,
    FanOutBlock,
    SynthesizeBlock,
    DebateBlock,
    RetryBlock,
    TeamLeadBlock,
    EngineeringManagerBlock,
    MessageBusBlock,
    RouterBlock,
    PlaceholderBlock,
    GateBlock,
    FileWriterBlock,
)
from runsight_core.primitives import Soul, Task
from runsight_core.runner import RunsightTeamRunner
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import (
    BlockDef,
    RunsightTaskFile,
    RunsightWorkflowFile,
)


# Builder function signature: (block_id, block_def, souls_map, runner, all_blocks) → BaseBlock
BlockBuilder = Callable[
    [str, BlockDef, Dict[str, Soul], RunsightTeamRunner, Dict[str, BaseBlock]],
    BaseBlock,
]


BUILT_IN_SOULS: Dict[str, Soul] = {
    "researcher": Soul(
        id="researcher_1",
        role="Senior Researcher",
        system_prompt=(
            "You are an expert researcher. Provide concise, structured summaries "
            "backed by evidence. Cite sources where possible."
        ),
    ),
    "reviewer": Soul(
        id="reviewer_1",
        role="Peer Reviewer",
        system_prompt=(
            "You are a strict peer reviewer. Evaluate submissions critically "
            "and provide actionable, specific feedback."
        ),
    ),
    "engineering_manager": Soul(
        id="manager_1",
        role="Engineering Manager",
        system_prompt=(
            "You are an engineering manager. Break down complex problems into "
            "clear, executable steps with defined owners and outcomes."
        ),
    ),
    "coder": Soul(
        id="coder_1",
        role="Software Engineer",
        system_prompt=(
            "You are a skilled software engineer. Write clean, well-documented, "
            "tested code. Follow language idioms and best practices."
        ),
    ),
    "architect": Soul(
        id="architect_1",
        role="Systems Architect",
        system_prompt=(
            "You are a systems architect. Design robust, scalable, maintainable "
            "architectures. Make trade-offs explicit."
        ),
    ),
    "synthesizer": Soul(
        id="synthesizer_1",
        role="Synthesis Agent",
        system_prompt=(
            "You synthesize multiple inputs into coherent, unified outputs. "
            "Identify common themes, resolve conflicts, and produce comprehensive summaries."
        ),
    ),
    "generalist": Soul(
        id="generalist_1",
        role="General-purpose Assistant",
        system_prompt=(
            "You are a general-purpose assistant. Handle diverse tasks with "
            "clarity, precision, and thoughtfulness."
        ),
    ),
}


def _resolve_soul(ref: str, souls_map: Dict[str, Soul]) -> Soul:
    """
    Look up soul_ref in merged souls_map.

    Raises:
        ValueError: If ref not found in souls_map.
    """
    soul = souls_map.get(ref)
    if soul is None:
        raise ValueError(
            f"Soul reference '{ref}' not found. Available souls: {sorted(souls_map.keys())}"
        )
    return soul


def _build_linear(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> LinearBlock:
    if block_def.soul_ref is None:
        raise ValueError(f"LinearBlock '{block_id}': soul_ref is required")
    return LinearBlock(block_id, _resolve_soul(block_def.soul_ref, souls_map), runner)


def _build_fanout(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> FanOutBlock:
    if not block_def.soul_refs:
        raise ValueError(f"FanOutBlock '{block_id}': soul_refs is required (non-empty list)")
    souls = [_resolve_soul(ref, souls_map) for ref in block_def.soul_refs]
    return FanOutBlock(block_id, souls, runner)


def _build_synthesize(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> SynthesizeBlock:
    if block_def.soul_ref is None:
        raise ValueError(f"SynthesizeBlock '{block_id}': soul_ref is required")
    if not block_def.input_block_ids:
        raise ValueError(
            f"SynthesizeBlock '{block_id}': input_block_ids is required (non-empty list)"
        )
    soul = _resolve_soul(block_def.soul_ref, souls_map)
    return SynthesizeBlock(block_id, block_def.input_block_ids, soul, runner)


def _build_debate(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> DebateBlock:
    if block_def.soul_a_ref is None:
        raise ValueError(f"DebateBlock '{block_id}': soul_a_ref is required")
    if block_def.soul_b_ref is None:
        raise ValueError(f"DebateBlock '{block_id}': soul_b_ref is required")
    if block_def.iterations is None:
        raise ValueError(f"DebateBlock '{block_id}': iterations is required")
    soul_a = _resolve_soul(block_def.soul_a_ref, souls_map)
    soul_b = _resolve_soul(block_def.soul_b_ref, souls_map)
    return DebateBlock(block_id, soul_a, soul_b, block_def.iterations, runner)


def _build_message_bus(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> MessageBusBlock:
    if not block_def.soul_refs:
        raise ValueError(f"MessageBusBlock '{block_id}': soul_refs is required (non-empty list)")
    if block_def.iterations is None:
        raise ValueError(f"MessageBusBlock '{block_id}': iterations is required")
    souls = [_resolve_soul(ref, souls_map) for ref in block_def.soul_refs]
    return MessageBusBlock(block_id, souls, block_def.iterations, runner)


def _build_router(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> RouterBlock:
    if block_def.soul_ref is None:
        raise ValueError(
            f"RouterBlock '{block_id}': soul_ref is required (YAML-based router uses Soul evaluator)"
        )
    soul = _resolve_soul(block_def.soul_ref, souls_map)
    return RouterBlock(block_id, soul, runner)


def _build_retry(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> RetryBlock:
    if block_def.inner_block_ref is None:
        raise ValueError(f"RetryBlock '{block_id}': inner_block_ref is required")
    inner = all_blocks.get(block_def.inner_block_ref)
    if inner is None:
        raise ValueError(
            f"RetryBlock '{block_id}': inner_block_ref '{block_def.inner_block_ref}' not found. "
            f"Available blocks from pass 1: {sorted(all_blocks.keys())}"
        )
    max_retries = block_def.max_retries if block_def.max_retries is not None else 3
    provide_error_context = (
        block_def.provide_error_context if block_def.provide_error_context is not None else False
    )
    return RetryBlock(block_id, inner, max_retries, provide_error_context=provide_error_context)


def _build_team_lead(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> TeamLeadBlock:
    if block_def.soul_ref is None:
        raise ValueError(f"TeamLeadBlock '{block_id}': soul_ref is required")
    if not block_def.failure_context_keys:
        raise ValueError(
            f"TeamLeadBlock '{block_id}': failure_context_keys is required (non-empty list)"
        )
    soul = _resolve_soul(block_def.soul_ref, souls_map)
    return TeamLeadBlock(block_id, block_def.failure_context_keys, soul, runner)


def _build_engineering_manager(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> EngineeringManagerBlock:
    if block_def.soul_ref is None:
        raise ValueError(f"EngineeringManagerBlock '{block_id}': soul_ref is required")
    soul = _resolve_soul(block_def.soul_ref, souls_map)
    return EngineeringManagerBlock(block_id, soul, runner)


def _build_placeholder(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> PlaceholderBlock:
    extra = block_def.model_extra or {}
    description = str(extra.get("description", f"Placeholder block {block_id}"))
    return PlaceholderBlock(block_id, description)


def _build_gate(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> GateBlock:
    if block_def.soul_ref is None:
        raise ValueError(f"GateBlock '{block_id}': soul_ref is required")
    if block_def.eval_key is None:
        raise ValueError(f"GateBlock '{block_id}': eval_key is required")
    soul = _resolve_soul(block_def.soul_ref, souls_map)
    return GateBlock(
        block_id, soul, block_def.eval_key, runner, extract_field=block_def.extract_field
    )


def _build_file_writer(
    block_id: str,
    block_def: BlockDef,
    souls_map: Dict[str, Soul],
    runner: RunsightTeamRunner,
    all_blocks: Dict[str, BaseBlock],
) -> FileWriterBlock:
    if block_def.output_path is None:
        raise ValueError(f"FileWriterBlock '{block_id}': output_path is required")
    if block_def.content_key is None:
        raise ValueError(f"FileWriterBlock '{block_id}': content_key is required")
    return FileWriterBlock(block_id, block_def.output_path, block_def.content_key)


BLOCK_TYPE_REGISTRY: Dict[str, BlockBuilder] = {
    "linear": _build_linear,
    "fanout": _build_fanout,
    "synthesize": _build_synthesize,
    "debate": _build_debate,
    "message_bus": _build_message_bus,
    "router": _build_router,
    "retry": _build_retry,  # pass 2 only
    "team_lead": _build_team_lead,
    "engineering_manager": _build_engineering_manager,
    "placeholder": _build_placeholder,
    "gate": _build_gate,
    "file_writer": _build_file_writer,
}


def parse_workflow_yaml(
    yaml_str_or_dict: Union[str, Dict[str, Any]],
    *,
    workflow_registry: Optional["WorkflowRegistry"] = None,
) -> Workflow:
    """
    Parse a YAML workflow definition into a runnable Workflow object.

    Args:
        yaml_str_or_dict: One of:
          - str with no newlines ending in .yaml/.yml/.json → load from file path
          - str with newlines (or any other str) → parse as YAML content
          - dict → use as pre-parsed data directly
        workflow_registry: Optional WorkflowRegistry for resolving workflow_ref in workflow blocks.
                          Required if workflow contains type: workflow blocks.

    Returns:
        Validated Workflow instance. workflow.validate() has been called and passed.

    Raises:
        ValidationError: If YAML doesn't match RunsightWorkflowFile schema.
        ValueError: If soul_ref/block_ref unresolvable, or validate() returns errors.
        FileNotFoundError: If file path provided but file does not exist.
        yaml.YAMLError: If YAML content is syntactically invalid.
    """
    # Step 1: Normalize input to raw dict
    if isinstance(yaml_str_or_dict, str):
        stripped = yaml_str_or_dict.strip()
        is_file_path = "\n" not in stripped and (
            stripped.endswith(".yaml") or stripped.endswith(".yml") or stripped.endswith(".json")
        )
        if is_file_path:
            with open(stripped, "r", encoding="utf-8") as f:
                raw: Any = yaml.safe_load(f)
        else:
            raw = yaml.safe_load(yaml_str_or_dict)
    else:
        raw = yaml_str_or_dict

    # Step 2: Validate against Pydantic schema (raises ValidationError on failure)
    file_def = RunsightWorkflowFile.model_validate(raw)

    # Step 3: Merge souls — YAML-defined souls override built-ins by key
    souls_map: Dict[str, Soul] = dict(BUILT_IN_SOULS)  # start with built-ins
    for key, soul_def in file_def.souls.items():
        souls_map[key] = Soul(
            id=soul_def.id,
            role=soul_def.role,
            system_prompt=soul_def.system_prompt,
            tools=soul_def.tools,
            model_name=soul_def.model_name,
        )

    # Step 4: Instantiate runner (shared across all blocks in this workflow)
    model_name = str(file_def.config.get("model_name", "gpt-4o"))
    runner = RunsightTeamRunner(model_name=model_name)

    # Step 5: Pass 1 — build all non-retry blocks
    built_blocks: Dict[str, BaseBlock] = {}
    for block_id, block_def in file_def.blocks.items():
        if block_def.type == "retry":
            continue  # handled in pass 2

        # Special case: WorkflowBlock (type: workflow)
        # Handle before BLOCK_TYPE_REGISTRY lookup to avoid "unknown type" error
        if block_def.type == "workflow":
            # Validate workflow_ref field (redundant check — already enforced by BlockDef validator)
            if block_def.workflow_ref is None:
                raise ValueError(f"WorkflowBlock '{block_id}': workflow_ref is required")

            # Require workflow_registry parameter
            if workflow_registry is None:
                raise ValueError(
                    f"WorkflowBlock '{block_id}': a WorkflowRegistry must be provided "
                    f"to parse_workflow_yaml() when workflow blocks are used. "
                    f"Pass workflow_registry=... parameter."
                )

            # Resolve child workflow file (registry returns RunsightWorkflowFile)
            child_file = workflow_registry.get(block_def.workflow_ref)

            # Normalize to dict so parse_workflow_yaml receives Union[str, Dict] not model instance
            child_raw = child_file.model_dump() if hasattr(child_file, "model_dump") else child_file

            # Recursively parse child workflow (passes registry for nested workflows)
            child_wf = parse_workflow_yaml(child_raw, workflow_registry=workflow_registry)

            # Read max_depth: block-level override → global config → default 10
            max_depth_value = (
                block_def.max_depth
                if block_def.max_depth is not None
                else file_def.config.get("max_workflow_depth", 10)
            )

            # Instantiate WorkflowBlock
            from runsight_core.blocks.implementations import WorkflowBlock

            block = WorkflowBlock(
                block_id=block_id,
                child_workflow=child_wf,
                inputs=block_def.inputs or {},
                outputs=block_def.outputs or {},
                max_depth=max_depth_value,
            )

            built_blocks[block_id] = block
            continue  # Skip BLOCK_TYPE_REGISTRY lookup

        builder = BLOCK_TYPE_REGISTRY.get(block_def.type)
        if builder is None:
            raise ValueError(
                f"Unknown block type '{block_def.type}' for block '{block_id}'. "
                f"Available types: {sorted(BLOCK_TYPE_REGISTRY.keys())}"
            )
        built_blocks[block_id] = builder(block_id, block_def, souls_map, runner, built_blocks)

    # Step 6: Pass 2 — build retry blocks (inner_block_ref now resolvable from pass 1)
    for block_id, block_def in file_def.blocks.items():
        if block_def.type != "retry":
            continue
        built_blocks[block_id] = _build_retry(block_id, block_def, souls_map, runner, built_blocks)

    # Step 7: Assemble Workflow object
    wf = Workflow(name=file_def.workflow.name)
    for block in built_blocks.values():
        wf.add_block(block)

    # Step 8: Register plain transitions
    for t in file_def.workflow.transitions:
        wf.add_transition(t.from_, t.to)

    # Step 9: Register conditional transitions
    for ct in file_def.workflow.conditional_transitions:
        condition_map: Dict[str, str] = {}
        if ct.default is not None:
            condition_map["default"] = ct.default
        # Extra fields = decision_key -> target_block_id (model_extra excludes defined fields)
        for decision_key, target_id in (ct.model_extra or {}).items():
            condition_map[decision_key] = str(target_id)
        wf.add_conditional_transition(ct.from_, condition_map)

    # Step 10: Set entry block
    wf.set_entry(file_def.workflow.entry)

    # Step 11: Validate (raises ValueError if topology is invalid)
    errors = wf.validate()
    if errors:
        raise ValueError(f"Workflow '{file_def.workflow.name}' failed validation: {errors}")

    return wf


def parse_task_yaml(yaml_str_or_dict: Union[str, Dict[str, Any]]) -> Task:
    """
    Parse a YAML task definition into a Task primitive.

    Args:
        yaml_str_or_dict: One of:
          - str with no newlines ending in .yaml/.yml/.json → load from file path
          - str with newlines (or any other str) → parse as YAML content
          - dict → use as pre-parsed data directly

    Returns:
        Validated Task instance with id, instruction, and optional context populated.

    Raises:
        ValidationError: If input doesn't match TaskDef schema (missing required fields, wrong types).
        FileNotFoundError: If file path provided but file does not exist.
        yaml.YAMLError: If YAML content is syntactically invalid.
    """
    # Step 1: Normalize input to raw dict
    if isinstance(yaml_str_or_dict, str):
        stripped = yaml_str_or_dict.strip()
        is_file_path = "\n" not in stripped and (
            stripped.endswith(".yaml") or stripped.endswith(".yml") or stripped.endswith(".json")
        )
        if is_file_path:
            with open(stripped, "r", encoding="utf-8") as f:
                raw: Any = yaml.safe_load(f)
        else:
            raw = yaml.safe_load(yaml_str_or_dict)
    else:
        raw = yaml_str_or_dict

    # Step 2: Validate against Pydantic schema (raises ValidationError on failure)
    file_def = RunsightTaskFile.model_validate(raw)
    task_def = file_def.task

    # Step 3: Create and return Task primitive
    return Task(
        id=task_def.id,
        instruction=task_def.instruction,
        context=task_def.context,
    )
