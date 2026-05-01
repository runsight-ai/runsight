"""Parser tests for custom tool discovery and metadata contracts."""

from __future__ import annotations

import pytest
from parser_yaml_helpers import (
    SnapshotGitService,
    blocked_import_tool_yaml,
    corrupt_python_tool_yaml,
    invalid_custom_tool_metadata_yaml,
    missing_main_tool_yaml,
    request_tool_yaml,
    shadow_builtin_tool_yaml,
    tool_validation_soul_workflow_yaml,
    valid_python_tool_yaml,
    write_custom_tool_file,
    write_workflow_file,
)
from runsight_core.yaml.parser import parse_workflow_yaml


def _workflow_file(tmp_path, *tool_ids: str, soul_tools: tuple[str, ...] | None = None) -> str:
    return write_workflow_file(
        tmp_path,
        tool_validation_soul_workflow_yaml(
            tool_ids=tool_ids,
            soul_tools=soul_tools if soul_tools is not None else tool_ids,
        ),
    )


def _tool_soul(workflow):
    return workflow.blocks["tool_validation_block"].soul


def test_missing_custom_tool_metadata_parses_with_empty_resolved_tools(tmp_path) -> None:
    workflow = parse_workflow_yaml(_workflow_file(tmp_path, "lookup_profile"))

    soul = _tool_soul(workflow)
    assert soul.tools == ["lookup_profile"]
    assert soul.resolved_tools == []


def test_reserved_builtin_id_collision_with_custom_slug_raises_valueerror(tmp_path) -> None:
    write_custom_tool_file(tmp_path, "http", shadow_builtin_tool_yaml())
    workflow_file = _workflow_file(tmp_path, "http")

    with pytest.raises(
        ValueError, match=r"reserved.*http.*custom/tools/http\.yaml|collision.*http"
    ):
        parse_workflow_yaml(workflow_file)


@pytest.mark.parametrize(
    ("slug", "tool_yaml_builder"),
    [
        ("blocked_import_tool", blocked_import_tool_yaml),
        ("missing_main_tool", missing_main_tool_yaml),
    ],
)
def test_invalid_custom_tool_code_parses_with_empty_resolved_tools(
    tmp_path, slug, tool_yaml_builder
) -> None:
    write_custom_tool_file(tmp_path, slug, tool_yaml_builder())
    workflow = parse_workflow_yaml(_workflow_file(tmp_path, slug))

    soul = _tool_soul(workflow)
    assert soul.tools == [slug]
    assert soul.resolved_tools == []


def test_snapshot_parse_skips_warning_only_corrupt_tools_and_resolves_sibling(tmp_path) -> None:
    write_custom_tool_file(tmp_path, "bad_one", corrupt_python_tool_yaml(name="Bad One"))
    write_custom_tool_file(tmp_path, "bad_two", corrupt_python_tool_yaml(name="Bad Two"))
    write_custom_tool_file(tmp_path, "good_three", valid_python_tool_yaml(name="Good Three"))
    workflow_file = _workflow_file(tmp_path, "bad_one", "bad_two", "good_three")

    workflow = parse_workflow_yaml(
        workflow_file,
        _discovery_git_ref="main",
        _discovery_git_service=SnapshotGitService(tmp_path),
    )

    soul = _tool_soul(workflow)
    assert soul.tools == ["bad_one", "bad_two", "good_three"]
    assert soul.resolved_tools is not None
    assert [tool.name for tool in soul.resolved_tools] == ["good_three"]


def test_snapshot_parse_fails_closed_for_missing_sibling_tool(tmp_path) -> None:
    write_custom_tool_file(tmp_path, "bad_one", corrupt_python_tool_yaml(name="Bad One"))
    workflow_file = _workflow_file(tmp_path, "bad_one", "missing_unused", soul_tools=("bad_one",))

    with pytest.raises(ValueError, match="missing_unused"):
        parse_workflow_yaml(
            workflow_file,
            _discovery_git_ref="main",
            _discovery_git_service=SnapshotGitService(tmp_path),
        )


def test_valid_builtin_and_discovered_custom_tool_ids_parse_successfully(tmp_path) -> None:
    write_custom_tool_file(tmp_path, "echo_tool", valid_python_tool_yaml(name="Echo Tool"))
    workflow = parse_workflow_yaml(_workflow_file(tmp_path, "http", "echo_tool"))

    soul = _tool_soul(workflow)
    assert soul.resolved_tools is not None
    assert len(soul.resolved_tools) == 2
    assert soul.tools == ["http", "echo_tool"]


def test_request_backed_custom_tool_file_parses_successfully(tmp_path) -> None:
    write_custom_tool_file(tmp_path, "fetch_answer", request_tool_yaml())
    workflow = parse_workflow_yaml(_workflow_file(tmp_path, "fetch_answer"))

    soul = _tool_soul(workflow)
    assert soul.resolved_tools is not None
    assert [tool.name for tool in soul.resolved_tools] == ["fetch_answer"]


@pytest.mark.parametrize(
    ("slug", "metadata_case", "expected_message"),
    [
        (
            "legacy_http",
            "legacy_http",
            r"(?s)(?:legacy_http.*type.*custom|legacy_http.*unsupported)",
        ),
        ("missing_request_url", "missing_request_url", r"(?s)missing_request_url.*url"),
        ("python_with_request", "python_with_request", r"python_with_request.*request"),
    ],
)
def test_invalid_custom_tool_metadata_surfaces_file_specific_errors(
    tmp_path, slug, metadata_case, expected_message
) -> None:
    write_custom_tool_file(tmp_path, slug, invalid_custom_tool_metadata_yaml(metadata_case))
    workflow_file = _workflow_file(tmp_path, slug)

    with pytest.raises(ValueError, match=expected_message):
        parse_workflow_yaml(workflow_file)
