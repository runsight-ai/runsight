"""
Pydantic schema models for Runsight YAML workflow files.
No imports from runsight_core — pure data definition layer.

Phase 1 (RUN-110): Discriminated-union BlockDef with per-type models.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


# ── Soul / Task / Task-file (unchanged) ────────────────────────────────────


class SoulDef(BaseModel):
    """Soul definition as expressed in the YAML souls: section."""

    id: str
    role: str
    system_prompt: str
    tools: Optional[List[Dict[str, Any]]] = None
    model_name: Optional[str] = None


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


# ── Supporting models for output conditions / inputs ───────────────────────


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


# ── Retry configuration ────────────────────────────────────────────────────


class RetryConfig(BaseModel):
    """Per-block retry configuration."""

    max_attempts: int = Field(default=3, ge=1, le=20)
    backoff: Literal["fixed", "exponential"] = "fixed"
    backoff_base_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    non_retryable_errors: Optional[List[str]] = None


# ── Base block model ───────────────────────────────────────────────────────


class BaseBlockDef(BaseModel):
    """Shared fields present on every block definition."""

    model_config = ConfigDict(extra="forbid")

    type: str
    stateful: bool = False
    output_conditions: Optional[List[CaseDef]] = None
    inputs: Optional[Dict[str, InputRef]] = None
    outputs: Optional[Dict[str, str]] = None  # name -> type string
    retry_config: Optional[RetryConfig] = None

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


# ── Per-type block models ──────────────────────────────────────────────────


class LinearBlockDef(BaseBlockDef):
    type: Literal["linear"] = "linear"
    soul_ref: str


class FanOutBlockDef(BaseBlockDef):
    type: Literal["fanout"] = "fanout"
    soul_refs: List[str]


class SynthesizeBlockDef(BaseBlockDef):
    type: Literal["synthesize"] = "synthesize"
    soul_ref: str
    input_block_ids: List[str]


class RouterBlockDef(BaseBlockDef):
    type: Literal["router"] = "router"
    soul_ref: str
    condition_ref: Optional[str] = None


class TeamLeadBlockDef(BaseBlockDef):
    type: Literal["team_lead"] = "team_lead"
    soul_ref: str
    failure_context_keys: Optional[List[str]] = None


class EngineeringManagerBlockDef(BaseBlockDef):
    type: Literal["engineering_manager"] = "engineering_manager"
    soul_ref: str


class GateBlockDef(BaseBlockDef):
    type: Literal["gate"] = "gate"
    soul_ref: str
    eval_key: str
    extract_field: Optional[str] = None


class FileWriterBlockDef(BaseBlockDef):
    type: Literal["file_writer"] = "file_writer"
    output_path: str
    content_key: str


class CodeBlockDef(BaseBlockDef):
    type: Literal["code"] = "code"
    code: str
    timeout_seconds: int = 30
    allowed_imports: Optional[List[str]] = None


class CarryContextConfig(BaseModel):
    """Configuration for carrying context between LoopBlock rounds."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    mode: Literal["last", "all"] = "last"
    source_blocks: Optional[List[str]] = None
    inject_as: str = "previous_round_context"


class LoopBlockDef(BaseBlockDef):
    type: Literal["loop"] = "loop"
    inner_block_refs: List[str] = Field(min_length=1)
    max_rounds: int = Field(default=5, ge=1, le=50)
    break_condition: Optional[Union[ConditionDef, ConditionGroupDef]] = None
    carry_context: Optional[CarryContextConfig] = None


class WorkflowBlockDef(BaseBlockDef):
    """
    WorkflowBlock definition.

    ``inputs`` and ``outputs`` override BaseBlockDef fields with workflow-specific
    types (Dict[str, str] for state key mapping) to maintain backward compatibility
    with existing YAML files and parser code that accesses ``block_def.inputs``.
    """

    type: Literal["workflow"] = "workflow"
    workflow_ref: str
    inputs: Optional[Dict[str, str]] = None  # type: ignore[assignment]  # child_state_key -> parent_path
    outputs: Optional[Dict[str, str]] = None  # parent_path -> child_dotted_path
    max_depth: Optional[int] = None


# ── Discriminated union ────────────────────────────────────────────────────

BlockDef = Annotated[
    Union[
        LinearBlockDef,
        FanOutBlockDef,
        SynthesizeBlockDef,
        RouterBlockDef,
        TeamLeadBlockDef,
        EngineeringManagerBlockDef,
        GateBlockDef,
        FileWriterBlockDef,
        CodeBlockDef,
        LoopBlockDef,
        WorkflowBlockDef,
    ],
    Field(discriminator="type"),
]


# ── Transition / Workflow / File models (unchanged) ────────────────────────


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
          - from: router_block
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
    config: Dict[str, Any] = Field(default_factory=dict)
    souls: Dict[str, SoulDef] = Field(default_factory=dict)
    blocks: Dict[str, BlockDef] = Field(default_factory=dict)
    workflow: WorkflowDef  # required — no default; Pydantic raises ValidationError if absent


# ── Dynamic union builders ─────────────────────────────────────────────────


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


# ── Backward-compat re-exports (lazy) ──────────────────────────────────────


def __getattr__(name: str) -> Any:
    if name == "HttpRequestBlockDef":
        from runsight_core.blocks.http_request import HttpRequestBlockDef

        return HttpRequestBlockDef
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
