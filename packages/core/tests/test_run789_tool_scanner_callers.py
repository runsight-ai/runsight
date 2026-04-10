from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from runsight_core.yaml.discovery import ToolMeta
from runsight_core.yaml.parser import (
    _attach_tool_runtime_metadata,
    _validate_declared_tool_definitions,
)


def _make_python_tool_meta(tool_id: str = "lookup_profile") -> ToolMeta:
    return ToolMeta(
        tool_id=tool_id,
        file_path=Path(f"/tmp/{tool_id}.yaml"),
        version="1.0",
        type="custom",
        executor="python",
        name="Lookup Profile",
        description="Look up a profile.",
        parameters={"type": "object"},
        code="def main(args):\n    return args\n",
    )


def _make_request_tool_meta(tool_id: str = "fetch_profile") -> ToolMeta:
    return ToolMeta(
        tool_id=tool_id,
        file_path=Path(f"/tmp/{tool_id}.yaml"),
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


def test_validate_declared_tool_definitions_uses_tool_scanner(tmp_path):
    file_def = SimpleNamespace(tools=["lookup_profile"])
    tool_meta = _make_python_tool_meta()

    with (
        patch("runsight_core.yaml.parser.ToolScanner") as mock_scanner,
        patch("runsight_core.yaml.parser._resolve_tool_for_parser") as mock_resolve,
    ):
        mock_scanner.return_value.scan.return_value.stems.return_value = {
            "lookup_profile": tool_meta
        }

        _validate_declared_tool_definitions(file_def, base_dir=str(tmp_path))

    mock_scanner.assert_called_once_with(str(tmp_path))
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.stems.assert_called_once()
    mock_resolve.assert_called_once_with("lookup_profile", base_dir=str(tmp_path))


def test_attach_tool_runtime_metadata_uses_tool_scanner(tmp_path):
    tool = Mock()
    tool_meta = _make_request_tool_meta("fetch_profile")

    with patch("runsight_core.yaml.parser.ToolScanner") as mock_scanner:
        mock_scanner.return_value.scan.return_value.stems.return_value = {
            "fetch_profile": tool_meta
        }

        result = _attach_tool_runtime_metadata(tool, "fetch_profile", base_dir=str(tmp_path))

    assert result is tool
    assert tool.tool_type == "custom"
    mock_scanner.assert_called_once_with(str(tmp_path))
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.stems.assert_called_once()


def test_resolve_custom_tool_id_uses_tool_scanner(tmp_path):
    from runsight_core.tools._catalog import ToolInstance, _resolve_custom_tool_id

    tool_meta = _make_python_tool_meta()

    with patch("runsight_core.tools._catalog.ToolScanner") as mock_scanner:
        mock_scanner.return_value.scan.return_value.stems.return_value = {
            "lookup_profile": tool_meta
        }

        result = _resolve_custom_tool_id("lookup_profile", base_dir=str(tmp_path))

    assert isinstance(result, ToolInstance)
    assert result.name == "lookup_profile"
    mock_scanner.assert_called_once_with(str(tmp_path))
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.stems.assert_called_once()


def test_resolve_http_tool_id_uses_tool_scanner(tmp_path):
    from runsight_core.tools._catalog import ToolInstance, _resolve_http_tool_id

    tool_meta = _make_request_tool_meta()

    with patch("runsight_core.tools._catalog.ToolScanner") as mock_scanner:
        mock_scanner.return_value.scan.return_value.stems.return_value = {
            "fetch_profile": tool_meta
        }

        result = _resolve_http_tool_id("fetch_profile", base_dir=str(tmp_path))

    assert isinstance(result, ToolInstance)
    assert result.name == "fetch_profile"
    mock_scanner.assert_called_once_with(str(tmp_path))
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.stems.assert_called_once()


def test_resolve_tool_id_uses_tool_scanner_for_custom_lookup(tmp_path):
    from runsight_core.tools._catalog import resolve_tool_id

    tool_meta = _make_python_tool_meta()
    resolved_tool = Mock()

    with (
        patch("runsight_core.tools._catalog.ToolScanner") as mock_scanner,
        patch(
            "runsight_core.tools._catalog._resolve_custom_tool_id",
            return_value=resolved_tool,
        ) as mock_resolve_custom,
    ):
        mock_scanner.return_value.scan.return_value.stems.return_value = {
            "lookup_profile": tool_meta
        }

        result = resolve_tool_id("lookup_profile", base_dir=str(tmp_path))

    assert result is resolved_tool
    mock_scanner.assert_called_once_with(str(tmp_path))
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.stems.assert_called_once()
    mock_resolve_custom.assert_called_once_with(
        "lookup_profile",
        tool_meta=tool_meta,
        base_dir=str(tmp_path),
    )
