"""Observer error redaction for registered sensitive values."""

from __future__ import annotations

import json
import logging

import pytest
from redaction_context_helpers import REDACTED, SENSITIVE_VALUE, redactor, state_with_redactor
from runsight_core.observer import LoggingObserver


def test_logging_observer_redacts_registered_sensitive_value_in_error_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    state = state_with_redactor(input_redactor=redactor(SENSITIVE_VALUE))
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


def test_logging_observer_redacts_json_escaped_registered_sensitive_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = 'alpha"beta\\gamma\nline2'
    serialized = json.dumps({"token": secret})
    escaped_secret = json.dumps(secret)[1:-1]
    state = state_with_redactor(input_redactor=redactor(secret))
    observer = LoggingObserver(level=logging.INFO)

    with caplog.at_level(logging.ERROR, logger="runsight.workflow"):
        observer.on_block_error(
            "wf_redaction",
            "leaky_block",
            "CodeBlock",
            0.5,
            RuntimeError(f"failed with {serialized}"),
            state=state,
        )

    assert escaped_secret not in caplog.text
    assert secret not in caplog.text
    assert REDACTED in caplog.text
