from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest
import yaml
from runsight_core.yaml.discovery import AssertionScanner, SoulScanner, ToolScanner, WorkflowScanner
from runsight_core.yaml.discovery._base import ScanIndex

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class FixtureScanResult:
    path: Path
    stem: str
    entity_id: str
    relative_path: str
    item: str
    aliases: frozenset[str]


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_soul_fixture(base_dir: Path, *, stem: str, entity_id: str, name: str) -> Path:
    path = base_dir / "custom" / "souls" / f"{stem}.yaml"
    _write_yaml(
        path,
        {
            "id": entity_id,
            "kind": "soul",
            "name": name,
            "role": name,
            "system_prompt": f"You are {name}.",
        },
    )
    return path


def _write_tool_fixture(base_dir: Path, *, stem: str, entity_id: str, name: str) -> Path:
    path = base_dir / "custom" / "tools" / f"{stem}.yaml"
    _write_yaml(
        path,
        {
            "version": "1.0",
            "id": entity_id,
            "kind": "tool",
            "type": "custom",
            "executor": "python",
            "name": name,
            "description": f"Tool {name}",
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


def _write_workflow_fixture(base_dir: Path, *, stem: str, entity_id: str, name: str) -> Path:
    path = base_dir / "custom" / "workflows" / f"{stem}.yaml"
    _write_yaml(
        path,
        {
            "version": "1.0",
            "id": entity_id,
            "kind": "workflow",
            "blocks": {
                "step": {"type": "linear", "soul_ref": "researcher"},
            },
            "workflow": {
                "name": name,
                "entry": "step",
                "transitions": [{"from": "step", "to": None}],
            },
        },
    )
    return path


def _write_nested_workflow_fixture(
    base_dir: Path,
    *,
    relative_path: str,
    entity_id: str,
    name: str,
) -> Path:
    path = base_dir / "custom" / "workflows" / relative_path
    _write_yaml(
        path,
        {
            "version": "1.0",
            "id": entity_id,
            "kind": "workflow",
            "blocks": {
                "step": {"type": "linear", "soul_ref": "researcher"},
            },
            "workflow": {
                "name": name,
                "entry": "step",
                "transitions": [{"from": "step", "to": None}],
            },
        },
    )
    return path


def _write_assertion_fixture(base_dir: Path, *, stem: str, entity_id: str, name: str) -> Path:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)
    source_path = assertions_dir / f"{stem}.py"
    source_path.write_text(
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
            "id": entity_id,
            "kind": "assertion",
            "name": name,
            "description": f"Assertion {name}",
            "returns": "bool",
            "source": f"{stem}.py",
        },
    )
    return path


def _fake_result(*, stem: str, entity_id: str, item: str) -> FixtureScanResult:
    return FixtureScanResult(
        path=ROOT / "custom" / "souls" / f"{stem}.yaml",
        stem=stem,
        entity_id=entity_id,
        relative_path=f"custom/souls/{stem}.yaml",
        item=item,
        aliases=frozenset({entity_id, stem}),
    )


def test_scan_index_ids_and_without_ids_use_entity_id() -> None:
    index = ScanIndex(
        [
            _fake_result(stem="researcher_legacy", entity_id="researcher", item="researcher"),
            _fake_result(stem="reviewer_legacy", entity_id="reviewer", item="reviewer"),
        ]
    )

    assert index.ids() == {"researcher": "researcher", "reviewer": "reviewer"}
    assert index.without_ids({"researcher"}).ids() == {"reviewer": "reviewer"}


def test_scan_index_get_does_not_register_filename_stem_alias() -> None:
    index = ScanIndex(
        [_fake_result(stem="researcher_legacy", entity_id="researcher", item="researcher")]
    )

    assert index.get("researcher") is not None
    assert index.get("researcher_legacy") is None


def test_scan_index_rejects_duplicate_entity_id_with_colliding_context() -> None:
    index = ScanIndex()
    index.add(_fake_result(stem="researcher_a", entity_id="researcher", item="first"))

    with pytest.raises(ValueError) as exc_info:
        index.add(
            FixtureScanResult(
                path=ROOT / "custom" / "souls" / "researcher_copy.yaml",
                stem="researcher_copy",
                entity_id="researcher",
                relative_path="custom/souls/researcher_copy.yaml",
                item="second",
                aliases=frozenset({"researcher", "researcher_copy"}),
            )
        )

    message = str(exc_info.value)
    assert "researcher" in message
    assert "researcher_copy" in message
    assert "duplicate" in message.lower()


@pytest.mark.parametrize(
    ("scanner_cls", "write_fixture", "stem", "entity_id", "name"),
    [
        (SoulScanner, _write_soul_fixture, "researcher", "researcher", "Senior Researcher"),
        (
            ToolScanner,
            _write_tool_fixture,
            "slack_payload_builder",
            "slack_payload_builder",
            "Slack Payload Builder",
        ),
        (
            WorkflowScanner,
            _write_workflow_fixture,
            "research-review",
            "research-review",
            "Research & Review",
        ),
        (
            AssertionScanner,
            _write_assertion_fixture,
            "budget_guard",
            "budget_guard",
            "Budget Guard",
        ),
    ],
)
def test_scanner_results_expose_entity_id(
    tmp_path: Path,
    scanner_cls,
    write_fixture,
    stem: str,
    entity_id: str,
    name: str,
) -> None:
    write_fixture(tmp_path, stem=stem, entity_id=entity_id, name=name)

    index = scanner_cls(tmp_path).scan()
    result = index.get(stem)

    assert result is not None
    assert result.entity_id == entity_id


@pytest.mark.parametrize(
    ("scanner_cls", "write_fixture", "stem", "entity_id", "name", "match_text"),
    [
        (
            SoulScanner,
            _write_soul_fixture,
            "researcher",
            "researcher_v2",
            "Senior Researcher",
            "researcher",
        ),
        (
            ToolScanner,
            _write_tool_fixture,
            "slack_payload_builder",
            "slack_payload_builder_v2",
            "Slack Payload Builder",
            "slack_payload_builder",
        ),
        (
            AssertionScanner,
            _write_assertion_fixture,
            "budget_guard",
            "budget_guard_v2",
            "Budget Guard",
            "budget_guard",
        ),
    ],
)
def test_scanners_reject_filename_stem_mismatch(
    tmp_path: Path,
    scanner_cls,
    write_fixture,
    stem: str,
    entity_id: str,
    name: str,
    match_text: str,
) -> None:
    write_fixture(tmp_path, stem=stem, entity_id=entity_id, name=name)

    with pytest.raises(ValueError, match=match_text):
        scanner_cls(tmp_path).scan()


def test_workflow_scanner_rejects_duplicate_entity_id_across_nested_paths(
    tmp_path: Path,
) -> None:
    _write_nested_workflow_fixture(
        tmp_path,
        relative_path="alpha/research-review.yaml",
        entity_id="research-review",
        name="Research & Review",
    )
    _write_nested_workflow_fixture(
        tmp_path,
        relative_path="beta/research-review.yaml",
        entity_id="research-review",
        name="Research & Review Copy",
    )

    with pytest.raises(ValueError, match="duplicate"):
        WorkflowScanner(tmp_path).scan()
