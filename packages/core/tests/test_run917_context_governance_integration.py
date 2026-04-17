"""Purple integration tests for RUN-917 context governance wiring."""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.block_io import build_block_context
from runsight_core.blocks.code import CodeBlock
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


class CapturingCodeBlock(CodeBlock):
    def __init__(self, block_id: str = "inspect") -> None:
        super().__init__(
            block_id,
            "def main(data):\n    return data\n",
        )
        self.captured_inputs: dict[str, Any] | None = None

    async def _run_subprocess(self, inputs: dict[str, Any]) -> tuple[bytes, bytes, int]:
        self.captured_inputs = inputs
        return json.dumps(inputs).encode(), b"", 0


class CapturingRunner:
    model_name = "gpt-4o"

    async def execute(self, instruction: str, content: Any, soul: Soul, **_: Any) -> Any:
        raise AssertionError("isolated wrapper test should stop at envelope capture")


def _soul() -> Soul:
    return Soul(
        id="analyst",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="Use only declared context.",
        model_name="gpt-4o",
    )


def _workflow_yaml_with_allowed_namespace_refs() -> str:
    return """\
version: "1.0"
id: run917
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
  name: run917
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
                output=json.dumps({"summary": "safe draft", "secret": "draft secret"})
            ),
            "workflow": BlockResult(
                output=json.dumps({"request": "external input", "secret": "workflow secret"})
            ),
            "unrelated": BlockResult(output="top secret result"),
        },
        shared_memory={
            "flags": {"safe": True, "secret": "flag sibling secret"},
            "_resolved_inputs": {"summary": "legacy leak"},
            "secret": "shared secret",
        },
        metadata={
            "run_id": "run_917",
            "workflow_name": "context_governance_integration",
            "runtime": {"branch": "codex/run-868-context-governance", "secret": "runtime secret"},
            "secret": "metadata secret",
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
        "branch": "codex/run-868-context-governance",
    }
    assert len(recorder.context_events) == 1
    event = recorder.context_events[0]
    assert event.node_id == "review"
    assert event.resolved_count == 4
    assert [record.namespace for record in event.records] == [
        "results",
        "results",
        "shared_memory",
        "metadata",
    ]
    event_json = event.model_dump_json()
    assert "draft secret" not in event_json
    assert "workflow secret" not in event_json
    assert "shared secret" not in event_json
    assert "metadata secret" not in event_json
    assert "legacy leak" not in event_json


def test_block_context_state_snapshot_is_scoped_to_declared_context() -> None:
    """Declared blocks must not get a full WorkflowState escape hatch."""
    workflow = parse_workflow_yaml(_workflow_yaml_with_allowed_namespace_refs())
    step = workflow._blocks["review"]
    assert isinstance(step, Step)

    ctx = build_block_context(step.block, _state(), step=step)

    assert ctx.state_snapshot is not None
    assert set(ctx.state_snapshot.results) == {"draft", "workflow"}
    assert json.loads(ctx.state_snapshot.results["draft"].output) == {"summary": "safe draft"}
    assert json.loads(ctx.state_snapshot.results["workflow"].output) == {
        "request": "external input"
    }
    assert ctx.state_snapshot.shared_memory == {"flags": {"safe": True}}
    assert ctx.state_snapshot.metadata == {
        "runtime": {"branch": "codex/run-868-context-governance"}
    }

    snapshot_json = ctx.state_snapshot.model_dump_json()
    assert "draft secret" not in snapshot_json
    assert "workflow secret" not in snapshot_json
    assert "top secret result" not in snapshot_json
    assert "shared secret" not in snapshot_json
    assert "metadata secret" not in snapshot_json
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
        "branch": "codex/run-868-context-governance",
    }
    assert set(envelope.scoped_results) == {"draft"}
    assert json.loads(envelope.scoped_results["draft"]["output"]) == {"summary": "safe draft"}
    assert envelope.scoped_shared_memory == {}
    assert envelope.scoped_metadata == {"runtime": {"branch": "codex/run-868-context-governance"}}
    assert len(envelope.context_audit) == 1
    envelope_json = envelope.model_dump_json()
    assert "draft secret" not in envelope_json
    assert "top secret result" not in envelope_json
    assert "shared secret" not in envelope_json
    assert "metadata secret" not in envelope_json
    assert "legacy leak" not in envelope_json

    worker_state = build_scoped_state(envelope)
    assert set(worker_state.results) == {"draft"}
    assert worker_state.shared_memory == {}
    assert worker_state.metadata == {"runtime": {"branch": "codex/run-868-context-governance"}}


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
                            "secret": "draft secret",
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
    assert "draft secret" not in envelope.model_dump_json()


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
        metadata={"run_id": "run_917", "workflow_name": "context_governance_integration"},
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


@pytest.mark.asyncio
async def test_codeblock_access_all_subprocess_shape_and_audit_are_explicit() -> None:
    """CodeBlock broad state is available only through explicit access: all."""
    block = CapturingCodeBlock()
    block.context_access = "all"
    block.declared_inputs = {}
    recorder = RecordingObserver()

    ctx = build_block_context(block, _state(), observer=recorder)
    await block.execute(ctx)

    assert set(block.captured_inputs or {}) == {"results", "metadata", "shared_memory"}
    assert block.captured_inputs["results"]["draft"] == json.dumps(
        {"summary": "safe draft", "secret": "draft secret"}
    )
    assert block.captured_inputs["shared_memory"]["secret"] == "shared secret"
    assert block.captured_inputs["metadata"]["secret"] == "metadata secret"
    assert len(recorder.context_events) == 1
    event = recorder.context_events[0]
    assert event.access == "all"
    assert event.records[0].status == "all_access"
    assert event.records[0].reason == "explicit all access"
