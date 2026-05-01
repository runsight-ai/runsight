"""Governance tests for core parser soul field forwarding fixture ownership.

Owner: tools/tests owns temporary static checks for core test fixture ownership
migrations.
Boundary: parser workflow payloads for soul field forwarding behavior belong
under packages/core/tests/fixtures/workflows and should be loaded through
packages/core/tests/workflow_fixture_helpers.py or the existing core fixture
helper pattern. Parser runtime workspaces in the behavior suite must be owned
by pytest tmp_path rather than unmanaged tempfile contexts. This suite inspects
only repo-owned source, not runtime or user state. Small inline soul snippets
and scalar assertions are intentionally outside this check.
Exit criteria: delete this suite once the parser soul field forwarding workflow
payloads have been externalized and the behavior tests preserve field
forwarding coverage through package-owned fixtures and tmp_path.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PARSER_SOUL_FIELD_FORWARDING_TEST = (
    REPO_ROOT / "packages" / "core" / "tests" / "test_parser_soul_field_forwarding.py"
)
WORKFLOW_WRITER_HELPERS = frozenset({"_write_workflow_file", "write_workflow_file"})

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class InlineWorkflowPayload:
    line_number: int
    helper_name: str
    workflow_id: str
    workflow_name: str
    block_names: tuple[str, ...]


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _workflow_details(text: str) -> tuple[str, str, tuple[str, ...]] | None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None
    if parsed.get("kind") != "workflow":
        return None

    workflow = parsed.get("workflow")
    blocks = parsed.get("blocks")
    if not isinstance(workflow, dict) or not isinstance(blocks, dict):
        return None

    workflow_id = parsed.get("id")
    workflow_name = workflow.get("name")
    if not isinstance(workflow_id, str):
        workflow_id = "<missing id>"
    if not isinstance(workflow_name, str):
        workflow_name = "<missing workflow.name>"

    block_names = tuple(sorted(name for name in blocks if isinstance(name, str)))
    return workflow_id, workflow_name, block_names


def _workflow_writer_payload_arg(call: ast.Call) -> ast.AST | None:
    helper_name = _call_name(call.func)
    if helper_name not in WORKFLOW_WRITER_HELPERS:
        return None
    if len(call.args) >= 2:
        return call.args[1]
    for keyword in call.keywords:
        if keyword.arg in {"yaml_content", "content", "workflow_yaml"}:
            return keyword.value
    return None


def _inline_workflow_payloads(path: Path) -> list[InlineWorkflowPayload]:
    payloads: list[InlineWorkflowPayload] = []
    for node in ast.walk(_source_tree(path)):
        if not isinstance(node, ast.Call):
            continue

        payload_arg = _workflow_writer_payload_arg(node)
        if payload_arg is None:
            continue

        text = _literal_string(payload_arg)
        if text is None:
            continue

        details = _workflow_details(text)
        if details is None:
            continue

        workflow_id, workflow_name, block_names = details
        helper_name = _call_name(node.func)
        payloads.append(
            InlineWorkflowPayload(
                line_number=node.lineno,
                helper_name=helper_name or "<unknown helper>",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                block_names=block_names,
            )
        )
    return payloads


def _temporary_directory_lines(path: Path) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(_source_tree(path))
        if isinstance(node, ast.Call) and _call_name(node.func) == "tempfile.TemporaryDirectory"
    ]


def test_parser_soul_field_forwarding_fixture_ownership_boundary() -> None:
    """Parser workspace and workflow payload ownership should stay explicit."""
    temporary_directory_lines = _temporary_directory_lines(PARSER_SOUL_FIELD_FORWARDING_TEST)
    payloads = _inline_workflow_payloads(PARSER_SOUL_FIELD_FORWARDING_TEST)

    violations: list[str] = []
    if temporary_directory_lines:
        violations.append(
            "uses tempfile.TemporaryDirectory for parser workspaces at lines "
            + ", ".join(str(line) for line in temporary_directory_lines)
        )
    if payloads:
        violations.append(
            "passes inline workflow-shaped YAML to workflow-writing helpers:\n"
            + "\n".join(
                "  - "
                f"{payload.helper_name} at line {payload.line_number} "
                f"(id={payload.workflow_id}, workflow={payload.workflow_name}, "
                f"blocks={', '.join(payload.block_names)})"
                for payload in payloads
            )
        )

    assert violations == [], (
        f"{_relative(PARSER_SOUL_FIELD_FORWARDING_TEST)} must use pytest's "
        "tmp_path for parser workspaces and package-owned workflow fixtures "
        "from packages/core/tests/fixtures/workflows loaded through "
        "workflow_fixture_helpers.py or the existing core fixture helper "
        "pattern. Small inline soul snippets and scalar assertions may remain "
        "local. Found:\n" + "\n".join(f"- {violation}" for violation in violations)
    )


def test_parser_soul_field_forwarding_workspace_uses_pytest_tmp_path() -> None:
    """Parser workspace setup should be visible to pytest-owned tmp_path cleanup."""
    temporary_directory_lines = _temporary_directory_lines(PARSER_SOUL_FIELD_FORWARDING_TEST)

    assert temporary_directory_lines == [], (
        f"{_relative(PARSER_SOUL_FIELD_FORWARDING_TEST)} must not create parser "
        "runtime workspaces with tempfile.TemporaryDirectory. Use pytest's "
        "tmp_path fixture and build custom/souls plus workflow files under that "
        "pytest-owned path. Found TemporaryDirectory calls at lines: "
        + ", ".join(str(line) for line in temporary_directory_lines)
    )


def test_parser_soul_field_forwarding_uses_package_owned_workflow_fixtures() -> None:
    """Reusable parser workflows should live in core workflow fixtures."""
    payloads = _inline_workflow_payloads(PARSER_SOUL_FIELD_FORWARDING_TEST)

    assert payloads == [], (
        f"{_relative(PARSER_SOUL_FIELD_FORWARDING_TEST)} must not pass inline "
        "workflow-shaped YAML payloads to workflow-writing helpers for parser "
        "soul field forwarding cases. Move these payloads to "
        "packages/core/tests/fixtures/workflows with behavior-focused names and "
        "load them through workflow_fixture_helpers.py or the existing core "
        "fixture helper pattern. Small inline soul snippets and scalar "
        "assertions may remain local. Found:\n"
        + "\n".join(
            "  - "
            f"{payload.helper_name} at line {payload.line_number} "
            f"(id={payload.workflow_id}, workflow={payload.workflow_name}, "
            f"blocks={', '.join(payload.block_names)})"
            for payload in payloads
        )
    )
