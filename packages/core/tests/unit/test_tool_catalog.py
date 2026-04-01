"""
Failing tests for RUN-275: tools/ package with ToolInstance, catalog, and registration.

Tests target:
- ToolInstance dataclass: name, description, parameters, execute
- ToolInstance.to_openai_schema(): returns valid OpenAI tool-calling format
- register_builtin(): registers a factory under a source string
- get_builtin(): retrieves registered factory, returns None for unknown
- BUILTIN_TOOL_CATALOG: importable dict
- resolve_tool(): given a ToolDef, looks up source, calls factory, returns ToolInstance
"""

from __future__ import annotations

import json
from textwrap import dedent

import pytest

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
    yaml_path = tools_dir / f"{slug}.yaml"
    yaml_path.write_text(dedent(contents), encoding="utf-8")
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
# AC4: resolve_tool with valid source returns ToolInstance
# ---------------------------------------------------------------------------


class TestResolveTool:
    """Tests for resolve_tool() function."""

    def test_resolve_tool_with_valid_source(self):
        """resolve_tool looks up the ToolDef.source in catalog and returns a ToolInstance."""
        from runsight_core.tools import (
            BUILTIN_TOOL_CATALOG,
            ToolInstance,
            register_builtin,
            resolve_tool,
        )
        from runsight_core.yaml.schema import ToolDef

        source = "test/resolve_valid"

        def factory(**kwargs):
            return ToolInstance(
                name="resolved_tool",
                description="A resolved tool",
                parameters={"type": "object", "properties": {}},
                execute=_dummy_execute,
            )

        BUILTIN_TOOL_CATALOG.pop(source, None)
        try:
            register_builtin(source, factory)
            tool_def = ToolDef(type="builtin", source=source)
            result = resolve_tool(tool_def)

            assert isinstance(result, ToolInstance)
            assert result.name == "resolved_tool"
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)

    def test_resolve_tool_calls_factory(self):
        """resolve_tool calls the factory function from the catalog."""
        from runsight_core.tools import (
            BUILTIN_TOOL_CATALOG,
            ToolInstance,
            register_builtin,
            resolve_tool,
        )
        from runsight_core.yaml.schema import ToolDef

        source = "test/resolve_calls_factory"
        call_count = {"n": 0}

        def factory(**kwargs):
            call_count["n"] += 1
            return ToolInstance(
                name="counted_tool",
                description="Counts calls",
                parameters={"type": "object", "properties": {}},
                execute=_dummy_execute,
            )

        BUILTIN_TOOL_CATALOG.pop(source, None)
        try:
            register_builtin(source, factory)
            tool_def = ToolDef(type="builtin", source=source)
            resolve_tool(tool_def)
            assert call_count["n"] == 1
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)

    def test_resolve_tool_unknown_source_raises(self):
        """resolve_tool with an unregistered source raises ValueError."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml.schema import ToolDef

        tool_def = ToolDef(type="builtin", source="nonexistent/missing_tool_xyz")

        with pytest.raises(ValueError):
            resolve_tool(tool_def)

    def test_resolve_tool_passes_kwargs_to_factory(self):
        """resolve_tool passes extra kwargs through to the factory."""
        from runsight_core.tools import (
            BUILTIN_TOOL_CATALOG,
            ToolInstance,
            register_builtin,
            resolve_tool,
        )
        from runsight_core.yaml.schema import ToolDef

        source = "test/resolve_kwargs"
        received_kwargs = {}

        def factory(**kwargs):
            received_kwargs.update(kwargs)
            return ToolInstance(
                name="kwargs_tool",
                description="Receives kwargs",
                parameters={"type": "object", "properties": {}},
                execute=_dummy_execute,
            )

        BUILTIN_TOOL_CATALOG.pop(source, None)
        try:
            register_builtin(source, factory)
            tool_def = ToolDef(type="builtin", source=source)
            resolve_tool(tool_def, api_key="secret123")
            assert received_kwargs.get("api_key") == "secret123"
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)


class TestResolveToolTypedDispatch:
    """RUN-524: resolve_tool dispatches by ToolDef variant type."""

    def test_resolve_tool_builtin_variant_still_returns_toolinstance(self):
        """BuiltinToolDef should continue resolving through the builtin catalog unchanged."""
        from runsight_core.tools import (
            BUILTIN_TOOL_CATALOG,
            ToolInstance,
            register_builtin,
            resolve_tool,
        )
        from runsight_core.yaml.schema import BuiltinToolDef

        source = "test/typed_builtin_dispatch"

        def factory(**kwargs):
            return ToolInstance(
                name="typed_builtin_tool",
                description="Resolved from a BuiltinToolDef",
                parameters={"type": "object", "properties": {}},
                execute=_dummy_execute,
            )

        BUILTIN_TOOL_CATALOG.pop(source, None)
        try:
            register_builtin(source, factory)
            tool_def = BuiltinToolDef(type="builtin", source=source)

            result = resolve_tool(tool_def)

            assert isinstance(result, ToolInstance)
            assert result.name == "typed_builtin_tool"
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)

    def test_resolve_tool_custom_variant_returns_toolinstance(self, tmp_path):
        """CustomToolDef should dispatch through the custom resolver and return a ToolInstance."""
        from runsight_core.tools import ToolInstance, resolve_tool
        from runsight_core.yaml.schema import CustomToolDef

        _write_custom_tool_yaml(
            tmp_path,
            "echo_tool",
            """
            type: custom
            source: echo_tool
            code: |
              def main(args):
                  return {"echo": args["message"]}
            """,
        )
        tool_def = CustomToolDef(type="custom", source="echo_tool")

        result = resolve_tool(tool_def, base_dir=tmp_path)

        assert isinstance(result, ToolInstance)
        assert callable(result.execute)

    def test_resolve_tool_http_variant_raises_notimplementederror_stub(self):
        """HTTPToolDef should dispatch to a stub path that raises NotImplementedError for now."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml.schema import HTTPToolDef

        tool_def = HTTPToolDef(type="http", source="http_tool")

        with pytest.raises(NotImplementedError):
            resolve_tool(tool_def, api_key="secret123")


class TestResolveCustomTool:
    """RUN-526: custom tools resolve from YAML and execute in the sandbox."""

    def test_catalog_exposes_resolve_custom_tool(self):
        """The catalog module should expose a dedicated custom-tool resolver."""
        from runsight_core.tools import _catalog as catalog_module

        assert callable(getattr(catalog_module, "resolve_custom_tool", None))

    @pytest.mark.asyncio
    async def test_execute_round_trips_args_through_json_subprocess_contract(self, tmp_path):
        """Resolved custom tools should execute user code via a JSON stdin/stdout contract."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml.schema import CustomToolDef

        _write_custom_tool_yaml(
            tmp_path,
            "echo_json",
            """
            type: custom
            source: echo_json
            code: |
              def main(args):
                  return {"message": "hello " + args["name"]}
            """,
        )

        tool = resolve_tool(CustomToolDef(type="custom", source="echo_json"), base_dir=tmp_path)

        result = await tool.execute({"name": "alice"})

        assert json.loads(result) == {"message": "hello alice"}

    def test_blocked_imports_are_rejected_at_resolve_time(self, tmp_path):
        """Dangerous imports should be rejected before a custom tool is returned."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml.schema import CustomToolDef

        _write_custom_tool_yaml(
            tmp_path,
            "blocked_import_tool",
            """
            type: custom
            source: blocked_import_tool
            code: |
              import os

              def main(args):
                  return {}
            """,
        )

        with pytest.raises(ValueError, match="not allowed"):
            resolve_tool(
                CustomToolDef(type="custom", source="blocked_import_tool"),
                base_dir=tmp_path,
            )

    def test_blocked_builtins_are_rejected_at_resolve_time(self, tmp_path):
        """Blocked builtins like eval/open/__import__ should be rejected during resolution."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml.schema import CustomToolDef

        _write_custom_tool_yaml(
            tmp_path,
            "blocked_builtin_tool",
            """
            type: custom
            source: blocked_builtin_tool
            code: |
              def main(args):
                  eval("1 + 1")
                  return {}
            """,
        )

        with pytest.raises(ValueError, match="not allowed"):
            resolve_tool(
                CustomToolDef(type="custom", source="blocked_builtin_tool"),
                base_dir=tmp_path,
            )

    @pytest.mark.asyncio
    async def test_timeout_returns_error_string(self, tmp_path):
        """Runaway custom tools should be killed and surfaced as an error string."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml.schema import CustomToolDef

        _write_custom_tool_yaml(
            tmp_path,
            "slow_tool",
            """
            type: custom
            source: slow_tool
            code: |
              import time

              def main(args):
                  time.sleep(5)
                  return {"done": True}
            """,
        )

        tool = resolve_tool(
            CustomToolDef(type="custom", source="slow_tool"),
            base_dir=tmp_path,
            timeout_seconds=1,
        )

        result = await tool.execute({})

        assert "timed out" in result.lower()

    @pytest.mark.asyncio
    async def test_code_file_variant_loads_external_python_file(self, tmp_path):
        """code_file metadata should load the external Python implementation before execution."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml.schema import CustomToolDef

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
            type: custom
            source: file_backed
            code_file: file_backed_impl.py
            """),
            encoding="utf-8",
        )

        tool = resolve_tool(CustomToolDef(type="custom", source="file_backed"), base_dir=tmp_path)

        result = await tool.execute({"port": "done"})

        assert json.loads(result) == {"port": "done"}
