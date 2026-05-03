"""Context audit previews for registered sensitive workflow inputs."""

from __future__ import annotations

import json

from redaction_context_helpers import (
    PUBLIC_VALUE,
    REDACTED,
    SENSITIVE_VALUE,
    redactor,
    resolver,
    state_with_redactor,
)
from runsight_core.context_governance import ContextDeclaration


def test_context_audit_redacts_runtime_registered_workflow_input_preview() -> None:
    state = state_with_redactor(
        input_redactor=redactor(SENSITIVE_VALUE),
        workflow_inputs={"private_note": SENSITIVE_VALUE, "public_note": PUBLIC_VALUE},
    )
    declaration = ContextDeclaration(
        block_id="consumer",
        block_type="linear",
        declared_inputs={
            "private_note": "workflow.private_note",
            "public_note": "workflow.public_note",
        },
    )

    scoped = resolver().resolve(declaration=declaration, state=state)

    previews = {record.input_name: record.preview for record in scoped.audit_event.records}
    assert scoped.inputs == {"private_note": SENSITIVE_VALUE, "public_note": PUBLIC_VALUE}
    assert previews == {"private_note": REDACTED, "public_note": PUBLIC_VALUE}
    assert SENSITIVE_VALUE not in scoped.audit_event.model_dump_json()


def test_secret_like_input_names_remain_visible_until_values_are_registered() -> None:
    declaration = ContextDeclaration(
        block_id="consumer",
        block_type="linear",
        declared_inputs={
            "api_token": "workflow.api_token",
            "private_note": "workflow.private_note",
        },
    )

    scoped = resolver().resolve(
        declaration=declaration,
        state=state_with_redactor(
            workflow_inputs={"api_token": PUBLIC_VALUE, "private_note": PUBLIC_VALUE}
        ),
    )

    assert {record.input_name: record.preview for record in scoped.audit_event.records} == {
        "api_token": PUBLIC_VALUE,
        "private_note": PUBLIC_VALUE,
    }


def test_named_structured_sensitive_inputs_redact_leaves_without_hiding_public_inputs() -> None:
    from runsight_core.redaction import RunRedactor

    instance = RunRedactor()
    credentials = {
        "api_key": SENSITIVE_VALUE,
        "nested": [SENSITIVE_VALUE, {"inner": SENSITIVE_VALUE}],
    }
    profile = {
        "refresh_token": SENSITIVE_VALUE,
        "nested": {"aliases": [PUBLIC_VALUE, SENSITIVE_VALUE]},
    }
    instance.register_named("credentials", credentials)
    instance.register_named("profile", profile)
    state = state_with_redactor(
        input_redactor=instance,
        workflow_inputs={"credentials": credentials, "profile": profile, "public": PUBLIC_VALUE},
    )

    scoped = resolver().resolve(
        declaration=ContextDeclaration(
            block_id="consumer",
            block_type="linear",
            declared_inputs={
                "credentials": "workflow.credentials",
                "profile": "workflow.profile",
                "public": "workflow.public",
            },
        ),
        state=state,
    )

    previews = {record.input_name: record.preview for record in scoped.audit_event.records}
    assert json.loads(previews["credentials"] or "") == {
        "api_key": REDACTED,
        "nested": [REDACTED, {"inner": REDACTED}],
    }
    assert json.loads(previews["profile"] or "") == {
        "refresh_token": REDACTED,
        "nested": {"aliases": [REDACTED, REDACTED]},
    }
    assert previews["public"] == PUBLIC_VALUE
    assert SENSITIVE_VALUE not in scoped.audit_event.model_dump_json()
