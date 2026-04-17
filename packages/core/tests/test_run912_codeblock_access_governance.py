"""
RED tests for RUN-912: CodeBlock declared-only governance behavior.

CodeBlock must stop receiving implicit full-state input. ``access: all`` is
unsupported configuration and must not survive into the runtime contract.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError
from runsight_core.block_io import BlockContext, build_block_context
from runsight_core.blocks.code import CodeBlock
from runsight_core.context_governance import (
    ContextDeclaration,
    ContextGovernancePolicy,
    ContextReadDeniedError,
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


def test_access_all_codeblock_declaration_is_rejected_before_runtime() -> None:
    """CodeBlock access: all must be rejected as unsupported configuration."""
    with pytest.raises(ValidationError):
        ContextDeclaration(
            block_id="all_code",
            block_type="code",
            access="all",
            declared_inputs={},
            internal_inputs={},
        )


def test_context_resolver_rejects_legacy_all_access_declaration() -> None:
    """Legacy all-access declarations must not expand into broad runtime state."""
    state = _state()
    declaration = ContextDeclaration.model_construct(
        block_id="all_code",
        block_type="code",
        access="all",
        declared_inputs={},
        internal_inputs={},
    )

    with pytest.raises(ContextReadDeniedError, match="all"):
        _resolver().resolve(declaration=declaration, state=state)


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
