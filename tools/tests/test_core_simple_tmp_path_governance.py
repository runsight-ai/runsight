"""Governance tests for simple core behavior-test tmp_path ownership.

Owner: tools/tests owns temporary static checks for core test workspace
ownership migrations.
Boundary: the listed normal core behavior suites must accept pytest tmp_path
and build test files under that pytest-owned path instead of creating unmanaged
TemporaryDirectory workspaces. This suite inspects only those repo-owned tests;
central conftest isolation fixtures and larger scanner/parser suites are
separate checkpoints and are intentionally out of scope.
Exit criteria: delete this suite once the target behavior tests use tmp_path
directly or through package-owned fixtures while preserving their behavior
coverage.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_CORE_BEHAVIOR_SUITES = (
    REPO_ROOT / "packages" / "core" / "tests" / "test_discover_soul_fields.py",
    REPO_ROOT / "packages" / "core" / "tests" / "test_observer.py",
    REPO_ROOT / "packages" / "core" / "tests" / "test_observer_soul_extension.py",
    REPO_ROOT / "packages" / "core" / "tests" / "test_tool_pydantic_validation.py",
)

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class TemporaryDirectoryReference:
    path: Path
    line_number: int
    kind: str
    detail: str


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _temporary_directory_import_aliases(
    tree: ast.Module,
    path: Path,
) -> tuple[dict[str, str], list[TemporaryDirectoryReference]]:
    aliases: dict[str, str] = {}
    references: list[TemporaryDirectoryReference] = []

    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name == "tempfile":
                    imported_name = alias.asname or alias.name
                    aliases[imported_name] = "tempfile"
        elif isinstance(statement, ast.ImportFrom) and statement.module == "tempfile":
            for alias in statement.names:
                if alias.name != "TemporaryDirectory":
                    continue
                imported_name = alias.asname or alias.name
                aliases[imported_name] = "TemporaryDirectory"
                references.append(
                    TemporaryDirectoryReference(
                        path=path,
                        line_number=statement.lineno,
                        kind="import",
                        detail=f"from tempfile import {alias.name}",
                    )
                )

    return aliases, references


def _temporary_directory_references(path: Path) -> list[TemporaryDirectoryReference]:
    tree = _source_tree(path)
    aliases, references = _temporary_directory_import_aliases(tree, path)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Attribute) and node.func.attr == "TemporaryDirectory":
            if (
                isinstance(node.func.value, ast.Name)
                and aliases.get(node.func.value.id) == "tempfile"
            ):
                references.append(
                    TemporaryDirectoryReference(
                        path=path,
                        line_number=node.lineno,
                        kind="call",
                        detail=f"{node.func.value.id}.TemporaryDirectory()",
                    )
                )
        elif isinstance(node.func, ast.Name) and aliases.get(node.func.id) == "TemporaryDirectory":
            references.append(
                TemporaryDirectoryReference(
                    path=path,
                    line_number=node.lineno,
                    kind="call",
                    detail=f"{node.func.id}()",
                )
            )

    return references


def test_simple_core_behavior_suites_use_pytest_owned_tmp_path() -> None:
    """Owner/boundary/exit: simple core behavior workspaces are pytest-owned."""
    references = [
        reference
        for suite_path in TARGET_CORE_BEHAVIOR_SUITES
        for reference in _temporary_directory_references(suite_path)
    ]

    assert references == [], (
        "Simple core behavior tests must not create unmanaged "
        "tempfile.TemporaryDirectory workspaces. Accept pytest tmp_path in the "
        "test or fixture and build all test files under that pytest-owned path. "
        "This policy intentionally scans only the four simple core behavior "
        "suites in TARGET_CORE_BEHAVIOR_SUITES; conftest.py isolation fixtures "
        "and larger scanner/parser suites are separate checkpoints. Found:\n"
        + "\n".join(
            f"  - {_relative(reference.path)}:{reference.line_number} "
            f"{reference.kind} {reference.detail}"
            for reference in references
        )
    )
