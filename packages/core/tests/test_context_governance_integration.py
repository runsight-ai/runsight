"""Context governance integration wiring coverage."""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.block_io import build_block_context
from runsight_core.blocks.linear import LinearBlock
from runsight_core.context_governance import (
    ContextAuditEventV1,
    ContextGovernancePolicy,
    ContextResolutionError,
)
from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope
from runsight_core.isolation.worker_support import build_scoped_state
from runsight_core.isolation.wrapper import IsolatedBlockWrapper
from runsight_core.observer import CompositeObserver
from runsight_core.primitives import Soul, Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml


class RecordingObserver:
    def __init__(self) -> None:
        self.context_events: list[ContextAuditEventV1] = []

    def on_context_resolution(self, event: ContextAuditEventV1) -> None:
        self.context_events.append(event)


class BrokenObserver:
    def on_context_resolution(self, event: ContextAuditEventV1) -> None:
        raise RuntimeError("observer failure should not stop broadcast")


class DeclaredBlock:
    block_id = "review"
    context_access = "declared"
    declared_inputs = {"summary": "draft.summary"}
    soul = None
    runner = None


class CapturingRunner:
    model_name = "fixture-model"

    async def execute(self, instruction: str, content: Any, soul: Soul, **_: Any) -> Any:
        raise AssertionError("isolated wrapper test should stop at envelope capture")


def _soul() -> Soul:
    return Soul(
        id="analyst",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="Use only declared context.",
        model_name="fixture-model",
    )


def _workflow_yaml_with_allowed_namespace_refs() -> str:
    return """\
version: "1.0"
id: context_governance_fixture
kind: workflow
souls:
  analyst:
    id: analyst
    kind: soul
    name: Analyst
    role: Analyst
    system_prompt: Use only declared context.
blocks:
  draft:
    type: code
    code: |
      def main(data):
          return {"summary": "safe draft"}
  review:
    type: linear
    soul_ref: analyst
    inputs:
      summary:
        from: draft.summary
      request:
        from: workflow.request
      feature_flag:
        from: shared_memory.flags.safe
      branch:
        from: metadata.runtime.branch
workflow:
  name: context_governance_workflow
  entry: draft
  transitions:
    - from: draft
      to: review
    - from: review
      to: null
"""


def _state() -> WorkflowState:
    return WorkflowState(
        results={
            "draft": BlockResult(
                output=json.dumps({"summary": "safe draft", "private": "draft private"})
            ),
            "unrelated": BlockResult(output="top private result"),
        },
        workflow_inputs={
            "request": "external input",
            "private": "workflow private",
        },
        shared_memory={
            "flags": {"safe": True, "private": "flag sibling private"},
            "_resolved_inputs": {"summary": "legacy leak"},
            "private": "shared private",
        },
        metadata={
            "run_id": "context-governance-run",
            "workflow_name": "context_governance_integration",
            "runtime": {"branch": "feature/context-governance", "private": "runtime private"},
            "private": "metadata private",
        },
    )


def test_parser_to_resolver_block_context_observer_resolves_only_declared_namespaces() -> None:
    """Parser declarations must drive resolver, BlockContext, and observer audit output."""
    workflow = parse_workflow_yaml(_workflow_yaml_with_allowed_namespace_refs())
    step = workflow._blocks["review"]
    assert isinstance(step, Step)
    recorder = RecordingObserver()
    observer = CompositeObserver(BrokenObserver(), recorder)

    ctx = build_block_context(step.block, _state(), step=step, observer=observer)

    assert ctx.inputs == {
        "summary": "safe draft",
        "request": "external input",
        "feature_flag": True,
        "branch": "feature/context-governance",
    }
    assert len(recorder.context_events) == 1
    event = recorder.context_events[0]
    assert event.node_id == "review"
    assert event.resolved_count == 4
    assert [record.namespace for record in event.records] == [
        "results",
        "workflow",
        "shared_memory",
        "metadata",
    ]
    event_json = event.model_dump_json()
    assert "draft private" not in event_json
    assert "workflow private" not in event_json
    assert "shared private" not in event_json
    assert "metadata private" not in event_json
    assert "legacy leak" not in event_json


def test_block_context_state_snapshot_is_scoped_to_declared_context() -> None:
    """Declared blocks must not get a full WorkflowState escape hatch."""
    workflow = parse_workflow_yaml(_workflow_yaml_with_allowed_namespace_refs())
    step = workflow._blocks["review"]
    assert isinstance(step, Step)

    ctx = build_block_context(step.block, _state(), step=step)

    assert ctx.state_snapshot is not None
    assert set(ctx.state_snapshot.results) == {"draft"}
    assert json.loads(ctx.state_snapshot.results["draft"].output) == {"summary": "safe draft"}
    assert ctx.state_snapshot.workflow_inputs == {"request": "external input"}
    assert ctx.state_snapshot.shared_memory == {"flags": {"safe": True}}
    assert ctx.state_snapshot.metadata == {"runtime": {"branch": "feature/context-governance"}}

    snapshot_json = ctx.state_snapshot.model_dump_json()
    assert "draft private" not in snapshot_json
    assert "top private result" not in snapshot_json
    assert "shared private" not in snapshot_json
    assert "metadata private" not in snapshot_json
    assert "legacy leak" not in snapshot_json


@pytest.mark.asyncio
async def test_isolated_wrapper_envelope_and_worker_state_are_scoped_from_same_declaration() -> (
    None
):
    """Isolation envelopes and worker reconstruction must not re-expand full state."""
    soul = _soul()
    inner = LinearBlock("isolated", soul=soul, runner=CapturingRunner())
    inner.context_access = "declared"
    inner.declared_inputs = {
        "summary": "draft.summary",
        "branch": "metadata.runtime.branch",
    }
    wrapper = IsolatedBlockWrapper("isolated", inner)
    wrapper.context_access = "declared"
    wrapper.declared_inputs = dict(inner.declared_inputs)
    captured: dict[str, ContextEnvelope] = {}

    async def _capture(envelope: ContextEnvelope) -> ResultEnvelope:
        captured["envelope"] = envelope
        return ResultEnvelope(
            block_id=envelope.block_id,
            output="ok",
            exit_handle="done",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

    wrapper._run_in_subprocess = _capture
    recorder = RecordingObserver()
    ctx = build_block_context(wrapper, _state(), observer=recorder)

    await wrapper.execute(ctx)

    envelope = captured["envelope"]
    assert envelope.inputs == {
        "summary": "safe draft",
        "branch": "feature/context-governance",
    }
    assert set(envelope.scoped_results) == {"draft"}
    assert json.loads(envelope.scoped_results["draft"]["output"]) == {"summary": "safe draft"}
    assert envelope.scoped_shared_memory == {}
    assert envelope.scoped_metadata == {"runtime": {"branch": "feature/context-governance"}}
    assert len(envelope.context_audit) == 1
    envelope_json = envelope.model_dump_json()
    assert "draft private" not in envelope_json
    assert "top private result" not in envelope_json
    assert "shared private" not in envelope_json
    assert "metadata private" not in envelope_json
    assert "legacy leak" not in envelope_json

    worker_state = build_scoped_state(envelope)
    assert set(worker_state.results) == {"draft"}
    assert worker_state.shared_memory == {}
    assert worker_state.metadata == {"runtime": {"branch": "feature/context-governance"}}


@pytest.mark.asyncio
async def test_isolated_wrapper_preserves_multiple_declared_fields_from_same_source() -> None:
    """Wrapper re-resolution must see every scoped slice from the same source."""
    soul = _soul()
    inner = LinearBlock("isolated", soul=soul, runner=CapturingRunner())
    inner.context_access = "declared"
    inner.declared_inputs = {
        "summary": "draft.summary",
        "title": "draft.title",
    }
    wrapper = IsolatedBlockWrapper("isolated", inner)
    wrapper.context_access = "declared"
    wrapper.declared_inputs = dict(inner.declared_inputs)
    captured: dict[str, ContextEnvelope] = {}

    async def _capture(envelope: ContextEnvelope) -> ResultEnvelope:
        captured["envelope"] = envelope
        return ResultEnvelope(
            block_id=envelope.block_id,
            output="ok",
            exit_handle="done",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )

    wrapper._run_in_subprocess = _capture
    state = _state().model_copy(
        update={
            "results": {
                **_state().results,
                "draft": BlockResult(
                    output=json.dumps(
                        {
                            "summary": "safe draft",
                            "title": "T",
                            "private": "draft private",
                        }
                    )
                ),
            }
        }
    )
    ctx = build_block_context(wrapper, state)

    await wrapper.execute(ctx)

    envelope = captured["envelope"]
    assert envelope.inputs == {"summary": "safe draft", "title": "T"}
    assert json.loads(envelope.scoped_results["draft"]["output"]) == {
        "summary": "safe draft",
        "title": "T",
    }
    assert "draft private" not in envelope.model_dump_json()


def test_strict_missing_ref_fails_and_emits_audit_record() -> None:
    """Strict missing refs should fail the block and still leave an auditable record."""
    recorder = RecordingObserver()

    with pytest.raises(ContextResolutionError):
        build_block_context(DeclaredBlock(), WorkflowState(), observer=recorder)

    assert len(recorder.context_events) == 1
    event = recorder.context_events[0]
    assert event.node_id == "review"
    assert event.records[0].from_ref == "draft.summary"
    assert event.records[0].status in {"missing", "denied"}
    assert event.records[0].severity in {"warn", "error"}


def test_dev_mode_missing_ref_warns_without_granting_implicit_data() -> None:
    """Dev mode may warn, but it must not bypass declared-only access."""
    recorder = RecordingObserver()
    state = WorkflowState(
        shared_memory={"_resolved_inputs": {"summary": "legacy leak"}},
        metadata={
            "run_id": "context-governance-run",
            "workflow_name": "context_governance_integration",
        },
    )

    ctx = build_block_context(
        DeclaredBlock(),
        state,
        policy=ContextGovernancePolicy(mode="dev"),
        observer=recorder,
    )

    assert ctx.inputs == {}
    assert len(recorder.context_events) == 1
    record = recorder.context_events[0].records[0]
    assert record.status == "missing"
    assert record.severity == "warn"
    assert "legacy leak" not in recorder.context_events[0].model_dump_json()
