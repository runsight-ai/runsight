from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from runsight_core.identity import EntityKind, EntityRef
from runsight_core.primitives import Soul
from runsight_core.yaml.discovery import (
    AssertionScanner,
    SoulScanner,
    ToolScanner,
    WorkflowScanner,
)
from runsight_core.yaml.parser import validate_tool_governance
from runsight_core.yaml.registry import WorkflowRegistry
from runsight_core.yaml.schema import RunsightWorkflowFile


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_soul(base_dir: Path, *, stem: str, name: str, tools: list[str] | None = None) -> Path:
    path = base_dir / "custom" / "souls" / f"{stem}.yaml"
    _write_yaml(
        path,
        {
            "id": stem,
            "kind": "soul",
            "name": name,
            "role": name,
            "system_prompt": f"You are {name}.",
            **({"tools": tools} if tools is not None else {}),
        },
    )
    return path


def _write_tool(base_dir: Path, *, stem: str, tool_type: str = "custom") -> Path:
    path = base_dir / "custom" / "tools" / f"{stem}.yaml"
    _write_yaml(
        path,
        {
            "version": "1.0",
            "id": stem,
            "kind": "tool",
            "type": tool_type,
            "executor": "python",
            "name": stem.replace("_", " ").title(),
            "description": f"Tool {stem}",
            "parameters": {"type": "object"},
            "code": dedent(
                """\
                def main(args):
                    return args
                """
            ),
        },
    )
    return path


def _write_workflow(
    base_dir: Path,
    *,
    relative_path: str,
    workflow_id: str,
    workflow_name: str,
    child_ref: str | None = None,
) -> Path:
    path = base_dir / "custom" / "workflows" / relative_path
    blocks: dict[str, dict[str, object]] = {}
    if child_ref is not None:
        blocks = {"call_child": {"type": "workflow", "workflow_ref": child_ref}}
    _write_yaml(
        path,
        {
            "version": "1.0",
            "id": workflow_id,
            "kind": "workflow",
            "blocks": blocks,
            "workflow": {
                "name": workflow_name,
                "entry": "call_child" if child_ref is not None else "start",
                "transitions": [
                    {"from": "call_child" if child_ref is not None else "start", "to": None}
                ],
            },
        },
    )
    return path


def _write_assertion(base_dir: Path, *, stem: str, name: str) -> Path:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)
    (assertions_dir / f"{stem}.py").write_text(
        dedent(
            """\
            def get_assert(output, context):
                return True
            """
        ),
        encoding="utf-8",
    )
    path = assertions_dir / f"{stem}.yaml"
    _write_yaml(
        path,
        {
            "version": "1.0",
            "id": stem,
            "kind": "assertion",
            "name": name,
            "description": f"Assertion {name}",
            "returns": "bool",
            "source": f"{stem}.py",
        },
    )
    return path


def test_soul_scanner_round_trip_embedded_identity(tmp_path: Path) -> None:
    _write_soul(tmp_path, stem="researcher", name="Senior Researcher", tools=["slack_webhook"])

    soul = SoulScanner(tmp_path).scan().ids()["researcher"]

    assert isinstance(soul, Soul)
    assert soul.id == "researcher"
    assert soul.kind == "soul"
    assert soul.name == "Senior Researcher"
    assert soul.tools == ["slack_webhook"]


def test_tool_scanner_round_trip_embedded_identity(tmp_path: Path) -> None:
    _write_tool(tmp_path, stem="slack_webhook")

    item = ToolScanner(tmp_path).scan().ids()["slack_webhook"]

    assert item.tool_id == "slack_webhook"
    assert item.name == "Slack Webhook"
    assert item.type == "custom"


def test_assertion_scanner_round_trip_embedded_identity(tmp_path: Path) -> None:
    _write_assertion(tmp_path, stem="custom_contains", name="Contains")

    item = AssertionScanner(tmp_path).scan().ids()["custom_contains"]

    assert item.assertion_id == "custom_contains"
    assert item.manifest.kind == "assertion"
    assert item.manifest.name == "Contains"


def test_workflow_scanner_round_trip_embedded_identity(tmp_path: Path) -> None:
    _write_workflow(
        tmp_path,
        relative_path="research-review.yaml",
        workflow_id="research-review",
        workflow_name="Research Review",
    )

    item = WorkflowScanner(tmp_path).scan().ids()["research-review"]

    assert item.id == "research-review"
    assert item.kind == "workflow"
    assert item.workflow.name == "Research Review"


def test_tool_scanner_rejects_stem_mismatch_and_reserved_builtin_id(tmp_path: Path) -> None:
    mismatch_dir = tmp_path / "mismatch"
    mismatch_path = _write_tool(mismatch_dir, stem="slack_webhook_v2")
    mismatch_path.write_text(
        yaml.safe_dump(
            {
                "version": "1.0",
                "id": "slack_webhook_v3",
                "kind": "tool",
                "type": "custom",
                "executor": "python",
                "name": "Slack Webhook",
                "description": "Tool slack_webhook_v3",
                "parameters": {"type": "object"},
                "code": "def main(args):\n    return args\n",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"slack_webhook_v2\.yaml: embedded tool id 'slack_webhook_v3' does not match filename stem 'slack_webhook_v2'",
    ):
        ToolScanner(mismatch_dir).scan()

    reserved_dir = tmp_path / "reserved"
    reserved_path = reserved_dir / "custom" / "tools" / "http.yaml"
    _write_yaml(
        reserved_path,
        {
            "version": "1.0",
            "id": "http",
            "kind": "tool",
            "type": "custom",
            "executor": "python",
            "name": "HTTP",
            "description": "Reserved builtin tool",
            "parameters": {"type": "object"},
            "code": "def main(args):\n    return args\n",
        },
    )

    with pytest.raises(ValueError, match="tool:http"):
        ToolScanner(reserved_dir).scan()


def test_workflow_registry_accepts_embedded_ids_and_rejects_aliases() -> None:
    registry = WorkflowRegistry()
    workflow = RunsightWorkflowFile.model_validate(
        {
            "version": "1.0",
            "id": "research-review",
            "kind": "workflow",
            "blocks": {},
            "workflow": {
                "name": "Research Review",
                "entry": "start",
                "transitions": [],
            },
        }
    )
    registry.register(workflow.id, workflow)

    assert registry.get("research-review") is workflow

    with pytest.raises(ValueError, match="cannot resolve ref"):
        registry.get("Research Review")

    with pytest.raises(ValueError, match="cannot resolve ref"):
        registry.get("custom/workflows/research-review.yaml")


def test_tool_governance_error_mentions_kind_qualified_refs(tmp_path: Path) -> None:
    _write_soul(tmp_path, stem="researcher", name="Senior Researcher", tools=["slack_webhook"])
    workflow_file = RunsightWorkflowFile.model_validate(
        {
            "version": "1.0",
            "id": "research-review",
            "kind": "workflow",
            "blocks": {
                "research": {"type": "linear", "soul_ref": "researcher"},
            },
            "workflow": {
                "name": "Research Review",
                "entry": "research",
                "transitions": [{"from": "research", "to": None}],
            },
        }
    )

    result = validate_tool_governance(workflow_file, souls_map=SoulScanner(tmp_path).scan().ids())

    assert result.has_warnings is True
    message = result.warnings[0].message
    assert str(EntityRef(EntityKind.SOUL, "researcher")) in message
    assert str(EntityRef(EntityKind.TOOL, "slack_webhook")) in message


def test_workflow_scanner_rejects_duplicate_embedded_ids_across_nested_files(
    tmp_path: Path,
) -> None:
    _write_workflow(
        tmp_path,
        relative_path="branch-a/dup.yaml",
        workflow_id="dup",
        workflow_name="Duplicate Workflow A",
    )
    _write_workflow(
        tmp_path,
        relative_path="branch-b/dup.yaml",
        workflow_id="dup",
        workflow_name="Duplicate Workflow B",
    )

    with pytest.raises(ValueError, match="duplicate scan entity id collision"):
        WorkflowScanner(tmp_path).scan()
