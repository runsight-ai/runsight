"""ExecutionService sensitive-input preparation redaction behavior."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from runsight_api.domain.errors import InputValidationError
from runsight_api.logic.services.execution_service import PreparedRunInputs

from sensitive_redaction_helpers import (
    PUBLIC_VALUE,
    REDACTED,
    SENSITIVE_VALUE,
    make_sensitive_execution_service,
    mixed_structured_sensitive_workflow_yaml,
    sensitive_default_workflow_yaml,
    sensitive_non_string_workflow_yaml,
)


def test_prepare_run_inputs_returns_values_and_runtime_redactor_for_sensitive_inputs() -> None:
    service = make_sensitive_execution_service()

    prepared = service.prepare_run_inputs(
        "sensitive_inputs_workflow",
        {
            "private_note": SENSITIVE_VALUE,
            "api_token": PUBLIC_VALUE,
        },
        branch=None,
    )

    assert isinstance(prepared, PreparedRunInputs)
    assert prepared.normalized_inputs == {
        "private_note": SENSITIVE_VALUE,
        "api_token": PUBLIC_VALUE,
        "optional_payload": {"mode": "public"},
    }
    assert set(prepared.normalized_inputs) == {
        "private_note",
        "api_token",
        "optional_payload",
    }
    assert not hasattr(prepared, "redacted")
    assert prepared.input_redactor.redact(
        {"private_note": SENSITIVE_VALUE, "api_token": PUBLIC_VALUE}
    ) == {"private_note": REDACTED, "api_token": PUBLIC_VALUE}


def test_secret_like_names_are_not_registered_without_sensitive_true() -> None:
    service = make_sensitive_execution_service()

    prepared = service.prepare_run_inputs(
        "sensitive_inputs_workflow",
        {
            "private_note": SENSITIVE_VALUE,
            "api_token": PUBLIC_VALUE,
        },
        branch=None,
    )

    redacted = prepared.input_redactor.redact(
        {"private_note": SENSITIVE_VALUE, "api_token": PUBLIC_VALUE}
    )

    assert redacted["private_note"] == REDACTED
    assert redacted["api_token"] == PUBLIC_VALUE


def test_prepare_run_inputs_redacts_sensitive_non_string_values_at_runtime_boundaries() -> None:
    service = make_sensitive_execution_service(yaml=sensitive_non_string_workflow_yaml())

    prepared = service.prepare_run_inputs(
        "sensitive_inputs_workflow",
        {
            "private_limit": 481516,
            "private_enabled": True,
            "private_payload": {
                "account_id": 23,
                "enabled": False,
            },
            "private_values": [3.5, True],
        },
        branch=None,
    )

    expected_normalized = {
        "private_limit": 481516,
        "private_enabled": True,
        "private_payload": {
            "account_id": 23,
            "enabled": False,
        },
        "private_values": [3.5, True],
    }
    payload = {
        **expected_normalized,
        "public": PUBLIC_VALUE,
    }

    assert prepared.normalized_inputs == expected_normalized
    assert prepared.input_redactor.redact_runtime_value(payload) == {
        "private_limit": REDACTED,
        "private_enabled": REDACTED,
        "private_payload": {
            "account_id": REDACTED,
            "enabled": REDACTED,
        },
        "private_values": [REDACTED, REDACTED],
        "public": PUBLIC_VALUE,
    }
    assert "value" not in prepared.workflow_inputs["private_limit"]
    assert "value" not in prepared.workflow_inputs["private_payload"]


def test_prepare_run_inputs_redacts_all_mixed_structured_sensitive_string_leaves() -> None:
    service = make_sensitive_execution_service(yaml=mixed_structured_sensitive_workflow_yaml())
    credentials = {"token": "SECRET-UNIQUE", "a": "dup", "b": "dup"}

    prepared = service.prepare_run_inputs(
        "sensitive_inputs_workflow",
        {"credentials": credentials},
        branch=None,
    )

    expected_credentials = {
        "token": REDACTED,
        "a": REDACTED,
        "b": REDACTED,
    }

    assert prepared.normalized_inputs == {"credentials": credentials}
    assert prepared.input_redactor.redact_runtime_value(credentials) == expected_credentials
    assert prepared.input_redactor.redact_runtime_value(json.dumps(credentials)) == (
        expected_credentials
    )
    assert prepared.input_redactor.redact_text("failed with SECRET-UNIQUE and dup") == (
        f"failed with {REDACTED} and {REDACTED}"
    )


def test_prepare_run_inputs_redacts_json_escaped_sensitive_string_leaf_text() -> None:
    service = make_sensitive_execution_service(yaml=mixed_structured_sensitive_workflow_yaml())
    secret = 'alpha"beta\\gamma\nline2'
    credentials = {"token": secret}
    prepared = service.prepare_run_inputs(
        "sensitive_inputs_workflow",
        {"credentials": credentials},
        branch=None,
    )
    serialized = json.dumps(credentials)
    escaped_secret = json.dumps(secret)[1:-1]

    redacted = prepared.input_redactor.redact_text(f"failed with {serialized}")

    assert escaped_secret not in redacted
    assert secret not in redacted
    assert redacted == f'failed with {{"token": "{REDACTED}"}}'


def test_prepare_run_inputs_rejects_sensitive_defaults_before_normalization() -> None:
    service = make_sensitive_execution_service(yaml=sensitive_default_workflow_yaml())

    with pytest.raises(InputValidationError) as exc_info:
        service.prepare_run_inputs("sensitive_inputs_workflow", {}, branch=None)

    payload = exc_info.value.to_dict()
    assert payload["error"] == "Workflow input validation failed"
    assert payload["error_code"] == "WORKFLOW_INPUT_VALIDATION_ERROR"
    assert SENSITIVE_VALUE not in str(payload)


@pytest.mark.asyncio
async def test_launch_execution_keeps_prepared_redactor_for_prepared_run_inputs() -> None:
    service = make_sensitive_execution_service()
    prepared = service.prepare_run_inputs(
        "sensitive_inputs_workflow",
        {
            "private_note": SENSITIVE_VALUE,
            "api_token": PUBLIC_VALUE,
        },
        branch=None,
    )
    captured: dict[str, object] = {}

    async def _capture_state(state, **kwargs):
        captured["state"] = state
        captured["inputs"] = kwargs["inputs"]
        return state

    mock_wf = Mock()
    mock_wf.run = AsyncMock(side_effect=_capture_state)

    with patch("runsight_api.logic.services.execution_service.parse_workflow_yaml") as mock_parse:
        mock_parse.return_value = mock_wf

        await service.launch_execution(
            "run_sensitive_launch",
            "sensitive_inputs_workflow",
            prepared,
            branch=None,
        )

        await asyncio.sleep(0.1)

    assert "state" in captured
    assert captured["inputs"] == prepared.normalized_inputs
    sample = {"private_note": SENSITIVE_VALUE, "api_token": PUBLIC_VALUE}
    redacted = captured["state"].input_redactor.redact(sample)
    assert redacted["private_note"] == REDACTED
    assert redacted["api_token"] == PUBLIC_VALUE


@pytest.mark.asyncio
async def test_launch_execution_rejects_raw_mapping_inputs_at_service_boundary() -> None:
    service = make_sensitive_execution_service()
    mock_wf = Mock()
    mock_wf.run = AsyncMock()

    with patch("runsight_api.logic.services.execution_service.parse_workflow_yaml") as mock_parse:
        mock_parse.return_value = mock_wf

        with pytest.raises(TypeError, match="PreparedRunInputs"):
            await service.launch_execution(
                "run_sensitive_launch",
                "sensitive_inputs_workflow",
                {
                    "private_note": SENSITIVE_VALUE,
                    "api_token": PUBLIC_VALUE,
                },
                branch=None,
            )

    mock_wf.run.assert_not_called()
