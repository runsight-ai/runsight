"""
YAML workflow parser for Runsight.
Exports: parse_workflow_yaml, parse_task_yaml, BUILT_IN_SOULS
"""

from __future__ import annotations

import yaml
from typing import Any, Dict, Union, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from runsight_core.yaml.registry import WorkflowRegistry

from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul, Step, Task
from runsight_core.runner import RunsightTeamRunner
from runsight_core.workflow import Workflow
from runsight_core.conditions.engine import (
    Condition,
    ConditionGroup,
)
from runsight_core.tools._catalog import BUILTIN_TOOL_CATALOG, resolve_tool
from runsight_core.yaml.schema import (
    ConditionDef,
    ConditionGroupDef,
    InputRef,
    RunsightTaskFile,
    RunsightWorkflowFile,
)


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


def _convert_condition(cond_def: ConditionDef) -> Condition:
    """Convert a ConditionDef schema model to a runtime Condition dataclass."""
    return Condition(
        eval_key=cond_def.eval_key,
        operator=cond_def.operator,
        value=cond_def.value,
    )


def _convert_condition_group(group_def: ConditionGroupDef) -> ConditionGroup:
    """Convert a ConditionGroupDef schema model to a runtime ConditionGroup dataclass."""
    return ConditionGroup(
        conditions=[_convert_condition(c) for c in group_def.conditions],
        combinator=group_def.combinator,
    )


# Trigger auto-discovery of co-located blocks and rebuild the discriminated
# union so that BlockDef includes all registered block types.
import runsight_core.blocks  # noqa: E402, F401

# Trigger auto-discovery of built-in tools so BUILTIN_TOOL_CATALOG is populated.
import runsight_core.tools.delegate  # noqa: E402, F401
import runsight_core.tools.file_io  # noqa: E402, F401
import runsight_core.tools.http  # noqa: E402, F401

from runsight_core.yaml.schema import rebuild_block_def_union as _rebuild  # noqa: E402

_rebuild()
del _rebuild


def parse_workflow_yaml(
    yaml_str_or_dict: Union[str, Dict[str, Any]],
    *,
    workflow_registry: Optional["WorkflowRegistry"] = None,
    api_key: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None,
) -> Workflow:
    """
    Parse a YAML workflow definition into a runnable Workflow object.

    Args:
        yaml_str_or_dict: One of:
          - str with no newlines ending in .yaml/.yml/.json -> load from file path
          - str with newlines (or any other str) -> parse as YAML content
          - dict -> use as pre-parsed data directly
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
    runner = RunsightTeamRunner(model_name=model_name, api_key=api_key, api_keys=api_keys)

    # Step 5: Build all blocks (single pass)
    built_blocks: Dict[str, BaseBlock] = {}
    for block_id, block_def in file_def.blocks.items():
        # Special case: WorkflowBlock (type: workflow)
        # Handle before registry lookup to avoid "unknown type" error
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
            child_wf = parse_workflow_yaml(
                child_raw, workflow_registry=workflow_registry, api_key=api_key, api_keys=api_keys
            )

            # Read max_depth: block-level override -> global config -> default 10
            max_depth_value = (
                block_def.max_depth
                if block_def.max_depth is not None
                else file_def.config.get("max_workflow_depth", 10)
            )

            # Instantiate WorkflowBlock
            from runsight_core.blocks.workflow_block import WorkflowBlock

            block = WorkflowBlock(
                block_id=block_id,
                child_workflow=child_wf,
                inputs=block_def.inputs or {},
                outputs=block_def.outputs or {},
                max_depth=max_depth_value,
            )

            built_blocks[block_id] = block
            continue  # Skip registry lookup

        from runsight_core.blocks._registry import get_builder

        builder = get_builder(block_def.type)
        if builder is None:
            from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

            raise ValueError(
                f"Unknown block type '{block_def.type}' for block '{block_id}'. "
                f"Available types: {sorted(BLOCK_BUILDER_REGISTRY.keys())}"
            )
        built_blocks[block_id] = builder(block_id, block_def, souls_map, runner, built_blocks)

    # Step 6.2: Bridge _declared_exits from schema to runtime blocks
    for block_id, block_def in file_def.blocks.items():
        if block_def.exits and block_id in built_blocks:
            built_blocks[block_id]._declared_exits = block_def.exits

    # Step 6.3: Bridge retry_config from schema to runtime blocks
    for block_id, block_def in file_def.blocks.items():
        if block_def.retry_config is not None and block_id in built_blocks:
            built_blocks[block_id].retry_config = block_def.retry_config

    # Step 6.4: Bridge stateful from schema to runtime blocks
    for block_id, block_def in file_def.blocks.items():
        if block_def.stateful and block_id in built_blocks:
            built_blocks[block_id].stateful = block_def.stateful

    # Step 6.6: Validate and resolve tools per soul
    # 6.6a: Validate tool sources exist in BUILTIN_TOOL_CATALOG
    for tool_key, tool_def in file_def.tools.items():
        if tool_def.source not in BUILTIN_TOOL_CATALOG:
            available = sorted(BUILTIN_TOOL_CATALOG.keys())
            raise ValueError(
                f"Tool '{tool_key}' has unknown source '{tool_def.source}'. Available: {available}"
            )

    # 6.6b: Validate soul tool references exist in file_def.tools keys
    for soul_key, soul_def in file_def.souls.items():
        if soul_def.tools:
            for tool_name in soul_def.tools:
                if tool_name not in file_def.tools:
                    raise ValueError(
                        f"Soul '{soul_key}' references undeclared tool '{tool_name}'. "
                        f"Declared tools: {sorted(file_def.tools.keys())}"
                    )

    # 6.6c: Resolve ToolInstance objects per soul
    for soul_key, soul_def in file_def.souls.items():
        if not soul_def.tools:
            continue

        resolved_tools = []
        for tool_name in soul_def.tools:
            tool_def = file_def.tools[tool_name]

            if tool_def.source == "runsight/delegate":
                # Find the block that references this soul via soul_ref
                block_id_for_soul = None
                block_def_for_soul = None
                for bid, bdef in file_def.blocks.items():
                    if getattr(bdef, "soul_ref", None) == soul_key:
                        block_id_for_soul = bid
                        block_def_for_soul = bdef
                        break

                exits = getattr(block_def_for_soul, "exits", None) if block_def_for_soul else None
                if not exits:
                    raise ValueError(
                        f"Soul '{soul_key}' uses delegate tool but block "
                        f"'{block_id_for_soul}' has no exits defined"
                    )
                resolved_tools.append(resolve_tool(tool_def, exits=exits))
            else:
                resolved_tools.append(resolve_tool(tool_def))

        # Attach resolved tools to the soul in souls_map
        soul = souls_map.get(soul_key)
        if soul is not None:
            soul.resolved_tools = resolved_tools

    # Step 6.5: Validate input references and detect circular dependencies
    # Build input dependency graph for cycle detection
    input_deps: Dict[str, list] = {}  # block_id -> [source_block_ids]
    for block_id, block_def in file_def.blocks.items():
        if block_def.inputs is not None and block_def.type != "workflow":
            deps = []
            for input_name, input_ref in block_def.inputs.items():
                from_ref = input_ref.from_ref if isinstance(input_ref, InputRef) else input_ref
                source_id = from_ref.split(".")[0]
                if source_id not in file_def.blocks:
                    raise ValueError(
                        f"Block '{block_id}': input '{input_name}' references unknown block '{source_id}'"
                    )
                if source_id == block_id:
                    raise ValueError(
                        f"Block '{block_id}': input '{input_name}' references itself (circular)"
                    )
                deps.append(source_id)
            input_deps[block_id] = deps

    # Detect circular input dependencies (topological sort / DFS)
    def _detect_input_cycle(
        node: str,
        visiting: set,
        visited: set,
        deps: Dict[str, list],
    ) -> bool:
        if node in visiting:
            return True  # cycle found
        if node in visited:
            return False
        visiting.add(node)
        for dep in deps.get(node, []):
            if _detect_input_cycle(dep, visiting, visited, deps):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    visiting_set: set = set()
    visited_set: set = set()
    for block_id in input_deps:
        if _detect_input_cycle(block_id, visiting_set, visited_set, input_deps):
            raise ValueError(
                f"Circular input dependency cycle detected involving block '{block_id}'"
            )

    # Step 6.6: Wrap blocks with declared_inputs in Step objects
    for block_id, block_def in file_def.blocks.items():
        if (
            block_def.inputs is not None
            and block_def.type != "workflow"
            and block_id in built_blocks
        ):
            declared_inputs: Dict[str, str] = {}
            for input_name, input_ref in block_def.inputs.items():
                from_ref = input_ref.from_ref if isinstance(input_ref, InputRef) else input_ref
                declared_inputs[input_name] = from_ref
            # Wrap the built block in a Step with declared_inputs
            built_blocks[block_id] = Step(
                block=built_blocks[block_id],
                declared_inputs=declared_inputs,
            )

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
            if target_id is not None:
                condition_map[decision_key] = str(target_id)
            # target_id=None means terminal (no successor for this decision path)
        wf.add_conditional_transition(ct.from_, condition_map)

    # Step 10: Set entry block
    wf.set_entry(file_def.workflow.entry)

    # Step 10.5: Wire output_conditions to Workflow
    for block_id, block_def in file_def.blocks.items():
        if block_def.output_conditions:
            from runsight_core.conditions.engine import Case, Condition, ConditionGroup

            cases = []
            default_decision = "default"
            for case_def in block_def.output_conditions:
                if case_def.default:
                    default_decision = case_def.case_id
                    continue  # default case has no condition_group
                if case_def.condition_group is not None:
                    conditions = [
                        Condition(
                            eval_key=c.eval_key,
                            operator=c.operator,
                            value=c.value,
                        )
                        for c in case_def.condition_group.conditions
                    ]
                    group = ConditionGroup(
                        conditions=conditions,
                        combinator=case_def.condition_group.combinator,
                    )
                    cases.append(Case(case_id=case_def.case_id, condition_group=group))
            wf.set_output_conditions(block_id, cases, default=default_decision)

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
          - str with no newlines ending in .yaml/.yml/.json -> load from file path
          - str with newlines (or any other str) -> parse as YAML content
          - dict -> use as pre-parsed data directly

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
