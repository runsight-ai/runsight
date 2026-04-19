"""RED tests for RUN-928 sensitive workflow input redaction boundaries."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from runsight_core.block_io import build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.context_governance import (
    ContextDeclaration,
    ContextGovernancePolicy,
    ContextResolver,
)
from runsight_core.observer import LoggingObserver
from runsight_core.state import BlockResult, WorkflowState

SENSITIVE_VALUE = "orchid-928-sensitive-value"
PUBLIC_VALUE = "orchid-928-public-value"
REDACTED = "[redacted]"


def _redactor(*values: object) -> Any:
    from runsight_core.redaction import SensitiveValueRedactor

    redactor = SensitiveValueRedactor()
    for value in values:
        redactor.register(value)
    return redactor


def _state_with_redactor(
    *,
    redactor: Any | None = None,
    workflow_inputs: dict[str, Any] | None = None,
    results: dict[str, Any] | None = None,
    shared_memory: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    execution_log: list[dict[str, str]] | None = None,
) -> WorkflowState:
    return WorkflowState(
        input_redactor=redactor,
        workflow_inputs=workflow_inputs or {},
        results=results or {},
        shared_memory=shared_memory or {},
        metadata=metadata or {},
        execution_log=execution_log or [],
    )


def _resolver() -> ContextResolver:
    return ContextResolver(
        policy=ContextGovernancePolicy(),
        run_id="run_928_core",
        workflow_name="redaction_context",
    )


def test_sensitive_value_redactor_redacts_registered_exact_values_in_nested_json() -> None:
    redactor = _redactor(SENSITIVE_VALUE)
    payload = {
        "plain": PUBLIC_VALUE,
        "token": SENSITIVE_VALUE,
        "nested": {
            "items": [
                SENSITIVE_VALUE,
                {"inner": SENSITIVE_VALUE},
                f"{SENSITIVE_VALUE}-suffix",
            ]
        },
    }

    redacted = redactor.redact(payload)

    assert redacted["plain"] == PUBLIC_VALUE
    assert redacted["token"] == REDACTED
    assert redacted["nested"]["items"][0] == REDACTED
    assert redacted["nested"]["items"][1]["inner"] == REDACTED
    assert redacted["nested"]["items"][2] == f"{SENSITIVE_VALUE}-suffix"


def test_empty_string_and_null_registrations_do_not_blanket_redact_values() -> None:
    redactor = _redactor("", None)
    payload = {
        "empty": "",
        "none": None,
        "nested": ["", None, {"value": PUBLIC_VALUE}],
    }

    assert redactor.redact(payload) == payload
    assert REDACTED not in json.dumps(redactor.redact(payload))


def test_workflow_state_carries_input_redactor_as_runtime_only_state() -> None:
    redactor = _redactor(SENSITIVE_VALUE)
    state = _state_with_redactor(
        redactor=redactor,
        workflow_inputs={"private_note": SENSITIVE_VALUE},
    )

    assert state.input_redactor is redactor
    assert state.model_copy(update={"total_tokens": 9}).input_redactor is redactor
    assert "input_redactor" in WorkflowState.model_fields
    assert WorkflowState.model_fields["input_redactor"].exclude is True
    assert "input_redactor" not in state.model_dump()
    assert "input_redactor" not in state.model_dump_json()


def test_context_audit_redacts_runtime_registered_workflow_input_preview() -> None:
    state = _state_with_redactor(
        redactor=_redactor(SENSITIVE_VALUE),
        workflow_inputs={
            "private_note": SENSITIVE_VALUE,
            "public_note": PUBLIC_VALUE,
        },
    )
    declaration = ContextDeclaration(
        block_id="consumer",
        block_type="linear",
        declared_inputs={
            "private_note": "workflow.private_note",
            "public_note": "workflow.public_note",
        },
    )

    scoped = _resolver().resolve(declaration=declaration, state=state)

    assert scoped.inputs["private_note"] == SENSITIVE_VALUE
    assert scoped.inputs["public_note"] == PUBLIC_VALUE
    assert scoped.audit_event.records[0].preview == REDACTED
    assert scoped.audit_event.records[1].preview == PUBLIC_VALUE
    assert SENSITIVE_VALUE not in scoped.audit_event.model_dump_json()


def test_logging_observer_redacts_registered_sensitive_value_in_error_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    state = _state_with_redactor(redactor=_redactor(SENSITIVE_VALUE))
    observer = LoggingObserver(level=logging.INFO)

    with caplog.at_level(logging.ERROR, logger="runsight.workflow"):
        observer.on_block_error(
            "wf_redaction",
            "leaky_block",
            "CodeBlock",
            0.5,
            RuntimeError(f"failed with {SENSITIVE_VALUE}"),
            state=state,
        )

    assert SENSITIVE_VALUE not in caplog.text
    assert REDACTED in caplog.text
    assert "leaky_block" in caplog.text


class _CapturingChildWorkflow:
    name = "child_redaction_workflow"

    def __init__(self) -> None:
        self.received_state: WorkflowState | None = None

    async def run(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        self.received_state = state
        return WorkflowState(
            input_redactor=state.input_redactor,
            workflow_inputs=dict(state.workflow_inputs),
            results={"echo": BlockResult(output=state.workflow_inputs["private_note"])},
            artifact_store=state.artifact_store,
        )


@pytest.mark.asyncio
async def test_workflow_block_passes_parent_redaction_context_to_child_state() -> None:
    child = _CapturingChildWorkflow()
    block = WorkflowBlock(
        block_id="invoke_child",
        child_workflow=child,
        inputs={"private_note": "shared_memory.private_note"},
        outputs={"shared_memory.child_echo": "results.echo"},
    )
    parent_state = _state_with_redactor(
        redactor=_redactor(SENSITIVE_VALUE),
        shared_memory={"private_note": SENSITIVE_VALUE},
    )
    ctx = build_block_context(block, parent_state)

    output = await block.execute(ctx)

    assert child.received_state is not None
    assert child.received_state.input_redactor is parent_state.input_redactor
    assert child.received_state.workflow_inputs == {"private_note": SENSITIVE_VALUE}
    assert child.received_state.input_redactor.redact(
        {"echo": child.received_state.workflow_inputs["private_note"]}
    ) == {"echo": REDACTED}
    assert output.shared_memory_updates == {"child_echo": SENSITIVE_VALUE}
