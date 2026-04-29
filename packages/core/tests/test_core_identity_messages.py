from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest
import yaml
from runsight_core.blocks._helpers import resolve_soul
from runsight_core.observer import LoggingObserver
from runsight_core.primitives import Soul
from runsight_core.state import WorkflowState
from runsight_core.tools._catalog import resolve_tool_id
from runsight_core.yaml.discovery import AssertionScanner, ToolScanner
from runsight_core.yaml.parser import (
    RunsightWorkflowFile,
    _validate_declared_tool_definitions,
    validate_tool_governance,
)


def _write_tool_fixture(base_dir: Path, *, stem: str, manifest_id: str) -> Path:
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "id": manifest_id,
        "kind": "tool",
        "type": "custom",
        "executor": "python",
        "name": "Lookup Profile",
        "description": "Looks up a profile.",
        "parameters": {"type": "object"},
        "code": dedent(
            """\
            def main(args):
                return args
            """
        ),
    }
    path = tools_dir / f"{stem}.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _write_assertion_fixture(base_dir: Path, *, stem: str, manifest_id: str) -> Path:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)

    (assertions_dir / "budget_guard.py").write_text(
        dedent(
            """\
            def get_assert(output, context):
                return True
            """
        ),
        encoding="utf-8",
    )
    payload = {
        "version": "1.0",
        "id": manifest_id,
        "kind": "assertion",
        "name": "Budget Guard",
        "description": "Keeps cost under budget.",
        "returns": "bool",
        "source": "budget_guard.py",
    }
    path = assertions_dir / f"{stem}.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _workflow_with_declared_soul_tool_violation() -> tuple[RunsightWorkflowFile, dict[str, Soul]]:
    file_def = RunsightWorkflowFile.model_validate(
        {
            "id": "research-review",
            "kind": "workflow",
            "blocks": {
                "research": {
                    "type": "linear",
                    "soul_ref": "researcher",
                }
            },
            "workflow": {
                "name": "research-review",
                "entry": "research",
                "transitions": [{"from": "research", "to": None}],
            },
        }
    )
    souls_map = {
        "researcher": Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Do research.",
            tools=["http"],
        )
    }
    return file_def, souls_map


def test_resolve_soul_missing_ref_mentions_kind_qualified_soul_ref() -> None:
    with pytest.raises(ValueError, match=r"soul:researcher"):
        resolve_soul("researcher", {})


def test_validate_tool_governance_mentions_kind_qualified_soul_and_tool_refs() -> None:
    file_def, souls_map = _workflow_with_declared_soul_tool_violation()

    result = validate_tool_governance(file_def, souls_map)

    assert result.has_warnings is True
    message = result.warnings[0].message
    assert "soul:researcher" in message
    assert "tool:http" in message


def test_tool_scanner_reserved_id_message_uses_kind_qualified_ref(tmp_path: Path) -> None:
    _write_tool_fixture(tmp_path, stem="lookup_profile", manifest_id="http")

    with pytest.raises(ValueError, match=r"tool:http"):
        ToolScanner(tmp_path).scan()


def test_assertion_scanner_reserved_id_message_uses_kind_qualified_ref(tmp_path: Path) -> None:
    _write_assertion_fixture(tmp_path, stem="budget_guard", manifest_id="contains")

    with pytest.raises(ValueError, match=r"assertion:contains"):
        AssertionScanner(tmp_path).scan()


def test_missing_custom_tool_metadata_mentions_kind_qualified_tool_ref(
    tmp_path: Path,
) -> None:
    file_def = RunsightWorkflowFile.model_validate(
        {
            "id": "research-review",
            "kind": "workflow",
            "tools": ["lookup_profile"],
            "workflow": {
                "name": "research-review",
                "entry": "research",
                "transitions": [{"from": "research", "to": None}],
            },
            "blocks": {},
        }
    )

    result = _validate_declared_tool_definitions(
        file_def,
        base_dir=str(tmp_path),
        require_custom_metadata=True,
    )

    assert result.has_warnings is True
    assert "tool:lookup_profile" in result.warnings[0].message


def test_unknown_custom_tool_id_mentions_kind_qualified_tool_ref(
    tmp_path: Path,
) -> None:
    file_def = RunsightWorkflowFile.model_validate(
        {
            "id": "research-review",
            "kind": "workflow",
            "tools": ["lookup_profile"],
            "workflow": {
                "name": "research-review",
                "entry": "research",
                "transitions": [{"from": "research", "to": None}],
            },
            "blocks": {},
        }
    )

    result = _validate_declared_tool_definitions(
        file_def,
        base_dir=str(tmp_path),
        require_custom_metadata=False,
    )

    assert result.has_warnings is True
    assert "tool:lookup_profile" in result.warnings[0].message


def test_reserved_builtin_tool_collision_mentions_kind_qualified_tool_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_scan_result = SimpleNamespace(
        ids=lambda: {"http": SimpleNamespace(file_path=Path("custom/tools/http.yaml"))}
    )

    monkeypatch.setattr(ToolScanner, "scan", lambda self: fake_scan_result)

    with pytest.raises(ValueError, match=r"tool:http"):
        resolve_tool_id("http", base_dir=".")


def test_workflow_start_log_mentions_kind_qualified_workflow_ref(
    caplog: pytest.LogCaptureFixture,
) -> None:
    observer = LoggingObserver()

    with caplog.at_level("INFO", logger="runsight.workflow"):
        observer.on_workflow_start("research-review", WorkflowState())

    assert "workflow:research-review" in caplog.text
