"""
YAML workflow parser for Runsight.
Exports: parse_workflow_yaml, parse_task_yaml
"""

from __future__ import annotations

import logging
from collections.abc import Collection
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

import yaml
from pydantic import BaseModel

if TYPE_CHECKING:
    from runsight_core.yaml.registry import WorkflowRegistry

from runsight_core.assertions.registry import register_custom_assertions
from runsight_core.blocks.base import BaseBlock
from runsight_core.conditions.engine import (
    Condition,
    ConditionGroup,
)
from runsight_core.primitives import Soul, Step, Task
from runsight_core.runner import RunsightTeamRunner
from runsight_core.tools._catalog import RESERVED_BUILTIN_TOOL_IDS, resolve_tool_id
from runsight_core.workflow import Workflow
from runsight_core.yaml.discovery import (
    AssertionScanner,
    SoulScanner,
    ToolScanner,
    WorkflowScanner,
    resolve_discovery_base_dir,
)
from runsight_core.yaml.schema import (
    CaseDef,
    ConditionDef,
    ConditionGroupDef,
    DispatchExitDef,
    InputRef,
    RunsightTaskFile,
    RunsightWorkflowFile,
)

# Supported schema versions.  When a future version bump is needed:
# 1. Add the new version string here.
# 2. Gate migration logic on ``file_def.version`` before the block-building loop.
SUPPORTED_VERSIONS: frozenset[str] = frozenset({"1.0"})
_UNSET_RUNNER_MODEL_NAME = "__runsight_explicit_model_required__"
logger = logging.getLogger(__name__)


def _bootstrap_runner_model_name(souls_map: Dict[str, Soul]) -> str:
    """Choose an explicit bootstrap model for parser-owned runner construction."""
    for soul in souls_map.values():
        if isinstance(soul.model_name, str) and soul.model_name.strip():
            return soul.model_name
    return _UNSET_RUNNER_MODEL_NAME


def _merge_inline_souls(
    file_def: RunsightWorkflowFile,
    external_souls: Dict[str, Soul],
) -> Dict[str, Soul]:
    """Merge inline workflow souls over external soul files."""
    if not file_def.souls:
        return external_souls

    overlapping_keys = sorted(set(file_def.souls) & set(external_souls))
    for soul_key in overlapping_keys:
        logger.warning("Inline soul '%s' overrides external soul file", soul_key)

    inline_souls = {
        soul_key: _coerce_inline_soul(soul_def) for soul_key, soul_def in file_def.souls.items()
    }

    return {**external_souls, **inline_souls}


def _coerce_inline_soul(soul_def: object) -> Soul:
    """Convert schema models, dicts, or lightweight doubles into runtime Soul objects."""
    if isinstance(Soul, type) and isinstance(soul_def, Soul):
        return soul_def
    if isinstance(soul_def, BaseModel):
        return Soul.model_validate(soul_def.model_dump())
    if isinstance(soul_def, dict):
        return Soul.model_validate(soul_def)
    raw_attrs = vars(soul_def)
    explicit_fields = {
        field_name: raw_attrs[field_name]
        for field_name in Soul.model_fields
        if field_name in raw_attrs
    }
    if explicit_fields:
        return Soul.model_validate(explicit_fields)
    return Soul.model_validate(soul_def, from_attributes=True)


def _discover_external_souls(
    souls_dir: Path,
    *,
    inline_soul_keys: Collection[str],
) -> Dict[str, Soul]:
    """Discover external soul files through the shared discovery seam."""
    base_dir = souls_dir.parent.parent
    return SoulScanner(base_dir).scan(ignore_keys=inline_soul_keys).stems()


def _normalize_depends(depends: str | list[str] | None) -> list[str]:
    """Normalize block depends sugar into a list of source block IDs."""
    if depends is None:
        return []
    if isinstance(depends, str):
        return [depends]
    return list(depends)


def _get_explicit_block_field(block_def: object, field_name: str) -> object | None:
    """Read a block field without treating mock attribute fallbacks as declared data."""
    if isinstance(block_def, BaseModel):
        return getattr(block_def, field_name, None)
    if isinstance(block_def, dict):
        return block_def.get(field_name)
    return vars(block_def).get(field_name)


def _expand_depends(file_def: RunsightWorkflowFile, wf: Workflow) -> None:
    """Expand block depends sugar into plain workflow transitions."""
    for block_id, block_def in file_def.blocks.items():
        depends = _get_explicit_block_field(block_def, "depends")
        for dependency_id in _normalize_depends(depends):
            existing_target = wf._transitions.get(dependency_id)
            if existing_target is not None:
                raise ValueError(
                    f"depends expansion conflict: '{dependency_id}' already transitions to "
                    f"'{existing_target}', cannot also depend-route to '{block_id}'"
                )
            try:
                wf.add_transition(dependency_id, block_id)
            except ValueError as exc:
                raise ValueError(
                    f"depends expansion failed for block '{block_id}' from '{dependency_id}': {exc}"
                ) from exc


def _bridge_error_routes(file_def: RunsightWorkflowFile, wf: Workflow) -> None:
    """Bridge declared block error_route fields onto workflow storage."""
    for block_id, block_def in file_def.blocks.items():
        error_route = _get_explicit_block_field(block_def, "error_route")
        if error_route is not None:
            wf.set_error_route(block_id, str(error_route))


def _expand_gate_shortcuts(file_def: RunsightWorkflowFile, wf: Workflow) -> None:
    """Expand gate pass/fail shorthand into conditional transitions."""
    for block_id, block_def in file_def.blocks.items():
        if getattr(block_def, "type", None) != "gate":
            continue

        pass_target = _get_explicit_block_field(block_def, "pass_")
        fail_target = _get_explicit_block_field(block_def, "fail_")
        if pass_target is None or fail_target is None:
            continue

        condition_map = {
            "pass": str(pass_target),
            "fail": str(fail_target),
            "default": str(fail_target),
        }
        wf.add_conditional_transition(block_id, condition_map)


def _wire_output_conditions(
    wf: Workflow,
    block_id: str,
    output_conditions: list[CaseDef] | None,
) -> None:
    """Convert schema CaseDef items into runtime output condition storage."""
    if not output_conditions:
        return

    from runsight_core.conditions.engine import Case, ConditionGroup

    cases = []
    default_decision = "default"
    for case_def in output_conditions:
        if case_def.default:
            default_decision = case_def.case_id
            continue

        condition_group = (
            _convert_condition_group(case_def.condition_group)
            if case_def.condition_group is not None
            else ConditionGroup()
        )
        cases.append(Case(case_id=case_def.case_id, condition_group=condition_group))

    wf.set_output_conditions(block_id, cases, default=default_decision)


def _expand_routes(file_def: RunsightWorkflowFile, wf: Workflow) -> None:
    """Expand routes shorthand into workflow output conditions and transitions."""
    for block_id, block_def in file_def.blocks.items():
        routes = _get_explicit_block_field(block_def, "routes")
        if not routes:
            continue

        route_cases: list[CaseDef] = []
        condition_map: Dict[str, str] = {}

        for route_def in routes:
            case_id = str(_get_explicit_block_field(route_def, "case_id"))
            goto = str(_get_explicit_block_field(route_def, "goto"))
            is_default = bool(_get_explicit_block_field(route_def, "default"))
            when = _get_explicit_block_field(route_def, "when")

            condition_map[case_id] = goto
            if is_default:
                condition_map["default"] = goto
                if when is not None:
                    logger.warning(
                        "Route '%s' on block '%s' is marked default; ignoring when",
                        case_id,
                        block_id,
                    )
                route_cases.append(CaseDef(case_id=case_id, default=True))
                continue

            route_cases.append(CaseDef(case_id=case_id, condition_group=when))

        _wire_output_conditions(wf, block_id, route_cases)
        wf.add_conditional_transition(block_id, condition_map)


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


def _find_duplicate_tool_ids(tool_ids: Collection[str]) -> list[str]:
    """Return workflow tool IDs that appear more than once, preserving first duplicate order."""
    duplicates: list[str] = []
    seen: set[str] = set()
    for tool_id in tool_ids:
        if tool_id in seen and tool_id not in duplicates:
            duplicates.append(tool_id)
        seen.add(tool_id)
    return duplicates


def _resolve_soul_tool_definition(tool_ref: str, workflow_tools: Collection[str]) -> str | None:
    """Resolve a soul tool ref from the workflow tool whitelist only."""
    return tool_ref if tool_ref in workflow_tools else None


def _collect_referenced_soul_keys(file_def: RunsightWorkflowFile) -> set[str]:
    """Return every library soul key referenced by workflow blocks and exits."""
    referenced_souls: set[str] = set()
    for block_def in file_def.blocks.values():
        soul_ref = getattr(block_def, "soul_ref", None)
        if soul_ref:
            referenced_souls.add(soul_ref)
        if block_def.exits:
            for exit_def in block_def.exits:
                if isinstance(exit_def, DispatchExitDef) and exit_def.soul_ref:
                    referenced_souls.add(exit_def.soul_ref)
    return referenced_souls


def validate_tool_governance(
    file_def: RunsightWorkflowFile,
    souls_map: Dict[str, Soul] | None = None,
) -> None:
    """Validate workflow tool declarations against referenced library souls."""
    if souls_map is None:
        souls_map = {}

    declared_tools = set(file_def.tools)
    for soul_key in _collect_referenced_soul_keys(file_def):
        soul = souls_map.get(soul_key)
        if soul is None or not soul.tools:
            continue

        for tool_name in soul.tools:
            if _resolve_soul_tool_definition(tool_name, declared_tools) is None:
                raise ValueError(
                    f"Soul '{soul_key}' (custom/souls/{soul_key}.yaml) references "
                    f"undeclared tool '{tool_name}'. Declared tools: {sorted(file_def.tools)}"
                )


def _validate_declared_tool_definitions(
    file_def: RunsightWorkflowFile,
    *,
    base_dir: str,
    require_custom_metadata: bool = False,
) -> None:
    """Validate that declared canonical tool IDs are parse-time resolvable."""
    discovered_tools = ToolScanner(base_dir).scan().stems()
    available_builtin_ids = sorted(RESERVED_BUILTIN_TOOL_IDS)
    available_custom_ids = sorted(discovered_tools.keys())

    for tool_id in file_def.tools:
        expected_file = Path(base_dir) / "custom" / "tools" / f"{tool_id}.yaml"

        if tool_id in RESERVED_BUILTIN_TOOL_IDS:
            if tool_id in discovered_tools:
                raise ValueError(
                    f"reserved builtin tool id '{tool_id}' collides with custom tool metadata at "
                    f"{expected_file}"
                )
            continue

        tool_meta = discovered_tools.get(tool_id)
        if tool_meta is None:
            if require_custom_metadata:
                raise ValueError(
                    f"Tool '{tool_id}' references missing custom tool metadata. "
                    f"Expected metadata at {expected_file}"
                )
            raise ValueError(
                f"Workflow declares unknown tool id '{tool_id}'. "
                f"Available builtin IDs: {available_builtin_ids}. "
                f"Discovered custom IDs: {available_custom_ids}"
            )

        try:
            _resolve_tool_for_parser(tool_id, base_dir=base_dir)
        except ValueError as exc:
            raise ValueError(f"Tool '{tool_id}': {exc}") from exc


def _resolve_tool_for_parser(
    tool_id: str,
    *,
    base_dir: str,
    exits: object | None = None,
) -> object:
    """Resolve a tool with only the parser context that its canonical ID needs."""
    kwargs: Dict[str, object] = {}
    if tool_id == "delegate" and exits is not None:
        kwargs["exits"] = exits
    elif tool_id == "file_io":
        kwargs["base_dir"] = base_dir
    elif tool_id not in RESERVED_BUILTIN_TOOL_IDS:
        kwargs["base_dir"] = base_dir

    return resolve_tool_id(tool_id, **kwargs)


def _attach_tool_runtime_metadata(tool: object, tool_id: str, *, base_dir: str) -> object:
    """Annotate a resolved ToolInstance with ID/type metadata for isolation."""
    setattr(tool, "source", tool_id)
    if tool_id in RESERVED_BUILTIN_TOOL_IDS:
        setattr(tool, "tool_type", "builtin")
    else:
        tool_meta = ToolScanner(base_dir).scan().stems().get(tool_id)
        setattr(tool, "tool_type", tool_meta.type if tool_meta is not None else "")
    setattr(tool, "config", {"id": tool_id})
    return tool


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


def _validate_workflow_block_contract(
    block_id: str,
    block_def: Any,
    child_file: RunsightWorkflowFile,
) -> None:
    child_interface = child_file.interface
    if child_interface is None:
        raise ValueError(
            f"WorkflowBlock '{block_id}': child workflow '{block_def.workflow_ref}' "
            "must declare an interface"
        )

    declared_inputs = {item.name: item for item in child_interface.inputs}
    declared_outputs = {item.name for item in child_interface.outputs}

    for binding_name in (block_def.inputs or {}).keys():
        if binding_name not in declared_inputs:
            raise ValueError(
                f"WorkflowBlock '{block_id}': unknown interface input '{binding_name}'. "
                f"Declared child inputs: {sorted(declared_inputs)}"
            )

    missing_required = [
        item.name
        for item in child_interface.inputs
        if item.required and item.default is None and item.name not in (block_def.inputs or {})
    ]
    if missing_required:
        raise ValueError(
            f"WorkflowBlock '{block_id}': missing required interface inputs {missing_required}"
        )

    for binding_name in (block_def.outputs or {}).values():
        if binding_name not in declared_outputs:
            raise ValueError(
                f"WorkflowBlock '{block_id}': unknown interface output '{binding_name}'. "
                f"Declared child outputs: {sorted(declared_outputs)}"
            )


def _validate_workflow_block_runtime_placement(
    file_def: RunsightWorkflowFile,
    *,
    workflow_label: str,
) -> None:
    """Reserved hook for workflow/loop placement validation."""
    return None


def _resolve_workflow_block_max_depth(
    file_def: RunsightWorkflowFile,
    block_def: Any,
) -> int:
    """Resolve the max_depth value a workflow block will enforce at runtime."""
    if block_def.max_depth is not None:
        return block_def.max_depth
    return file_def.config.get("max_workflow_depth", 10)


def validate_workflow_call_contracts(
    file_def: RunsightWorkflowFile,
    *,
    base_dir: str,
    validation_index: dict[str, tuple[Path, RunsightWorkflowFile]] | None = None,
    current_workflow_ref: str | None = None,
    ancestry: tuple[str, ...] | None = None,
    current_call_stack_depth: int = 1,
    allow_filesystem_fallback: bool = True,
    _depth_uses_strict_comparison: bool = False,
) -> None:
    workflow_scanner: WorkflowScanner | None = None
    workflow_scan_index = None
    if validation_index is None:
        workflow_scanner = WorkflowScanner(base_dir)
        workflow_scan_index = workflow_scanner.scan()
        validation_index = {
            alias: (result.path, result.item)
            for result in workflow_scan_index.get_all()
            for alias in result.aliases
        }
    workflow_label = getattr(file_def.workflow, "name", None) or current_workflow_ref or "<root>"
    _validate_workflow_block_runtime_placement(file_def, workflow_label=workflow_label)
    if ancestry is None:
        root_ref = current_workflow_ref or getattr(file_def.workflow, "name", "<root>")
        ancestry = (root_ref,)

    for block_id, block_def in file_def.blocks.items():
        if block_def.type != "workflow":
            continue

        resolved_child = None
        if workflow_scanner is not None:
            resolved_child = workflow_scanner.resolve_ref(
                block_def.workflow_ref,
                index=workflow_scan_index,
                allow_candidate_fallback=allow_filesystem_fallback,
            )
        elif allow_filesystem_fallback:
            workflow_scanner = WorkflowScanner(base_dir)
            resolved_child = workflow_scanner.resolve_ref(
                block_def.workflow_ref,
                allow_candidate_fallback=True,
            )
        if resolved_child is None:
            indexed = validation_index.get(block_def.workflow_ref)
            if indexed is None:
                raise ValueError(
                    f"WorkflowRegistry: cannot resolve ref '{block_def.workflow_ref}'. "
                    "Not found as named workflow or filesystem path."
                )
            child_path, child_file = indexed
        else:
            child_path = resolved_child.path
            child_file = resolved_child.item
        child_ref = str(child_path)
        if child_ref in ancestry:
            cycle_path = " -> ".join([*ancestry, child_ref])
            raise ValueError(f"Circular workflow reference cycle detected: {cycle_path}")

        _validate_workflow_block_contract(block_id, block_def, child_file)

        # max_depth counts nesting levels: 1=child, 2=grandchild, 3=great-grandchild.
        # When a child workflow declares config.max_workflow_depth, the depth
        # increment is +1 and the comparison uses strict '>' (the declared
        # config establishes a fresh depth budget).  Without a config
        # declaration the legacy +2 increment with '>=' applies.
        max_depth = _resolve_workflow_block_max_depth(file_def, block_def)
        depth_exceeded = (
            current_call_stack_depth > max_depth
            if _depth_uses_strict_comparison
            else current_call_stack_depth >= max_depth
        )
        if depth_exceeded:
            raise ValueError(
                f"WorkflowBlock '{block_id}': maximum depth {max_depth} exceeded while "
                f"resolving child workflow '{block_def.workflow_ref}'. "
                f"Call stack depth: {current_call_stack_depth}"
            )

        child_has_config_depth = child_file.config.get("max_workflow_depth") is not None
        if child_has_config_depth:
            next_depth = current_call_stack_depth + 1
            next_strict = True
        else:
            next_depth = current_call_stack_depth + 2
            next_strict = False

        validate_workflow_call_contracts(
            child_file,
            base_dir=resolve_discovery_base_dir(child_path.parent),
            validation_index=validation_index,
            current_workflow_ref=child_ref,
            ancestry=(*ancestry, child_ref),
            current_call_stack_depth=next_depth,
            allow_filesystem_fallback=allow_filesystem_fallback,
            _depth_uses_strict_comparison=next_strict,
        )


def parse_workflow_yaml(
    yaml_str_or_dict: Union[str, Dict[str, Any]],
    *,
    workflow_registry: Optional["WorkflowRegistry"] = None,
    api_keys: Optional[Dict[str, str]] = None,
    runner: Optional[Any] = None,
    _base_dir: Optional[str] = None,
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
        ValueError: If schema version is unsupported, soul_ref/block_ref
            unresolvable, or validate() returns errors.
        FileNotFoundError: If file path provided but file does not exist.
        yaml.YAMLError: If YAML content is syntactically invalid.
    """
    # Step 1: Normalize input to raw dict
    workflow_base_dir = _base_dir or "."
    require_custom_metadata = False
    if isinstance(yaml_str_or_dict, str):
        stripped = yaml_str_or_dict.strip()
        is_file_path = "\n" not in stripped and (
            stripped.endswith(".yaml") or stripped.endswith(".yml") or stripped.endswith(".json")
        )
        if is_file_path:
            workflow_base_dir = _base_dir or resolve_discovery_base_dir(
                Path(stripped).resolve().parent
            )
            require_custom_metadata = True
            with open(stripped, "r", encoding="utf-8") as f:
                raw: Any = yaml.safe_load(f)
        else:
            raw = yaml.safe_load(yaml_str_or_dict)
    else:
        raw = yaml_str_or_dict

    if isinstance(raw, dict):
        raw_tools = raw.get("tools")
        if isinstance(raw_tools, list):
            duplicates = _find_duplicate_tool_ids(raw_tools)
            if duplicates:
                joined = ", ".join(repr(tool_id) for tool_id in duplicates)
                raise ValueError(f"duplicate workflow tool ids are not allowed: {joined}")
        raw_souls = raw.get("souls")
        if isinstance(raw_souls, dict):
            for soul_data in raw_souls.values():
                if isinstance(soul_data, dict):
                    soul_data.pop("exits", None)

    # Step 2: Validate against Pydantic schema (raises ValidationError on failure)
    file_def = RunsightWorkflowFile.model_validate(raw)

    # Step 2.1: Validate schema version
    if file_def.version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported schema version '{file_def.version}'. "
            f"Supported versions: {sorted(SUPPORTED_VERSIONS)}. "
            f"If you are using a newer version of Runsight YAML, "
            f"please upgrade runsight-core to a compatible release."
        )

    _validate_workflow_block_runtime_placement(
        file_def,
        workflow_label=getattr(file_def.workflow, "name", "<root>"),
    )

    assertion_index = AssertionScanner(workflow_base_dir).scan()
    register_custom_assertions(assertion_index)

    # Step 3: Discover library souls from custom/souls/.
    souls_dir = Path(workflow_base_dir) / "custom" / "souls"
    external_souls = _discover_external_souls(souls_dir, inline_soul_keys=file_def.souls)

    # Step 3.5: Merge inline workflow souls over discovered external soul files.
    souls_map: Dict[str, Soul] = _merge_inline_souls(file_def, external_souls)

    # Step 4: Instantiate runner (shared across all blocks in this workflow)
    if runner is None:
        model_name = _bootstrap_runner_model_name(souls_map)
        runner = RunsightTeamRunner(model_name=model_name, api_keys=api_keys)

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
            _validate_workflow_block_contract(block_id, block_def, child_file)

            # Normalize to dict so parse_workflow_yaml receives Union[str, Dict] not model instance
            child_raw = child_file.model_dump() if hasattr(child_file, "model_dump") else child_file

            # Recursively parse child workflow (passes registry + base_dir for nested workflows)
            child_wf = parse_workflow_yaml(
                child_raw,
                workflow_registry=workflow_registry,
                api_keys=api_keys,
                _base_dir=workflow_base_dir,
            )

            # Instantiate WorkflowBlock
            from runsight_core.blocks.workflow_block import WorkflowBlock

            block = WorkflowBlock(
                block_id=block_id,
                child_workflow=child_wf,
                inputs=block_def.inputs or {},
                outputs=block_def.outputs or {},
                workflow_ref=block_def.workflow_ref,
                max_depth=_resolve_workflow_block_max_depth(file_def, block_def),
                interface=child_file.interface,
                on_error=block_def.on_error,
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

    # Step 6.5a: Wrap LLM blocks with IsolatedBlockWrapper at build time
    from runsight_core.isolation.wrapper import LLM_BLOCK_TYPES, IsolatedBlockWrapper

    for block_id, block_def in file_def.blocks.items():
        if block_def.type in LLM_BLOCK_TYPES and block_id in built_blocks:
            inner = built_blocks[block_id]
            wrapper = IsolatedBlockWrapper(
                block_id=block_id,
                inner_block=inner,
                retry_config=inner.retry_config,
            )
            wrapper.stateful = inner.stateful
            built_blocks[block_id] = wrapper

    # Step 6.5b: Bridge block-owned assertions onto the final runtime blocks
    for block_id, block_def in file_def.blocks.items():
        if block_id in built_blocks:
            block_assertions = getattr(block_def, "assertions", None)
            built_blocks[block_id].assertions = (
                [dict(assertion) for assertion in block_assertions]
                if block_assertions is not None
                else None
            )

    # Step 6.5c: Bridge exit_conditions from schema to runtime blocks
    for block_id, block_def in file_def.blocks.items():
        if block_id in built_blocks:
            exit_conditions = getattr(block_def, "exit_conditions", None)
            if exit_conditions is not None:
                built_blocks[block_id].exit_conditions = exit_conditions

    # Step 6.5d: Bridge limits from schema to runtime blocks
    for block_id, block_def in file_def.blocks.items():
        if block_id in built_blocks and block_def.limits:
            blk = built_blocks[block_id]
            blk.limits = block_def.limits
            if block_def.limits.max_duration_seconds:
                blk.max_duration_seconds = block_def.limits.max_duration_seconds
            # Also bridge onto the inner block if wrapped (IsolatedBlockWrapper)
            inner_blk = getattr(blk, "inner_block", None)
            if inner_blk is not None:
                inner_blk.limits = block_def.limits
                if block_def.limits.max_duration_seconds:
                    inner_blk.max_duration_seconds = block_def.limits.max_duration_seconds

    # Step 6.6: Validate and resolve tools per soul
    validate_tool_governance(file_def, souls_map)
    _validate_declared_tool_definitions(
        file_def,
        base_dir=workflow_base_dir,
        require_custom_metadata=require_custom_metadata,
    )

    # 6.6c: Resolve ToolInstance objects per soul
    referenced_souls = _collect_referenced_soul_keys(file_def)
    for soul_key in referenced_souls:
        soul = souls_map.get(soul_key)
        if soul is None or not soul.tools:
            continue

        resolved_tools = []
        for tool_name in soul.tools:
            tool_id = _resolve_soul_tool_definition(tool_name, file_def.tools)
            if tool_id is None:
                continue

            if tool_id == "delegate":
                # Find the block that references this soul via soul_ref
                block_id_for_soul = None
                block_def_for_soul = None
                for bid, bdef in file_def.blocks.items():
                    if getattr(bdef, "soul_ref", None) == soul_key:
                        block_id_for_soul = bid
                        block_def_for_soul = bdef
                        break
                    exits = getattr(bdef, "exits", None) or []
                    if any(getattr(exit_def, "soul_ref", None) == soul_key for exit_def in exits):
                        block_id_for_soul = bid
                        block_def_for_soul = bdef
                        break

                exits = getattr(block_def_for_soul, "exits", None) if block_def_for_soul else None
                if not exits:
                    raise ValueError(
                        f"Soul '{soul_key}' uses delegate tool but block "
                        f"'{block_id_for_soul}' has no exits defined"
                    )
                resolved_tools.append(
                    _attach_tool_runtime_metadata(
                        _resolve_tool_for_parser(
                            tool_id,
                            exits=exits,
                            base_dir=workflow_base_dir,
                        ),
                        tool_id,
                        base_dir=workflow_base_dir,
                    )
                )
            else:
                resolved_tools.append(
                    _attach_tool_runtime_metadata(
                        _resolve_tool_for_parser(tool_id, base_dir=workflow_base_dir),
                        tool_id,
                        base_dir=workflow_base_dir,
                    )
                )

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

    # Step 7.1: Bridge workflow-level limits onto the Workflow object
    if file_def.limits:
        wf.limits = file_def.limits

    # Step 8: Register plain transitions
    for t in file_def.workflow.transitions:
        wf.add_transition(t.from_, t.to)

    # Step 8.5: Expand depends sugar into plain transitions
    _expand_depends(file_def, wf)

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

    # Step 9.5: Expand gate pass/fail shorthand into conditional transitions
    _expand_gate_shortcuts(file_def, wf)

    # Step 10: Set entry block
    wf.set_entry(file_def.workflow.entry)

    # Step 10.5: Wire output_conditions to Workflow
    for block_id, block_def in file_def.blocks.items():
        _wire_output_conditions(wf, block_id, block_def.output_conditions)

    # Step 10.6: Expand routes shorthand into output_conditions and conditional transitions
    _expand_routes(file_def, wf)

    # Step 10.75: Bridge error_route declarations onto the workflow
    _bridge_error_routes(file_def, wf)

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
