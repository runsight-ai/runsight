from __future__ import annotations

from pathlib import Path

from packages.core.tests.discovery_fixtures import write_tool_yaml


def _scan_tools(base_dir: Path):
    from runsight_core.yaml.discovery import ToolScanner

    return ToolScanner(base_dir).scan().ids()


def test_tool_scanner_returns_empty_without_custom_tools_dir_and_discovers_tool_metadata(
    tmp_path: Path,
) -> None:
    from runsight_core.yaml.discovery import ToolMeta

    assert _scan_tools(tmp_path) == {}

    write_tool_yaml(
        tmp_path,
        "python_helper.yaml",
        tool_id="python_helper",
        executor="python",
        name="Python Helper",
        description="Echo values back to the caller.",
        parameters=[
            "type: object",
            "properties:",
            "  value:",
            "    type: string",
            "required:",
            "  - value",
        ],
        code="def main(args):\n    return args",
    )
    write_tool_yaml(
        tmp_path,
        "request_lookup.yaml",
        tool_id="request_lookup",
        executor="request",
        name="Request Lookup",
        description="Fetch data from a fixture service.",
        parameters=[
            "type: object",
            "properties:",
            "  user_id:",
            "    type: integer",
            "required:",
            "  - user_id",
        ],
        request=[
            "method: GET",
            "url: https://fixture.test/users/{{ user_id }}",
            "headers:",
            "  X-Test: runsight",
            "response_path: data.id",
        ],
        extra_lines=["timeout_seconds: 12"],
    )

    discovered = _scan_tools(tmp_path)

    assert set(discovered) == {"python_helper", "request_lookup"}
    assert isinstance(discovered["python_helper"], ToolMeta)
    assert discovered["python_helper"].executor == "python"
    assert discovered["python_helper"].type == "custom"
    assert discovered["request_lookup"].executor == "request"
    assert discovered["request_lookup"].request["url"] == "https://fixture.test/users/{{ user_id }}"
