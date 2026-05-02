"""Pydantic contracts for custom tool manifests and metadata."""

from __future__ import annotations

from pathlib import Path

import pydantic
import pytest
from tool_validation_helpers import valid_request_dict, valid_tool_dict


def test_tool_manifest_is_pydantic_model_with_extra_forbid() -> None:
    from pydantic import BaseModel
    from runsight_core.yaml.discovery._tool import ToolManifest

    assert issubclass(ToolManifest, BaseModel)
    assert ToolManifest.model_config.get("extra") == "forbid"


@pytest.mark.parametrize("field", ["name", "description", "executor", "version"])
def test_tool_manifest_missing_required_fields_raise_validation_error(field: str) -> None:
    from runsight_core.yaml.discovery._tool import ToolManifest

    data = valid_tool_dict()
    del data[field]

    with pytest.raises(pydantic.ValidationError):
        ToolManifest(**data)


def test_tool_manifest_extra_fields_raise_validation_error_not_valueerror() -> None:
    from runsight_core.yaml.discovery._tool import ToolManifest

    data = valid_tool_dict() | {"unexpected_field": True}

    with pytest.raises(pydantic.ValidationError):
        ToolManifest(**data)


def test_request_config_is_pydantic_model_with_extra_forbid() -> None:
    from pydantic import BaseModel
    from runsight_core.yaml.discovery._tool import RequestConfig

    assert issubclass(RequestConfig, BaseModel)
    assert RequestConfig.model_config.get("extra") == "forbid"


def test_request_config_extra_fields_raise_validation_error_not_valueerror() -> None:
    from runsight_core.yaml.discovery._tool import RequestConfig

    data = valid_request_dict() | {"extra_key": "surprise"}

    with pytest.raises(pydantic.ValidationError):
        RequestConfig(**data)


def test_tool_meta_is_pydantic_model_with_attribute_access(tmp_path: Path) -> None:
    from pydantic import BaseModel
    from runsight_core.yaml.discovery import ToolMeta

    meta = ToolMeta(
        tool_id="profile_lookup_tool",
        file_path=tmp_path / "profile_lookup_tool.yaml",
        version="1.0",
        type="custom",
        executor="python",
        name="Lookup Profile",
        description="Look up a profile.",
        parameters={"type": "object"},
        code="def main(args):\n    return args\n",
    )

    assert issubclass(ToolMeta, BaseModel)
    assert not hasattr(ToolMeta, "__dataclass_fields__")
    assert meta.tool_id == "profile_lookup_tool"
    assert meta.file_path == tmp_path / "profile_lookup_tool.yaml"
    assert meta.executor == "python"
    assert meta.request is None
    assert meta.timeout_seconds is None


def test_request_tool_meta_exposes_request_config(tmp_path: Path) -> None:
    from runsight_core.yaml.discovery import ToolMeta

    meta = ToolMeta(
        tool_id="profile_request_tool",
        file_path=tmp_path / "profile_request_tool.yaml",
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

    assert meta.request is not None
    assert meta.request["method"] == "GET"
    assert meta.timeout_seconds == 9
    assert meta.code is None
