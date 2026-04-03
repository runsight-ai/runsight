"""
Failing tests for RUN-276: built-in tools http, file_io, delegate.

Tests target:
- HTTP tool: factory returns ToolInstance(name="http_request"), executes httpx
  requests, SSRF blocks private IPs, parameters schema correct.
- File I/O tool: factory returns ToolInstance(name="file_io"), reads/writes files,
  rejects path traversal, parameters schema correct.
- Delegate tool: factory accepts exits list, returns ToolInstance(name="delegate"),
  parameters schema has port enum from exit IDs, valid/invalid port handling.
- Catalog registration: all three registered in BUILTIN_TOOL_CATALOG.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from runsight_core.security import SSRFError
from runsight_core.tools import BUILTIN_TOOL_CATALOG, ToolInstance
from runsight_core.yaml.schema import ExitDef

# ===========================================================================
# AC5: Catalog registration — all three tools registered
# ===========================================================================


class TestCatalogRegistration:
    """All three built-in tools are registered in BUILTIN_TOOL_CATALOG."""

    def test_http_registered(self):
        """'http' is a key in BUILTIN_TOOL_CATALOG."""
        from runsight_core.tools.http import create_http_tool  # noqa: F401 — side effect

        assert "http" in BUILTIN_TOOL_CATALOG

    def test_file_io_registered(self):
        """'file_io' is a key in BUILTIN_TOOL_CATALOG."""
        from runsight_core.tools.file_io import create_file_io_tool  # noqa: F401

        assert "file_io" in BUILTIN_TOOL_CATALOG

    def test_delegate_registered(self):
        """'delegate' is a key in BUILTIN_TOOL_CATALOG."""
        from runsight_core.tools.delegate import create_delegate_tool  # noqa: F401

        assert "delegate" in BUILTIN_TOOL_CATALOG

    @pytest.mark.parametrize(
        "legacy_source",
        ["runsight/http", "runsight/file-io", "runsight/delegate"],
    )
    def test_legacy_builtin_aliases_are_not_registered(self, legacy_source: str):
        """Legacy builtin aliases must not remain in the internal registry."""
        from runsight_core.tools.delegate import create_delegate_tool  # noqa: F401
        from runsight_core.tools.file_io import create_file_io_tool  # noqa: F401
        from runsight_core.tools.http import create_http_tool  # noqa: F401

        assert legacy_source not in BUILTIN_TOOL_CATALOG


# ===========================================================================
# AC1: runsight/http — HTTP tool
# ===========================================================================


class TestHttpToolFactory:
    """HTTP tool factory returns a properly configured ToolInstance."""

    def test_factory_returns_tool_instance(self):
        """create_http_tool() returns a ToolInstance."""
        from runsight_core.tools.http import create_http_tool

        tool = create_http_tool()
        assert isinstance(tool, ToolInstance)

    def test_tool_name_is_http_request(self):
        """The HTTP tool's LLM name is 'http_request'."""
        from runsight_core.tools.http import create_http_tool

        tool = create_http_tool()
        assert tool.name == "http_request"

    def test_parameters_schema_has_method(self):
        """Parameters JSON schema includes 'method'."""
        from runsight_core.tools.http import create_http_tool

        tool = create_http_tool()
        assert "method" in tool.parameters["properties"]

    def test_parameters_schema_has_url(self):
        """Parameters JSON schema includes 'url'."""
        from runsight_core.tools.http import create_http_tool

        tool = create_http_tool()
        assert "url" in tool.parameters["properties"]

    def test_parameters_schema_has_headers(self):
        """Parameters JSON schema includes 'headers'."""
        from runsight_core.tools.http import create_http_tool

        tool = create_http_tool()
        assert "headers" in tool.parameters["properties"]

    def test_parameters_schema_has_body(self):
        """Parameters JSON schema includes 'body'."""
        from runsight_core.tools.http import create_http_tool

        tool = create_http_tool()
        assert "body" in tool.parameters["properties"]

    def test_parameters_schema_requires_method_and_url(self):
        """Method and url are required parameters."""
        from runsight_core.tools.http import create_http_tool

        tool = create_http_tool()
        required = tool.parameters.get("required", [])
        assert "method" in required
        assert "url" in required

    def test_openai_schema_name(self):
        """to_openai_schema() exposes name='http_request'."""
        from runsight_core.tools.http import create_http_tool

        tool = create_http_tool()
        schema = tool.to_openai_schema()
        assert schema["function"]["name"] == "http_request"


class TestHttpToolExecute:
    """HTTP tool execute function: canonical request behavior."""

    @pytest.mark.asyncio
    async def test_execute_get_returns_normalized_json_payload(self):
        """JSON responses should return the shared normalized payload, not the legacy wrapper."""
        from runsight_core.tools import resolve_tool

        tool = resolve_tool("http")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"ok": true}'
        mock_response.json.return_value = {"ok": True}

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await tool.execute({"method": "GET", "url": "https://example.com/api"})

        parsed = json.loads(result)
        assert parsed == {"ok": True}

    @pytest.mark.asyncio
    async def test_execute_text_response_returns_plain_text_without_wrapper(self):
        """Plain-text responses should round-trip directly without the legacy JSON envelope."""
        from runsight_core.tools import resolve_tool

        tool = resolve_tool("http")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "hello"

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await tool.execute({"method": "GET", "url": "https://example.com"})

        assert result == "hello"

    @pytest.mark.asyncio
    async def test_execute_html_response_returns_readable_text_without_markup(self):
        """Builtin http should normalize HTML into readable text before returning it."""
        from runsight_core.tools import resolve_tool

        tool = resolve_tool("http")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = """
        <html>
          <body>
            <main>
              <h1>Runsight Docs</h1>
              <p>Keep tool output bounded.</p>
              <script>console.log("drop me")</script>
            </main>
          </body>
        </html>
        """

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await tool.execute({"method": "GET", "url": "https://example.com/docs"})

        assert "Runsight Docs" in result
        assert "Keep tool output bounded." in result
        assert "<html" not in result.lower()
        assert "<script" not in result.lower()
        assert "console.log" not in result

    @pytest.mark.asyncio
    async def test_execute_post_with_body_returns_normalized_json_payload(self):
        """POST responses should preserve the shared JSON payload contract as well."""
        from runsight_core.tools import resolve_tool

        tool = resolve_tool("http")

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"created": true}'
        mock_response.json.return_value = {"created": True}

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await tool.execute(
                {
                    "method": "POST",
                    "url": "https://example.com/api",
                    "body": '{"key": "value"}',
                }
            )

        parsed = json.loads(result)
        assert parsed == {"created": True}

    @pytest.mark.asyncio
    async def test_execute_ssrf_blocks_private_ip(self):
        """Private IP targets should fail closed before any outbound request is sent."""
        from runsight_core.tools import resolve_tool

        tool = resolve_tool("http")

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            with pytest.raises(SSRFError):
                await tool.execute({"method": "GET", "url": "http://192.168.1.1/admin"})

        client_instance.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_dns_resolution_failure_raises_ssrf_and_skips_request(self):
        """DNS lookup failures must fail closed before any outbound request is made."""
        from runsight_core.tools import resolve_tool

        tool = resolve_tool("http")
        fake_loop = Mock()
        fake_loop.getaddrinfo = AsyncMock(side_effect=OSError("temporary DNS failure"))
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"ok": true}'

        with patch("runsight_core.security.asyncio.get_running_loop", return_value=fake_loop):
            with patch("httpx.AsyncClient") as MockClient:
                client_instance = AsyncMock()
                client_instance.request.return_value = mock_response
                client_instance.__aenter__ = AsyncMock(return_value=client_instance)
                client_instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = client_instance

                with pytest.raises(SSRFError):
                    await tool.execute({"method": "GET", "url": "https://provider.example/api"})

                client_instance.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_oversized_response_uses_response_size_policy(self):
        """Builtin http should route oversized responses through the shared size policy hook."""
        from runsight_core.tools import resolve_tool

        response_size_policy = Mock(return_value="truncated body")
        tool = resolve_tool("http", max_output_bytes=5, response_size_policy=response_size_policy)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "0123456789"

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await tool.execute({"method": "GET", "url": "https://example.com"})

        assert result == "truncated body"
        response_size_policy.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_uses_default_size_cap_when_no_explicit_limit_is_provided(self):
        """Builtin http should still apply a default cap so callers are not responsible for safety."""
        from runsight_core.tools import resolve_tool

        response_size_policy = Mock(return_value="default-capped body")
        tool = resolve_tool("http", response_size_policy=response_size_policy)

        large_html = "<html><body>" + ("Alpha " * 300_000) + "</body></html>"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = large_html

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await tool.execute({"method": "GET", "url": "https://example.com/huge"})

        assert result == "default-capped body"
        response_size_policy.assert_called_once()
        assert response_size_policy.call_args.kwargs["max_output_bytes"] is not None


# ===========================================================================
# AC2: runsight/file-io — File I/O tool
# ===========================================================================


class TestFileIoToolFactory:
    """File I/O tool factory returns a properly configured ToolInstance."""

    def test_factory_returns_tool_instance(self):
        """create_file_io_tool() returns a ToolInstance."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool()
        assert isinstance(tool, ToolInstance)

    def test_tool_name_is_file_io(self):
        """The file I/O tool's LLM name is 'file_io'."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool()
        assert tool.name == "file_io"

    def test_parameters_schema_has_action(self):
        """Parameters schema includes 'action'."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool()
        assert "action" in tool.parameters["properties"]

    def test_parameters_action_has_enum(self):
        """The 'action' parameter has enum constraint: ['read', 'write']."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool()
        action_schema = tool.parameters["properties"]["action"]
        assert "enum" in action_schema
        assert set(action_schema["enum"]) == {"read", "write"}

    def test_parameters_schema_has_path(self):
        """Parameters schema includes 'path'."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool()
        assert "path" in tool.parameters["properties"]

    def test_parameters_schema_has_content(self):
        """Parameters schema includes 'content'."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool()
        assert "content" in tool.parameters["properties"]

    def test_parameters_schema_requires_action_and_path(self):
        """Action and path are required parameters."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool()
        required = tool.parameters.get("required", [])
        assert "action" in required
        assert "path" in required


class TestFileIoToolExecute:
    """File I/O tool execute: read/write with path traversal protection."""

    @pytest.mark.asyncio
    async def test_read_returns_file_content(self, tmp_path: Path):
        """Read action returns the content of an existing file."""
        from runsight_core.tools.file_io import create_file_io_tool

        target = tmp_path / "hello.txt"
        target.write_text("hello world")

        tool = create_file_io_tool(base_dir=str(tmp_path))
        result = await tool.execute({"action": "read", "path": "hello.txt"})

        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_write_creates_file(self, tmp_path: Path):
        """Write action creates a file with the given content."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool(base_dir=str(tmp_path))
        await tool.execute(
            {
                "action": "write",
                "path": "output.txt",
                "content": "written by tool",
            }
        )

        target = tmp_path / "output.txt"
        assert target.exists()
        assert target.read_text() == "written by tool"

    @pytest.mark.asyncio
    async def test_write_returns_confirmation(self, tmp_path: Path):
        """Write action returns a confirmation string."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool(base_dir=str(tmp_path))
        result = await tool.execute(
            {
                "action": "write",
                "path": "out.txt",
                "content": "data",
            }
        )

        # Confirmation should be a non-empty string (not the file content itself)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_path_traversal_rejected_dotdot(self, tmp_path: Path):
        """Path traversal with '../' is rejected."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool(base_dir=str(tmp_path))

        with pytest.raises((ValueError, PermissionError)):
            await tool.execute({"action": "read", "path": "../../../etc/passwd"})

    @pytest.mark.asyncio
    async def test_path_traversal_rejected_absolute(self, tmp_path: Path):
        """Absolute path outside base_dir is rejected."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool(base_dir=str(tmp_path))

        with pytest.raises((ValueError, PermissionError)):
            await tool.execute({"action": "read", "path": "/etc/passwd"})

    @pytest.mark.asyncio
    async def test_read_nonexistent_file_returns_error(self, tmp_path: Path):
        """Reading a file that doesn't exist returns an error (not crash)."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool(base_dir=str(tmp_path))

        # Should either raise or return error string — not an unhandled exception
        try:
            result = await tool.execute({"action": "read", "path": "nonexistent.txt"})
            # If it returns a string, it should indicate an error
            assert "error" in result.lower() or "not found" in result.lower()
        except FileNotFoundError:
            pass  # Also acceptable


# ===========================================================================
# AC3 + AC4: runsight/delegate — Delegate tool
# ===========================================================================


class TestDelegateToolFactory:
    """Delegate tool factory returns a properly configured ToolInstance."""

    def test_factory_returns_tool_instance(self):
        """create_delegate_tool(exits) returns a ToolInstance."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="done", label="Done"), ExitDef(id="retry", label="Retry")]
        tool = create_delegate_tool(exits=exits)
        assert isinstance(tool, ToolInstance)

    def test_tool_name_is_delegate(self):
        """The delegate tool's LLM name is 'delegate'."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="done", label="Done")]
        tool = create_delegate_tool(exits=exits)
        assert tool.name == "delegate"

    def test_parameters_schema_has_port(self):
        """Parameters schema includes 'port'."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="done", label="Done")]
        tool = create_delegate_tool(exits=exits)
        assert "port" in tool.parameters["properties"]


class TestDelegateToolSchemaEnum:
    """AC4: Delegate tool JSON schema has enum constraint from exits."""

    def test_port_enum_from_exit_ids(self):
        """The port parameter enum is built from exit IDs."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [
            ExitDef(id="done", label="Done"),
            ExitDef(id="retry", label="Retry"),
            ExitDef(id="escalate", label="Escalate"),
        ]
        tool = create_delegate_tool(exits=exits)
        port_schema = tool.parameters["properties"]["port"]

        assert "enum" in port_schema
        assert set(port_schema["enum"]) == {"done", "retry", "escalate"}

    def test_port_enum_single_exit(self):
        """A single exit produces a single-element enum."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="only_exit", label="Only Exit")]
        tool = create_delegate_tool(exits=exits)
        port_schema = tool.parameters["properties"]["port"]

        assert port_schema["enum"] == ["only_exit"]

    def test_openai_schema_contains_port_enum(self):
        """to_openai_schema() exposes the port enum in parameters."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="a", label="A"), ExitDef(id="b", label="B")]
        tool = create_delegate_tool(exits=exits)
        schema = tool.to_openai_schema()
        port_schema = schema["function"]["parameters"]["properties"]["port"]

        assert set(port_schema["enum"]) == {"a", "b"}

    def test_empty_exits_no_enum(self):
        """With no exits, the port field has no enum constraint (or empty enum)."""
        from runsight_core.tools.delegate import create_delegate_tool

        tool = create_delegate_tool(exits=[])
        port_schema = tool.parameters["properties"]["port"]

        # Either no enum key, or enum is empty list
        if "enum" in port_schema:
            assert port_schema["enum"] == []


class TestDelegateToolExecute:
    """Delegate tool execute: port validation and return."""

    @pytest.mark.asyncio
    async def test_valid_port_returns_port_string(self):
        """Execute with a valid port returns the port string."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="done", label="Done"), ExitDef(id="retry", label="Retry")]
        tool = create_delegate_tool(exits=exits)
        result = await tool.execute({"port": "done"})

        assert result == "done"

    @pytest.mark.asyncio
    async def test_another_valid_port(self):
        """Execute with another valid port returns that port string."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="done", label="Done"), ExitDef(id="retry", label="Retry")]
        tool = create_delegate_tool(exits=exits)
        result = await tool.execute({"port": "retry"})

        assert result == "retry"

    @pytest.mark.asyncio
    async def test_invalid_port_returns_error(self):
        """Execute with an invalid port returns an error string (not crash)."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="done", label="Done")]
        tool = create_delegate_tool(exits=exits)
        result = await tool.execute({"port": "nonexistent"})

        # Should return an error string, not the port
        assert isinstance(result, str)
        assert (
            "nonexistent" not in result or "error" in result.lower() or "invalid" in result.lower()
        )

    @pytest.mark.asyncio
    async def test_invalid_port_does_not_raise(self):
        """Execute with an invalid port does not raise — returns error string."""
        from runsight_core.tools.delegate import create_delegate_tool

        exits = [ExitDef(id="done", label="Done")]
        tool = create_delegate_tool(exits=exits)

        # Should not raise
        result = await tool.execute({"port": "unknown_port"})
        assert isinstance(result, str)
