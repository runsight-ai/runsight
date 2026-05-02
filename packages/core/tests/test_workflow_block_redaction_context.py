"""WorkflowBlock redaction propagation across invoked workflow boundaries."""

from __future__ import annotations

import json

import pytest
from redaction_context_helpers import (
    PUBLIC_VALUE,
    REDACTED,
    SENSITIVE_VALUE,
    CapturingRedactionWorkflow,
    ParentErrorObserver,
    raising_sensitive_input_workflow,
    redactor,
    sensitive_input_workflow,
    state_with_redactor,
)
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.workflow import BlockExecutionContext, execute_block


@pytest.mark.asyncio
async def test_workflow_block_passes_parent_redaction_context_to_invoked_state() -> None:
    invoked = CapturingRedactionWorkflow()
    block = WorkflowBlock(
        block_id="call_redaction_context_workflow",
        child_workflow=invoked,
        inputs={"private_note": "shared_memory.private_note"},
        outputs={"shared_memory.redaction_echo": "results.echo"},
    )
    parent_state = state_with_redactor(
        input_redactor=redactor(SENSITIVE_VALUE),
        shared_memory={"private_note": SENSITIVE_VALUE},
    )

    output = await block.execute(build_block_context(block, parent_state))

    assert invoked.received_state is not None
    assert invoked.received_state.input_redactor is parent_state.input_redactor
    assert invoked.received_state.workflow_inputs == {"private_note": SENSITIVE_VALUE}
    assert invoked.received_state.input_redactor.redact({"echo": SENSITIVE_VALUE}) == {
        "echo": REDACTED
    }
    assert output.shared_memory_updates == {"redaction_echo": SENSITIVE_VALUE}


@pytest.mark.asyncio
async def test_workflow_block_registers_invoked_sensitive_inputs_at_boundary() -> None:
    invoked, captured = sensitive_input_workflow()
    block = WorkflowBlock(
        block_id="call_sensitive_input_workflow",
        child_workflow=invoked,
        inputs={"invoked_secret": "shared_memory.topic"},
        outputs={},
    )
    parent_state = state_with_redactor(
        input_redactor=redactor(SENSITIVE_VALUE),
        shared_memory={"topic": PUBLIC_VALUE},
    )

    await block.execute(build_block_context(block, parent_state))

    received_state = captured["received_state"]
    returned_state = captured["returned_state"]
    assert received_state.input_redactor is parent_state.input_redactor
    assert received_state.input_redactor.redact({"invoked_secret": PUBLIC_VALUE}) == {
        "invoked_secret": REDACTED
    }
    assert json.loads(returned_state.results["sensitive_result"].output) == {
        "invoked_secret": REDACTED,
        "public_note": PUBLIC_VALUE,
    }
    assert PUBLIC_VALUE not in returned_state.model_dump_json()


@pytest.mark.asyncio
async def test_workflow_block_merges_invoked_sensitive_input_back_into_caller_redaction_state() -> (
    None
):
    invoked, captured = sensitive_input_workflow(raw_return=True)
    block = WorkflowBlock(
        block_id="call_sensitive_input_workflow",
        child_workflow=invoked,
        inputs={"invoked_secret": "shared_memory.topic"},
        outputs={"shared_memory.sensitive_echo": "results.sensitive_result"},
    )
    parent_state = state_with_redactor(shared_memory={"topic": SENSITIVE_VALUE})

    output = await block.execute(build_block_context(block, parent_state))
    merged_state = apply_block_output(parent_state, block.block_id, output)

    assert parent_state.input_redactor is None
    assert captured["received_state"].input_redactor is not None
    assert merged_state.input_redactor is not None
    assert SENSITIVE_VALUE not in merged_state.model_dump_json()


@pytest.mark.asyncio
async def test_workflow_block_promotes_invoked_sensitive_redactor_before_raise_observer_surface() -> (
    None
):
    block = WorkflowBlock(
        block_id="call_sensitive_input_workflow",
        child_workflow=raising_sensitive_input_workflow(),
        inputs={"invoked_secret": "shared_memory.topic"},
        outputs={},
        on_error="raise",
    )
    observer = ParentErrorObserver()
    exec_ctx = BlockExecutionContext(
        workflow_name="redaction_caller_workflow",
        blocks={block.block_id: block},
        call_stack=[],
        workflow_registry=None,
        observer=observer,
    )

    with pytest.raises(RuntimeError, match="invoked workflow failed"):
        await execute_block(
            block, state_with_redactor(shared_memory={"topic": SENSITIVE_VALUE}), exec_ctx
        )

    assert observer.error is not None
    assert observer.state is not None
    assert observer.state.input_redactor is not None
    assert observer.state.input_redactor.redact_text(str(observer.error)) == (
        f"invoked workflow failed with {REDACTED}"
    )
