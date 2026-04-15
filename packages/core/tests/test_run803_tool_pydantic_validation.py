"""
RUN-803: ToolScanner Pydantic migration — failing tests.

These tests verify that:
- ToolManifest and RequestConfig are Pydantic BaseModels with extra="forbid"
- ToolMeta is converted from @dataclass to Pydantic BaseModel
- runsight_core/tools/contract.py exists with TOOL_FUNCTION_NAME / TOOL_FUNCTION_PARAMS
- _validate_tool_main_contract references the shared constants
- End-to-end ToolScanner raises Pydantic ValidationError for invalid YAML
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_tool_dict() -> dict:
    """Minimal valid tool YAML dict (python executor)."""
    return {
        "version": "1.0",
        "id": "my_tool",
        "kind": "tool",
        "type": "custom",
        "executor": "python",
        "name": "My Tool",
        "description": "Does a thing.",
        "parameters": {"type": "object"},
        "code": "def main(args):\n    return args\n",
    }


def _valid_request_dict() -> dict:
    """Minimal valid request config dict."""
    return {
        "method": "GET",
        "url": "https://example.com/api",
    }


# ---------------------------------------------------------------------------
# 1. ToolManifest exists and is a Pydantic BaseModel with extra="forbid"
# ---------------------------------------------------------------------------


class TestToolManifestIsABaseModel:
    """ToolManifest must be a Pydantic BaseModel with extra='forbid'."""

    def test_tool_manifest_is_importable(self):
        from runsight_core.yaml.discovery._tool import ToolManifest  # noqa: F401

    def test_tool_manifest_is_pydantic_base_model(self):
        from pydantic import BaseModel
        from runsight_core.yaml.discovery._tool import ToolManifest

        assert issubclass(ToolManifest, BaseModel)

    def test_tool_manifest_has_extra_forbid(self):
        from runsight_core.yaml.discovery._tool import ToolManifest

        config = ToolManifest.model_config
        assert config.get("extra") == "forbid", "ToolManifest.model_config must have extra='forbid'"


# ---------------------------------------------------------------------------
# 2. ToolManifest rejects extra fields with ValidationError (not ValueError)
# ---------------------------------------------------------------------------


class TestToolManifestRejectsExtraFields:
    """Extra top-level fields must raise pydantic.ValidationError, not ValueError."""

    def test_extra_field_raises_validation_error(self):
        import pydantic
        from runsight_core.yaml.discovery._tool import ToolManifest

        data = _valid_tool_dict()
        data["bogus"] = "should not be here"

        with pytest.raises(pydantic.ValidationError):
            ToolManifest(**data)

    def test_extra_field_does_not_raise_value_error(self):
        """Ensure the old hand-rolled allowlist path is gone."""
        import pydantic
        from runsight_core.yaml.discovery._tool import ToolManifest

        data = _valid_tool_dict()
        data["unexpected_field"] = True

        try:
            ToolManifest(**data)
            pytest.fail("Expected ValidationError but no exception was raised")
        except pydantic.ValidationError:
            pass  # correct
        except ValueError as exc:
            pytest.fail(
                f"Got ValueError instead of ValidationError — "
                f"hand-rolled check still in place: {exc}"
            )


# ---------------------------------------------------------------------------
# 3. ToolManifest rejects missing required fields with ValidationError
# ---------------------------------------------------------------------------


class TestToolManifestRejectsMissingFields:
    """Missing required fields must raise pydantic.ValidationError, not ValueError."""

    def test_missing_name_raises_validation_error(self):
        import pydantic
        from runsight_core.yaml.discovery._tool import ToolManifest

        data = _valid_tool_dict()
        del data["name"]

        with pytest.raises(pydantic.ValidationError):
            ToolManifest(**data)

    def test_missing_description_raises_validation_error(self):
        import pydantic
        from runsight_core.yaml.discovery._tool import ToolManifest

        data = _valid_tool_dict()
        del data["description"]

        with pytest.raises(pydantic.ValidationError):
            ToolManifest(**data)

    def test_missing_executor_raises_validation_error(self):
        import pydantic
        from runsight_core.yaml.discovery._tool import ToolManifest

        data = _valid_tool_dict()
        del data["executor"]

        with pytest.raises(pydantic.ValidationError):
            ToolManifest(**data)

    def test_missing_required_field_is_not_value_error(self):
        """Old _require_string raised ValueError — must be gone."""
        import pydantic
        from runsight_core.yaml.discovery._tool import ToolManifest

        data = _valid_tool_dict()
        del data["version"]

        try:
            ToolManifest(**data)
            pytest.fail("Expected ValidationError but no exception was raised")
        except pydantic.ValidationError:
            pass  # correct
        except ValueError as exc:
            pytest.fail(
                f"Got ValueError instead of ValidationError — _require_string still in use: {exc}"
            )


# ---------------------------------------------------------------------------
# 4. RequestConfig exists and is a Pydantic BaseModel with extra="forbid"
# ---------------------------------------------------------------------------


class TestRequestConfigIsABaseModel:
    """RequestConfig must be a Pydantic BaseModel with extra='forbid'."""

    def test_request_config_is_importable(self):
        from runsight_core.yaml.discovery._tool import RequestConfig  # noqa: F401

    def test_request_config_is_pydantic_base_model(self):
        from pydantic import BaseModel
        from runsight_core.yaml.discovery._tool import RequestConfig

        assert issubclass(RequestConfig, BaseModel)

    def test_request_config_has_extra_forbid(self):
        from runsight_core.yaml.discovery._tool import RequestConfig

        config = RequestConfig.model_config
        assert config.get("extra") == "forbid", (
            "RequestConfig.model_config must have extra='forbid'"
        )


# ---------------------------------------------------------------------------
# 5. RequestConfig rejects extra request fields with ValidationError
# ---------------------------------------------------------------------------


class TestRequestConfigRejectsExtraFields:
    """Extra fields inside a request config must raise pydantic.ValidationError."""

    def test_extra_request_field_raises_validation_error(self):
        import pydantic
        from runsight_core.yaml.discovery._tool import RequestConfig

        data = _valid_request_dict()
        data["not_a_valid_field"] = "oops"

        with pytest.raises(pydantic.ValidationError):
            RequestConfig(**data)

    def test_extra_request_field_does_not_raise_value_error(self):
        """Old _normalize_request_config raised ValueError — must be gone."""
        import pydantic
        from runsight_core.yaml.discovery._tool import RequestConfig

        data = _valid_request_dict()
        data["extra_key"] = "surprise"

        try:
            RequestConfig(**data)
            pytest.fail("Expected ValidationError but no exception was raised")
        except pydantic.ValidationError:
            pass  # correct
        except ValueError as exc:
            pytest.fail(
                f"Got ValueError instead of ValidationError — "
                f"_normalize_request_config still in use: {exc}"
            )


# ---------------------------------------------------------------------------
# 6. ToolMeta is a Pydantic BaseModel, not a dataclass
# ---------------------------------------------------------------------------


class TestToolMetaIsBaseModel:
    """ToolMeta must be a Pydantic BaseModel and must NOT be a dataclass."""

    def test_tool_meta_is_importable(self):
        from runsight_core.yaml.discovery import ToolMeta  # noqa: F401

    def test_tool_meta_is_pydantic_base_model(self):
        from pydantic import BaseModel
        from runsight_core.yaml.discovery import ToolMeta

        assert issubclass(ToolMeta, BaseModel), (
            "ToolMeta must be a Pydantic BaseModel, not a dataclass"
        )

    def test_tool_meta_is_not_a_dataclass(self):
        from runsight_core.yaml.discovery import ToolMeta

        assert not hasattr(ToolMeta, "__dataclass_fields__"), (
            "ToolMeta still has __dataclass_fields__ — it has not been migrated from @dataclass"
        )


# ---------------------------------------------------------------------------
# 7. Shared contract constants exist
# ---------------------------------------------------------------------------


class TestToolContractConstants:
    """runsight_core.tools.contract must export TOOL_FUNCTION_NAME and TOOL_FUNCTION_PARAMS."""

    def test_contract_module_is_importable(self):
        import runsight_core.tools.contract  # noqa: F401

    def test_tool_function_name_constant(self):
        from runsight_core.tools.contract import TOOL_FUNCTION_NAME

        assert TOOL_FUNCTION_NAME == "main", (
            f"TOOL_FUNCTION_NAME must be 'main', got {TOOL_FUNCTION_NAME!r}"
        )

    def test_tool_function_params_constant(self):
        from runsight_core.tools.contract import TOOL_FUNCTION_PARAMS

        assert TOOL_FUNCTION_PARAMS == ("args",), (
            f"TOOL_FUNCTION_PARAMS must be ('args',), got {TOOL_FUNCTION_PARAMS!r}"
        )


# ---------------------------------------------------------------------------
# 8. _validate_tool_main_contract uses shared constants
# ---------------------------------------------------------------------------


class TestValidateToolMainContractUsesConstants:
    """_validate_tool_main_contract must validate against TOOL_FUNCTION_NAME / TOOL_FUNCTION_PARAMS."""

    def test_valid_code_passes(self):
        from runsight_core.yaml.discovery._tool import _validate_tool_main_contract

        _validate_tool_main_contract("def main(args):\n    return args\n")

    def test_wrong_function_name_fails(self):
        from runsight_core.tools.contract import TOOL_FUNCTION_NAME
        from runsight_core.yaml.discovery._tool import _validate_tool_main_contract

        bad_code = "def run(args):\n    return args\n"
        with pytest.raises((ValueError, Exception)) as exc_info:
            _validate_tool_main_contract(bad_code)

        # The error message should reference the expected function name from the constant
        assert TOOL_FUNCTION_NAME in str(exc_info.value), (
            f"Error message should reference constant TOOL_FUNCTION_NAME={TOOL_FUNCTION_NAME!r}"
        )

    def test_wrong_param_name_fails(self):
        from runsight_core.tools.contract import TOOL_FUNCTION_PARAMS
        from runsight_core.yaml.discovery._tool import _validate_tool_main_contract

        bad_code = "def main(context):\n    return context\n"
        with pytest.raises((ValueError, Exception)) as exc_info:
            _validate_tool_main_contract(bad_code)

        # The error message should reference the expected param from the constant
        expected_param = TOOL_FUNCTION_PARAMS[0]
        assert expected_param in str(exc_info.value), (
            f"Error message should reference constant TOOL_FUNCTION_PARAMS param {expected_param!r}"
        )

    def test_validate_tool_main_contract_imports_from_contract_module(self):
        """_tool.py must import TOOL_FUNCTION_NAME / TOOL_FUNCTION_PARAMS from tools/contract.py."""
        import ast
        import inspect

        # Read the source of _tool.py
        import runsight_core.yaml.discovery._tool as tool_module

        source_file = inspect.getfile(tool_module)
        source = Path(source_file).read_text(encoding="utf-8")
        tree = ast.parse(source)

        # Look for any import of TOOL_FUNCTION_NAME from runsight_core.tools.contract
        found_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                if "tools.contract" in module and "TOOL_FUNCTION_NAME" in names:
                    found_import = True
                    break

        assert found_import, (
            "_tool.py must import TOOL_FUNCTION_NAME from runsight_core.tools.contract"
        )


# ---------------------------------------------------------------------------
# 9. End-to-end: ToolScanner raises errors originating from Pydantic validation
# ---------------------------------------------------------------------------


class TestToolScannerUsesPydanticValidation:
    """ToolScanner must delegate field validation to Pydantic, not hand-rolled checks."""

    def test_scan_extra_field_raises_pydantic_validation_error(self):
        """A tool YAML with an extra field should produce an error rooted in ValidationError."""
        import pydantic
        from runsight_core.yaml.discovery import ToolScanner

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)

            tool_yaml = tools_dir / "my_tool.yaml"
            tool_yaml.write_text(
                dedent("""
                version: "1.0"
                id: my_tool
                kind: tool
                type: custom
                executor: python
                name: My Tool
                description: Does a thing.
                parameters:
                  type: object
                code: |
                  def main(args):
                      return args
                bogus_extra_field: should_fail
                """).lstrip()
            )

            with pytest.raises(Exception) as exc_info:
                ToolScanner(base_dir).scan()

            # The exception chain must include a Pydantic ValidationError
            exc = exc_info.value
            chain = []
            while exc is not None:
                chain.append(exc)
                exc = exc.__cause__ or exc.__context__

            assert any(isinstance(e, pydantic.ValidationError) for e in chain), (
                "Expected a pydantic.ValidationError somewhere in the exception chain, "
                f"got: {[type(e).__name__ for e in chain]}"
            )

    def test_scan_missing_required_field_raises_pydantic_validation_error(self):
        """A tool YAML missing a required field should produce an error rooted in ValidationError."""
        import pydantic
        from runsight_core.yaml.discovery import ToolScanner

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)

            tool_yaml = tools_dir / "bad_tool.yaml"
            tool_yaml.write_text(
                dedent("""
                version: "1.0"
                id: bad_tool
                kind: tool
                type: custom
                executor: python
                description: Missing name field.
                parameters:
                  type: object
                code: |
                  def main(args):
                      return args
                """).lstrip()
            )

            with pytest.raises(Exception) as exc_info:
                ToolScanner(base_dir).scan()

            exc = exc_info.value
            chain = []
            while exc is not None:
                chain.append(exc)
                exc = exc.__cause__ or exc.__context__

            assert any(isinstance(e, pydantic.ValidationError) for e in chain), (
                "Expected a pydantic.ValidationError somewhere in the exception chain, "
                f"got: {[type(e).__name__ for e in chain]}"
            )

    def test_scan_extra_request_field_raises_pydantic_validation_error(self):
        """A request config with extra fields should produce an error rooted in ValidationError."""
        import pydantic
        from runsight_core.yaml.discovery import ToolScanner

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            tools_dir = base_dir / "custom" / "tools"
            tools_dir.mkdir(parents=True)

            tool_yaml = tools_dir / "http_tool.yaml"
            tool_yaml.write_text(
                dedent("""
                version: "1.0"
                id: http_tool
                kind: tool
                type: custom
                executor: request
                name: HTTP Tool
                description: Fetches something.
                parameters:
                  type: object
                request:
                  method: GET
                  url: https://example.com/api
                  unsupported_extra: oops
                """).lstrip()
            )

            with pytest.raises(Exception) as exc_info:
                ToolScanner(base_dir).scan()

            exc = exc_info.value
            chain = []
            while exc is not None:
                chain.append(exc)
                exc = exc.__cause__ or exc.__context__

            assert any(isinstance(e, pydantic.ValidationError) for e in chain), (
                "Expected a pydantic.ValidationError somewhere in the exception chain, "
                f"got: {[type(e).__name__ for e in chain]}"
            )


# ---------------------------------------------------------------------------
# 10. ToolMeta attribute access unchanged for consumers
# ---------------------------------------------------------------------------


class TestToolMetaAttributeAccess:
    """ToolMeta constructed with keyword args must expose all expected attributes."""

    def test_tool_meta_python_executor_attribute_access(self):
        from runsight_core.yaml.discovery import ToolMeta

        meta = ToolMeta(
            tool_id="lookup_profile",
            file_path=Path("/tmp/lookup_profile.yaml"),
            version="1.0",
            type="custom",
            executor="python",
            name="Lookup Profile",
            description="Look up a profile.",
            parameters={"type": "object"},
            code="def main(args):\n    return args\n",
        )

        assert meta.tool_id == "lookup_profile"
        assert meta.file_path == Path("/tmp/lookup_profile.yaml")
        assert meta.executor == "python"
        assert meta.name == "Lookup Profile"
        assert meta.description == "Look up a profile."
        assert meta.parameters == {"type": "object"}
        assert meta.code == "def main(args):\n    return args\n"
        assert meta.request is None
        assert meta.timeout_seconds is None

    def test_tool_meta_request_executor_attribute_access(self):
        from runsight_core.yaml.discovery import ToolMeta

        meta = ToolMeta(
            tool_id="fetch_profile",
            file_path=Path("/tmp/fetch_profile.yaml"),
            version="1.0",
            type="custom",
            executor="request",
            name="Fetch Profile",
            description="Fetch a remote profile.",
            parameters={"type": "object"},
            request={
                "method": "GET",
                "url": "https://example.com/profiles/{{ profile_id }}",
                "headers": {},
                "body_template": None,
                "response_path": "data.profile",
            },
            timeout_seconds=9,
        )

        assert meta.tool_id == "fetch_profile"
        assert meta.executor == "request"
        assert meta.request is not None
        assert meta.request["method"] == "GET"
        assert meta.timeout_seconds == 9
        assert meta.code is None
