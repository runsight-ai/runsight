"""
Failing tests for RUN-275: tools/ package with ToolInstance, catalog, and registration.

Tests target:
- ToolInstance dataclass: name, description, parameters, execute
- ToolInstance.to_openai_schema(): returns valid OpenAI tool-calling format
- register_builtin(): registers a factory under a source string
- get_builtin(): retrieves registered factory, returns None for unknown
- BUILTIN_TOOL_CATALOG: importable dict
- resolve_tool(): accepts canonical tool IDs only, rejects legacy typed/source-based inputs
"""

from __future__ import annotations

import json
from textwrap import dedent
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from runsight_core.security import SSRFError

# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


async def _dummy_execute(args: dict) -> str:
    """Dummy async execute function for test ToolInstances."""
    return f"executed with {args}"


def _make_dummy_tool_instance():
    """Import ToolInstance and return a basic instance for reuse in tests."""
    from runsight_core.tools import ToolInstance

    return ToolInstance(
        name="test_tool",
        description="A tool for testing",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
        execute=_dummy_execute,
    )


def _write_custom_tool_yaml(base_dir, slug: str, contents: str):
    """Create a custom tool YAML file under custom/tools/ for resolver tests."""
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    content = dedent(contents)
    lines = content.lstrip().splitlines()
    first_key = lines[0].split(":")[0].strip() if lines else ""
    if first_key != "id":
        content = f"id: {slug}\nkind: tool\n" + content
    yaml_path = tools_dir / f"{slug}.yaml"
    yaml_path.write_text(content, encoding="utf-8")
    return yaml_path


# ---------------------------------------------------------------------------
# AC1: ToolInstance — construction and attributes
# ---------------------------------------------------------------------------


class TestToolInstanceConstruction:
    """Tests for ToolInstance creation and field access."""

    def test_tool_instance_has_name(self):
        """ToolInstance stores a name field."""
        ti = _make_dummy_tool_instance()
        assert ti.name == "test_tool"

    def test_tool_instance_has_description(self):
        """ToolInstance stores a description field."""
        ti = _make_dummy_tool_instance()
        assert ti.description == "A tool for testing"

    def test_tool_instance_has_parameters(self):
        """ToolInstance stores a parameters dict (JSON Schema)."""
        ti = _make_dummy_tool_instance()
        assert isinstance(ti.parameters, dict)
        assert ti.parameters["type"] == "object"
        assert "query" in ti.parameters["properties"]

    def test_tool_instance_has_execute_callable(self):
        """ToolInstance stores an async execute callable."""
        ti = _make_dummy_tool_instance()
        assert callable(ti.execute)


# ---------------------------------------------------------------------------
# AC1: ToolInstance.to_openai_schema() — valid OpenAI tool format
# ---------------------------------------------------------------------------


class TestToolInstanceToOpenAISchema:
    """Tests for ToolInstance.to_openai_schema() output format."""

    def test_to_openai_schema_returns_dict(self):
        """to_openai_schema() returns a dict."""
        ti = _make_dummy_tool_instance()
        schema = ti.to_openai_schema()
        assert isinstance(schema, dict)

    def test_to_openai_schema_has_type_function(self):
        """to_openai_schema() has 'type': 'function' at top level."""
        ti = _make_dummy_tool_instance()
        schema = ti.to_openai_schema()
        assert schema["type"] == "function"

    def test_to_openai_schema_has_function_key(self):
        """to_openai_schema() has a 'function' key containing tool metadata."""
        ti = _make_dummy_tool_instance()
        schema = ti.to_openai_schema()
        assert "function" in schema
        assert isinstance(schema["function"], dict)

    def test_to_openai_schema_function_has_name(self):
        """The 'function' dict contains the tool name."""
        ti = _make_dummy_tool_instance()
        schema = ti.to_openai_schema()
        assert schema["function"]["name"] == "test_tool"

    def test_to_openai_schema_function_has_description(self):
        """The 'function' dict contains the tool description."""
        ti = _make_dummy_tool_instance()
        schema = ti.to_openai_schema()
        assert schema["function"]["description"] == "A tool for testing"

    def test_to_openai_schema_function_has_parameters(self):
        """The 'function' dict contains the parameters JSON Schema."""
        ti = _make_dummy_tool_instance()
        schema = ti.to_openai_schema()
        params = schema["function"]["parameters"]
        assert isinstance(params, dict)
        assert params["type"] == "object"
        assert "query" in params["properties"]

    def test_to_openai_schema_full_structure(self):
        """to_openai_schema() matches the complete OpenAI tool format."""
        ti = _make_dummy_tool_instance()
        schema = ti.to_openai_schema()

        expected = {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A tool for testing",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            },
        }
        assert schema == expected


# ---------------------------------------------------------------------------
# AC2: register_builtin + get_builtin round-trip
# ---------------------------------------------------------------------------


class TestRegisterAndGetBuiltin:
    """Tests for register_builtin() and get_builtin() functions."""

    def test_register_builtin_then_get_builtin(self):
        """register_builtin stores a factory; get_builtin retrieves it."""
        from runsight_core.tools import (
            BUILTIN_TOOL_CATALOG,
            get_builtin,
            register_builtin,
        )

        # Use a unique source key to avoid cross-test pollution
        source = "test/roundtrip_tool"

        def factory(**kwargs):
            return _make_dummy_tool_instance()

        # Clean up before and after
        BUILTIN_TOOL_CATALOG.pop(source, None)
        try:
            register_builtin(source, factory)
            retrieved = get_builtin(source)
            assert retrieved is factory
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)

    def test_register_builtin_overwrites_existing(self):
        """Registering the same source twice overwrites the previous factory."""
        from runsight_core.tools import (
            BUILTIN_TOOL_CATALOG,
            get_builtin,
            register_builtin,
        )

        source = "test/overwrite_tool"

        def factory_a(**kwargs):
            pass

        def factory_b(**kwargs):
            pass

        BUILTIN_TOOL_CATALOG.pop(source, None)
        try:
            register_builtin(source, factory_a)
            register_builtin(source, factory_b)
            assert get_builtin(source) is factory_b
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)


# ---------------------------------------------------------------------------
# AC3: get_builtin("nonexistent") returns None
# ---------------------------------------------------------------------------


class TestGetBuiltinUnknown:
    """Tests for get_builtin with unknown source keys."""

    def test_get_builtin_nonexistent_returns_none(self):
        """get_builtin for an unregistered source returns None."""
        from runsight_core.tools import get_builtin

        result = get_builtin("nonexistent/tool_xyz_does_not_exist")
        assert result is None

    def test_get_builtin_empty_string_returns_none(self):
        """get_builtin with empty string returns None."""
        from runsight_core.tools import get_builtin

        result = get_builtin("")
        assert result is None


# ---------------------------------------------------------------------------
# AC10: BUILTIN_TOOL_CATALOG is importable and is a dict
# ---------------------------------------------------------------------------


class TestBuiltinToolCatalog:
    """Tests for the BUILTIN_TOOL_CATALOG module-level dict."""

    def test_catalog_is_importable(self):
        """BUILTIN_TOOL_CATALOG can be imported from runsight_core.tools."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG

        assert BUILTIN_TOOL_CATALOG is not None

    def test_catalog_is_dict(self):
        """BUILTIN_TOOL_CATALOG is a dict."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG

        assert isinstance(BUILTIN_TOOL_CATALOG, dict)


# ---------------------------------------------------------------------------
# AC4: resolve_tool public contract uses canonical tool IDs only
# ---------------------------------------------------------------------------


class TestResolveToolPublicContract:
    """RUN-579: resolve_tool should expose a canonical-ID-only runtime contract."""

    def test_resolve_tool_accepts_reserved_builtin_id(self):
        """Public callers should resolve builtin tools by reserved canonical IDs like http."""
        from runsight_core.tools import ToolInstance, resolve_tool

        result = resolve_tool("http")

        assert isinstance(result, ToolInstance)
        assert result.name == "http_request"

    def test_resolve_tool_accepts_discovered_python_tool_id(self, tmp_path):
        """Public callers should resolve discovered python tools by filename-derived tool ID."""
        from runsight_core.tools import ToolInstance, resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "adder",
            """
            version: "1.0"
            type: custom
            executor: python
            name: Adder
            description: Add integers together.
            parameters:
              type: object
              properties:
                a:
                  type: integer
                b:
                  type: integer
              required:
                - a
                - b
            code: |
              def main(args):
                  return {"sum": args["a"] + args["b"]}
            """,
        )

        result = resolve_tool("adder", base_dir=tmp_path)

        assert isinstance(result, ToolInstance)
        assert result.name == "adder"

    def test_resolve_tool_accepts_discovered_request_tool_id(self, tmp_path):
        """Public callers should resolve request-backed custom tools by canonical ID."""
        from runsight_core.tools import ToolInstance, resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "fetch_answer",
            """
            version: "1.0"
            type: custom
            executor: request
            name: Fetch Answer
            description: Fetch an answer from a remote API.
            parameters:
              type: object
              properties:
                item_id:
                  type: integer
              required:
                - item_id
            request:
              method: GET
              url: https://example.com/items/{{ item_id }}
              response_path: data.answer
            timeout_seconds: 9
            """,
        )

        result = resolve_tool("fetch_answer", base_dir=tmp_path)

        assert isinstance(result, ToolInstance)
        assert result.name == "fetch_answer"

    def test_resolve_tool_missing_discovered_custom_tool_raises_explicit_valueerror(self, tmp_path):
        """Missing canonical custom IDs should fail explicitly instead of falling back."""
        from runsight_core.tools import resolve_tool

        with pytest.raises(ValueError, match=r"Unknown tool id: 'lookup_profile'"):
            resolve_tool("lookup_profile", base_dir=tmp_path)

    def test_resolve_tool_builtin_custom_collision_raises_explicit_valueerror(self, tmp_path):
        """Reserved builtin IDs must stay invalid when custom discovery collides with them."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "http",
            """
            version: "1.0"
            type: custom
            executor: python
            name: Shadow HTTP
            description: Attempts to shadow the reserved builtin ID.
            parameters:
              type: object
            code: |
              def main(args):
                  return args
            """,
        )

        with pytest.raises(ValueError, match=r"reserved builtin tool:http|collision.*http"):
            resolve_tool("http", base_dir=tmp_path)


class TestResolveToolRejectsLegacyInputs:
    """RUN-579: legacy typed defs and leaked source strings should be rejected outright."""

    @pytest.mark.parametrize(
        ("tool_def", "seed_yaml"),
        [
            pytest.param(
                {"factory": "BuiltinToolDef", "kwargs": {"type": "builtin", "source": "http"}},
                None,
                id="builtin-tooldef",
            ),
            pytest.param(
                {"factory": "CustomToolDef", "kwargs": {"type": "custom", "source": "adder"}},
                """
                version: "1.0"
                type: custom
                executor: python
                name: Adder
                description: Add integers together.
                parameters:
                  type: object
                  properties:
                    a:
                      type: integer
                    b:
                      type: integer
                  required:
                    - a
                    - b
                code: |
                  def main(args):
                      return {"sum": args["a"] + args["b"]}
                """,
                id="custom-tooldef",
            ),
            pytest.param(
                {
                    "factory": "HTTPToolDef",
                    "kwargs": {"type": "http", "source": "fetch_answer"},
                },
                """
                version: "1.0"
                type: custom
                executor: request
                name: Fetch Answer
                description: Fetch an answer from a remote API.
                parameters:
                  type: object
                  properties:
                    item_id:
                      type: integer
                  required:
                    - item_id
                request:
                  method: GET
                  url: https://example.com/items/{{ item_id }}
                  response_path: data.answer
                timeout_seconds: 9
                """,
                id="http-tooldef",
            ),
        ],
    )
    def test_rejects_typed_tool_definition_inputs(self, tmp_path, tool_def, seed_yaml):
        """resolve_tool should no longer accept typed workflow definitions at runtime."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml import schema as schema_module

        if seed_yaml is not None:
            _write_custom_tool_yaml(tmp_path, tool_def["kwargs"]["source"], seed_yaml)

        typed_def = getattr(schema_module, tool_def["factory"])(**tool_def["kwargs"])

        with pytest.raises((TypeError, ValueError)):
            resolve_tool(typed_def, base_dir=tmp_path)

    @pytest.mark.parametrize(
        "legacy_source", ["runsight/http", "runsight/file-io", "runsight/delegate"]
    )
    def test_rejects_legacy_builtin_source_strings(self, legacy_source):
        """Legacy source slugs should not leak through the public resolution contract."""
        from runsight_core.tools import resolve_tool

        with pytest.raises((TypeError, ValueError)):
            resolve_tool(legacy_source)


class TestResolveCanonicalPythonTools:
    """RUN-579: canonical python custom IDs should be the only custom runtime path."""

    @pytest.mark.asyncio
    async def test_execute_round_trips_args_through_json_subprocess_contract(self, tmp_path):
        """Resolved python custom tools should execute via the canonical tool ID contract."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "echo_json",
            """
            version: "1.0"
            type: custom
            executor: python
            name: Echo JSON
            description: Return a personalized message.
            parameters:
              type: object
              properties:
                name:
                  type: string
              required:
                - name
            code: |
              def main(args):
                  return {"message": "hello " + args["name"]}
            """,
        )

        tool = resolve_tool("echo_json", base_dir=tmp_path)
        result = await tool.execute({"name": "alice"})

        assert json.loads(result) == {"message": "hello alice"}

    def test_blocked_imports_are_rejected_at_resolve_time(self, tmp_path):
        """Dangerous imports should be rejected before a canonical custom tool is returned."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "blocked_import_tool",
            """
            version: "1.0"
            type: custom
            executor: python
            name: Blocked Import Tool
            description: Imports a blocked module.
            parameters:
              type: object
            code: |
              import os

              def main(args):
                  return {}
            """,
        )

        with pytest.raises(ValueError, match="not allowed"):
            resolve_tool("blocked_import_tool", base_dir=tmp_path)

    def test_blocked_builtins_are_rejected_at_resolve_time(self, tmp_path):
        """Blocked builtins like eval/open/__import__ should be rejected during resolution."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "blocked_builtin_tool",
            """
            version: "1.0"
            type: custom
            executor: python
            name: Blocked Builtin Tool
            description: Uses a blocked builtin.
            parameters:
              type: object
            code: |
              def main(args):
                  eval("1 + 1")
                  return {}
            """,
        )

        with pytest.raises(ValueError, match="not allowed"):
            resolve_tool("blocked_builtin_tool", base_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_timeout_returns_error_string(self, tmp_path):
        """Runaway custom tools should be killed and surfaced as an error string."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "slow_tool",
            """
            version: "1.0"
            type: custom
            executor: python
            name: Slow Tool
            description: Sleeps longer than the timeout.
            parameters:
              type: object
            code: |
              import time

              def main(args):
                  time.sleep(5)
                  return {"done": True}
            """,
        )

        tool = resolve_tool("slow_tool", base_dir=tmp_path, timeout_seconds=1)
        result = await tool.execute({})

        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_code_file_variant_loads_external_python_file(self, tmp_path):
        """code_file metadata should still resolve through canonical discovery IDs."""
        from runsight_core.tools import resolve_tool

        tools_dir = tmp_path / "custom" / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        (tools_dir / "file_backed_impl.py").write_text(
            dedent("""
            def main(args):
                return {"port": args["port"]}
            """),
            encoding="utf-8",
        )
        (tools_dir / "file_backed.yaml").write_text(
            dedent("""
            id: file_backed
            kind: tool
            version: "1.0"
            type: custom
            executor: python
            name: File Backed
            description: Loads code from an external file.
            parameters:
              type: object
              properties:
                port:
                  type: string
              required:
                - port
            code_file: file_backed_impl.py
            """),
            encoding="utf-8",
        )

        tool = resolve_tool("file_backed", base_dir=tmp_path)
        result = await tool.execute({"port": "done"})

        assert json.loads(result) == {"port": "done"}


class TestResolveCanonicalRequestTools:
    """RUN-579: request-backed tools should resolve only from canonical discovered IDs."""

    @pytest.mark.asyncio
    async def test_request_tool_renders_templates_resolves_env_and_extracts_json_path(
        self, monkeypatch, tmp_path
    ):
        """Canonical request tools should render templates and extract configured JSON paths."""
        from runsight_core.tools import resolve_tool

        monkeypatch.setenv("API_TOKEN", "secret-123")
        _write_custom_tool_yaml(
            tmp_path,
            "lookup_profile",
            """
            version: "1.0"
            type: custom
            executor: request
            name: Lookup Profile
            description: Fetch a user profile.
            parameters:
              type: object
              properties:
                user_id:
                  type: string
                note:
                  type: string
              required:
                - user_id
                - note
            request:
              method: POST
              url: https://api.example.com/users/{{ user_id }}
              body_template: '{"token":"${API_TOKEN}","note":"{{ note }}"}'
              response_path: data.profile.name
            """,
        )

        tool = resolve_tool("lookup_profile", base_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"data":{"profile":{"name":"Alice"}}}'
        mock_response.json.return_value = {"data": {"profile": {"name": "Alice"}}}

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await tool.execute({"user_id": "42", "note": "hello"})

        client_instance.request.assert_awaited_once_with(
            "POST",
            "https://api.example.com/users/42",
            headers={},
            content='{"token":"secret-123","note":"hello"}',
        )
        assert json.loads(result) == "Alice"

    @pytest.mark.asyncio
    async def test_request_tool_applies_ssrf_validation_to_rendered_url(self, tmp_path):
        """Rendered URLs should still be blocked by SSRF validation before any request is sent."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "lookup_admin",
            """
            version: "1.0"
            type: custom
            executor: request
            name: Lookup Admin
            description: Fetch an admin page.
            parameters:
              type: object
              properties:
                host:
                  type: string
              required:
                - host
            request:
              method: GET
              url: http://{{ host }}/admin
            """,
        )

        tool = resolve_tool("lookup_admin", base_dir=tmp_path)

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            with pytest.raises(SSRFError):
                await tool.execute({"host": "127.0.0.1"})

        client_instance.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_tool_returns_plain_text_responses_as_is(self, tmp_path):
        """Plain-text request tool responses should still round-trip directly."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "read_page",
            """
            version: "1.0"
            type: custom
            executor: request
            name: Read Page
            description: Read a remote page.
            parameters:
              type: object
              properties: {}
            request:
              method: GET
              url: https://example.com
            """,
        )

        tool = resolve_tool("read_page", base_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "plain text body"

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await tool.execute({})

        assert result == "plain text body"

    @pytest.mark.asyncio
    async def test_request_tool_normalizes_html_into_readable_text(self, tmp_path):
        """HTML responses should be stripped into readable text instead of raw markup."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "read_page",
            """
            version: "1.0"
            type: custom
            executor: request
            name: Read Page
            description: Read a remote page.
            parameters:
              type: object
              properties: {}
            request:
              method: GET
              url: https://example.com
            """,
        )

        tool = resolve_tool("read_page", base_dir=tmp_path)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = """
        <html>
          <body>
            <article>
              <h1>Runsight Docs</h1>
              <p>Ship tools safely.</p>
              <script>console.log("drop me")</script>
            </article>
          </body>
        </html>
        """

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            result = await tool.execute({})

        assert "Runsight Docs" in result
        assert "Ship tools safely." in result
        assert "<html" not in result.lower()
        assert "<script" not in result.lower()
        assert "console.log" not in result

    @pytest.mark.parametrize("location", ["headers", "body_template"])
    @pytest.mark.asyncio
    async def test_request_tool_missing_env_secret_fails_closed_before_request(
        self, tmp_path, location
    ):
        """Missing env-secret placeholders in shared request execution should fail closed."""
        from runsight_core.tools import resolve_tool

        request_block = """
            request:
              method: POST
              url: https://example.com/secure
              headers:
                Authorization: Bearer ${MISSING_API_TOKEN}
              body_template: '{"token":"${MISSING_API_TOKEN}"}'
            """
        if location == "headers":
            request_block = """
            request:
              method: GET
              url: https://example.com/secure
              headers:
                Authorization: Bearer ${MISSING_API_TOKEN}
            """
        elif location == "body_template":
            request_block = """
            request:
              method: POST
              url: https://example.com/secure
              body_template: '{"token":"${MISSING_API_TOKEN}"}'
            """

        _write_custom_tool_yaml(
            tmp_path,
            f"secure_lookup_{location}",
            f"""
            version: "1.0"
            type: custom
            executor: request
            name: Secure Lookup
            description: Fetches a protected resource.
            parameters:
              type: object
              properties: {{}}
            {request_block}
            """,
        )

        tool = resolve_tool(f"secure_lookup_{location}", base_dir=tmp_path)

        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text = '{"ok": true}'
            mock_response.json.return_value = {"ok": True}
            client_instance.request.return_value = mock_response
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = client_instance

            with pytest.raises(ValueError, match=r"MISSING_API_TOKEN"):
                await tool.execute({})

        client_instance.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_tool_oversized_response_invokes_size_policy_and_can_truncate(
        self, tmp_path
    ):
        """Oversized shared request responses should flow through the size policy hook."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "read_large_page",
            """
            version: "1.0"
            type: custom
            executor: request
            name: Read Large Page
            description: Read a large remote page.
            parameters:
              type: object
              properties: {}
            request:
              method: GET
              url: https://example.com/large
            """,
        )

        response_size_policy = Mock(return_value="truncated body")
        tool = resolve_tool(
            "read_large_page",
            base_dir=tmp_path,
            max_output_bytes=5,
            response_size_policy=response_size_policy,
        )

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

            result = await tool.execute({})

        assert result == "truncated body"
        response_size_policy.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_tool_applies_default_size_cap_when_no_explicit_limit_is_passed(
        self, tmp_path
    ):
        """Shared request execution should still cap very large responses when callers use defaults."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "read_large_page",
            """
            version: "1.0"
            type: custom
            executor: request
            name: Read Large Page
            description: Read a large remote page.
            parameters:
              type: object
              properties: {}
            request:
              method: GET
              url: https://example.com/large
            """,
        )

        response_size_policy = Mock(return_value="default-capped body")
        tool = resolve_tool(
            "read_large_page",
            base_dir=tmp_path,
            response_size_policy=response_size_policy,
        )

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

            result = await tool.execute({})

        assert result == "default-capped body"
        response_size_policy.assert_called_once()
        assert response_size_policy.call_args.kwargs["max_output_bytes"] is not None

    @pytest.mark.asyncio
    async def test_request_tool_size_policy_can_fail_closed_for_oversized_response(self, tmp_path):
        """Size policy failures should be surfaced directly with no fallback body return."""
        from runsight_core.tools import resolve_tool

        _write_custom_tool_yaml(
            tmp_path,
            "read_large_page",
            """
            version: "1.0"
            type: custom
            executor: request
            name: Read Large Page
            description: Read a large remote page.
            parameters:
              type: object
              properties: {}
            request:
              method: GET
              url: https://example.com/large
            """,
        )

        response_size_policy = Mock(side_effect=ValueError("response exceeded max_output_bytes"))
        tool = resolve_tool(
            "read_large_page",
            base_dir=tmp_path,
            max_output_bytes=5,
            response_size_policy=response_size_policy,
        )

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

            with pytest.raises(ValueError, match="max_output_bytes"):
                await tool.execute({})

        response_size_policy.assert_called_once()
