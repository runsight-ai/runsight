"""Red tests for RUN-289: Structured error base class + enriched error handler.

Tests cover:
- RunsightError structured fields: error_code, status_code, to_dict()
- All 8 subclasses have correct class-level error_code and status_code
- Auto-reads contextvars (run_id, block_id, workflow_name) when not passed
- ProviderNotFound bug fix (status_code=404, not 500)
- Backward compat: raise SubClass("msg") still works
- Error handler uses to_dict() + request_id from contextvar
- Unhandled exceptions return 500 with no details leaked

All tests should FAIL until the implementation is written.
"""

import pytest

# ---------------------------------------------------------------------------
# Tests — RunsightError class-level defaults
# ---------------------------------------------------------------------------


class TestRunsightErrorClassDefaults:
    """RunsightError must have class-level error_code and status_code."""

    def test_error_code_class_attr(self):
        from runsight_api.domain.errors import RunsightError

        assert RunsightError.error_code == "RUNSIGHT_ERROR"

    def test_status_code_class_attr(self):
        from runsight_api.domain.errors import RunsightError

        assert RunsightError.status_code == 500

    def test_instance_inherits_error_code(self):
        from runsight_api.domain.errors import RunsightError

        err = RunsightError("something broke")
        assert err.error_code == "RUNSIGHT_ERROR"

    def test_instance_inherits_status_code(self):
        from runsight_api.domain.errors import RunsightError

        err = RunsightError("something broke")
        assert err.status_code == 500


# ---------------------------------------------------------------------------
# Tests — RunsightError.to_dict()
# ---------------------------------------------------------------------------


class TestRunsightErrorToDict:
    """RunsightError("msg").to_dict() returns a structured dict."""

    def test_to_dict_exists(self):
        from runsight_api.domain.errors import RunsightError

        err = RunsightError("boom")
        assert callable(err.to_dict)

    def test_to_dict_has_error_key(self):
        from runsight_api.domain.errors import RunsightError

        result = RunsightError("boom").to_dict()
        assert result["error"] == "boom"

    def test_to_dict_has_error_code_key(self):
        from runsight_api.domain.errors import RunsightError

        result = RunsightError("boom").to_dict()
        assert result["error_code"] == "RUNSIGHT_ERROR"

    def test_to_dict_has_status_code_key(self):
        from runsight_api.domain.errors import RunsightError

        result = RunsightError("boom").to_dict()
        assert result["status_code"] == 500

    def test_to_dict_includes_run_id_when_set(self):
        from runsight_api.domain.errors import RunsightError

        err = RunsightError("fail", run_id="run-123")
        result = err.to_dict()
        assert result["run_id"] == "run-123"

    def test_to_dict_includes_block_id_when_set(self):
        from runsight_api.domain.errors import RunsightError

        err = RunsightError("fail", block_id="blk-456")
        result = err.to_dict()
        assert result["block_id"] == "blk-456"

    def test_to_dict_includes_workflow_name_when_set(self):
        from runsight_api.domain.errors import RunsightError

        err = RunsightError("fail", workflow_name="my_pipeline")
        result = err.to_dict()
        assert result["workflow_name"] == "my_pipeline"

    def test_to_dict_includes_details_when_set(self):
        from runsight_api.domain.errors import RunsightError

        err = RunsightError("fail", details={"key": "val"})
        result = err.to_dict()
        assert result["details"] == {"key": "val"}

    def test_to_dict_omits_empty_optional_fields(self):
        from runsight_api.domain.errors import RunsightError

        result = RunsightError("boom").to_dict()
        assert "run_id" not in result
        assert "block_id" not in result
        assert "workflow_name" not in result
        assert "details" not in result


# ---------------------------------------------------------------------------
# Tests — auto-read from contextvars
# ---------------------------------------------------------------------------


class TestAutoReadContextVars:
    """RunsightError auto-reads run_id, block_id, workflow_name from contextvars."""

    def test_auto_reads_run_id_from_contextvar(self):
        from runsight_api.core.context import bind_execution_context, clear_execution_context
        from runsight_api.domain.errors import RunsightError

        bind_execution_context(run_id="ctx-run-1", workflow_name="ctx-wf")
        try:
            err = RunsightError("auto")
            assert err.to_dict()["run_id"] == "ctx-run-1"
        finally:
            clear_execution_context()

    def test_auto_reads_workflow_name_from_contextvar(self):
        from runsight_api.core.context import bind_execution_context, clear_execution_context
        from runsight_api.domain.errors import RunsightError

        bind_execution_context(run_id="ctx-run-2", workflow_name="ctx-wf-2")
        try:
            err = RunsightError("auto")
            assert err.to_dict()["workflow_name"] == "ctx-wf-2"
        finally:
            clear_execution_context()

    def test_auto_reads_block_id_from_contextvar(self):
        from runsight_api.core.context import bind_block_context, clear_block_context
        from runsight_api.domain.errors import RunsightError

        bind_block_context("ctx-blk-1")
        try:
            err = RunsightError("auto")
            assert err.to_dict()["block_id"] == "ctx-blk-1"
        finally:
            clear_block_context()

    def test_explicit_run_id_overrides_contextvar(self):
        from runsight_api.core.context import bind_execution_context, clear_execution_context
        from runsight_api.domain.errors import RunsightError

        bind_execution_context(run_id="ctx-run", workflow_name="ctx-wf")
        try:
            err = RunsightError("override", run_id="explicit-run")
            assert err.to_dict()["run_id"] == "explicit-run"
        finally:
            clear_execution_context()


# ---------------------------------------------------------------------------
# Tests — all 8 subclasses have correct error_code and status_code
# ---------------------------------------------------------------------------


SUBCLASS_EXPECTATIONS = [
    ("WorkflowNotFound", "WORKFLOW_NOT_FOUND", 404),
    ("RunNotFound", "RUN_NOT_FOUND", 404),
    ("RunFailed", "RUN_FAILED", 500),
    ("ProviderNotConfigured", "PROVIDER_NOT_CONFIGURED", 400),
    ("SoulNotFound", "SOUL_NOT_FOUND", 404),
    ("TaskNotFound", "TASK_NOT_FOUND", 404),
    ("StepNotFound", "STEP_NOT_FOUND", 404),
    ("ProviderNotFound", "PROVIDER_NOT_FOUND", 404),
]


class TestSubclassErrorCodes:
    """Each subclass must have its own class-level error_code and status_code."""

    @pytest.mark.parametrize("cls_name,expected_code,expected_status", SUBCLASS_EXPECTATIONS)
    def test_error_code(self, cls_name, expected_code, expected_status):
        import runsight_api.domain.errors as mod

        cls = getattr(mod, cls_name)
        assert cls.error_code == expected_code

    @pytest.mark.parametrize("cls_name,expected_code,expected_status", SUBCLASS_EXPECTATIONS)
    def test_status_code(self, cls_name, expected_code, expected_status):
        import runsight_api.domain.errors as mod

        cls = getattr(mod, cls_name)
        assert cls.status_code == expected_status

    @pytest.mark.parametrize("cls_name,expected_code,expected_status", SUBCLASS_EXPECTATIONS)
    def test_to_dict_reflects_subclass_defaults(self, cls_name, expected_code, expected_status):
        import runsight_api.domain.errors as mod

        cls = getattr(mod, cls_name)
        err = cls("test message")
        d = err.to_dict()
        assert d["error_code"] == expected_code
        assert d["status_code"] == expected_status
        assert d["error"] == "test message"


# ---------------------------------------------------------------------------
# Tests — ProviderNotFound bug fix
# ---------------------------------------------------------------------------


class TestProviderNotFoundBugFix:
    """ProviderNotFound must return 404, not 500 (it was unhandled before)."""

    def test_provider_not_found_status_is_404(self):
        from runsight_api.domain.errors import ProviderNotFound

        assert ProviderNotFound.status_code == 404

    def test_provider_not_found_error_code(self):
        from runsight_api.domain.errors import ProviderNotFound

        assert ProviderNotFound.error_code == "PROVIDER_NOT_FOUND"


# ---------------------------------------------------------------------------
# Tests — backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """raise SubClass("msg") must still work — str(exc) returns the message."""

    def test_run_not_found_str(self):
        from runsight_api.domain.errors import RunNotFound

        err = RunNotFound("run xyz not found")
        assert str(err) == "run xyz not found"

    def test_run_not_found_is_runsight_error(self):
        from runsight_api.domain.errors import RunNotFound, RunsightError

        err = RunNotFound("msg")
        assert isinstance(err, RunsightError)

    def test_run_not_found_is_exception(self):
        from runsight_api.domain.errors import RunNotFound

        err = RunNotFound("msg")
        assert isinstance(err, Exception)

    def test_can_catch_subclass_as_runsight_error(self):
        from runsight_api.domain.errors import RunsightError, WorkflowNotFound

        with pytest.raises(RunsightError):
            raise WorkflowNotFound("wf-1 not found")


# ---------------------------------------------------------------------------
# Tests — error handler returns JSON with request_id
# ---------------------------------------------------------------------------


class TestErrorHandlerStructuredResponse:
    """Error handler uses exc.to_dict() and injects request_id from contextvar."""

    @pytest.mark.asyncio
    async def test_handler_returns_status_from_exc(self):
        from unittest.mock import AsyncMock

        from runsight_api.domain.errors import WorkflowNotFound
        from runsight_api.transport.middleware.error_handler import global_exception_handler

        request = AsyncMock()
        exc = WorkflowNotFound("wf-missing")
        response = await global_exception_handler(request, exc)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_handler_body_contains_error_code(self):
        import json
        from unittest.mock import AsyncMock

        from runsight_api.domain.errors import WorkflowNotFound
        from runsight_api.transport.middleware.error_handler import global_exception_handler

        request = AsyncMock()
        exc = WorkflowNotFound("wf-missing")
        response = await global_exception_handler(request, exc)
        body = json.loads(response.body.decode())
        assert body["error_code"] == "WORKFLOW_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_handler_injects_request_id(self):
        import json
        from unittest.mock import AsyncMock

        from runsight_api.core.context import bind_request_context, request_id
        from runsight_api.domain.errors import RunNotFound
        from runsight_api.transport.middleware.error_handler import global_exception_handler

        bind_request_context("req-handler-test")
        try:
            request = AsyncMock()
            exc = RunNotFound("run-gone")
            response = await global_exception_handler(request, exc)
            body = json.loads(response.body.decode())
            assert body["request_id"] == "req-handler-test"
        finally:
            request_id.set("")

    @pytest.mark.asyncio
    async def test_handler_uses_exc_status_code_not_isinstance(self):
        """ProviderNotFound must get 404 from the handler (was unhandled = 500)."""
        from unittest.mock import AsyncMock

        from runsight_api.domain.errors import ProviderNotFound
        from runsight_api.transport.middleware.error_handler import global_exception_handler

        request = AsyncMock()
        exc = ProviderNotFound("provider xyz")
        response = await global_exception_handler(request, exc)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — unhandled exceptions return 500, no details leaked
# ---------------------------------------------------------------------------


class TestUnhandledExceptionResponse:
    """Unhandled (non-RunsightError) exceptions return 500 with no internals."""

    @pytest.mark.asyncio
    async def test_unhandled_returns_500(self):
        from unittest.mock import AsyncMock

        from runsight_api.transport.middleware.error_handler import global_exception_handler

        request = AsyncMock()
        exc = RuntimeError("secret db password in traceback")
        response = await global_exception_handler(request, exc)
        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_unhandled_does_not_leak_details(self):
        import json
        from unittest.mock import AsyncMock

        from runsight_api.transport.middleware.error_handler import global_exception_handler

        request = AsyncMock()
        exc = RuntimeError("secret db password in traceback")
        response = await global_exception_handler(request, exc)
        body = json.loads(response.body.decode())
        assert body["error"] == "Internal server error"
        assert "secret" not in json.dumps(body)

    @pytest.mark.asyncio
    async def test_unhandled_includes_request_id(self):
        import json
        from unittest.mock import AsyncMock

        from runsight_api.core.context import bind_request_context, request_id
        from runsight_api.transport.middleware.error_handler import global_exception_handler

        bind_request_context("req-unhandled")
        try:
            request = AsyncMock()
            exc = ValueError("oops")
            response = await global_exception_handler(request, exc)
            body = json.loads(response.body.decode())
            assert body["request_id"] == "req-unhandled"
        finally:
            request_id.set("")
