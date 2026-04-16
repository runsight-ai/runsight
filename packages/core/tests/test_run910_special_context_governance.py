"""
RED tests for RUN-910: govern special block context declarations.

RUN-910 brings implicit block reads into the same ContextDeclaration contract as
user-declared inputs. These tests stay at the contract/build-context boundary:
no observer publication, no CodeBlock all-access runtime behavior, and no
isolation envelope scoping.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from runsight_core.block_io import BlockOutput, build_block_context
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.loop import LoopBlock
from runsight_core.blocks.synthesize import SynthesizeBlock
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.context_governance import (
    ContextDeclaration,
    ContextGovernancePolicy,
    ContextResolver,
)
from runsight_core.primitives import Soul, Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext


@pytest.fixture
def analyst_soul() -> Soul:
    return Soul(
        id="analyst",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="Analyze carefully.",
        model_name="gpt-4o",
    )


@pytest.fixture
def fake_runner() -> SimpleNamespace:
    return SimpleNamespace(model_name="gpt-4o")


def _state(**kwargs: Any) -> WorkflowState:
    return WorkflowState(**kwargs)


def _resolver() -> ContextResolver:
    return ContextResolver(
        policy=ContextGovernancePolicy(),
        run_id="run_910",
        workflow_name="special_context_governance",
    )


def _collect_context_declaration(block: Any, *, step: Step | None = None) -> ContextDeclaration:
    from runsight_core import context_governance

    return context_governance.collect_context_declaration(block, step=step)


def test_collect_gate_declaration_resolves_internal_content_with_internal_audit(
    analyst_soul: Soul,
    fake_runner: SimpleNamespace,
) -> None:
    """GateBlock eval_key is represented as internal content input."""
    block = GateBlock(
        block_id="quality_gate",
        gate_soul=analyst_soul,
        eval_key="draft",
        runner=fake_runner,
    )
    state = _state(results={"draft": BlockResult(output="draft text")})

    declaration = _collect_context_declaration(block)
    scoped = _resolver().resolve(declaration=declaration, state=state)

    assert declaration == ContextDeclaration(
        block_id="quality_gate",
        block_type="gate",
        access="declared",
        declared_inputs={},
        internal_inputs={"content": "draft"},
    )
    assert scoped.inputs == {"content": "draft text"}
    assert len(scoped.audit_event.records) == 1
    assert scoped.audit_event.records[0].input_name == "content"
    assert scoped.audit_event.records[0].from_ref == "draft"
    assert scoped.audit_event.records[0].internal is True


def test_gate_build_block_context_uses_internal_declaration_without_legacy_fallback(
    analyst_soul: Soul,
    fake_runner: SimpleNamespace,
) -> None:
    """GateBlock context comes from governed internal input, not broad fallbacks."""
    block = GateBlock(
        block_id="quality_gate",
        gate_soul=analyst_soul,
        eval_key="draft",
        runner=fake_runner,
    )
    state = _state(
        results={"draft": BlockResult(output="draft text")},
        shared_memory={
            "_resolved_inputs": {
                "content": "legacy content leak",
                "context": "legacy context leak",
            }
        },
    )

    ctx = build_block_context(block, state)

    assert ctx.inputs == {"content": "draft text"}
    assert ctx.context == "draft text"
    assert "legacy content leak" not in json.dumps(ctx.inputs)
    assert "legacy context leak" not in (ctx.context or "")


def test_synthesize_build_context_scopes_only_declared_internal_inputs(
    analyst_soul: Soul,
    fake_runner: SimpleNamespace,
) -> None:
    """SynthesizeBlock exposes only its input_block_ids, not unrelated state."""
    block = SynthesizeBlock("combine", ["a", "b"], analyst_soul, fake_runner)
    state = _state(
        results={
            "a": BlockResult(output="alpha"),
            "b": BlockResult(output="beta"),
            "c": BlockResult(output="charlie leak"),
        },
        shared_memory={"_resolved_inputs": {"context": "legacy leak", "c": "shared leak"}},
    )

    ctx = build_block_context(block, state)

    assert ctx.inputs == {"a": "alpha", "b": "beta"}
    assert "alpha" in (ctx.context or "")
    assert "beta" in (ctx.context or "")
    assert "charlie leak" not in json.dumps(ctx.inputs)
    assert "charlie leak" not in (ctx.context or "")
    assert "legacy leak" not in json.dumps(ctx.inputs)
    assert "shared leak" not in (ctx.context or "")


def test_dispatch_without_declared_inputs_ignores_legacy_resolved_inputs(
    analyst_soul: Soul,
    fake_runner: SimpleNamespace,
) -> None:
    """DispatchBlock no-input path must not read broad _resolved_inputs fallback."""
    branch = DispatchBranch(
        exit_id="review",
        label="Review",
        soul=analyst_soul,
        task_instruction="Review the declared context only.",
    )
    block = DispatchBlock("fanout", [branch], fake_runner)
    state = _state(
        shared_memory={
            "_resolved_inputs": {
                "context": "legacy context leak",
                "instruction": "legacy instruction leak",
                "secret": "legacy input leak",
            }
        }
    )

    ctx = build_block_context(block, state)

    assert ctx.inputs == {}
    assert ctx.context is None
    assert "legacy input leak" not in json.dumps(ctx.inputs)
    assert "legacy context leak" not in (ctx.context or "")
    assert "legacy instruction leak" not in ctx.instruction


def test_linear_without_declared_inputs_still_ignores_legacy_resolved_inputs(
    analyst_soul: Soul,
    fake_runner: SimpleNamespace,
) -> None:
    """LinearBlock remains protected from broad _resolved_inputs after special cleanup."""
    block = LinearBlock("linear", analyst_soul, fake_runner)
    state = _state(
        shared_memory={
            "_resolved_inputs": {
                "context": "legacy context leak",
                "instruction": "legacy instruction leak",
                "secret": "legacy input leak",
            }
        }
    )

    ctx = build_block_context(block, state)

    assert ctx.inputs == {}
    assert ctx.context is None
    assert "legacy input leak" not in json.dumps(ctx.inputs)
    assert "legacy context leak" not in (ctx.context or "")
    assert "legacy instruction leak" not in ctx.instruction


def test_workflow_and_loop_system_keys_are_injected_after_governance_not_audit_rows() -> None:
    """System execution keys are post-governance inputs, not declared/internal audit records."""

    class CaptureBlock:
        block_id = "capture"
        context_access = "declared"
        declared_inputs = {"payload": "workflow.payload"}
        received_inputs: dict[str, Any] | None = None

        async def execute(self, ctx: Any) -> BlockOutput:
            self.received_inputs = dict(ctx.inputs)
            return BlockOutput(output="captured")

    block = CaptureBlock()
    step = Step(block=block, declared_inputs={"payload": "workflow.payload"})
    state = _state(results={"workflow": BlockResult(output=json.dumps({"payload": "hello"}))})
    execution_context = BlockExecutionContext(
        workflow_name="parent",
        blocks={"capture": block},
        call_stack=["parent"],
        workflow_registry={"child": object()},
        observer=object(),
    )

    declaration = ContextDeclaration(
        block_id="capture",
        block_type="workflow",
        access="declared",
        declared_inputs=step.declared_inputs,
        internal_inputs={},
    )
    scoped = _resolver().resolve(declaration=declaration, state=state)

    assert [record.input_name for record in scoped.audit_event.records] == ["payload"]
    assert {"call_stack", "workflow_registry", "observer", "blocks", "ctx"}.isdisjoint(
        {record.input_name for record in scoped.audit_event.records}
    )

    workflow_ctx = build_block_context(block, state, step=step)
    workflow_inputs = {
        **workflow_ctx.inputs,
        "call_stack": execution_context.call_stack + [execution_context.workflow_name],
        "workflow_registry": execution_context.workflow_registry,
        "observer": execution_context.observer,
    }
    assert workflow_inputs["payload"] == "hello"
    assert workflow_inputs["call_stack"] == ["parent", "parent"]
    assert "call_stack" not in scoped.inputs
    assert "workflow_registry" not in scoped.inputs
    assert "observer" not in scoped.inputs

    loop_ctx = build_block_context(block, state, step=step)
    loop_inputs = {
        **loop_ctx.inputs,
        "blocks": execution_context.blocks,
        "ctx": execution_context,
    }
    assert loop_inputs["payload"] == "hello"
    assert loop_inputs["blocks"] == {"capture": block}
    assert loop_inputs["ctx"] is execution_context
    assert "blocks" not in scoped.inputs
    assert "ctx" not in scoped.inputs


def test_workflow_and_loop_build_context_do_not_audit_system_keys() -> None:
    """Real special block declarations exclude workflow/loop system execution keys."""
    child_workflow = SimpleNamespace(name="child")
    workflow_block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child_workflow,
        inputs={"payload": "results.workflow.payload"},
        outputs={},
    )
    loop_block = LoopBlock("iterate", ["writer"], max_rounds=1)
    state = _state(results={"workflow": BlockResult(output=json.dumps({"payload": "hello"}))})

    workflow_declaration = _collect_context_declaration(workflow_block)
    loop_declaration = _collect_context_declaration(loop_block)
    workflow_scoped = _resolver().resolve(declaration=workflow_declaration, state=state)
    loop_scoped = _resolver().resolve(declaration=loop_declaration, state=state)

    workflow_record_names = {record.input_name for record in workflow_scoped.audit_event.records}
    loop_record_names = {record.input_name for record in loop_scoped.audit_event.records}

    assert "payload" in workflow_scoped.inputs
    assert {"call_stack", "workflow_registry", "observer"}.isdisjoint(workflow_record_names)
    assert {"blocks", "ctx"}.isdisjoint(loop_record_names)
    assert loop_scoped.inputs == {}


def test_user_declared_input_name_collision_with_internal_input_raises_clear_error(
    analyst_soul: Soul,
    fake_runner: SimpleNamespace,
) -> None:
    """User inputs must not collide with internal special-block input names."""
    block = GateBlock(
        block_id="quality_gate",
        gate_soul=analyst_soul,
        eval_key="draft",
        runner=fake_runner,
    )
    step = Step(block=block, declared_inputs={"content": "workflow.content"})

    with pytest.raises(ValueError, match=r"quality_gate.*content.*internal"):
        _collect_context_declaration(block, step=step)
