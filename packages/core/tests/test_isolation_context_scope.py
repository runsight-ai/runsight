"""
RED tests for RUN-911: scope isolation envelopes and worker reconstruction.

RUN-911 extends Epic C context governance across the subprocess boundary. The
isolation envelope must carry only resolver-scoped context for declared access,
and worker reconstruction must not re-expand broad WorkflowState data.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.block_io import BlockContext
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.context_governance import ContextAuditEventV1
from runsight_core.isolation.envelope import ContextEnvelope, PromptEnvelope, SoulEnvelope
from runsight_core.isolation.worker_support import build_scoped_state
from runsight_core.isolation.wrapper import IsolatedBlockWrapper
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState


class CapturingRunner:
    """Minimal async runner that records content sent by worker-side blocks."""

    model_name = "gpt-4o"

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any, Soul]] = []

    async def execute(
        self, instruction: str, content: Any, soul: Soul, **_: Any
    ) -> ExecutionResult:
        self.calls.append((instruction, content, soul))
        return ExecutionResult(
            task_id="task",
            soul_id=soul.id,
            output="PASS: scoped",
            cost_usd=0.0,
            total_tokens=0,
        )


def _soul() -> Soul:
    return Soul(
        id="analyst",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="Analyze only declared context.",
        model_name="gpt-4o",
    )


def _soul_envelope() -> SoulEnvelope:
    return SoulEnvelope(
        id="analyst",
        name="Analyst",
        role="Analyst",
        system_prompt="Analyze only declared context.",
        model_name="gpt-4o",
        max_tool_iterations=5,
    )


def _context_envelope(**overrides: Any) -> ContextEnvelope:
    defaults = dict(
        block_id="isolated",
        block_type="linear",
        block_config={},
        soul=_soul_envelope(),
        tools=[],
        prompt=PromptEnvelope(id="isolated_task", instruction="", context={}),
        inputs={},
        scoped_results={},
        scoped_shared_memory={},
        scoped_metadata={},
        access="declared",
        context_audit=[],
        conversation_history=[],
        timeout_seconds=30,
        max_output_bytes=1_000_000,
    )
    defaults.update(overrides)
    return ContextEnvelope(**defaults)


def test_context_envelope_carries_access_scoped_metadata_and_audit() -> None:
    """RUN-911 envelope contract includes access, scoped metadata, and audit events."""
    audit = ContextAuditEventV1(
        run_id="run_911",
        workflow_name="isolation_scope",
        node_id="isolated",
        block_type="linear",
        access="declared",
        mode="strict",
        records=[],
        resolved_count=0,
        denied_count=0,
        warning_count=0,
        emitted_at="2026-04-16T00:00:00+00:00",
    )

    envelope = _context_envelope(
        scoped_metadata={"run": {"safe": True}},
        access="declared",
        context_audit=[audit],
    )

    assert envelope.access == "declared"
    assert envelope.scoped_metadata == {"run": {"safe": True}}
    assert envelope.context_audit == [audit]
    assert "context_audit" in envelope.model_dump()


@pytest.mark.asyncio
async def test_isolated_wrapper_serializes_only_resolver_scoped_values() -> None:
    """Declared isolated execution must omit unrelated state from the envelope."""
    soul = _soul()
    inner = LinearBlock("isolated", soul=soul, runner=CapturingRunner())
    inner.context_access = "declared"
    inner.declared_inputs = {"summary": "a.summary"}
    wrapper = IsolatedBlockWrapper("isolated", inner)
    wrapper.context_access = "declared"
    wrapper.declared_inputs = {"summary": "a.summary"}
    captured: dict[str, ContextEnvelope] = {}

    async def _capture(envelope: ContextEnvelope):
        from runsight_core.isolation.envelope import ResultEnvelope

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
    state = WorkflowState(
        results={
            "a": BlockResult(output=json.dumps({"summary": "safe", "secret": "sibling leak"})),
            "secret": BlockResult(output="top secret"),
        },
        shared_memory={
            "allowed": {"value": "safe"},
            "secret": "shared secret",
            "_resolved_inputs": {"summary": "legacy leak"},
        },
        metadata={"safe": "visible only if declared", "secret": "metadata leak"},
    )
    ctx = BlockContext(
        block_id="isolated",
        instruction="",
        context=None,
        inputs={"summary": "safe"},
        soul=soul,
        state_snapshot=state,
    )

    await wrapper.execute(ctx)

    envelope = captured["envelope"]
    assert envelope.access == "declared"
    assert envelope.inputs == {"summary": "safe"}
    assert set(envelope.scoped_results) == {"a"}
    assert json.loads(envelope.scoped_results["a"]["output"]) == {"summary": "safe"}
    assert "secret" not in envelope.scoped_results
    assert "sibling leak" not in envelope.model_dump_json()
    assert "shared secret" not in envelope.model_dump_json()
    assert "metadata leak" not in envelope.model_dump_json()
    assert "legacy leak" not in envelope.model_dump_json()


def test_build_scoped_state_reconstructs_only_envelope_scoped_values() -> None:
    """Worker state reconstruction is limited to envelope-scoped data."""
    envelope = _context_envelope(
        scoped_results={"a": {"output": json.dumps({"summary": "safe"})}},
        scoped_shared_memory={"allowed": {"value": "safe"}},
        scoped_metadata={"run": {"priority": "high"}},
        inputs={"summary": "safe"},
    )

    state = build_scoped_state(envelope)

    assert set(state.results) == {"a"}
    assert json.loads(state.results["a"].output) == {"summary": "safe"}
    assert state.shared_memory == {"allowed": {"value": "safe"}}
    assert state.metadata == {"run": {"priority": "high"}}
    assert "secret" not in state.results
    assert "_resolved_inputs" not in state.shared_memory


def test_build_scoped_state_preserves_declared_field_path_without_sibling_fields() -> None:
    """Scoped results keep enough structure for field paths without sibling leakage."""
    envelope = _context_envelope(
        scoped_results={"a": {"output": json.dumps({"outer": {"summary": "safe"}})}},
        inputs={"summary": "safe"},
    )

    state = build_scoped_state(envelope)

    payload = json.loads(state.results["a"].output)
    assert payload == {"outer": {"summary": "safe"}}
    assert "secret" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_worker_reconstructed_gate_uses_internal_eval_key_without_unrelated_state() -> None:
    """Worker-side GateBlock can evaluate scoped eval_key without unrelated state."""
    from runsight_core.block_io import build_block_context
    from runsight_core.isolation import worker_support

    envelope = _context_envelope(
        block_id="gate",
        block_type="gate",
        block_config={"eval_key": "draft"},
        inputs={"content": "safe draft"},
        scoped_results={"draft": {"output": "safe draft"}},
        scoped_shared_memory={"unrelated": "should not be used"},
        scoped_metadata={"run": {"safe": True}},
    )
    soul = worker_support.reconstruct_soul(envelope.soul)
    runner = CapturingRunner()
    block = worker_support._create_block(envelope, soul, runner)
    state = worker_support.build_scoped_state(envelope)

    ctx = build_block_context(block, state)
    output = await block.execute(ctx)

    assert isinstance(block, GateBlock)
    assert ctx.inputs == {"content": "safe draft"}
    assert ctx.context == "safe draft"
    assert "unrelated" not in json.dumps(ctx.inputs)
    assert runner.calls[0][1] == "safe draft"
    assert output.exit_handle == "pass"


def test_worker_reconstruction_cannot_expand_broad_context_from_envelope_state() -> None:
    """Even if envelope state has scoped values, build context must not broaden them."""
    from runsight_core.block_io import build_block_context
    from runsight_core.isolation import worker_support

    envelope = _context_envelope(
        block_id="isolated",
        block_type="linear",
        inputs={},
        scoped_results={"a": {"output": json.dumps({"summary": "safe"})}},
        scoped_shared_memory={"allowed": "safe"},
        scoped_metadata={"run": {"priority": "high"}},
    )
    soul = worker_support.reconstruct_soul(envelope.soul)
    runner = CapturingRunner()
    block = worker_support._create_block(envelope, soul, runner)
    state = worker_support.build_scoped_state(envelope)

    ctx = build_block_context(block, state)

    assert ctx.inputs == {}
    assert ctx.context is None
    assert "a" not in ctx.inputs
    assert "allowed" not in ctx.inputs
    assert "run" not in ctx.inputs
