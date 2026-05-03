"""External invocation transport guardrail coverage."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


def _assert_runsight_error_shape(response, expected_status: int) -> dict:
    assert response.status_code == expected_status
    body = response.json()
    assert body["status_code"] == expected_status
    assert "error" in body
    assert "error_code" in body
    assert "detail" not in body
    return body


def test_body_limit_rejects_oversized_payload_before_json_parsing_or_storage() -> None:
    from runsight_api.transport.middleware.body_limit import BodySizeLimitMiddleware

    handler_calls: list[str] = []
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=32)

    @app.post("/api/workflows/{workflow_id}/runs")
    async def direct_api_run(workflow_id: str, request: Request):
        handler_calls.append(workflow_id)
        await request.json()
        return {"ok": True}

    response = TestClient(app).post(
        "/api/workflows/wf_runtime_guardrails/runs",
        content=b'{"inputs":{"query":"' + (b"x" * 128),
        headers={
            "content-type": "application/json",
            "authorization": "Bearer secret-runtime-guardrails",
        },
    )

    body = _assert_runsight_error_shape(response, 413)
    assert body["error_code"] == "REQUEST_BODY_TOO_LARGE"
    assert handler_calls == []


def test_external_invocation_log_context_redacts_auth_headers_raw_body_and_inputs() -> None:
    from runsight_api.logic.services.trigger_runtime import redact_external_invocation_log_context

    context = redact_external_invocation_log_context(
        method="POST",
        path="/api/workflows/wf_runtime_guardrails/runs",
        headers={
            "authorization": "Bearer secret-token-944",
            "x-api-key": "secret-api-key-944",
            "content-type": "application/json",
        },
        body=b'{"inputs":{"api_token":"secret-input-944","query":"safe"}}',
        inputs={
            "api_token": "secret-input-944",
            "password": "secret-password-944",
            "query": "safe",
        },
    )

    rendered = json.dumps(context, sort_keys=True)
    assert "secret-token-944" not in rendered
    assert "secret-api-key-944" not in rendered
    assert "secret-input-944" not in rendered
    assert "secret-password-944" not in rendered
    assert context["headers"]["authorization"] == "[redacted]"
    assert context["headers"]["x-api-key"] == "[redacted]"
    assert context["raw_body"] == "[redacted]"
    assert context["inputs"]["api_token"] == "[redacted]"
    assert context["inputs"]["password"] == "[redacted]"
    assert context["inputs"]["query"] == "safe"


def test_external_invocation_log_context_redacts_sensitive_keys_inside_input_lists() -> None:
    from runsight_api.logic.services.trigger_runtime import redact_external_invocation_log_context

    context = redact_external_invocation_log_context(
        method="POST",
        path="/api/workflows/wf_runtime_guardrails/runs",
        headers={},
        body=None,
        inputs={"records": [{"token": "secret-list-token", "query": "safe"}]},
    )

    rendered = json.dumps(context, sort_keys=True)
    assert "secret-list-token" not in rendered
    assert context["inputs"]["records"] == [{"token": "[redacted]", "query": "safe"}]


@pytest.mark.parametrize(
    "raw_body",
    [
        b'{"inputs":{"token":"secret-from-truncated-json"',
        b"x" * 2048,
    ],
)
def test_redaction_handles_malformed_or_huge_body_without_leaking(raw_body: bytes) -> None:
    from runsight_api.logic.services.trigger_runtime import redact_external_invocation_log_context

    context = redact_external_invocation_log_context(
        method="POST",
        path="/api/workflows/wf_runtime_guardrails/runs",
        headers={"authorization": "Bearer secret-token-944"},
        body=raw_body,
        inputs=None,
    )

    rendered = json.dumps(context, sort_keys=True)
    assert "secret" not in rendered.lower()
    assert context["raw_body"] == "[redacted]"
