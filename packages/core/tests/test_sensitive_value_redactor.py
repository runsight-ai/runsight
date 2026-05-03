"""Sensitive value redactor runtime behavior."""

from __future__ import annotations

import json

from redaction_context_helpers import (
    PUBLIC_VALUE,
    REDACTED,
    SENSITIVE_VALUE,
    redactor,
    state_with_redactor,
)
from runsight_core.state import BlockResult, WorkflowState


def test_sensitive_value_redactor_redacts_exact_values_and_json_escaped_text() -> None:
    secret = 'alpha"beta\\gamma\nline2'
    instance = redactor(SENSITIVE_VALUE, secret)
    payload = {
        "plain": PUBLIC_VALUE,
        "token": SENSITIVE_VALUE,
        "nested": [{"inner": SENSITIVE_VALUE}],
    }
    serialized = json.dumps({"token": secret})
    escaped_secret = json.dumps(secret)[1:-1]

    assert instance.redact(payload) == {
        "plain": PUBLIC_VALUE,
        "token": REDACTED,
        "nested": [{"inner": REDACTED}],
    }
    redacted_text = instance.redact_text(f"failed with {serialized}")
    assert escaped_secret not in redacted_text
    assert secret not in redacted_text
    assert REDACTED in redacted_text


def test_empty_and_null_registrations_do_not_blanket_redact_values() -> None:
    instance = redactor("", None)
    payload = {"empty": "", "none": None, "nested": ["", None, {"value": PUBLIC_VALUE}]}

    assert instance.redact(payload) == payload
    assert REDACTED not in json.dumps(instance.redact(payload))


def test_workflow_state_carries_redactor_as_runtime_only_excluded_state() -> None:
    instance = redactor(SENSITIVE_VALUE)
    state = state_with_redactor(
        input_redactor=instance,
        workflow_inputs={"private_note": SENSITIVE_VALUE},
        results={"echo": BlockResult(output=SENSITIVE_VALUE)},
    )

    assert state.input_redactor is instance
    assert state.model_copy(update={"total_tokens": 9}).input_redactor is instance
    assert WorkflowState.model_fields["input_redactor"].exclude is True
    assert "input_redactor" not in state.model_dump()
    assert SENSITIVE_VALUE not in state.model_dump_json()
