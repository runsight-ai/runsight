"""Workflow input snapshot serialization redaction behavior."""

from __future__ import annotations

import json

from runsight_core.redaction import RunRedactor
from runsight_core.yaml.schema import WorkflowInputDef

from runsight_api.logic.services.execution_service import _workflow_input_values_snapshot

from sensitive_redaction_helpers import PUBLIC_VALUE, REDACTED, SENSITIVE_VALUE


def test_workflow_input_snapshot_omits_public_child_value_when_runtime_redactor_marks_it_sensitive() -> (
    None
):
    redactor = RunRedactor()
    redactor.register_named("api_token", SENSITIVE_VALUE)

    snapshot = _workflow_input_values_snapshot(
        {"child_query": WorkflowInputDef(type="string", sensitive=False)},
        {"child_query": SENSITIVE_VALUE},
        redactor=redactor,
    )

    assert snapshot["child_query"] == {
        "type": "string",
        "sensitive": True,
        "source": "provided",
    }


def test_workflow_input_snapshot_omits_runtime_sensitive_value_with_existing_redacted_leaf() -> (
    None
):
    redactor = RunRedactor()
    redactor.register_named("api_token", SENSITIVE_VALUE)
    child_payload = {"already_safe": REDACTED, "token": SENSITIVE_VALUE}

    snapshot = _workflow_input_values_snapshot(
        {"child_payload": WorkflowInputDef(type="json", sensitive=False)},
        {"child_payload": child_payload},
        redactor=redactor,
    )

    assert snapshot["child_payload"] == {
        "type": "json",
        "sensitive": True,
        "source": "provided",
    }


def test_workflow_input_snapshot_preserves_non_sensitive_json_string_values() -> None:
    redactor = RunRedactor()
    redactor.register_named("private_note", SENSITIVE_VALUE)
    public_json_string = '{"kind":"public","items":[1,2]}'

    snapshot = _workflow_input_values_snapshot(
        {"config": WorkflowInputDef(type="string", sensitive=False)},
        {"config": public_json_string},
        redactor=redactor,
    )

    assert snapshot["config"] == {
        "type": "string",
        "sensitive": False,
        "source": "provided",
        "value": public_json_string,
    }


def test_workflow_input_snapshot_preserves_public_json_string_with_redacted_marker() -> None:
    redactor = RunRedactor()
    redactor.register_named("private_note", SENSITIVE_VALUE)
    public_json_string = '{"kind":"public","placeholder":"[redacted]"}'

    snapshot = _workflow_input_values_snapshot(
        {"config": WorkflowInputDef(type="string", sensitive=False)},
        {"config": public_json_string},
        redactor=redactor,
    )

    assert snapshot["config"] == {
        "type": "string",
        "sensitive": False,
        "source": "provided",
        "value": public_json_string,
    }


def test_workflow_input_snapshot_omits_stringified_structured_sensitive_value() -> None:
    redactor = RunRedactor()
    redactor.register_named("credentials", {"token": SENSITIVE_VALUE})
    child_payload = json.dumps(
        {
            "credentials": {"token": "rotated-runtime-token"},
            "public": PUBLIC_VALUE,
        }
    )

    snapshot = _workflow_input_values_snapshot(
        {"child_payload": WorkflowInputDef(type="string", sensitive=False)},
        {"child_payload": child_payload},
        redactor=redactor,
    )

    assert snapshot["child_payload"] == {
        "type": "string",
        "sensitive": True,
        "source": "provided",
    }
