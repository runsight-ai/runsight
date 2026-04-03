"""
RUN-281 — Unit-level tests for tool registry: catalog, ToolInstance, registration.

These complement the existing tests in unit/test_tool_catalog.py by covering
the full catalog state after all built-in tools are auto-registered via the
parser import side-effect, and by testing the canonical builtin ids are present
when the package is fully initialised.

Tests cover:
  AC1: All three built-in sources registered in BUILTIN_TOOL_CATALOG after import
  AC2: ToolInstance.to_openai_schema() produces valid OpenAI tool format
  AC3: register_builtin / get_builtin round-trip
  AC4: resolve_tool raises ValueError for unknown source
  AC5: resolve_tool passes kwargs to factory (e.g. exits= for delegate)
  AC6: ToolInstance.execute is callable and async
  AC7: Catalog is mutable — register then remove leaves it clean
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

# Trigger auto-registration of all built-ins via parser import
import runsight_core.yaml.parser  # noqa: F401

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _noop_execute(args: dict) -> str:
    return "noop"


def _make_simple_tool_instance(name: str = "simple_tool"):
    """Build a minimal ToolInstance for non-catalog tests."""
    from runsight_core.tools import ToolInstance

    return ToolInstance(
        name=name,
        description="A simple test tool",
        parameters={
            "type": "object",
            "properties": {"param": {"type": "string"}},
            "required": ["param"],
        },
        execute=_noop_execute,
    )


# ===========================================================================
# AC1: Built-in sources present in BUILTIN_TOOL_CATALOG after parser import
# ===========================================================================


class TestBuiltinCatalogPopulated:
    """After importing runsight_core.yaml.parser, all three built-in tool
    sources must be registered in BUILTIN_TOOL_CATALOG."""

    def test_http_source_registered(self):
        """'http' key present in BUILTIN_TOOL_CATALOG."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG

        assert "http" in BUILTIN_TOOL_CATALOG

    def test_file_io_source_registered(self):
        """'file_io' key present in BUILTIN_TOOL_CATALOG."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG

        assert "file_io" in BUILTIN_TOOL_CATALOG

    def test_delegate_source_registered(self):
        """'delegate' key present in BUILTIN_TOOL_CATALOG."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG

        assert "delegate" in BUILTIN_TOOL_CATALOG

    def test_catalog_contains_callables(self):
        """Every value in BUILTIN_TOOL_CATALOG must be a callable factory."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG

        for source, factory in BUILTIN_TOOL_CATALOG.items():
            assert callable(factory), f"Factory for '{source}' is not callable"

    def test_catalog_has_at_least_three_entries(self):
        """BUILTIN_TOOL_CATALOG has at least the three built-in entries."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG

        assert len(BUILTIN_TOOL_CATALOG) >= 3


# ===========================================================================
# AC2: ToolInstance.to_openai_schema() — OpenAI tool format
# ===========================================================================


class TestToolInstanceOpenAISchema:
    """ToolInstance.to_openai_schema() must produce exactly the expected
    OpenAI function-calling schema structure."""

    def test_schema_top_level_type_is_function(self):
        """Schema top-level 'type' must equal 'function'."""
        tool = _make_simple_tool_instance("weather")
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"

    def test_schema_has_function_key(self):
        """Schema must contain a 'function' key."""
        tool = _make_simple_tool_instance("weather")
        schema = tool.to_openai_schema()
        assert "function" in schema

    def test_schema_function_name_matches_tool_name(self):
        """function.name must equal ToolInstance.name."""
        tool = _make_simple_tool_instance("my_tool")
        schema = tool.to_openai_schema()
        assert schema["function"]["name"] == "my_tool"

    def test_schema_function_description_matches(self):
        """function.description must equal ToolInstance.description."""
        tool = _make_simple_tool_instance("my_tool")
        schema = tool.to_openai_schema()
        assert schema["function"]["description"] == "A simple test tool"

    def test_schema_function_parameters_matches(self):
        """function.parameters must equal ToolInstance.parameters."""
        tool = _make_simple_tool_instance("my_tool")
        schema = tool.to_openai_schema()
        assert schema["function"]["parameters"] == tool.parameters

    def test_schema_full_structure(self):
        """to_openai_schema() must produce exactly the OpenAI tool format."""
        from runsight_core.tools import ToolInstance

        params = {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        }
        tool = ToolInstance(
            name="get_weather",
            description="Fetch weather for a city.",
            parameters=params,
            execute=_noop_execute,
        )
        expected = {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Fetch weather for a city.",
                "parameters": params,
            },
        }
        assert tool.to_openai_schema() == expected

    def test_http_tool_schema_name(self):
        """HTTP tool to_openai_schema() reports name 'http_request'."""
        from runsight_core.tools.http import create_http_tool

        tool = create_http_tool()
        schema = tool.to_openai_schema()
        assert schema["function"]["name"] == "http_request"

    def test_file_io_tool_schema_name(self):
        """File I/O tool to_openai_schema() reports name 'file_io'."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool()
        schema = tool.to_openai_schema()
        assert schema["function"]["name"] == "file_io"

    def test_delegate_tool_schema_name(self):
        """Delegate tool to_openai_schema() reports name 'delegate'."""
        from runsight_core.tools.delegate import create_delegate_tool
        from runsight_core.yaml.schema import ExitDef

        exits = [ExitDef(id="done", label="Done")]
        tool = create_delegate_tool(exits=exits)
        schema = tool.to_openai_schema()
        assert schema["function"]["name"] == "delegate"


# ===========================================================================
# AC3: register_builtin / get_builtin round-trip
# ===========================================================================


class TestRegisterBuiltinRoundTrip:
    """register_builtin stores; get_builtin retrieves exactly that factory."""

    def test_register_and_retrieve(self):
        """Factory stored with register_builtin is returned by get_builtin."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG, get_builtin, register_builtin

        source = "test/runtool_registry_roundtrip"
        BUILTIN_TOOL_CATALOG.pop(source, None)

        def my_factory(**kwargs: Any):
            return _make_simple_tool_instance("roundtrip")

        try:
            register_builtin(source, my_factory)
            retrieved = get_builtin(source)
            assert retrieved is my_factory
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)

    def test_second_registration_overwrites_first(self):
        """Registering the same source twice replaces the first factory."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG, get_builtin, register_builtin

        source = "test/runtool_registry_overwrite"
        BUILTIN_TOOL_CATALOG.pop(source, None)

        def factory_v1(**kwargs: Any):
            pass

        def factory_v2(**kwargs: Any):
            pass

        try:
            register_builtin(source, factory_v1)
            register_builtin(source, factory_v2)
            assert get_builtin(source) is factory_v2
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)

    def test_get_builtin_unknown_returns_none(self):
        """get_builtin for a never-registered source returns None."""
        from runsight_core.tools import get_builtin

        result = get_builtin("test/definitely_not_registered_xyz_281")
        assert result is None


# ===========================================================================
# AC4: resolve_tool raises ValueError for unknown source
# ===========================================================================


class TestResolveToolUnknownSource:
    """resolve_tool must raise ValueError when source is not in catalog."""

    def test_unknown_source_raises_value_error(self):
        """resolve_tool with unregistered source raises ValueError."""
        from runsight_core.tools import resolve_tool

        with pytest.raises(ValueError):
            resolve_tool("does_not_exist_xyz")

    def test_error_message_mentions_source(self):
        """ValueError message includes the unknown source string."""
        from runsight_core.tools import resolve_tool

        with pytest.raises(ValueError, match="mystery_source"):
            resolve_tool("mystery_source")

    def test_typed_tool_def_runtime_input_is_rejected(self):
        """Legacy ToolDef runtime inputs should be rejected in favor of canonical IDs."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml.schema import ToolDef

        tool_def = ToolDef(type="builtin", source="http")

        with pytest.raises((TypeError, ValueError)):
            resolve_tool(tool_def)

    @pytest.mark.parametrize("legacy_source", ["runsight/http", "runsight/delegate"])
    def test_legacy_source_strings_are_rejected(self, legacy_source: str):
        """Legacy source slugs should not be accepted by the runtime resolver."""
        from runsight_core.tools import resolve_tool

        with pytest.raises((TypeError, ValueError)):
            resolve_tool(legacy_source)


# ===========================================================================
# AC5: resolve_tool passes kwargs to factory (e.g. exits= for delegate)
# ===========================================================================


class TestResolveToolKwargs:
    """resolve_tool must pass extra kwargs through to the factory function."""

    def test_kwargs_forwarded_to_factory(self):
        """Extra kwargs passed to resolve_tool are forwarded to the factory."""
        from runsight_core.tools import (
            BUILTIN_TOOL_CATALOG,
            ToolInstance,
            register_builtin,
            resolve_tool,
        )

        source = "http"
        received: dict = {}
        original_factory = BUILTIN_TOOL_CATALOG.get(source)

        def factory(**kwargs: Any):
            received.update(kwargs)
            return ToolInstance(
                name="kwargs_tool",
                description="Records kwargs",
                parameters={"type": "object", "properties": {}},
                execute=_noop_execute,
            )

        try:
            register_builtin(source, factory)
            resolve_tool(source, custom_param="test_value_281")
            assert received.get("custom_param") == "test_value_281"
        finally:
            if original_factory is None:
                BUILTIN_TOOL_CATALOG.pop(source, None)
            else:
                BUILTIN_TOOL_CATALOG[source] = original_factory

    def test_delegate_resolve_passes_exits(self):
        """resolve_tool for canonical delegate passes exits kwarg to factory."""
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml.schema import ExitDef

        exits = [ExitDef(id="approve", label="Approve"), ExitDef(id="reject", label="Reject")]
        tool = resolve_tool("delegate", exits=exits)

        port_schema = tool.parameters["properties"]["port"]
        assert "enum" in port_schema
        assert set(port_schema["enum"]) == {"approve", "reject"}


# ===========================================================================
# AC6: ToolInstance.execute is callable and returns a string asynchronously
# ===========================================================================


class TestToolInstanceExecuteAsync:
    """ToolInstance.execute must be an async callable returning a string."""

    def test_execute_is_callable(self):
        """ToolInstance.execute attribute is callable."""
        tool = _make_simple_tool_instance()
        assert callable(tool.execute)

    def test_execute_returns_string(self):
        """Calling execute() returns a string."""
        tool = _make_simple_tool_instance()
        result = asyncio.get_event_loop().run_until_complete(tool.execute({"param": "hello"}))
        assert isinstance(result, str)

    def test_file_io_execute_write_returns_string(self, tmp_path):
        """File I/O tool execute returns a string on write."""
        from runsight_core.tools.file_io import create_file_io_tool

        tool = create_file_io_tool(base_dir=str(tmp_path))
        result = asyncio.get_event_loop().run_until_complete(
            tool.execute({"action": "write", "path": "hello.txt", "content": "hi"})
        )
        assert isinstance(result, str)

    def test_delegate_execute_returns_port_string(self):
        """Delegate tool execute returns the port string."""
        from runsight_core.tools.delegate import create_delegate_tool
        from runsight_core.yaml.schema import ExitDef

        exits = [ExitDef(id="done", label="Done")]
        tool = create_delegate_tool(exits=exits)
        result = asyncio.get_event_loop().run_until_complete(tool.execute({"port": "done"}))
        assert result == "done"


# ===========================================================================
# AC7: Catalog is mutable — register, confirm, remove, confirm gone
# ===========================================================================


class TestCatalogMutability:
    """Registering and removing entries from BUILTIN_TOOL_CATALOG must work cleanly."""

    def test_registered_key_appears_in_catalog(self):
        """After register_builtin, the source key appears in catalog."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG, register_builtin

        source = "test/runtool_registry_mutability_add"
        BUILTIN_TOOL_CATALOG.pop(source, None)

        def factory(**kwargs: Any):
            return _make_simple_tool_instance()

        try:
            register_builtin(source, factory)
            assert source in BUILTIN_TOOL_CATALOG
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)

    def test_removed_key_no_longer_in_catalog(self):
        """After removing a key from catalog, get_builtin returns None for it."""
        from runsight_core.tools import BUILTIN_TOOL_CATALOG, get_builtin, register_builtin

        source = "test/runtool_registry_mutability_remove"

        def factory(**kwargs: Any):
            return _make_simple_tool_instance()

        register_builtin(source, factory)
        assert source in BUILTIN_TOOL_CATALOG

        BUILTIN_TOOL_CATALOG.pop(source)
        assert get_builtin(source) is None
