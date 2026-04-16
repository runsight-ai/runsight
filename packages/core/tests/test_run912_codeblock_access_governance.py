"""
RED tests for RUN-912: CodeBlock declared and explicit all-access behavior.

CodeBlock must stop receiving implicit full-state input. Broad state access is
allowed only through explicit ``access: all`` and must be visible in the
governance audit contract.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.block_io import BlockContext, build_block_context
from runsight_core.blocks.code import CodeBlock
from runsight_core.context_governance import (
    ContextDeclaration,
    ContextGovernancePolicy,
    ContextResolver,
)
from runsight_core.primitives import Step
from runsight_core.state import BlockResult, WorkflowState

ECHO_CODE = """\
def main(data):
    return data
"""


class CapturingCodeBlock(CodeBlock):
    """CodeBlock test double that captures subprocess input without spawning Python."""

    def __init__(self, block_id: str = "code", code: str = ECHO_CODE):
        super().__init__(block_id, code)
        self.captured_inputs: dict[str, Any] | None = None

    async def _run_subprocess(self, inputs: dict[str, Any]) -> tuple[bytes, bytes, int]:
        self.captured_inputs = inputs
        return json.dumps(inputs).encode(), b"", 0


def _state() -> WorkflowState:
    return WorkflowState(
        results={
            "a": BlockResult(output=json.dumps({"value": "safe", "secret": "hidden"})),
            "secret": BlockResult(output="top secret"),
        },
        metadata={"run": {"id": "run_912"}, "secret": "metadata secret"},
        shared_memory={"visible": "ok", "secret": "shared secret"},
    )


def _resolver() -> ContextResolver:
    return ContextResolver(
        policy=ContextGovernancePolicy(),
        run_id="run_912",
        workflow_name="codeblock_access_governance",
    )


@pytest.mark.asyncio
async def test_declared_codeblock_passes_only_declared_inputs_to_subprocess() -> None:
    """Declared CodeBlock input shape is exactly the declared local input map."""
    block = CapturingCodeBlock("declared_code")
    step = Step(block=block, declared_inputs={"x": "a.value"})
    ctx = build_block_context(block, _state(), step=step)

    await block.execute(ctx)

    assert block.captured_inputs == {"x": "safe"}
    assert "results" not in block.captured_inputs
    assert "metadata" not in block.captured_inputs
    assert "shared_memory" not in block.captured_inputs
    assert "hidden" not in json.dumps(block.captured_inputs)


@pytest.mark.asyncio
async def test_access_all_codeblock_passes_explicit_broad_state_shape_to_subprocess() -> None:
    """Explicit access: all gives CodeBlock results, metadata, and shared_memory."""
    block = CapturingCodeBlock("all_code")
    block.context_access = "all"
    block.declared_inputs = {}
    ctx = build_block_context(block, _state())

    await block.execute(ctx)

    assert set(block.captured_inputs or {}) == {"results", "metadata", "shared_memory"}
    assert block.captured_inputs["results"]["a"] == json.dumps(
        {"value": "safe", "secret": "hidden"}
    )
    assert block.captured_inputs["metadata"] == {
        "run": {"id": "run_912"},
        "secret": "metadata secret",
    }
    assert block.captured_inputs["shared_memory"] == {
        "visible": "ok",
        "secret": "shared secret",
    }


def test_context_resolver_access_all_audit_is_bounded_and_marked_all_access() -> None:
    """All-access resolver output is audited without dumping raw full-state previews."""
    state = _state()
    declaration = ContextDeclaration(
        block_id="all_code",
        block_type="code",
        access="all",
        declared_inputs={},
        internal_inputs={},
    )

    scoped = _resolver().resolve(declaration=declaration, state=state)

    assert set(scoped.inputs) == {"results", "metadata", "shared_memory"}
    assert scoped.audit_event.access == "all"
    assert len(scoped.audit_event.records) == 1
    record = scoped.audit_event.records[0]
    assert record.status == "all_access"
    assert record.severity == "allow"
    assert record.preview is None or len(record.preview) <= 200
    assert "top secret" not in scoped.audit_event.model_dump_json()
    assert "metadata secret" not in scoped.audit_event.model_dump_json()
    assert "shared secret" not in scoped.audit_event.model_dump_json()


@pytest.mark.asyncio
async def test_strict_codeblock_without_declaration_receives_empty_input() -> None:
    """Strict default CodeBlock without inputs/access: all receives no data."""
    block = CapturingCodeBlock("strict_empty")
    ctx = build_block_context(block, _state())

    await block.execute(ctx)

    assert block.captured_inputs == {}


@pytest.mark.asyncio
async def test_dev_codeblock_without_declaration_still_receives_empty_input() -> None:
    """Dev mode may warn, but it must not grant implicit CodeBlock all-access."""
    block = CapturingCodeBlock("dev_empty")
    ctx = build_block_context(
        block,
        _state(),
        policy=ContextGovernancePolicy(mode="dev"),
    )

    await block.execute(ctx)

    assert block.captured_inputs == {}


@pytest.mark.asyncio
async def test_codeblock_execute_passes_custom_ctx_inputs_unchanged_to_subprocess() -> None:
    """CodeBlock.execute forwards the full governed ctx.inputs shape."""
    block = CapturingCodeBlock("custom_inputs")
    ctx = BlockContext(
        block_id="custom_inputs",
        instruction="",
        context=None,
        inputs={"x": "safe", "nested": {"value": 1}},
    )

    await block.execute(ctx)

    assert block.captured_inputs == {"x": "safe", "nested": {"value": 1}}
