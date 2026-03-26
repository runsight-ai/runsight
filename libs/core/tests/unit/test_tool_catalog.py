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
            register_builtin,
            get_builtin,
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
            register_builtin,
            get_builtin,
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
