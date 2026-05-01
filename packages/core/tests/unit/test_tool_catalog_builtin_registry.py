"""ToolInstance schema, builtin registry, and canonical-ID contract tests."""

from __future__ import annotations

import pytest

from packages.core.tests.tool_catalog_fixtures import (
    make_dummy_tool_instance,
    write_adder_python_tool,
    write_fetch_answer_request_tool,
    write_shadow_http_python_tool,
)


class TestToolInstanceConstruction:
    """ToolInstance creation and field access."""

    def test_tool_instance_has_name(self) -> None:
        ti = make_dummy_tool_instance()
        assert ti.name == "test_tool"

    def test_tool_instance_has_description(self) -> None:
        ti = make_dummy_tool_instance()
        assert ti.description == "A tool for testing"

    def test_tool_instance_has_parameters(self) -> None:
        ti = make_dummy_tool_instance()
        assert isinstance(ti.parameters, dict)
        assert ti.parameters["type"] == "object"
        assert "query" in ti.parameters["properties"]

    def test_tool_instance_has_execute_callable(self) -> None:
        ti = make_dummy_tool_instance()
        assert callable(ti.execute)


class TestToolInstanceToOpenAISchema:
    """ToolInstance.to_openai_schema() output format."""

    def test_to_openai_schema_returns_openai_function_tool_structure(self) -> None:
        ti = make_dummy_tool_instance()

        assert ti.to_openai_schema() == {
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


class TestBuiltinRegistry:
    """Builtin catalog registration and lookup behavior."""

    def test_register_builtin_then_get_builtin(self) -> None:
        from runsight_core.tools import BUILTIN_TOOL_CATALOG, get_builtin, register_builtin

        source = "test/roundtrip_tool"

        def factory(**kwargs):
            return make_dummy_tool_instance()

        BUILTIN_TOOL_CATALOG.pop(source, None)
        try:
            register_builtin(source, factory)
            assert get_builtin(source) is factory
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)

    def test_register_builtin_overwrites_existing(self) -> None:
        from runsight_core.tools import BUILTIN_TOOL_CATALOG, get_builtin, register_builtin

        source = "test/overwrite_tool"

        def factory_a(**kwargs):
            return None

        def factory_b(**kwargs):
            return None

        BUILTIN_TOOL_CATALOG.pop(source, None)
        try:
            register_builtin(source, factory_a)
            register_builtin(source, factory_b)
            assert get_builtin(source) is factory_b
        finally:
            BUILTIN_TOOL_CATALOG.pop(source, None)

    @pytest.mark.parametrize("source", ["nonexistent/tool_xyz_does_not_exist", ""])
    def test_get_builtin_unknown_source_returns_none(self, source: str) -> None:
        from runsight_core.tools import get_builtin

        assert get_builtin(source) is None

    def test_builtin_catalog_is_importable_dict(self) -> None:
        from runsight_core.tools import BUILTIN_TOOL_CATALOG

        assert isinstance(BUILTIN_TOOL_CATALOG, dict)


class TestResolveToolCanonicalIdContract:
    """resolve_tool exposes a canonical-ID-only runtime contract."""

    def test_resolve_tool_accepts_reserved_builtin_id(self, tmp_path) -> None:
        from runsight_core.tools import ToolInstance, resolve_tool

        result = resolve_tool("http", base_dir=tmp_path)

        assert isinstance(result, ToolInstance)
        assert result.name == "http_request"

    def test_resolve_tool_accepts_discovered_python_tool_id(self, tmp_path) -> None:
        from runsight_core.tools import ToolInstance, resolve_tool

        write_adder_python_tool(tmp_path)

        result = resolve_tool("adder", base_dir=tmp_path)

        assert isinstance(result, ToolInstance)
        assert result.name == "adder"

    def test_resolve_tool_accepts_discovered_request_tool_id(self, tmp_path) -> None:
        from runsight_core.tools import ToolInstance, resolve_tool

        write_fetch_answer_request_tool(tmp_path)

        result = resolve_tool("fetch_answer", base_dir=tmp_path)

        assert isinstance(result, ToolInstance)
        assert result.name == "fetch_answer"

    def test_resolve_tool_missing_discovered_custom_tool_raises_valueerror(self, tmp_path) -> None:
        from runsight_core.tools import resolve_tool

        with pytest.raises(ValueError, match=r"Unknown tool id: 'lookup_profile'"):
            resolve_tool("lookup_profile", base_dir=tmp_path)

    def test_resolve_tool_builtin_custom_collision_raises_valueerror(self, tmp_path) -> None:
        from runsight_core.tools import resolve_tool

        write_shadow_http_python_tool(tmp_path)

        with pytest.raises(ValueError, match=r"reserved builtin tool:http|collision.*http"):
            resolve_tool("http", base_dir=tmp_path)


class TestResolveToolRejectsLegacyInputs:
    """Legacy typed defs and leaked source strings are rejected outright."""

    @pytest.mark.parametrize(
        ("factory_name", "kwargs"),
        [
            pytest.param(
                "BuiltinToolDef",
                {"type": "builtin", "source": "http"},
                id="builtin-tooldef",
            ),
            pytest.param(
                "CustomToolDef",
                {"type": "custom", "source": "adder"},
                id="custom-tooldef",
            ),
            pytest.param(
                "HTTPToolDef",
                {"type": "http", "source": "fetch_answer"},
                id="http-tooldef",
            ),
        ],
    )
    def test_rejects_typed_tool_definition_inputs(
        self, tmp_path, factory_name: str, kwargs: dict[str, str]
    ) -> None:
        from runsight_core.tools import resolve_tool
        from runsight_core.yaml import schema as schema_module

        if factory_name == "CustomToolDef":
            write_adder_python_tool(tmp_path)
        elif factory_name == "HTTPToolDef":
            write_fetch_answer_request_tool(tmp_path)

        typed_def = getattr(schema_module, factory_name)(**kwargs)

        with pytest.raises((TypeError, ValueError)):
            resolve_tool(typed_def, base_dir=tmp_path)

    @pytest.mark.parametrize(
        "legacy_source", ["runsight/http", "runsight/file-io", "runsight/delegate"]
    )
    def test_rejects_legacy_builtin_source_strings(self, tmp_path, legacy_source: str) -> None:
        from runsight_core.tools import resolve_tool

        with pytest.raises((TypeError, ValueError)):
            resolve_tool(legacy_source, base_dir=tmp_path)
