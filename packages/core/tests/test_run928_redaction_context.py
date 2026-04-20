"""RED tests for RUN-928 sensitive workflow input redaction boundaries."""

from __future__ import annotations

import json
import logging
from typing import Any
from unittest.mock import AsyncMock

import pytest
from runsight_core.block_io import apply_block_output, build_block_context
from runsight_core.blocks.workflow_block import WorkflowBlock
from runsight_core.context_governance import (
    ContextDeclaration,
    ContextGovernancePolicy,
    ContextResolver,
)
from runsight_core.observer import LoggingObserver
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import BlockExecutionContext, Workflow, execute_block
from runsight_core.yaml.schema import WorkflowInputDef

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


def test_named_structured_sensitive_input_redacts_unique_leaves_directly_and_in_preview() -> None:
    from runsight_core.redaction import RunRedactor

    redactor = RunRedactor()
    credentials = {"api_key": "alpha", "nested": {"inner": "beta"}}
    redactor.register_named("credentials", credentials)
    state = _state_with_redactor(
        redactor=redactor,
        workflow_inputs={"credentials": credentials},
    )

    scoped = _resolver().resolve(
        declaration=ContextDeclaration(
            block_id="consumer",
            block_type="linear",
            declared_inputs={"credentials": "workflow.credentials"},
        ),
        state=state,
    )

    preview = scoped.audit_event.records[0].preview or ""
    expected = {
        "api_key": REDACTED,
        "nested": {"inner": REDACTED},
    }

    assert (redactor.redact(credentials), json.loads(preview)) == (expected, expected)


def test_context_audit_preview_keeps_secret_like_names_visible_until_registered() -> None:
    declaration = ContextDeclaration(
        block_id="consumer",
        block_type="linear",
        declared_inputs={
            "api_token": "workflow.api_token",
            "private_note": "workflow.private_note",
        },
    )

    plain_scoped = _resolver().resolve(
        declaration=declaration,
        state=_state_with_redactor(
            workflow_inputs={
                "api_token": PUBLIC_VALUE,
                "private_note": PUBLIC_VALUE,
            },
        ),
    )
    plain_previews = {
        record.input_name: record.preview for record in plain_scoped.audit_event.records
    }
    assert plain_previews == {
        "api_token": PUBLIC_VALUE,
        "private_note": PUBLIC_VALUE,
    }

    redacted_scoped = _resolver().resolve(
        declaration=declaration,
        state=_state_with_redactor(
            redactor=_redactor(PUBLIC_VALUE),
            workflow_inputs={
                "api_token": PUBLIC_VALUE,
                "private_note": PUBLIC_VALUE,
            },
        ),
    )
    redacted_previews = {
        record.input_name: record.preview for record in redacted_scoped.audit_event.records
    }
    assert redacted_previews == {
        "api_token": REDACTED,
        "private_note": REDACTED,
    }


def test_context_audit_preview_redacts_every_exact_leaf_in_named_structured_input() -> None:
    """Named redaction must cover every exact sensitive leaf in structured previews."""
    from runsight_core.redaction import RunRedactor

    redactor = RunRedactor()
    credentials = {
        "api_key": SENSITIVE_VALUE,
        "nested": [SENSITIVE_VALUE, {"inner": SENSITIVE_VALUE}],
        "public": PUBLIC_VALUE,
    }
    redactor.register_named("credentials", credentials)
    state = _state_with_redactor(
        redactor=redactor,
        workflow_inputs={"credentials": credentials},
    )

    scoped = _resolver().resolve(
        declaration=ContextDeclaration(
            block_id="consumer",
            block_type="linear",
            declared_inputs={"credentials": "workflow.credentials"},
        ),
        state=state,
    )

    preview = scoped.audit_event.records[0].preview or ""

    assert scoped.inputs == {"credentials": credentials}
    assert SENSITIVE_VALUE not in preview
    assert preview.count(REDACTED) >= 3
    assert PUBLIC_VALUE in preview
    assert SENSITIVE_VALUE not in scoped.audit_event.model_dump_json()


def test_context_audit_preview_redacts_each_registered_structured_input_recursively() -> None:
    from runsight_core.redaction import RunRedactor

    redactor = RunRedactor()
    credentials = {
        "api_key": SENSITIVE_VALUE,
        "nested": [SENSITIVE_VALUE, {"inner": SENSITIVE_VALUE}],
    }
    profile = {
        "refresh_token": SENSITIVE_VALUE,
        "nested": {"aliases": [PUBLIC_VALUE, SENSITIVE_VALUE]},
    }
    redactor.register_named("credentials", credentials)
    redactor.register_named("profile", profile)
    state = _state_with_redactor(
        redactor=redactor,
        workflow_inputs={
            "credentials": credentials,
            "profile": profile,
        },
    )

    scoped = _resolver().resolve(
        declaration=ContextDeclaration(
            block_id="consumer",
            block_type="linear",
            declared_inputs={
                "credentials": "workflow.credentials",
                "profile": "workflow.profile",
            },
        ),
        state=state,
    )

    previews = {record.input_name: record.preview for record in scoped.audit_event.records}

    assert scoped.inputs == {
        "credentials": credentials,
        "profile": profile,
    }
    assert json.loads(previews["credentials"] or "") == {
        "api_key": REDACTED,
        "nested": [REDACTED, {"inner": REDACTED}],
    }
    assert json.loads(previews["profile"] or "") == {
        "refresh_token": REDACTED,
        "nested": {"aliases": [PUBLIC_VALUE, REDACTED]},
    }
    assert SENSITIVE_VALUE not in scoped.audit_event.model_dump_json()


def test_sensitive_structured_redaction_covers_non_string_leaves_in_runtime_dumps() -> None:
    from runsight_core.redaction import RunRedactor

    redactor = RunRedactor()
    credentials = {
        "account_id": 481516,
        "enabled": True,
        "limits": [3.5, False],
    }
    redactor.register_named("credentials", credentials)
    state = _state_with_redactor(
        redactor=redactor,
        workflow_inputs={"credentials": credentials},
        results={
            "echo": BlockResult(
                output=json.dumps(
                    {
                        "credentials": credentials,
                        "public": PUBLIC_VALUE,
                    }
                )
            )
        },
    )

    redacted_credentials = {
        "account_id": REDACTED,
        "enabled": REDACTED,
        "limits": [REDACTED, REDACTED],
    }

    assert redactor.redact_runtime_value({"credentials": credentials}) == {
        "credentials": redacted_credentials
    }
    assert state.model_dump()["workflow_inputs"]["credentials"] == redacted_credentials

    dumped = state.model_dump_json()
    assert "481516" not in dumped
    assert "3.5" not in dumped
    assert '"enabled":true' not in dumped
    assert '"public":"orchid-928-public-value"' in dumped


def test_named_structured_sensitive_input_redacts_duplicate_and_unique_leaves_without_over_redacting_public_siblings() -> (
    None
):
    """Mixed structured sensitive leaves must all redact while public siblings stay visible."""
    from runsight_core.redaction import RunRedactor

    redactor = RunRedactor()
    credentials = {"a": "dup", "b": "dup", "c": "unique"}
    payload = {
        "credentials": credentials,
        "public": PUBLIC_VALUE,
    }
    redactor.register_named("credentials", credentials)
    state = _state_with_redactor(
        redactor=redactor,
        workflow_inputs=payload,
    )

    scoped = _resolver().resolve(
        declaration=ContextDeclaration(
            block_id="consumer",
            block_type="linear",
            declared_inputs={
                "credentials": "workflow.credentials",
                "public": "workflow.public",
            },
        ),
        state=state,
    )

    redacted_payload = redactor.redact(payload)
    state_dump = state.model_dump()
    state_dump_json = state.model_dump_json()
    previews = {record.input_name: record.preview for record in scoped.audit_event.records}

    expected_credentials = {"a": REDACTED, "b": REDACTED, "c": REDACTED}

    assert redacted_payload["credentials"] == expected_credentials
    assert redacted_payload["public"] == PUBLIC_VALUE
    assert state_dump["workflow_inputs"]["credentials"] == expected_credentials
    assert state_dump["workflow_inputs"]["public"] == PUBLIC_VALUE
    assert "dup" not in state_dump_json
    assert "unique" not in state_dump_json
    assert PUBLIC_VALUE in state_dump_json
    assert json.loads(previews["credentials"] or "") == expected_credentials
    assert previews["public"] == PUBLIC_VALUE


def test_explicit_sensitive_registration_redacts_leaves_under_public_paths() -> None:
    from runsight_core.redaction import RunRedactor

    redactor = RunRedactor()
    credentials = {
        "public": {
            "token": SENSITIVE_VALUE,
            "nested": [SENSITIVE_VALUE, {"inner": SENSITIVE_VALUE}],
        },
        "private": {"inner": PUBLIC_VALUE},
    }
    redactor.register_named("credentials", credentials)

    redacted = redactor.redact(credentials)

    assert redacted["public"]["token"] == REDACTED
    assert redacted["public"]["nested"][0] == REDACTED
    assert redacted["public"]["nested"][1]["inner"] == REDACTED
    assert redacted["private"]["inner"] == PUBLIC_VALUE
    assert SENSITIVE_VALUE not in json.dumps(redacted)


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


def _sensitive_child_workflow() -> tuple[Workflow, dict[str, WorkflowState]]:
    child = Workflow(
        name="child_sensitive_workflow",
        input_schema={
            "child_secret": WorkflowInputDef(type="string", sensitive=True),
        },
    )
    captured: dict[str, WorkflowState] = {}

    async def _run(state: WorkflowState, **kwargs: Any) -> WorkflowState:
        captured["received_state"] = state
        redactor = state.input_redactor
        assert redactor is not None

        child_secret = state.workflow_inputs["child_secret"]
        redacted_payload = redactor.redact(
            {
                "child_secret": child_secret,
                "public_note": PUBLIC_VALUE,
            }
        )
        returned_state = WorkflowState(
            input_redactor=redactor,
            workflow_inputs=dict(state.workflow_inputs),
            results={
                "child_result": BlockResult(output=json.dumps(redacted_payload)),
            },
            execution_log=[
                {
                    "role": "system",
                    "content": redactor.redact_text(f"child saw {child_secret}"),
                }
            ],
        )
        captured["returned_state"] = returned_state
        return returned_state

    child.run = AsyncMock(side_effect=_run)
    return child, captured


def _raw_sensitive_child_workflow() -> tuple[Workflow, dict[str, WorkflowState]]:
    child = Workflow(
        name="child_sensitive_workflow",
        input_schema={
            "child_secret": WorkflowInputDef(type="string", sensitive=True),
        },
    )
    captured: dict[str, WorkflowState] = {}

    async def _run(state: WorkflowState, **kwargs: Any) -> WorkflowState:
        captured["received_state"] = state
        child_secret = state.workflow_inputs["child_secret"]
        returned_state = WorkflowState(
            input_redactor=state.input_redactor,
            workflow_inputs=dict(state.workflow_inputs),
            results={
                "child_result": BlockResult(output=child_secret),
            },
            execution_log=[
                {
                    "role": "system",
                    "content": f"child saw {child_secret}",
                }
            ],
        )
        captured["returned_state"] = returned_state
        return returned_state

    child.run = AsyncMock(side_effect=_run)
    return child, captured


@pytest.mark.asyncio
async def test_workflow_block_registers_child_sensitive_inputs_at_child_boundary() -> None:
    child, captured = _sensitive_child_workflow()
    block = WorkflowBlock(
        block_id="invoke_sensitive_child",
        child_workflow=child,
        inputs={"child_secret": "shared_memory.topic"},
        outputs={},
    )
    parent_state = _state_with_redactor(
        redactor=_redactor(SENSITIVE_VALUE),
        shared_memory={"topic": PUBLIC_VALUE},
    )
    ctx = build_block_context(block, parent_state)

    await block.execute(ctx)

    received_state = captured["received_state"]
    returned_state = captured["returned_state"]

    assert received_state.workflow_inputs == {"child_secret": PUBLIC_VALUE}
    assert received_state.input_redactor is parent_state.input_redactor
    assert received_state.input_redactor.redact({"child_secret": PUBLIC_VALUE}) == {
        "child_secret": REDACTED
    }
    assert json.loads(returned_state.results["child_result"].output) == {
        "child_secret": REDACTED,
        "public_note": PUBLIC_VALUE,
    }
    assert returned_state.execution_log[0]["content"] == f"child saw {REDACTED}"
    assert PUBLIC_VALUE not in returned_state.model_dump_json()


@pytest.mark.asyncio
async def test_workflow_block_merges_child_sensitive_input_back_into_parent_redaction_state() -> (
    None
):
    """Parent state must inherit child-sensitive redaction after block application."""
    child, captured = _raw_sensitive_child_workflow()
    block = WorkflowBlock(
        block_id="invoke_sensitive_child",
        child_workflow=child,
        inputs={"child_secret": "shared_memory.topic"},
        outputs={"shared_memory.child_echo": "results.child_result"},
    )
    parent_state = _state_with_redactor(
        shared_memory={"topic": SENSITIVE_VALUE},
    )
    ctx = build_block_context(block, parent_state)

    output = await block.execute(ctx)
    merged_state = apply_block_output(parent_state, block.block_id, output)

    assert parent_state.input_redactor is None
    assert captured["received_state"].input_redactor is not None
    assert merged_state.input_redactor is not None
    assert merged_state.input_redactor.redact({"child_echo": SENSITIVE_VALUE}) == {
        "child_echo": REDACTED
    }
    assert SENSITIVE_VALUE not in merged_state.model_dump_json()


class _ParentErrorObserver:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.state: WorkflowState | None = None

    def on_block_start(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        **kwargs: Any,
    ) -> None:
        return None

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
        state: WorkflowState,
    ) -> None:
        self.error = error
        self.state = state


def _raising_sensitive_child_workflow() -> Workflow:
    child = Workflow(
        name="child_sensitive_raise_workflow",
        input_schema={
            "child_secret": WorkflowInputDef(type="string", sensitive=True),
        },
    )

    async def _run(state: WorkflowState, **kwargs: Any) -> WorkflowState:
        child_secret = state.workflow_inputs["child_secret"]
        raise RuntimeError(f"child failed with {child_secret}")

    child.run = AsyncMock(side_effect=_run)
    return child


@pytest.mark.asyncio
async def test_workflow_block_promotes_child_sensitive_redactor_before_raise_observer_surface() -> (
    None
):
    child = _raising_sensitive_child_workflow()
    block = WorkflowBlock(
        block_id="invoke_sensitive_child",
        child_workflow=child,
        inputs={"child_secret": "shared_memory.topic"},
        outputs={},
        on_error="raise",
    )
    parent_state = _state_with_redactor(
        shared_memory={"topic": SENSITIVE_VALUE},
    )
    observer = _ParentErrorObserver()
    exec_ctx = BlockExecutionContext(
        workflow_name="parent_workflow",
        blocks={block.block_id: block},
        call_stack=[],
        workflow_registry=None,
        observer=observer,
    )

    with pytest.raises(RuntimeError, match="child failed"):
        await execute_block(block, parent_state, exec_ctx)

    assert observer.error is not None
    assert observer.state is not None
    assert observer.state.input_redactor is not None
    assert observer.state.input_redactor.redact_text(str(observer.error)) == (
        f"child failed with {REDACTED}"
    )
