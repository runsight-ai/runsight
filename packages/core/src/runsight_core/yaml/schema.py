"""
Pydantic schema models for Runsight YAML workflow files.
No imports from runsight_core — pure data definition layer.

Phase 1 (RUN-110): Discriminated-union BlockDef with per-type models.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    TypeAdapter,
    field_validator,
    model_validator,
)

# -- Soul / Task / Task-file (unchanged) ------------------------------------


class BaseToolDef(BaseModel):
    """Shared fields for YAML tool definitions."""

    model_config = ConfigDict(extra="forbid")

    source: Optional[str] = None


class BuiltinToolDef(BaseToolDef):
    """Built-in tool definition as expressed in the YAML tools: section."""

    type: Literal["builtin"]
    source: str


class CustomToolDef(BaseToolDef):
    """Custom tool definition as expressed in the YAML tools: section."""

    type: Literal["custom"]
    source: str


class HTTPToolDef(BaseToolDef):
    """HTTP tool definition as expressed in the YAML tools: section."""

    type: Literal["http"]
    method: Optional[str] = None
    url: Optional[str] = None
    body_template: Optional[str] = None
    response_path: Optional[str] = None


_ToolDefUnion = Annotated[
    Union[BuiltinToolDef, CustomToolDef, HTTPToolDef],
    Field(discriminator="type"),
]
_TOOL_DEF_ADAPTER = TypeAdapter(_ToolDefUnion)


class ToolDef:
    """Compatibility wrapper for the discriminated YAML tool union."""

    def __new__(cls, **data: Any) -> BuiltinToolDef | CustomToolDef | HTTPToolDef:
        return _TOOL_DEF_ADAPTER.validate_python(data)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> Any:
        return handler.generate_schema(_ToolDefUnion)


class SoulDef(BaseModel):
    """Soul definition as expressed in the YAML souls: section."""

    model_config = ConfigDict(extra="forbid")

    id: str
    role: str
    system_prompt: str
    tools: Optional[List[str]] = None
    required_tool_calls: Optional[List[str]] = None
    max_tool_iterations: int = 5
    model_name: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    avatar_color: Optional[str] = None
    assertions: Optional[List[Dict[str, Any]]] = None


class TaskDef(BaseModel):
    """Task definition as expressed in the YAML tasks: section."""

    id: str
    instruction: str
    context: Optional[str] = None


class RunsightTaskFile(BaseModel):
    """
    Root model for a Runsight task YAML file.
    Uses wrapper format: version + task.
    """

    version: str = "1.0"
    task: TaskDef  # required — no default; Pydantic raises ValidationError if absent


# -- Supporting models for output conditions / inputs -----------------------


class ConditionDef(BaseModel):
    """Single condition rule."""

    model_config = ConfigDict(extra="forbid")

    eval_key: str  # dot-notation path into block's own result
    operator: str  # one of 15 operators
    value: Optional[Any] = None  # comparison value (None for unary: is_empty, exists, etc.)


class ConditionGroupDef(BaseModel):
    """Group of conditions with AND/OR combinator."""

    model_config = ConfigDict(extra="forbid")

    combinator: str = "and"  # "and" | "or"
    conditions: List[ConditionDef]


class CaseDef(BaseModel):
    """A named branch case for output_conditions."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    condition_group: Optional[ConditionGroupDef] = None  # None when default=True
    default: bool = False


class InputRef(BaseModel):
    """Reference to an upstream block's output."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_ref: str = Field(alias="from")  # "step_id.output_field" dot-notation


class WorkflowInterfaceInputDef(BaseModel):
    """Child-owned public input contract for callable workflows."""

    model_config = ConfigDict(extra="forbid")

    name: str
    target: str
    type: Optional[str] = None
    required: bool = True
    default: Optional[Any] = None
    description: Optional[str] = None


class WorkflowInterfaceOutputDef(BaseModel):
    """Child-owned public output contract for callable workflows."""

    model_config = ConfigDict(extra="forbid")

    name: str
    source: str
    type: Optional[str] = None
    description: Optional[str] = None


class WorkflowInterfaceDef(BaseModel):
    """Public callable contract exposed by a child workflow."""

    model_config = ConfigDict(extra="forbid")

    inputs: List[WorkflowInterfaceInputDef] = Field(default_factory=list)
    outputs: List[WorkflowInterfaceOutputDef] = Field(default_factory=list)

    @field_validator("inputs")
    @classmethod
    def _validate_unique_input_names(
        cls, items: List[WorkflowInterfaceInputDef]
    ) -> List[WorkflowInterfaceInputDef]:
        seen: set[str] = set()
        for item in items:
            if item.name in seen:
                raise ValueError(f"duplicate workflow interface input name: {item.name}")
            seen.add(item.name)
        return items

    @field_validator("outputs")
    @classmethod
    def _validate_unique_output_names(
        cls, items: List[WorkflowInterfaceOutputDef]
    ) -> List[WorkflowInterfaceOutputDef]:
        seen: set[str] = set()
        for item in items:
            if item.name in seen:
                raise ValueError(f"duplicate workflow interface output name: {item.name}")
            seen.add(item.name)
        return items


# -- Retry configuration ---------------------------------------------------


class RetryConfig(BaseModel):
    """Per-block retry configuration."""

    max_attempts: int = Field(default=3, ge=1, le=20)
    backoff: Literal["fixed", "exponential"] = "fixed"
    backoff_base_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    non_retryable_errors: Optional[List[str]] = None


# -- Exit definition -------------------------------------------------------


class ExitDef(BaseModel):
    """Named exit port on a block definition."""

    id: str
    label: str


class DispatchExitDef(ExitDef):
    """Exit port on a dispatch block with per-exit soul and task."""

    model_config = ConfigDict(extra="forbid")
    soul_ref: str
    task: str


# -- Base block model ------------------------------------------------------


class BaseBlockDef(BaseModel):
    """Shared fields present on every block definition."""

    model_config = ConfigDict(extra="forbid")

    type: str
    stateful: bool = False
    output_conditions: Optional[List[CaseDef]] = None
    inputs: Optional[Dict[str, InputRef]] = None
    outputs: Optional[Dict[str, str]] = None  # name -> type string
    retry_config: Optional[RetryConfig] = None
    exits: Optional[List[ExitDef]] = None
    assertions: Optional[List[Dict[str, Any]]] = None
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    stall_thresholds: Optional[Dict[str, int]] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Only register concrete block defs (those with Literal["..."] type).
        # Use cls.__annotations__ (not model_fields) because Pydantic has not
        # finished building the model at __init_subclass__ time.
        annotation = cls.__annotations__.get("type")
        if annotation is None:
            return
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", None)
        if origin is Literal or (args and len(args) == 1 and isinstance(args[0], str)):
            block_type = args[0] if args else None
            if block_type:
                from runsight_core.blocks._registry import register_block_def

                register_block_def(block_type, cls)


# -- Discriminated union (built dynamically from registry) ------------------

# Placeholder — rebuilt by rebuild_block_def_union() once blocks are discovered.
BlockDef = Any


# -- Transition / Workflow / File models (unchanged) ------------------------


class TransitionDef(BaseModel):
    """Plain (single-path) transition: from -> to. to=None means terminal block."""

    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")  # 'from' is a Python keyword; alias maps YAML 'from:' key
    to: Optional[str] = None


class ConditionalTransitionDef(BaseModel):
    """
    Conditional (multi-path) transition. Extra fields are decision_key -> target_block_id.

    YAML structure:
        conditional_transitions:
          - from: branch_block
            approved: approve_block
            rejected: reject_block
            default: reject_block   # optional fallback
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    from_: str = Field(alias="from")
    default: Optional[str] = None
    # Extra fields accessed via model_extra: {decision_key: target_block_id, ...}


class WorkflowDef(BaseModel):
    """Top-level workflow graph definition."""

    name: str
    entry: str  # required — no default
    transitions: List[TransitionDef] = Field(default_factory=list)
    conditional_transitions: List[ConditionalTransitionDef] = Field(default_factory=list)


class RunsightWorkflowFile(BaseModel):
    """
    Root model for a Runsight .yaml workflow file.
    'workflow' is the only required top-level key — all others have defaults.
    """

    version: str = "1.0"
    enabled: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)
    interface: Optional[WorkflowInterfaceDef] = None
    tools: List[str] = Field(default_factory=list)
    souls: Dict[str, SoulDef] = Field(default_factory=dict)
    blocks: Dict[str, BlockDef] = Field(default_factory=dict)
    workflow: WorkflowDef  # required — no default; Pydantic raises ValidationError if absent

    @field_validator("tools")
    @classmethod
    def _validate_unique_tool_ids(cls, tool_ids: List[str]) -> List[str]:
        duplicates: List[str] = []
        seen: set[str] = set()
        for tool_id in tool_ids:
            if tool_id in seen and tool_id not in duplicates:
                duplicates.append(tool_id)
            seen.add(tool_id)

        if duplicates:
            joined = ", ".join(repr(tool_id) for tool_id in duplicates)
            raise ValueError(f"duplicate workflow tool ids are not allowed: {joined}")

        return tool_ids

    @model_validator(mode="after")
    def _validate_inline_soul_ids(self) -> "RunsightWorkflowFile":
        for soul_key, soul_def in self.souls.items():
            if soul_key != soul_def.id:
                raise ValueError(
                    f"Inline soul key/id mismatch: key '{soul_key}' must match id '{soul_def.id}'"
                )
        return self


# -- Dynamic union builders -------------------------------------------------


def build_block_def_union() -> Any:
    """Build a discriminated-union type from all registered BlockDef subclasses."""
    from runsight_core.blocks._registry import get_all_block_types

    registry = get_all_block_types()
    if not registry:
        raise RuntimeError("No block types registered.")
    types = [registry[k] for k in sorted(registry.keys())]
    union_type = Union[tuple(types)]
    return Annotated[union_type, Field(discriminator="type")]


def rebuild_block_def_union() -> None:
    """Rebuild ``BlockDef`` from the registry and call ``model_rebuild``."""
    global BlockDef
    BlockDef = build_block_def_union()
    # Update model_fields and __pydantic_fields__ so Pydantic re-resolves the type
    from pydantic.fields import FieldInfo

    new_field = FieldInfo(annotation=Dict[str, BlockDef], default_factory=dict)
    RunsightWorkflowFile.model_fields["blocks"] = new_field
    RunsightWorkflowFile.__pydantic_fields__["blocks"] = new_field
    RunsightWorkflowFile.__pydantic_complete__ = False
    RunsightWorkflowFile.model_rebuild(force=True)
