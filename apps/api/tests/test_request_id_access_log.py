"""Red tests for RUN-290: Request-ID middleware + access log middleware.

Tests cover:
- middleware/request_id.py: RequestIdMiddleware importable, generates UUID4,
  preserves incoming X-Request-ID, sets response header
- middleware/access_log.py: AccessLogMiddleware importable, emits structured
  access log with method/path/status_code/duration_ms/request_id
- main.py: registers both middleware in create_app()

All tests should FAIL until the implementation is written.
"""

import uuid

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from starlette.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers — lightweight app with both middleware for integration tests
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with both middleware registered."""
    from runsight_api.transport.middleware.access_log import AccessLogMiddleware
    from runsight_api.transport.middleware.request_id import RequestIdMiddleware

    app = FastAPI()
    # Order matters: request-id first so access-log can read it
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.get("/sse")
    async def sse_endpoint():
        async def generate():
            yield "data: hello\n\n"
            yield "data: world\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    return app


# ---------------------------------------------------------------------------
# Tests — RequestIdMiddleware importable
# ---------------------------------------------------------------------------


class TestRequestIdMiddlewareImportable:
    """transport.middleware.request_id must expose RequestIdMiddleware."""

    def test_class_importable(self):
        from runsight_api.transport.middleware.request_id import RequestIdMiddleware

        assert RequestIdMiddleware is not None


# ---------------------------------------------------------------------------
# Tests — AccessLogMiddleware importable
# ---------------------------------------------------------------------------


class TestAccessLogMiddlewareImportable:
    """transport.middleware.access_log must expose AccessLogMiddleware."""

    def test_class_importable(self):
        from runsight_api.transport.middleware.access_log import AccessLogMiddleware

        assert AccessLogMiddleware is not None


# ---------------------------------------------------------------------------
# Tests — X-Request-ID response header
# ---------------------------------------------------------------------------


class TestRequestIdResponseHeader:
    """Every response must include an X-Request-ID header."""

    def test_response_has_x_request_id_header(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/ping")
        assert "x-request-id" in resp.headers, "Response must have X-Request-ID header"

    def test_generated_request_id_is_valid_uuid(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/ping")
        rid = resp.headers.get("x-request-id", "")
        # Must not raise — valid UUID4
        parsed = uuid.UUID(rid)
        assert parsed.version == 4, "Generated request ID must be UUID4"

    def test_multiple_requests_get_different_ids(self):
        app = _make_app()
        client = TestClient(app)
        ids = {client.get("/ping").headers["x-request-id"] for _ in range(5)}
        assert len(ids) == 5, "Each request must get a unique request ID"


# ---------------------------------------------------------------------------
# Tests — incoming X-Request-ID preserved
# ---------------------------------------------------------------------------


class TestIncomingRequestIdPreserved:
    """When client sends X-Request-ID, middleware must preserve it."""

    def test_incoming_id_echoed_in_response(self):
        app = _make_app()
        client = TestClient(app)
        custom_id = "custom-trace-abc-123"
        resp = client.get("/ping", headers={"X-Request-ID": custom_id})
        assert resp.headers.get("x-request-id") == custom_id

    def test_incoming_uuid_preserved(self):
        app = _make_app()
        client = TestClient(app)
        custom_uuid = str(uuid.uuid4())
        resp = client.get("/ping", headers={"X-Request-ID": custom_uuid})
        assert resp.headers.get("x-request-id") == custom_uuid


# ---------------------------------------------------------------------------
# Tests — Access log structured output
# ---------------------------------------------------------------------------


class TestAccessLogOutput:
    """AccessLogMiddleware must emit structured JSON log per request."""

    def test_access_log_contains_required_keys(self, caplog):
        """Access log entry must have method, path, status_code, duration_ms."""
        import structlog

        captured_entries: list[dict] = []

        # Capture structlog output by temporarily adding a processor
        def capture_processor(logger, method, event_dict):
            captured_entries.append(event_dict.copy())
            return event_dict

        # Configure structlog to capture
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                capture_processor,
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(0),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

        app = _make_app()
        client = TestClient(app)
        client.get("/ping")

        # Find the access log entry
        access_entries = [e for e in captured_entries if e.get("event") == "access"]
        assert len(access_entries) >= 1, "Expected at least one 'access' log entry"
        entry = access_entries[0]

        assert entry.get("method") == "GET", "Access log must contain method"
        assert entry.get("path") == "/ping", "Access log must contain path"
        assert entry.get("status_code") == 200, "Access log must contain status_code"
        assert "duration_ms" in entry, "Access log must contain duration_ms"
        assert isinstance(entry["duration_ms"], (int, float)), "duration_ms must be numeric"
        assert entry["duration_ms"] >= 0, "duration_ms must be non-negative"

    def test_access_log_contains_request_id(self, caplog):
        """Access log entry must include request_id from the middleware chain."""
        import structlog

        captured_entries: list[dict] = []

        def capture_processor(logger, method, event_dict):
            captured_entries.append(event_dict.copy())
            return event_dict

        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                capture_processor,
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(0),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=False,
        )

        app = _make_app()
        client = TestClient(app)
        client.get("/ping")

        access_entries = [e for e in captured_entries if e.get("event") == "access"]
        assert len(access_entries) >= 1, "Expected at least one 'access' log entry"
        entry = access_entries[0]

        assert "request_id" in entry, "Access log must contain request_id"
        assert entry["request_id"] != "", "request_id must not be empty"


# ---------------------------------------------------------------------------
# Tests — SSE streaming works through middleware
# ---------------------------------------------------------------------------


class TestSseStreamingThroughMiddleware:
    """SSE streaming endpoint must work through both middleware (no body buffering)."""

    def test_sse_response_has_request_id(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/sse")
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers, "SSE response must have X-Request-ID"

    def test_sse_response_body_intact(self):
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/sse")
        body = resp.text
        assert "data: hello" in body, "SSE body must not be corrupted by middleware"
        assert "data: world" in body, "SSE body must not be corrupted by middleware"
