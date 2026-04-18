"""
RED tests for RUN-899: wire validated workflow inputs into runtime state.

These tests pin the contract at the core/runtime boundary:
- named workflow inputs must come from WorkflowState.workflow_inputs
- bare workflow access is not allowed
- missing named workflow inputs fail without leaking unrelated state
- existing block result resolution continues to work
- nested WorkflowBlock calls forward child inputs into the child state
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.block_io import build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.context_governance import (
    ContextDeclaration,
    ContextGovernancePolicy,
    ContextReadDeniedError,
    ContextResolutionError,
    ContextResolver,
)
from runsight_core.state import BlockResult, WorkflowState


class CapturingWorkflow:
    """Child workflow spy that records the state passed by WorkflowBlock."""

    def __init__(self) -> None:
        self.name = "child_workflow"
        self.received_state: WorkflowState | None = None
        self.received_kwargs: dict[str, Any] | None = None

    async def run(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        self.received_state = state
        self.received_kwargs = kwargs
        return WorkflowState(
            artifact_store=state.artifact_store,
            total_cost_usd=0.0,
            total_tokens=0,
        )


def _resolver() -> ContextResolver:
    return ContextResolver(
        policy=ContextGovernancePolicy(),
        run_id="run_899",
        workflow_name="workflow_inputs",
    )


def _state(
    *,
    results: dict[str, Any] | None = None,
    shared_memory: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    workflow_inputs: dict[str, Any] | None = None,
) -> WorkflowState:
    state = WorkflowState(
        results=results or {},
        shared_memory=shared_memory or {},
        metadata=metadata or {},
    )
    if workflow_inputs is not None:
        state = state.model_copy(update={"workflow_inputs": workflow_inputs})
    return state


def test_context_resolver_reads_named_workflow_input_from_workflow_state() -> None:
    """Named workflow inputs must resolve from runtime workflow_inputs, not synthetic results."""
    declaration = ContextDeclaration(
        block_id="consumer",
        block_type="linear",
        declared_inputs={
            "query": "workflow.query",
            "summary": "draft.summary",
        },
    )
    state = _state(
        workflow_inputs={"query": "typed query"},
        results={
            "workflow": BlockResult(output=json.dumps({"query": "synthetic query"})),
            "draft": BlockResult(output=json.dumps({"summary": "upstream summary"})),
        },
    )

    scoped = _resolver().resolve(declaration=declaration, state=state)

    assert scoped.inputs["query"] == "typed query"
    assert scoped.inputs["summary"] == "upstream summary"
    assert scoped.audit_event.records[0].from_ref == "workflow.query"
    assert scoped.audit_event.records[1].from_ref == "draft.summary"


def test_parse_context_ref_rejects_bare_workflow_access() -> None:
    """Broad workflow access must be rejected instead of resolving to a whole result source."""
    from runsight_core import context_governance as cg

    with pytest.raises((ValueError, ContextReadDeniedError), match="workflow|named input"):
        cg.parse_context_ref("workflow")


def test_context_resolver_missing_named_workflow_input_does_not_expose_unrelated_state() -> None:
    """Missing workflow refs should name the missing input without echoing unrelated state keys."""
    declaration = ContextDeclaration(
        block_id="consumer",
        block_type="linear",
        declared_inputs={"query": "workflow.query"},
    )
    state = _state(
        results={
            "draft": BlockResult(output=json.dumps({"summary": "visible"})),
            "unrelated": BlockResult(output=json.dumps({"secret": "hidden"})),
        },
        shared_memory={"secret": "hidden"},
        metadata={"runtime": {"branch": "main", "commit": "abc123"}},
    )

    with pytest.raises(ContextResolutionError) as exc_info:
        _resolver().resolve(declaration=declaration, state=state)

    message = str(exc_info.value)
    assert "query" in message
    assert "draft" not in message
    assert "unrelated" not in message
    assert "secret" not in message
    assert "branch" not in message


@pytest.mark.asyncio
async def test_workflow_block_passes_child_inputs_into_child_workflow_state() -> None:
    """Nested WorkflowBlock execution must seed child workflow_inputs from the mapped inputs."""
    child_workflow = CapturingWorkflow()
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={"query": "shared_memory.topic"},
        outputs={},
    )
    parent_state = _state(shared_memory={"topic": "climate"})
    ctx = build_block_context(block, parent_state)

    await block.execute(ctx)

    assert child_workflow.received_kwargs is not None
    assert child_workflow.received_kwargs["inputs"] == {"query": "climate"}
    assert child_workflow.received_state is not None
    assert child_workflow.received_state.workflow_inputs == {"query": "climate"}
