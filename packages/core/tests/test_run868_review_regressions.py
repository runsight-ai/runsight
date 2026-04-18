"""Regression tests for accepted RUN-868 review findings."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from runsight_core.block_io import BlockContext, _resolve_declared_inputs, build_block_context
from runsight_core.blocks.base import BaseBlock
from runsight_core.blocks.code import CodeBlock
from runsight_core.context_governance import (
    ContextDeclaration,
    ContextGovernancePolicy,
    ContextResolutionAuditError,
    ContextResolutionError,
    ContextResolver,
)
from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope
from runsight_core.isolation.harness import _serialize_scoped_results
from runsight_core.isolation.wrapper import IsolatedBlockWrapper
from runsight_core.observer import CompositeObserver
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


class _RecordingObserver:
    def __init__(self) -> None:
        self.events: list[Any] = []

    def on_context_resolution(self, event: Any) -> None:
        self.events.append(event)


class _MissingContextObserver:
    pass


class _DummyIsolatedInnerBlock(BaseBlock):
    async def execute(self, ctx: BlockContext) -> Any:
        raise AssertionError("inner block should execute through the isolation harness")


class _CapturingIsolatedWrapper(IsolatedBlockWrapper):
    def __init__(self) -> None:
        super().__init__("isolated", _DummyIsolatedInnerBlock("inner"))
        self.captured_envelope: ContextEnvelope | None = None

    async def _run_in_subprocess(self, envelope: ContextEnvelope) -> ResultEnvelope:
        self.captured_envelope = envelope
        return ResultEnvelope(
            block_id="isolated",
            output="ok",
            exit_handle="",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=None,
            error_type=None,
        )


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


def test_context_audit_redacts_secret_json_key_under_neutral_names() -> None:
    """Audit previews must redact secret-looking object keys in neutral refs."""
    secret = "plain-secret-value"
    scoped = _resolver().resolve(
        declaration=_declaration({"config": "metadata.config"}),
        state=WorkflowState(metadata={"config": {"api_key": secret}}),
    )

    record = scoped.audit_event.records[0]
    assert scoped.inputs == {"config": {"api_key": secret}}
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


def test_malformed_context_ref_emits_audit_before_error() -> None:
    """Parser failures must still emit context-audit diagnostics."""
    block = SimpleNamespace(block_id="review_block")
    step = Step(block=block, declared_inputs={"bad": "metadata."})
    observer = _RecordingObserver()

    with pytest.raises(ContextResolutionAuditError):
        build_block_context(block, WorkflowState(), step=step, observer=observer)

    assert len(observer.events) == 1
    event = observer.events[0]
    assert event.records[0].from_ref == "metadata."
    assert event.records[0].status == "missing"
    assert event.records[0].severity == "error"
    assert "context ref" in (event.records[0].reason or "")


def test_dev_mode_synthesize_missing_input_does_not_keyerror() -> None:
    """DEV-mode missing synthesize inputs should warn, not crash with KeyError."""
    ctx = build_block_context(
        SimpleNamespace(block_id="synth", input_block_ids=["missing"]),
        WorkflowState(),
        policy=ContextGovernancePolicy(mode="dev"),
    )

    assert ctx.inputs == {}
    assert ctx.context == ""


def test_dev_mode_gate_missing_eval_key_does_not_keyerror() -> None:
    """DEV-mode missing gate content should warn, not crash with KeyError."""
    ctx = build_block_context(
        SimpleNamespace(block_id="gate", eval_key="missing"),
        WorkflowState(),
        policy=ContextGovernancePolicy(mode="dev"),
    )

    assert ctx.inputs == {}
    assert ctx.context == ""


@pytest.mark.asyncio
async def test_isolated_wrapper_preserves_ctx_inputs_when_state_snapshot_is_missing() -> None:
    """Legacy direct isolated execution still passes caller-provided inputs."""
    wrapper = _CapturingIsolatedWrapper()
    wrapper.context_access = "declared"
    ctx = BlockContext(
        block_id="isolated",
        instruction="",
        context=None,
        inputs={"x": "kept"},
        state_snapshot=None,
    )

    await wrapper.execute(ctx)

    assert wrapper.captured_envelope is not None
    assert wrapper.captured_envelope.inputs == {"x": "kept"}


def test_harness_scoped_result_serializer_accepts_raw_result_values() -> None:
    """Envelope helpers must tolerate raw values in state.results."""
    assert _serialize_scoped_results({"raw": {"x": 1}}) == {
        "raw": {"output": {"x": 1}},
    }


def test_composite_observer_skips_children_without_context_resolution(caplog) -> None:
    """Audit events should not produce warnings for observers without this hook."""
    event = (
        _resolver()
        .resolve(
            declaration=_declaration({"value": "metadata.config.value"}),
            state=WorkflowState(metadata={"config": {"value": "ordinary-status"}}),
        )
        .audit_event
    )
    recorder = _RecordingObserver()
    composite = CompositeObserver(_MissingContextObserver(), recorder)

    with caplog.at_level(logging.WARNING):
        composite.on_context_resolution(event)

    assert recorder.events == [event]
    assert "on_context_resolution failed" not in caplog.text


def test_resolve_declared_inputs_raises_for_invalid_field_path() -> None:
    """The stale helper must not silently omit invalid declared inputs."""
    step = Step(
        block=SimpleNamespace(block_id="review_block"),
        declared_inputs={"summary": "draft.missing"},
    )
    state = WorkflowState(results={"draft": BlockResult(output=json.dumps({"summary": "S"}))})

    with pytest.raises((ValueError, ContextResolutionError), match="draft|missing"):
        _resolve_declared_inputs(step, state)
