"""ToolScanner Pydantic manifest and metadata validation behavior."""

from __future__ import annotations

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
        "id": "profile_lookup_tool",
        "kind": "tool",
        "type": "custom",
        "executor": "python",
        "name": "Profile Lookup",
        "description": "Returns profile data.",
        "parameters": {"type": "object"},
        "code": "def main(args):\n    return args\n",
    }


def _valid_request_dict() -> dict:
    """Minimal valid request config dict."""
    return {
        "method": "GET",
        "url": "http://127.0.0.1:18080/api",
    }


# ---------------------------------------------------------------------------
# ToolManifest model contract
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
# ToolManifest extra-field rejection
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
# ToolManifest missing-field rejection
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
# RequestConfig model contract
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
# RequestConfig extra-field rejection
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
# ToolMeta model contract
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
# Shared contract constants
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
# _validate_tool_main_contract constant usage
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
# ToolScanner Pydantic validation errors
# ---------------------------------------------------------------------------


class TestToolScannerUsesPydanticValidation:
    """ToolScanner must delegate field validation to Pydantic, not hand-rolled checks."""

    def test_scan_extra_field_raises_pydantic_validation_error(self, tmp_path):
        """A tool YAML with an extra field should produce an error rooted in ValidationError."""
        import pydantic
        from runsight_core.yaml.discovery import ToolScanner

        base_dir = tmp_path
        tools_dir = base_dir / "custom" / "tools"
        tools_dir.mkdir(parents=True)

        tool_yaml = tools_dir / "profile_lookup_tool.yaml"
        tool_yaml.write_text(
            dedent("""
            version: "1.0"
            id: profile_lookup_tool
            kind: tool
            type: custom
            executor: python
            name: Profile Lookup
            description: Returns profile data.
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

    def test_scan_missing_required_field_raises_pydantic_validation_error(self, tmp_path):
        """A tool YAML missing a required field should produce an error rooted in ValidationError."""
        import pydantic
        from runsight_core.yaml.discovery import ToolScanner

        base_dir = tmp_path
        tools_dir = base_dir / "custom" / "tools"
        tools_dir.mkdir(parents=True)

        tool_yaml = tools_dir / "profile_missing_name_tool.yaml"
        tool_yaml.write_text(
            dedent("""
            version: "1.0"
            id: profile_missing_name_tool
            kind: tool
            type: custom
            executor: python
            description: Returns profile data without a name field.
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

    def test_scan_extra_request_field_raises_pydantic_validation_error(self, tmp_path):
        """A request config with extra fields should produce an error rooted in ValidationError."""
        import pydantic
        from runsight_core.yaml.discovery import ToolScanner

        base_dir = tmp_path
        tools_dir = base_dir / "custom" / "tools"
        tools_dir.mkdir(parents=True)

        tool_yaml = tools_dir / "profile_request_tool.yaml"
        tool_yaml.write_text(
            dedent("""
            version: "1.0"
            id: profile_request_tool
            kind: tool
            type: custom
            executor: request
            name: Profile Request
            description: Fetches profile data from a local harness.
            parameters:
              type: object
            request:
              method: GET
              url: http://127.0.0.1:18080/api
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
# ToolMeta attribute access for consumers
# ---------------------------------------------------------------------------


class TestToolMetaAttributeAccess:
    """ToolMeta constructed with keyword args must expose all expected attributes."""

    def test_tool_meta_python_executor_attribute_access(self):
        from runsight_core.yaml.discovery import ToolMeta

        meta = ToolMeta(
            tool_id="profile_lookup_tool",
            file_path=Path("/tmp/profile_lookup_tool.yaml"),
            version="1.0",
            type="custom",
            executor="python",
            name="Lookup Profile",
            description="Look up a profile.",
            parameters={"type": "object"},
            code="def main(args):\n    return args\n",
        )

        assert meta.tool_id == "profile_lookup_tool"
        assert meta.file_path == Path("/tmp/profile_lookup_tool.yaml")
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
            tool_id="profile_request_tool",
            file_path=Path("/tmp/profile_request_tool.yaml"),
            version="1.0",
            type="custom",
            executor="request",
            name="Profile Request",
            description="Fetch profile data from a local harness.",
            parameters={"type": "object"},
            request={
                "method": "GET",
                "url": "http://127.0.0.1:18080/profiles/{{ profile_id }}",
                "headers": {},
                "body_template": None,
                "response_path": "data.profile",
            },
            timeout_seconds=9,
        )

        assert meta.tool_id == "profile_request_tool"
        assert meta.executor == "request"
        assert meta.request is not None
        assert meta.request["method"] == "GET"
        assert meta.timeout_seconds == 9
        assert meta.code is None
