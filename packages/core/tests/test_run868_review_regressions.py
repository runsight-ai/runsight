"""Regression tests for accepted RUN-868 review findings."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from runsight_core.block_io import BlockContext, _resolve_declared_inputs
from runsight_core.blocks.code import CodeBlock
from runsight_core.context_governance import (
    ContextDeclaration,
    ContextGovernancePolicy,
    ContextResolutionError,
    ContextResolver,
)
from runsight_core.primitives import Step
from runsight_core.state import BlockResult, WorkflowState


def _resolver() -> ContextResolver:
    return ContextResolver(
        policy=ContextGovernancePolicy(),
        run_id="run_868_review",
        workflow_name="review_regressions",
    )


def _declaration(declared_inputs: dict[str, str]) -> ContextDeclaration:
    return ContextDeclaration(
        block_id="review_block",
        block_type="linear",
        access="declared",
        declared_inputs=declared_inputs,
    )


def _state_with_results(results: dict[str, Any]) -> WorkflowState:
    # Some legacy/model_copy paths can carry non-BlockResult values despite the
    # nominal WorkflowState annotation. The resolver must preserve their shape.
    return WorkflowState().model_copy(update={"results": results})


def test_context_resolver_resolves_dotted_path_from_plain_dict_result() -> None:
    """Plain structured result values must not be coerced through str()."""
    state = _state_with_results(
        {
            "draft": {
                "summary": "S",
                "title": "T",
                "nested": {"count": 2},
            }
        }
    )

    scoped = _resolver().resolve(
        declaration=_declaration(
            {
                "summary": "draft.summary",
                "count": "draft.nested.count",
            }
        ),
        state=state,
    )

    assert scoped.inputs == {"summary": "S", "count": 2}
    assert json.loads(scoped.scoped_results["draft"].output) == {
        "summary": "S",
        "nested": {"count": 2},
    }


def test_context_resolver_does_not_treat_plain_dict_result_as_non_json_alias() -> None:
    """A plain dict result is already structured JSON data, not a non-JSON alias."""
    state = _state_with_results({"draft": {"output": "explicit output field"}})

    scoped = _resolver().resolve(
        declaration=_declaration({"value": "draft.output"}),
        state=state,
    )

    assert scoped.inputs == {"value": "explicit output field"}
    assert scoped.audit_event.records[0].status == "resolved"
    assert scoped.audit_event.records[0].reason is None


@pytest.mark.asyncio
async def test_codeblock_filters_non_serializable_infra_inputs_before_subprocess() -> None:
    """Runtime infra objects must not crash serialization or reach user code."""
    block = CodeBlock(
        "code_filter",
        code="""\
def main(data):
    return {
        "keys": sorted(data.keys()),
        "safe": data["safe"],
        "nested": data["nested"],
    }
""",
    )
    ctx = BlockContext(
        block_id="code_filter",
        instruction="",
        context=None,
        inputs={
            "safe": "ok",
            "nested": {"value": 1},
            "blocks": {"serializable": "infra"},
            "call_stack": ["parent"],
            "ctx": "serializable-infra",
            "observer": "serializable-infra",
            "workflow_registry": {"serializable": "infra"},
        },
    )

    output = await block.execute(ctx)

    assert output.exit_handle is None
    assert not output.output.startswith("Error:")
    payload = json.loads(output.output)
    assert payload == {
        "keys": ["nested", "safe"],
        "safe": "ok",
        "nested": {"value": 1},
    }


def test_context_audit_redacts_secret_looking_value_under_neutral_names() -> None:
    """Audit JSON must not leak credentials whose path names look neutral."""
    secret = "sk-secret-value"
    scoped = _resolver().resolve(
        declaration=_declaration({"value": "metadata.config.value"}),
        state=WorkflowState(metadata={"config": {"value": secret}}),
    )

    record = scoped.audit_event.records[0]
    assert scoped.inputs == {"value": secret}
    assert record.preview == "[redacted]"
    assert secret not in scoped.audit_event.model_dump_json()


def test_context_audit_keeps_neutral_non_secret_preview() -> None:
    """Value-based redaction must not suppress every neutral preview."""
    scoped = _resolver().resolve(
        declaration=_declaration({"value": "metadata.config.value"}),
        state=WorkflowState(metadata={"config": {"value": "ordinary-status"}}),
    )

    assert scoped.inputs == {"value": "ordinary-status"}
    assert scoped.audit_event.records[0].preview == "ordinary-status"


def test_resolve_declared_inputs_raises_for_invalid_field_path() -> None:
    """The stale helper must not silently omit invalid declared inputs."""
    step = Step(
        block=SimpleNamespace(block_id="review_block"),
        declared_inputs={"summary": "draft.missing"},
    )
    state = WorkflowState(results={"draft": BlockResult(output=json.dumps({"summary": "S"}))})

    with pytest.raises((ValueError, ContextResolutionError), match="draft|missing"):
        _resolve_declared_inputs(step, state)
