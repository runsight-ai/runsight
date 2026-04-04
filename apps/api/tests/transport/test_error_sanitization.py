"""Tests for RUN-227: error message sanitization in global exception handler.

The global exception handler must NOT leak internal details (file paths,
stack traces, DB schema) to the client.  Unhandled exceptions should return
a generic "Internal server error" message and log the real exception
server-side via logger.exception().

Known domain exceptions (WorkflowNotFound, SoulNotFound, RunFailed,
ProviderNotConfigured) must continue to return their specific messages.
"""

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from runsight_api.domain.errors import (
    ProviderNotConfigured,
    RunFailed,
    RunsightError,
    SoulNotFound,
    WorkflowNotFound,
)
from runsight_api.transport.middleware.error_handler import global_exception_handler

# ---------------------------------------------------------------------------
# Minimal test app with the real handler + routes that raise exceptions
# ---------------------------------------------------------------------------

_app = FastAPI()
_app.add_exception_handler(RunsightError, global_exception_handler)
_app.add_exception_handler(Exception, global_exception_handler)


@_app.get("/raise-runtime")
async def _raise_runtime():
    raise RuntimeError("secret database connection string postgres://user:pass@db:5432/prod")


@_app.get("/raise-file-not-found")
async def _raise_file_not_found():
    raise FileNotFoundError("/home/deploy/.config/runsight/secrets.yaml")


@_app.get("/raise-key-error")
async def _raise_key_error():
    raise KeyError("_internal_api_token")


@_app.get("/raise-workflow-not-found")
async def _raise_workflow_not_found():
    raise WorkflowNotFound("Workflow 'demo' not found")


@_app.get("/raise-soul-not-found")
async def _raise_soul_not_found():
    raise SoulNotFound("Soul 'planner' not found")


@_app.get("/raise-run-failed")
async def _raise_run_failed():
    raise RunFailed("Step 3 timed out after 30s")


@_app.get("/raise-provider-not-configured")
async def _raise_provider_not_configured():
    raise ProviderNotConfigured("Provider 'openai' has no API key")


client = TestClient(_app, raise_server_exceptions=False)


# ===================================================================
# Tests that should FAIL (unhandled exceptions are not yet sanitized)
# ===================================================================


class TestUnhandledExceptionSanitization:
    """Unhandled exceptions must return a generic message, not str(exc)."""

    def test_runtime_error_returns_generic_message(self):
        resp = client.get("/raise-runtime")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "Internal server error"

    def test_runtime_error_does_not_leak_details(self):
        resp = client.get("/raise-runtime")
        body = resp.json()
        assert "postgres://" not in body["error"]
        assert "secret" not in body["error"].lower()

    def test_file_not_found_returns_generic_message(self):
        resp = client.get("/raise-file-not-found")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "Internal server error"

    def test_file_not_found_does_not_leak_path(self):
        resp = client.get("/raise-file-not-found")
        body = resp.json()
        assert "/home/deploy" not in body["error"]
        assert "secrets.yaml" not in body["error"]

    def test_key_error_returns_generic_message(self):
        resp = client.get("/raise-key-error")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "Internal server error"

    def test_key_error_does_not_leak_key_name(self):
        resp = client.get("/raise-key-error")
        body = resp.json()
        assert "_internal_api_token" not in body["error"]

    def test_unhandled_exception_omits_legacy_code_field(self):
        """Unhandled exceptions should not emit the deprecated 'code' field."""
        resp = client.get("/raise-runtime")
        body = resp.json()
        assert "code" not in body


class TestUnhandledExceptionLogging:
    """The real exception must be logged server-side."""

    @patch("runsight_api.transport.middleware.error_handler.logger", create=True)
    def test_unhandled_exception_is_logged(self, mock_logger):
        resp = client.get("/raise-runtime")
        assert resp.status_code == 500
        mock_logger.exception.assert_called_once()

    @patch("runsight_api.transport.middleware.error_handler.logger", create=True)
    def test_file_not_found_is_logged(self, mock_logger):
        resp = client.get("/raise-file-not-found")
        assert resp.status_code == 500
        mock_logger.exception.assert_called_once()


# ===================================================================
# Tests that should PASS (known domain exceptions keep their messages)
# ===================================================================


class TestKnownExceptionsPreserved:
    """Domain-specific exceptions must still return their specific messages."""

    def test_workflow_not_found_returns_404_with_message(self):
        resp = client.get("/raise-workflow-not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "Workflow 'demo' not found"
        assert "code" not in body

    def test_soul_not_found_returns_404_with_message(self):
        resp = client.get("/raise-soul-not-found")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "Soul 'planner' not found"
        assert "code" not in body

    def test_run_failed_returns_500_with_message(self):
        resp = client.get("/raise-run-failed")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"] == "Step 3 timed out after 30s"
        assert "code" not in body

    def test_provider_not_configured_returns_400_with_message(self):
        resp = client.get("/raise-provider-not-configured")
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "Provider 'openai' has no API key"
        assert "code" not in body
