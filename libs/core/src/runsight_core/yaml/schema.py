"""
Pydantic schema models for Runsight YAML workflow files.
No imports from runsight_core — pure data definition layer.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class BlockDef(BaseModel):
    """
    Block definition. `type` is the only required field.
    All other fields are optional; extra fields are allowed for custom block configs.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    # Common optional fields — present on specific block types
    soul_ref: Optional[str] = None  # LinearBlock, SynthesizeBlock, RouterBlock, etc.
    soul_refs: Optional[List[str]] = None  # FanOutBlock, MessageBusBlock
    soul_a_ref: Optional[str] = None  # DebateBlock
    soul_b_ref: Optional[str] = None  # DebateBlock
    input_block_ids: Optional[List[str]] = None  # SynthesizeBlock
    inner_block_ref: Optional[str] = None  # RetryBlock
    failure_context_keys: Optional[List[str]] = None  # TeamLeadBlock
    condition_ref: Optional[str] = None  # RouterBlock (Callable path, future use)
    iterations: Optional[int] = None  # DebateBlock, MessageBusBlock
    max_retries: Optional[int] = None  # RetryBlock

    # WorkflowBlock-specific fields
    workflow_ref: Optional[str] = None  # Required when type == "workflow"
    inputs: Optional[Dict[str, str]] = None  # child_state_key -> parent_path mapping
    outputs: Optional[Dict[str, str]] = None  # parent_path -> child_dotted_path mapping
    max_depth: Optional[int] = None  # Recursion depth override (default: 10)

    # GateBlock-specific fields
    eval_key: Optional[str] = None  # results key to evaluate
    extract_field: Optional[str] = None  # JSON field to extract on PASS

    # FileWriterBlock-specific fields
    output_path: Optional[str] = None  # file path to write to
    content_key: Optional[str] = None  # results key to read content from

    # RetryBlock enhancement
    provide_error_context: Optional[bool] = None  # inject errors between retries

    @model_validator(mode="after")
    def _validate_workflow_block(self) -> "BlockDef":
        """Enforce workflow_ref requirement when type == 'workflow'."""
        if self.type == "workflow" and self.workflow_ref is None:
            raise ValueError(
                "BlockDef with type='workflow' requires workflow_ref field. "
                "Provide the child workflow name or relative file path."
            )
        return self


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
