"""
YAML workflow parser for Runsight.
Exports: parse_workflow_yaml
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
from runsight_core.identity import EntityKind, EntityRef
from runsight_core.primitives import Soul, Step
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
    RunsightWorkflowFile,
)
from runsight_core.yaml.validation import ValidationResult

# Supported schema versions.  When a future version bump is needed:
# 1. Add the new version string here.
# 2. Gate migration logic on ``file_def.version`` before the block-building loop.
SUPPORTED_VERSIONS: frozenset[str] = frozenset({"1.0"})
_UNSET_RUNNER_MODEL_NAME = "__runsight_explicit_model_required__"
_RESERVED_CONTEXT_BLOCK_IDS = frozenset({"workflow", "results", "shared_memory", "metadata"})
_RESERVED_BLOCK_INPUT_NAMES = frozenset(
    {
        "workflow",
        "results",
        "shared_memory",
        "metadata",
        "blocks",
        "ctx",
        "call_stack",
        "workflow_registry",
        "observer",
    }
)
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
    return SoulScanner(base_dir).scan(ignore_keys=inline_soul_keys).ids()


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
) -> ValidationResult:
    """Validate workflow tool declarations against referenced library souls."""
    result = ValidationResult()
    if souls_map is None:
        souls_map = {}

    declared_tools = set(file_def.tools)
    for soul_key in _collect_referenced_soul_keys(file_def):
        soul = souls_map.get(soul_key)
        if soul is None or not soul.tools:
            continue

        for tool_name in soul.tools:
            if _resolve_soul_tool_definition(tool_name, declared_tools) is None:
                soul_ref = str(EntityRef(EntityKind.SOUL, soul_key))
                tool_ref = str(EntityRef(EntityKind.TOOL, tool_name))
                message = (
                    f"{soul_ref} (custom/souls/{soul_key}.yaml) references undeclared "
                    f"{tool_ref}. Declared tools: {sorted(file_def.tools)}"
                )
                if "/" in tool_name:
                    result.add_error(message, source="tool_governance", context=soul_key)
                else:
                    result.add_warning(message, source="tool_governance", context=soul_key)
    return result


def _validate_declared_tool_definitions(
    file_def: RunsightWorkflowFile,
    *,
    base_dir: str,
    require_custom_metadata: bool = False,
) -> ValidationResult:
    """Validate that declared canonical tool IDs are parse-time resolvable."""
    result = ValidationResult()

    for tool_id in file_def.tools:
        if tool_id not in RESERVED_BUILTIN_TOOL_IDS:
            continue

        expected_file = Path(base_dir) / "custom" / "tools" / f"{tool_id}.yaml"
        if expected_file.exists():
            result.add_error(
                (
                    f"reserved builtin tool id '{tool_id}' collides with custom tool metadata at "
                    f"{expected_file}"
                ),
                source="tool_definitions",
                context=tool_id,
            )

    if result.has_errors:
        return result

    try:
        discovered_tools = ToolScanner(base_dir).scan().ids()
    except ValueError as exc:
        scanner_message = str(exc)
        for tool_id in file_def.tools:
            expected_file = Path(base_dir) / "custom" / "tools" / f"{tool_id}.yaml"
            if tool_id in RESERVED_BUILTIN_TOOL_IDS:
                if (
                    f"reserved builtin tool id '{tool_id}'" in scanner_message
                    or str(expected_file) in scanner_message
                ):
                    result.add_error(
                        (
                            f"reserved builtin tool id '{tool_id}' collides with custom tool "
                            f"metadata at {expected_file}"
                        ),
                        source="tool_definitions",
                        context=tool_id,
                    )
                    return result
                continue

            if expected_file.name in scanner_message and (
                "Tool code must define" in scanner_message
                or "Tool code has a syntax error" in scanner_message
            ):
                result.add_warning(
                    f"Tool '{tool_id}': {scanner_message}",
                    source="tool_definitions",
                    context=tool_id,
                )
                return result

        raise

    available_builtin_ids = sorted(RESERVED_BUILTIN_TOOL_IDS)
    available_custom_ids = sorted(discovered_tools.keys())

    for tool_id in file_def.tools:
        if tool_id in RESERVED_BUILTIN_TOOL_IDS and tool_id in discovered_tools:
            result.add_error(
                (
                    f"reserved builtin tool id '{tool_id}' collides with custom tool metadata at "
                    f"{Path(base_dir) / 'custom' / 'tools' / f'{tool_id}.yaml'}"
                ),
                source="tool_definitions",
                context=tool_id,
            )

    if result.has_errors:
        return result

    for tool_id in file_def.tools:
        expected_file = Path(base_dir) / "custom" / "tools" / f"{tool_id}.yaml"

        if tool_id in RESERVED_BUILTIN_TOOL_IDS:
            continue

        tool_meta = discovered_tools.get(tool_id)
        if tool_meta is None:
            tool_ref = str(EntityRef(EntityKind.TOOL, tool_id))
            if require_custom_metadata:
                result.add_warning(
                    (
                        f"{tool_ref} references missing custom tool metadata. "
                        f"Expected metadata at {expected_file}"
                    ),
                    source="tool_definitions",
                    context=tool_id,
                )
            else:
                result.add_warning(
                    (
                        f"Workflow declares unknown {tool_ref}. "
                        f"Available builtin IDs: {available_builtin_ids}. "
                        f"Discovered custom IDs: {available_custom_ids}"
                    ),
                    source="tool_definitions",
                    context=tool_id,
                )
            continue

        try:
            _resolve_tool_for_parser(tool_id, base_dir=base_dir)
        except ValueError as exc:
            result.add_warning(
                f"Tool '{tool_id}': {exc}", source="tool_definitions", context=tool_id
            )

    return result


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
        tool_meta = ToolScanner(base_dir).scan().ids().get(tool_id)
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

from runsight_core.blocks.workflow_block import (  # noqa: E402
    _resolve_workflow_block_max_depth,
    _validate_workflow_block_contract,
)


def _validate_workflow_block_runtime_placement(
    file_def: RunsightWorkflowFile,
    *,
    workflow_label: str,
) -> None:
    """Reserved hook for workflow/loop placement validation."""
    return None


def validate_workflow_call_contracts(
    file_def: RunsightWorkflowFile,
    *,
    base_dir: str,
    validation_index: dict[str, tuple[Path, RunsightWorkflowFile]] | None = None,
    current_workflow_ref: str | None = None,
    ancestry: tuple[str, ...] | None = None,
    current_call_stack_depth: int = 1,
    _depth_uses_strict_comparison: bool = False,
) -> None:
    if validation_index is None:
        workflow_scan_index = WorkflowScanner(base_dir).scan()
        validation_index = {
            result.entity_id: (result.path, result.item)
            for result in workflow_scan_index.get_all()
            if result.entity_id is not None
        }
    workflow_label = getattr(file_def.workflow, "name", None) or current_workflow_ref or "<root>"
    _validate_workflow_block_runtime_placement(file_def, workflow_label=workflow_label)
    if ancestry is None:
        root_ref = current_workflow_ref or getattr(file_def.workflow, "name", "<root>")
        ancestry = (root_ref,)

    for block_id, block_def in file_def.blocks.items():
        if block_def.type != "workflow":
            continue

        indexed = validation_index.get(block_def.workflow_ref)
        if indexed is None:
            raise ValueError(
                f"WorkflowRegistry: cannot resolve ref '{block_def.workflow_ref}'. "
                "Not found among registered workflow ids."
            )
        child_path, child_file = indexed
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
            _depth_uses_strict_comparison=next_strict,
        )


def _normalize_workflow_input(
    yaml_str_or_dict: Union[str, Dict[str, Any]],
    _base_dir: Optional[str],
) -> tuple[RunsightWorkflowFile, str, bool]:
    """Normalize input, validate schema, and return (file_def, workflow_base_dir, require_custom_metadata)."""
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
        _validate_raw_context_config(raw)

    file_def = RunsightWorkflowFile.model_validate(raw)

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

    return file_def, workflow_base_dir, require_custom_metadata


def _validate_raw_context_config(raw: dict[str, Any]) -> None:
    raw_blocks = raw.get("blocks")
    if not isinstance(raw_blocks, dict):
        return
    for block_id, block_config in raw_blocks.items():
        if not isinstance(block_config, dict):
            continue
        if "access" in block_config:
            raise ValueError(
                f"Block '{block_id}': unsupported block field 'access'; "
                "declare context with the 'inputs' field"
            )
        raw_inputs = block_config.get("inputs")
        if not isinstance(raw_inputs, dict):
            continue
        reserved_inputs = sorted(set(raw_inputs) & _RESERVED_BLOCK_INPUT_NAMES)
        if reserved_inputs:
            input_name = reserved_inputs[0]
            raise ValueError(f"Block '{block_id}': local input '{input_name}' is reserved")


def _bridge_block_attributes(block_id: str, block_def: Any, block: Any) -> None:
    """Bridge all schema attributes onto a runtime block in a single pass."""
    if block_def.exits:
        block._declared_exits = block_def.exits
    if block_def.retry_config is not None:
        block.retry_config = block_def.retry_config
    if block_def.stateful:
        block.stateful = block_def.stateful
    block_assertions = getattr(block_def, "assertions", None)
    block.assertions = (
        [dict(assertion) for assertion in block_assertions]
        if block_assertions is not None
        else None
    )
    exit_conditions = getattr(block_def, "exit_conditions", None)
    if exit_conditions is not None:
        block.exit_conditions = exit_conditions
    if block_def.limits:
        block.limits = block_def.limits
        if block_def.limits.max_duration_seconds:
            block.max_duration_seconds = block_def.limits.max_duration_seconds
        inner_blk = getattr(block, "inner_block", None)
        if inner_blk is not None:
            inner_blk.limits = block_def.limits
            if block_def.limits.max_duration_seconds:
                inner_blk.max_duration_seconds = block_def.limits.max_duration_seconds
    _attach_context_metadata(block, _context_access(block_def), _declared_inputs(block_def))


def _context_access(block_def: Any) -> str:
    return "declared"


def _declared_inputs(block_def: Any) -> Dict[str, str]:
    inputs = getattr(block_def, "inputs", None)
    if inputs is None:
        return {}
    declared_inputs: Dict[str, str] = {}
    for input_name, input_ref in inputs.items():
        declared_inputs[input_name] = (
            input_ref.from_ref if isinstance(input_ref, InputRef) else input_ref
        )
    return declared_inputs


def _attach_context_metadata(
    block: Any, context_access: str, declared_inputs: Dict[str, str]
) -> None:
    block.context_access = context_access
    block.declared_inputs = dict(declared_inputs)
    inner_block = getattr(block, "inner_block", None)
    if inner_block is not None:
        inner_block.context_access = context_access
        inner_block.declared_inputs = dict(declared_inputs)


def _validate_context_declarations(file_def: RunsightWorkflowFile) -> None:
    for block_id, block_def in file_def.blocks.items():
        access = _context_access(block_def)
        if access != "declared":
            raise ValueError(f"Block '{block_id}': access {access!r} is unsupported")


def _context_ref_dependency_source_id(from_ref: str) -> str | None:
    parts = from_ref.split(".")
    root = parts[0]
    if root in {"metadata", "shared_memory"}:
        return None
    if root == "workflow":
        return None
    if root == "results":
        if len(parts) < 2:
            raise ValueError("results context references must include a source")
        source_id = parts[1]
        return None if source_id == "workflow" else source_id
    return root


def _find_block_for_soul(file_def: RunsightWorkflowFile, soul_key: str) -> tuple[Any, Any]:
    """Return (block_id, block_def) for the block that owns soul_key, or (None, None)."""
    for bid, bdef in file_def.blocks.items():
        if getattr(bdef, "soul_ref", None) == soul_key:
            return bid, bdef
        exits = getattr(bdef, "exits", None) or []
        if any(getattr(ex, "soul_ref", None) == soul_key for ex in exits):
            return bid, bdef
    return None, None


def _resolve_tools_for_souls(
    file_def: RunsightWorkflowFile,
    souls_map: Dict[str, Soul],
    workflow_base_dir: str,
) -> None:
    """Resolve ToolInstance objects per soul and assign to soul.resolved_tools."""
    for soul_key in _collect_referenced_soul_keys(file_def):
        soul = souls_map.get(soul_key)
        if soul is None or not soul.tools:
            continue
        resolved_tools = []
        for tool_name in soul.tools:
            tool_id = _resolve_soul_tool_definition(tool_name, file_def.tools)
            if tool_id is None:
                continue
            if tool_id == "delegate":
                block_id_for_soul, block_def_for_soul = _find_block_for_soul(file_def, soul_key)
                exits = getattr(block_def_for_soul, "exits", None) if block_def_for_soul else None
                if not exits:
                    raise ValueError(
                        f"Soul '{soul_key}' uses delegate tool but block "
                        f"'{block_id_for_soul}' has no exits defined"
                    )
                try:
                    resolved_tool = _resolve_tool_for_parser(
                        tool_id, exits=exits, base_dir=workflow_base_dir
                    )
                except Exception as exc:
                    logger.warning(
                        "Skipping unresolved tool '%s' for soul '%s': %s", tool_id, soul_key, exc
                    )
                    continue
            else:
                try:
                    resolved_tool = _resolve_tool_for_parser(tool_id, base_dir=workflow_base_dir)
                except Exception as exc:
                    logger.warning(
                        "Skipping unresolved tool '%s' for soul '%s': %s", tool_id, soul_key, exc
                    )
                    continue
            resolved_tools.append(
                _attach_tool_runtime_metadata(resolved_tool, tool_id, base_dir=workflow_base_dir)
            )
        soul.resolved_tools = resolved_tools


def _validate_inputs_and_detect_cycles(
    file_def: RunsightWorkflowFile,
    built_blocks: Dict[str, Any],
) -> None:
    """Validate input references, detect cycles, and wrap input-bearing blocks in Step objects."""
    input_deps: Dict[str, list] = {}
    for block_id, block_def in file_def.blocks.items():
        if block_def.inputs is not None and block_def.type != "workflow":
            deps = []
            for input_name, input_ref in block_def.inputs.items():
                from_ref = input_ref.from_ref if isinstance(input_ref, InputRef) else input_ref
                source_id = _context_ref_dependency_source_id(from_ref)
                if source_id is None:
                    continue
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

    def _detect_cycle(node: str, visiting: set, visited: set) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dep in input_deps.get(node, []):
            if _detect_cycle(dep, visiting, visited):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    visiting_set: set = set()
    visited_set: set = set()
    for block_id in input_deps:
        if _detect_cycle(block_id, visiting_set, visited_set):
            raise ValueError(
                f"Circular input dependency cycle detected involving block '{block_id}'"
            )

    for block_id, block_def in file_def.blocks.items():
        if block_def.inputs is None or block_def.type == "workflow" or block_id not in built_blocks:
            continue
        _wrap_declared_input_block(block_id, block_def, built_blocks)


def _wrap_declared_input_block(
    block_id: str,
    block_def: Any,
    built_blocks: Dict[str, Any],
) -> None:
    declared_inputs = _declared_inputs(block_def)
    context_access = _context_access(block_def)
    _attach_context_metadata(built_blocks[block_id], context_access, declared_inputs)
    built_blocks[block_id] = Step(
        block=built_blocks[block_id],
        declared_inputs=declared_inputs,
        context_access=context_access,
    )


def _wrap_llm_blocks_with_isolation(
    file_def: RunsightWorkflowFile,
    built_blocks: Dict[str, Any],
    api_keys: Optional[Dict[str, str]],
) -> None:
    """Wrap LLM blocks with IsolatedBlockWrapper (Step 6.5a — structural replacement)."""
    from runsight_core.isolation.harness import SubprocessHarness
    from runsight_core.isolation.wrapper import LLM_BLOCK_TYPES, IsolatedBlockWrapper

    for block_id, block_def in file_def.blocks.items():
        if block_def.type in LLM_BLOCK_TYPES and block_id in built_blocks:
            inner = built_blocks[block_id]
            harness = SubprocessHarness(
                api_keys=dict(api_keys or {}),
                timeout_seconds=block_def.timeout_seconds,
                stall_thresholds=dict(block_def.stall_thresholds or {}),
            )
            wrapper = IsolatedBlockWrapper(
                block_id=block_id,
                inner_block=inner,
                harness=harness,
                retry_config=inner.retry_config,
            )
            wrapper.assertions = getattr(inner, "assertions", None)
            wrapper.exit_conditions = getattr(inner, "exit_conditions", None)
            if hasattr(inner, "_declared_exits"):
                wrapper._declared_exits = getattr(inner, "_declared_exits")
            if hasattr(inner, "limits"):
                wrapper.limits = getattr(inner, "limits")
            if hasattr(inner, "max_duration_seconds"):
                wrapper.max_duration_seconds = getattr(inner, "max_duration_seconds")
            _attach_context_metadata(
                wrapper,
                _context_access(block_def),
                _declared_inputs(block_def),
            )
            wrapper.stateful = inner.stateful
            built_blocks[block_id] = wrapper


def _assemble_workflow(
    file_def: RunsightWorkflowFile,
    built_blocks: Dict[str, Any],
) -> Workflow:
    """Assemble, wire, and validate the final Workflow object."""
    wf = Workflow(name=file_def.workflow.name)
    wf.identity = file_def.id
    for block in built_blocks.values():
        wf.add_block(block)
    if file_def.limits:
        wf.limits = file_def.limits
    for t in file_def.workflow.transitions:
        wf.add_transition(t.from_, t.to)
    _expand_depends(file_def, wf)
    for ct in file_def.workflow.conditional_transitions:
        condition_map: Dict[str, str] = {}
        if ct.default is not None:
            condition_map["default"] = ct.default
        for decision_key, target_id in (ct.model_extra or {}).items():
            if target_id is not None:
                condition_map[decision_key] = str(target_id)
        wf.add_conditional_transition(ct.from_, condition_map)
    _expand_gate_shortcuts(file_def, wf)
    wf.set_entry(file_def.workflow.entry)
    for block_id, block_def in file_def.blocks.items():
        _wire_output_conditions(wf, block_id, block_def.output_conditions)
    _expand_routes(file_def, wf)
    _bridge_error_routes(file_def, wf)
    errors = wf.validate()
    if errors:
        raise ValueError(f"Workflow '{file_def.workflow.name}' failed validation: {errors}")
    return wf


def parse_workflow_yaml(
    yaml_str_or_dict: Union[str, Dict[str, Any]],
    *,
    workflow_registry: Optional["WorkflowRegistry"] = None,
    api_keys: Optional[Dict[str, str]] = None,
    runner: Optional[Any] = None,
    _base_dir: Optional[str] = None,
) -> Workflow:
    """Parse a YAML workflow definition into a validated, runnable Workflow object."""
    file_def, workflow_base_dir, require_custom_metadata = _normalize_workflow_input(
        yaml_str_or_dict, _base_dir
    )

    assertion_index = AssertionScanner(workflow_base_dir).scan()
    register_custom_assertions(assertion_index)

    souls_dir = Path(workflow_base_dir) / "custom" / "souls"
    external_souls = _discover_external_souls(souls_dir, inline_soul_keys=file_def.souls)
    souls_map: Dict[str, Soul] = _merge_inline_souls(file_def, external_souls)

    if runner is None:
        model_name = _bootstrap_runner_model_name(souls_map)
        runner = RunsightTeamRunner(model_name=model_name, api_keys=api_keys)

    _validate_reserved_context_block_ids(file_def)
    _validate_context_declarations(file_def)

    built_blocks: Dict[str, BaseBlock] = {}
    for block_id, block_def in file_def.blocks.items():
        from runsight_core.blocks._registry import get_builder

        builder = get_builder(block_def.type)
        if builder is None:
            from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

            raise ValueError(
                f"Unknown block type '{block_def.type}' for block '{block_id}'. "
                f"Available types: {sorted(BLOCK_BUILDER_REGISTRY.keys())}"
            )
        built_blocks[block_id] = builder(
            block_id,
            block_def,
            souls_map,
            runner,
            built_blocks,
            workflow_registry=workflow_registry,
            api_keys=api_keys,
            workflow_base_dir=workflow_base_dir,
            parent_file_def=file_def,
        )

    for block_id, block_def in file_def.blocks.items():
        if block_id in built_blocks:
            _bridge_block_attributes(block_id, block_def, built_blocks[block_id])

    _wrap_llm_blocks_with_isolation(file_def, built_blocks, api_keys)

    validation_result = validate_tool_governance(file_def, souls_map)
    validation_result.merge(
        _validate_declared_tool_definitions(
            file_def, base_dir=workflow_base_dir, require_custom_metadata=require_custom_metadata
        )
    )
    if validation_result.has_errors:
        raise ValueError(validation_result.error_summary or "Tool governance validation failed")

    _resolve_tools_for_souls(file_def, souls_map, workflow_base_dir)
    _validate_inputs_and_detect_cycles(file_def, built_blocks)
    return _assemble_workflow(file_def, built_blocks)


def _validate_reserved_context_block_ids(file_def: RunsightWorkflowFile) -> None:
    reserved_block_ids = sorted(set(file_def.blocks) & _RESERVED_CONTEXT_BLOCK_IDS)
    if reserved_block_ids:
        reserved_id = reserved_block_ids[0]
        raise ValueError(
            f"Block ID '{reserved_id}' is reserved for context namespace access and cannot be used as a block ID."
        )
