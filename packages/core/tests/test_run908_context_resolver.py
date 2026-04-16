"""
RED tests for RUN-908: central ContextResolver enforcement path.

These tests pin the declared-only context access contract introduced by Epic C:
- resolver contracts live in runsight_core.context_governance
- strict mode resolves only declared refs and raises governance errors
- dev mode may warn, but never grants undeclared data
- build_block_context uses the resolver on the generic declared path
- legacy shared_memory["_resolved_inputs"] does not leak into declared blocks
"""

from __future__ import annotations

import json
from importlib import import_module
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from runsight_core import block_io
from runsight_core.block_io import build_block_context
from runsight_core.blocks.linear import LinearBlock
from runsight_core.primitives import Soul, Step
from runsight_core.state import BlockResult, WorkflowState


class _FakeDeclaredBlock:
    """Minimal block that exercises build_block_context's generic path."""

    block_id = "summarize"
    access = "declared"
    soul = None
    runner = None


def _linear_block(block_id: str = "summarize") -> LinearBlock:
    soul = Soul(
        id="analyst",
        kind="soul",
        name="Analyst",
        role="Analyst",
        system_prompt="",
        model_name="gpt-4o",
    )
    runner = SimpleNamespace(model_name="gpt-4o")
    return LinearBlock(block_id=block_id, soul=soul, runner=runner)


def _cg():
    return import_module("runsight_core.context_governance")


def _state(
    *,
    results: dict[str, BlockResult] | None = None,
    shared_memory: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkflowState:
    return WorkflowState(
        results=results or {},
        shared_memory=shared_memory or {},
        metadata=metadata or {},
    )


@pytest.fixture
def cheap_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep build_block_context tests focused on context resolution."""

    def _fit_to_budget(request: Any, counter: Any) -> Any:
        return SimpleNamespace(
            instruction=request.instruction,
            context=request.context,
            messages=list(request.conversation_history),
        )

    monkeypatch.setattr(block_io, "fit_to_budget", _fit_to_budget)


def _resolver(*, mode: str = "strict") -> Any:
    cg = _cg()
    return cg.ContextResolver(
        policy=cg.ContextGovernancePolicy(mode=mode),
        run_id="run_908",
        workflow_name="resolver_contract",
    )


def _declaration(
    declared_inputs: dict[str, str] | None = None,
    *,
    access: str = "declared",
    internal_inputs: dict[str, str] | None = None,
    block_id: str = "summarize",
    block_type: str = "linear",
) -> Any:
    cg = _cg()
    payload: dict[str, Any] = {
        "block_id": block_id,
        "block_type": block_type,
        "access": access,
        "declared_inputs": declared_inputs or {},
    }
    if internal_inputs is not None:
        payload["internal_inputs"] = internal_inputs
    return cg.ContextDeclaration(**payload)


def test_context_governance_exports_resolver_contract_symbols() -> None:
    """RUN-908 adds the central resolver contract to the governance module."""
    cg = _cg()

    for name in {
        "ContextDeclaration",
        "ScopedContextData",
        "ContextResolver",
        "ContextResolutionError",
        "ContextReadDeniedError",
    }:
        assert hasattr(cg, name), f"missing RUN-908 context resolver symbol: {name}"


def test_context_declaration_defaults_and_rejects_invalid_access() -> None:
    """ContextDeclaration is a block-level declaration with empty internal inputs."""
    cg = _cg()

    declaration = cg.ContextDeclaration(
        block_id="summarize",
        block_type="linear",
        access="declared",
        declared_inputs={"summary": "draft.summary"},
    )

    assert declaration.block_id == "summarize"
    assert declaration.block_type == "linear"
    assert declaration.access == "declared"
    assert declaration.declared_inputs == {"summary": "draft.summary"}
    assert declaration.internal_inputs == {}

    with pytest.raises(ValidationError):
        cg.ContextDeclaration(
            block_id="summarize",
            block_type="linear",
            access="legacy",
            declared_inputs={},
        )


def test_context_resolver_resolves_declared_field_path() -> None:
    """A declared input resolves a field from a prior block result."""
    scoped = _resolver().resolve(
        declaration=_declaration({"summary": "draft.summary"}),
        state=_state(
            results={
                "draft": BlockResult(
                    output=json.dumps({"summary": "short version", "other": "hidden"})
                )
            }
        ),
    )

    assert scoped.inputs == {"summary": "short version"}
    assert scoped.audit_event.resolved_count == 1
    assert scoped.audit_event.denied_count == 0
    assert scoped.audit_event.records[0].from_ref == "draft.summary"
    assert scoped.audit_event.records[0].status == "resolved"


def test_context_resolver_missing_declared_ref_raises_resolution_error() -> None:
    """Strict mode treats a missing declared ref as a governance resolution error."""
    cg = _cg()

    with pytest.raises(cg.ContextResolutionError, match="draft.summary"):
        _resolver().resolve(
            declaration=_declaration({"summary": "draft.summary"}),
            state=_state(results={}),
        )


def test_context_resolver_no_declarations_returns_empty_inputs() -> None:
    """Declared access with no input declarations grants no context."""
    scoped = _resolver().resolve(
        declaration=_declaration(),
        state=_state(results={"draft": BlockResult(output='{"summary": "hidden"}')}),
    )

    assert scoped.inputs == {}
    assert scoped.audit_event.resolved_count == 0
    assert scoped.audit_event.records == []


def test_context_resolver_dev_mode_warns_without_granting_missing_data() -> None:
    """Dev mode may report warnings, but it must not insert undeclared fallback data."""
    scoped = _resolver(mode="dev").resolve(
        declaration=_declaration({"summary": "draft.summary"}),
        state=_state(
            results={},
            shared_memory={"_resolved_inputs": {"summary": "legacy leak"}},
        ),
    )

    assert scoped.inputs == {}
    assert scoped.audit_event.warning_count == 1
    assert scoped.audit_event.denied_count == 0
    assert scoped.audit_event.records[0].status == "missing"
    assert scoped.audit_event.records[0].severity == "warn"
    assert "legacy leak" not in scoped.model_dump_json()


def test_context_resolver_full_block_ref_preserves_raw_non_json_output() -> None:
    """A full-block ref returns raw output even when that output is not JSON."""
    scoped = _resolver().resolve(
        declaration=_declaration({"raw_draft": "draft"}),
        state=_state(results={"draft": BlockResult(output="plain text draft")}),
    )

    assert scoped.inputs == {"raw_draft": "plain text draft"}
    assert scoped.audit_event.records[0].value_type == "str"


def test_context_resolver_field_path_into_non_json_output_fails_clearly() -> None:
    """Field refs into non-JSON block output fail with a resolver error."""
    cg = _cg()

    with pytest.raises(cg.ContextResolutionError, match="non-JSON.*draft.summary"):
        _resolver().resolve(
            declaration=_declaration({"summary": "draft.summary"}),
            state=_state(results={"draft": BlockResult(output="plain text draft")}),
        )


def test_context_resolver_audit_preview_is_bounded_but_value_remains_full() -> None:
    """Audit previews stay bounded while resolved inputs keep the full value."""
    large_value = {
        "items": ["x" * 1000 for _ in range(8)],
        "nested": {"keep": "full object"},
    }

    scoped = _resolver().resolve(
        declaration=_declaration({"payload": "draft.payload"}),
        state=_state(results={"draft": BlockResult(output=json.dumps({"payload": large_value}))}),
    )

    assert scoped.inputs["payload"] == large_value
    preview = scoped.audit_event.records[0].preview
    assert preview is not None
    assert len(preview) <= 200
    assert "x" * 500 not in preview


def test_scoped_context_data_is_least_privilege_for_declared_result_ref() -> None:
    """ScopedContextData exposes only the declared result slice, not full state."""
    scoped = _resolver().resolve(
        declaration=_declaration({"summary": "draft.summary"}),
        state=_state(
            results={
                "draft": BlockResult(
                    output=json.dumps(
                        {
                            "summary": "short version",
                            "secret": "must stay hidden",
                        }
                    )
                ),
                "private_notes": BlockResult(output="hidden block"),
            },
            shared_memory={"secret": "hidden memory"},
            metadata={"secret": "hidden metadata"},
        ),
    )

    assert scoped.inputs == {"summary": "short version"}
    assert isinstance(scoped.scoped_results["draft"], BlockResult)
    assert json.loads(scoped.scoped_results["draft"].output) == {"summary": "short version"}
    assert scoped.scoped_shared_memory == {}
    assert scoped.scoped_metadata == {}
    assert scoped.state_snapshot is None
    assert scoped.audit_event.resolved_count == 1
    assert "must stay hidden" not in scoped.model_dump_json()
    assert "hidden block" not in scoped.model_dump_json()
    assert "hidden memory" not in scoped.model_dump_json()
    assert "hidden metadata" not in scoped.model_dump_json()


def test_context_resolver_supports_declared_shared_memory_and_metadata_refs() -> None:
    """Explicit non-results namespaces populate matching scoped context buckets."""
    scoped = _resolver().resolve(
        declaration=_declaration(
            {
                "customer_id": "shared_memory.customer.id",
                "priority": "metadata.run.priority",
            }
        ),
        state=_state(
            shared_memory={
                "customer": {
                    "id": "cust_123",
                    "token": "must stay hidden",
                }
            },
            metadata={
                "run": {
                    "priority": "high",
                    "api_key": "must stay hidden",
                }
            },
        ),
    )

    assert scoped.inputs == {"customer_id": "cust_123", "priority": "high"}
    assert scoped.scoped_results == {}
    assert scoped.scoped_shared_memory == {"customer": {"id": "cust_123"}}
    assert scoped.scoped_metadata == {"run": {"priority": "high"}}
    assert "must stay hidden" not in scoped.model_dump_json()


def test_build_block_context_resolves_declared_inputs_through_resolver(cheap_budget: None) -> None:
    """build_block_context supports namespace-aware refs through the central resolver."""
    block = _FakeDeclaredBlock()
    step = Step(block=block, declared_inputs={"summary": "results.draft.summary"})

    ctx = build_block_context(
        block,
        _state(results={"draft": BlockResult(output=json.dumps({"summary": "ready"}))}),
        step=step,
    )

    assert ctx.inputs == {"summary": "ready"}


def test_build_block_context_resolves_declared_workflow_input_through_resolver(
    cheap_budget: None,
) -> None:
    """Workflow-seeded input is available only through an explicit declaration."""
    block = _FakeDeclaredBlock()
    step = Step(block=block, declared_inputs={"reason": "workflow.reason"})

    ctx = build_block_context(
        block,
        _state(results={"workflow": BlockResult(output=json.dumps({"reason": "audit"}))}),
        step=step,
    )

    assert ctx.inputs == {"reason": "audit"}


def test_build_block_context_linear_block_rejects_arbitrary_non_json_field_path(
    cheap_budget: None,
) -> None:
    """LinearBlock must not rewrite arbitrary non-JSON field paths to raw output."""
    cg = _cg()
    block = _linear_block()
    step = Step(block=block, declared_inputs={"summary": "draft.subfield"})
    state = _state(results={"draft": BlockResult(output="plain text draft")})

    with pytest.raises(cg.ContextResolutionError, match="draft.subfield"):
        build_block_context(block, state, step=step)


def test_build_block_context_linear_block_preserves_result_and_output_aliases(
    cheap_budget: None,
) -> None:
    """.result and .output remain explicit aliases for whole non-JSON output."""
    block = _linear_block()
    step = Step(
        block=block,
        declared_inputs={
            "from_result": "draft.result",
            "from_output": "draft.output",
        },
    )
    state = _state(results={"draft": BlockResult(output="plain text draft")})

    ctx = build_block_context(block, state, step=step)

    assert ctx.inputs == {
        "from_result": "plain text draft",
        "from_output": "plain text draft",
    }


def test_build_block_context_missing_declared_input_raises_governance_error(
    cheap_budget: None,
) -> None:
    """Strict build context failures use ContextResolutionError, not legacy ValueError."""
    cg = _cg()
    block = _FakeDeclaredBlock()
    step = Step(block=block, declared_inputs={"summary": "draft.summary"})

    with pytest.raises(cg.ContextResolutionError, match="draft.summary"):
        build_block_context(block, _state(results={}), step=step)


def test_build_block_context_declared_without_inputs_ignores_legacy_resolved_inputs(
    cheap_budget: None,
) -> None:
    """Legacy _resolved_inputs must not backfill declared blocks with no declarations."""
    block = _FakeDeclaredBlock()
    step = Step(block=block, declared_inputs={})
    state = _state(
        results={"draft": BlockResult(output=json.dumps({"summary": "hidden"}))},
        shared_memory={"_resolved_inputs": {"summary": "legacy leak"}},
    )

    ctx = build_block_context(block, state, step=step)

    assert ctx.inputs == {}


def test_build_block_context_declared_no_step_ignores_legacy_resolved_inputs(
    cheap_budget: None,
) -> None:
    """Parsed no-input declared blocks have no Step and still ignore legacy inputs."""
    block = _FakeDeclaredBlock()
    state = _state(
        results={"draft": BlockResult(output=json.dumps({"summary": "hidden"}))},
        shared_memory={"_resolved_inputs": {"summary": "legacy leak"}},
    )

    ctx = build_block_context(block, state, step=None)

    assert ctx.inputs == {}


def test_build_block_context_declared_no_step_does_not_expose_workflow_result_context(
    cheap_budget: None,
) -> None:
    """No-input declared blocks must not receive workflow-seeded input as context."""
    block = _FakeDeclaredBlock()
    state = _state(
        results={
            "workflow": BlockResult(
                output=json.dumps(
                    {
                        "reason": "workflow context leak",
                        "prompt": "undeclared workflow input",
                    }
                )
            )
        }
    )

    ctx = build_block_context(block, state, step=None)

    assert ctx.inputs == {}
    assert ctx.context is None
    assert "workflow context leak" not in (ctx.context or "")
    assert "undeclared workflow input" not in (ctx.context or "")


def test_build_block_context_declared_no_step_does_not_expose_legacy_instruction_or_context(
    cheap_budget: None,
) -> None:
    """Legacy _resolved_inputs must not leak through generic instruction/context fields."""
    block = _FakeDeclaredBlock()
    state = _state(
        shared_memory={
            "_resolved_inputs": {
                "instruction": "legacy instruction leak",
                "context": "legacy context leak",
                "summary": "legacy input leak",
            }
        },
    )

    ctx = build_block_context(block, state, step=None)

    assert ctx.inputs == {}
    assert "legacy input leak" not in json.dumps(ctx.inputs)
    assert "legacy instruction leak" not in (ctx.instruction or "")
    assert "legacy context leak" not in (ctx.context or "")


def test_build_block_context_dev_policy_warns_without_legacy_fallback(
    cheap_budget: None,
) -> None:
    """The optional dev policy must not weaken declared-only input isolation."""
    cg = _cg()
    block = _FakeDeclaredBlock()
    step = Step(block=block, declared_inputs={"summary": "draft.summary"})
    state = _state(shared_memory={"_resolved_inputs": {"summary": "legacy leak"}})

    ctx = build_block_context(
        block,
        state,
        step=step,
        policy=cg.ContextGovernancePolicy(mode="dev"),
    )

    assert ctx.inputs == {}
