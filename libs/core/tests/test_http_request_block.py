"""
RUN-214 — Red tests: HttpRequestBlock core implementation.

These tests cover the full execute() implementation:
1. Template resolution — {{block_id}} → state.results[block_id].output
2. SSRF protection — private IP blocking, allow_private_ips bypass
3. Auth header generation — bearer, api_key, basic, none
4. HTTP execution — GET/POST/PUT/DELETE, custom headers, timeout
5. Response handling — JSON auto-parse, raw text, metadata
6. Status code validation — 2xx pass, 4xx/5xx error, expected_status_codes override
7. Retry logic — retry on 5xx, no retry on 4xx

All tests MUST fail because execute() raises NotImplementedError.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx

from runsight_core.blocks.http_request import HttpRequestBlock
from runsight_core.state import BlockResult, WorkflowState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**results: str) -> WorkflowState:
    """Build a WorkflowState with string results keyed by block_id."""
    return WorkflowState(results={k: BlockResult(output=v) for k, v in results.items()})


def _make_block(
    block_id: str = "http1",
    url: str = "https://api.example.com/data",
    method: str = "GET",
    **kwargs,
) -> HttpRequestBlock:
    """Create an HttpRequestBlock with sensible defaults."""
    return HttpRequestBlock(block_id=block_id, url=url, method=method, **kwargs)


async def _execute_must_not_raise_not_implemented(block, state):
    """Call execute() and ensure NotImplementedError is not raised.

    If NotImplementedError fires, it means execute() is still a stub — the
    test should fail because the implementation doesn't exist yet.
    """
    try:
        return await block.execute(state)
    except NotImplementedError:
        pytest.fail(
            f"execute() raised NotImplementedError — implementation missing (block={block.block_id})"
        )


async def _execute_expecting_error(block, state):
    """Call execute() expecting a domain-specific error (NOT NotImplementedError).

    Returns the raised exception for further assertions, or fails if
    NotImplementedError fires (meaning the stub hasn't been replaced).
    """
    try:
        await block.execute(state)
    except NotImplementedError:
        pytest.fail(
            f"execute() raised NotImplementedError — implementation missing (block={block.block_id})"
        )
    except Exception as exc:
        return exc
    else:
        pytest.fail("execute() should have raised an error but returned successfully")


# ===========================================================================
# Template Resolution
# ===========================================================================


class TestTemplateResolution:
    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_simple_variable(self):
        """{{step_1}} in URL resolves to state.results['step_1'].output."""
        respx.get("https://api.example.com/hello").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        block = _make_block(url="https://api.example.com/{{step_1}}")
        state = _make_state(step_1="hello")

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert result.results[block.block_id].output is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_multiple_variables(self):
        """URL with multiple {{...}} placeholders all resolve."""
        respx.get("https://api.example.com/v2/users/42").mock(
            return_value=httpx.Response(200, json={"id": 42})
        )
        block = _make_block(url="https://api.example.com/{{version}}/users/{{user_id}}")
        state = _make_state(version="v2", user_id="42")

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert result.results[block.block_id].output is not None

    @pytest.mark.asyncio
    async def test_resolve_missing_variable_raises(self):
        """Unknown template variable raises a domain error (not NotImplementedError)."""
        block = _make_block(url="https://api.example.com/{{unknown_var}}")
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert "unknown_var" in str(exc).lower() or "template" in str(exc).lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_no_templates(self):
        """Plain URL without templates passes through unchanged."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "ok"})
        )
        block = _make_block(url="https://api.example.com/data")
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert result.results[block.block_id].output is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_resolve_partial_template(self):
        """Partial template '{{' without '}}' is left as-is."""
        respx.get("https://api.example.com/data?q={{incomplete").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        block = _make_block(url="https://api.example.com/data?q={{incomplete")
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert result.results[block.block_id].output is not None


# ===========================================================================
# SSRF Protection
# ===========================================================================


class TestSSRFProtection:
    @pytest.mark.asyncio
    async def test_ssrf_blocks_localhost(self):
        """http://localhost must be blocked when allow_private_ips=False."""
        block = _make_block(url="http://localhost/secret", allow_private_ips=False)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        # Error message should mention SSRF, private IP, or the blocked address
        assert exc is not None

    @pytest.mark.asyncio
    async def test_ssrf_blocks_private_10(self):
        """http://10.0.0.1 must be blocked when allow_private_ips=False."""
        block = _make_block(url="http://10.0.0.1/internal", allow_private_ips=False)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert exc is not None

    @pytest.mark.asyncio
    async def test_ssrf_blocks_private_172(self):
        """http://172.16.0.1 must be blocked when allow_private_ips=False."""
        block = _make_block(url="http://172.16.0.1/admin", allow_private_ips=False)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert exc is not None

    @pytest.mark.asyncio
    async def test_ssrf_blocks_private_192(self):
        """http://192.168.1.1 must be blocked when allow_private_ips=False."""
        block = _make_block(url="http://192.168.1.1/config", allow_private_ips=False)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert exc is not None

    @pytest.mark.asyncio
    async def test_ssrf_blocks_link_local(self):
        """http://169.254.169.254 (AWS metadata) must be blocked."""
        block = _make_block(url="http://169.254.169.254/latest/meta-data", allow_private_ips=False)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert exc is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_ssrf_allows_public_ip(self):
        """Public IP (e.g., 8.8.8.8) must be allowed."""
        respx.get("http://8.8.8.8/api").mock(return_value=httpx.Response(200, json={"dns": True}))
        block = _make_block(url="http://8.8.8.8/api", allow_private_ips=False)
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert result.results[block.block_id].output is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_ssrf_bypass_with_flag(self):
        """allow_private_ips=True allows localhost."""
        respx.get("http://localhost/api").mock(
            return_value=httpx.Response(200, json={"local": True})
        )
        block = _make_block(url="http://localhost/api", allow_private_ips=True)
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert result.results[block.block_id].output is not None

    @pytest.mark.asyncio
    async def test_ssrf_blocks_ipv6_loopback(self):
        """http://[::1] must be blocked when allow_private_ips=False."""
        block = _make_block(url="http://[::1]/secret", allow_private_ips=False)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert exc is not None


# ===========================================================================
# Auth
# ===========================================================================


class TestAuth:
    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_bearer(self):
        """Bearer auth adds Authorization: Bearer <token> header."""
        route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"auth": "ok"})
        )
        block = _make_block(
            auth_type="bearer",
            auth_config={"token": "my-secret-token"},
        )
        state = _make_state()

        await _execute_must_not_raise_not_implemented(block, state)

        # Verify the request was made with the correct auth header
        assert route.called
        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer my-secret-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_api_key_header(self):
        """API key auth adds custom header with the key value."""
        route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"auth": "ok"})
        )
        block = _make_block(
            auth_type="api_key",
            auth_config={"header": "X-API-Key", "value": "secret-key-123"},
        )
        state = _make_state()

        await _execute_must_not_raise_not_implemented(block, state)

        assert route.called
        request = route.calls.last.request
        assert request.headers["X-API-Key"] == "secret-key-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_basic(self):
        """Basic auth adds Authorization: Basic <base64(user:pass)> header."""
        route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"auth": "ok"})
        )
        block = _make_block(
            auth_type="basic",
            auth_config={"username": "admin", "password": "p@ssw0rd"},
        )
        state = _make_state()

        await _execute_must_not_raise_not_implemented(block, state)

        assert route.called
        request = route.calls.last.request
        expected = base64.b64encode(b"admin:p@ssw0rd").decode()
        assert request.headers["Authorization"] == f"Basic {expected}"

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_none(self):
        """No auth_type means no Authorization header added."""
        route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        block = _make_block(auth_type=None)
        state = _make_state()

        await _execute_must_not_raise_not_implemented(block, state)

        assert route.called
        request = route.calls.last.request
        assert "Authorization" not in request.headers


# ===========================================================================
# Request Execution
# ===========================================================================


class TestRequestExecution:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_json_response(self):
        """GET request returns parsed JSON as output."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(
                200,
                json={"message": "hello", "count": 42},
                headers={"Content-Type": "application/json"},
            )
        )
        block = _make_block(method="GET")
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        block_result = result.results[block.block_id]
        parsed = json.loads(block_result.output)
        assert parsed["message"] == "hello"
        assert parsed["count"] == 42

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_with_json_body(self):
        """POST sends JSON body and returns response."""
        route = respx.post("https://api.example.com/data").mock(
            return_value=httpx.Response(
                201,
                json={"id": 1, "created": True},
                headers={"Content-Type": "application/json"},
            )
        )
        block = _make_block(
            method="POST",
            body='{"name": "test"}',
            body_type="json",
        )
        state = _make_state()

        result_state = await _execute_must_not_raise_not_implemented(block, state)

        assert route.called
        block_result = result_state.results[block.block_id]
        parsed = json.loads(block_result.output)
        assert parsed["created"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_put_request(self):
        """PUT request works correctly."""
        route = respx.put("https://api.example.com/data").mock(
            return_value=httpx.Response(
                200,
                json={"updated": True},
                headers={"Content-Type": "application/json"},
            )
        )
        block = _make_block(
            method="PUT",
            body='{"name": "updated"}',
            body_type="json",
        )
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert route.called
        block_result = result.results[block.block_id]
        parsed = json.loads(block_result.output)
        assert parsed["updated"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_request(self):
        """DELETE request works correctly."""
        route = respx.delete("https://api.example.com/data").mock(return_value=httpx.Response(204))
        block = _make_block(method="DELETE")
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert route.called
        assert result.results[block.block_id] is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_custom_headers(self):
        """Custom headers are sent with the request."""
        route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        block = _make_block(
            headers={"X-Custom-Header": "custom-value", "Accept-Language": "en-US"},
        )
        state = _make_state()

        await _execute_must_not_raise_not_implemented(block, state)

        assert route.called
        request = route.calls.last.request
        assert request.headers["X-Custom-Header"] == "custom-value"
        assert request.headers["Accept-Language"] == "en-US"

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_raises(self):
        """Request that exceeds timeout raises a domain error (not NotImplementedError)."""
        respx.get("https://api.example.com/slow").mock(
            side_effect=httpx.ReadTimeout("read timed out")
        )
        block = _make_block(url="https://api.example.com/slow", timeout_seconds=1)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert "timeout" in str(exc).lower() or "timed out" in str(exc).lower()


# ===========================================================================
# Response Handling
# ===========================================================================


class TestResponseHandling:
    @pytest.mark.asyncio
    @respx.mock
    async def test_json_content_type_parsed(self):
        """Response with Content-Type: application/json is auto-parsed to formatted JSON string."""
        payload = {"key": "value", "nested": {"a": 1}}
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(
                200,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        )
        block = _make_block()
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        block_result = result.results[block.block_id]
        parsed = json.loads(block_result.output)
        assert parsed == payload

    @pytest.mark.asyncio
    @respx.mock
    async def test_text_content_type_raw(self):
        """Non-JSON response is stored as raw text."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(
                200,
                text="Hello, plain text response",
                headers={"Content-Type": "text/plain"},
            )
        )
        block = _make_block()
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        block_result = result.results[block.block_id]
        assert block_result.output == "Hello, plain text response"

    @pytest.mark.asyncio
    @respx.mock
    async def test_metadata_contains_status_code(self):
        """BlockResult metadata includes status_code."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        block = _make_block()
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        block_result = result.results[block.block_id]
        assert block_result.metadata is not None
        assert block_result.metadata["status_code"] == 200

    @pytest.mark.asyncio
    @respx.mock
    async def test_metadata_contains_headers(self):
        """BlockResult metadata includes response headers."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(
                200,
                json={"ok": True},
                headers={"X-Request-Id": "abc-123", "Content-Type": "application/json"},
            )
        )
        block = _make_block()
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        block_result = result.results[block.block_id]
        assert block_result.metadata is not None
        assert "headers" in block_result.metadata
        assert block_result.metadata["headers"]["x-request-id"] == "abc-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_metadata_contains_latency(self):
        """BlockResult metadata includes latency_ms."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        block = _make_block()
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        block_result = result.results[block.block_id]
        assert block_result.metadata is not None
        assert "latency_ms" in block_result.metadata
        assert isinstance(block_result.metadata["latency_ms"], (int, float))
        assert block_result.metadata["latency_ms"] >= 0


# ===========================================================================
# Status Code Validation
# ===========================================================================


class TestStatusCodeValidation:
    @pytest.mark.asyncio
    @respx.mock
    async def test_2xx_success_200(self):
        """HTTP 200 is treated as success."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        block = _make_block()
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert result.results[block.block_id].metadata["status_code"] == 200

    @pytest.mark.asyncio
    @respx.mock
    async def test_2xx_success_201(self):
        """HTTP 201 is treated as success."""
        respx.post("https://api.example.com/data").mock(
            return_value=httpx.Response(201, json={"created": True})
        )
        block = _make_block(method="POST", body='{"x": 1}')
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert result.results[block.block_id].metadata["status_code"] == 201

    @pytest.mark.asyncio
    @respx.mock
    async def test_2xx_success_204(self):
        """HTTP 204 is treated as success."""
        respx.delete("https://api.example.com/data").mock(return_value=httpx.Response(204))
        block = _make_block(method="DELETE")
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        assert result.results[block.block_id].metadata["status_code"] == 204

    @pytest.mark.asyncio
    @respx.mock
    async def test_4xx_raises_400(self):
        """HTTP 400 raises a domain error (not NotImplementedError)."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(400, json={"error": "bad request"})
        )
        block = _make_block()
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert "400" in str(exc) or "bad request" in str(exc).lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_4xx_raises_404(self):
        """HTTP 404 raises a domain error (not NotImplementedError)."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(404, json={"error": "not found"})
        )
        block = _make_block()
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert "404" in str(exc) or "not found" in str(exc).lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_5xx_raises_500(self):
        """HTTP 500 raises a domain error (after retries exhausted)."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(500, json={"error": "internal"})
        )
        block = _make_block(retry_count=0)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert "500" in str(exc) or "server" in str(exc).lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_5xx_raises_503(self):
        """HTTP 503 raises a domain error (after retries exhausted)."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )
        block = _make_block(retry_count=0)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert "503" in str(exc) or "unavailable" in str(exc).lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_expected_status_overrides(self):
        """expected_status_codes=[404] makes 404 pass without error."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(
                404,
                json={"error": "not found"},
                headers={"Content-Type": "application/json"},
            )
        )
        block = _make_block(expected_status_codes=[404])
        state = _make_state()

        result = await _execute_must_not_raise_not_implemented(block, state)

        block_result = result.results[block.block_id]
        assert block_result.metadata["status_code"] == 404


# ===========================================================================
# Retry
# ===========================================================================


class TestRetry:
    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_5xx(self):
        """retry_count=2 with 500 response -> 3 total attempts (1 + 2 retries)."""
        route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(500, json={"error": "server error"})
        )
        block = _make_block(retry_count=2)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert exc is not None
        assert route.call_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_retry_on_4xx(self):
        """4xx errors should NOT trigger retry — only 1 attempt."""
        route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(400, json={"error": "bad request"})
        )
        block = _make_block(retry_count=2)
        state = _make_state()

        exc = await _execute_expecting_error(block, state)
        assert exc is not None
        assert route.call_count == 1
