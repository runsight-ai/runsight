"""Smoke governance for API filesystem repository workspace ownership.

Owner: tools/tests owns this temporary static boundary check.
Boundary: API filesystem repository behavior suites must build repository
workspaces under pytest-owned tmp_path, not unmanaged tempfile directories.
Exit criteria: delete this suite once the targeted API filesystem repository
tests preserve behavior coverage while using tmp_path-owned workspaces.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_FILESYSTEM_REPOSITORY_TESTS = (
    REPO_ROOT / "apps" / "api" / "tests" / "data" / "test_base_yaml_identity.py",
    REPO_ROOT
    / "apps"
    / "api"
    / "tests"
    / "unit"
    / "data"
    / "filesystem"
    / "test_provider_repo_identity.py",
    REPO_ROOT / "apps" / "api" / "tests" / "data" / "test_base_yaml_repository.py",
    REPO_ROOT / "apps" / "api" / "tests" / "data" / "test_filesystem.py",
    REPO_ROOT / "apps" / "api" / "tests" / "data" / "test_soul_repo.py",
)

pytestmark = pytest.mark.governance


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _temporary_directory_uses(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tempfile_aliases: set[str] = set()
    temporary_directory_aliases: set[str] = set()
    findings: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tempfile":
                    tempfile_aliases.add(alias.asname or alias.name)
                    findings.append(f"line {node.lineno}: import tempfile")
            continue

        if isinstance(node, ast.ImportFrom) and node.module == "tempfile":
            for alias in node.names:
                if alias.name == "TemporaryDirectory":
                    temporary_directory_aliases.add(alias.asname or alias.name)
                    findings.append(f"line {node.lineno}: from tempfile import TemporaryDirectory")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id in tempfile_aliases
            and func.attr == "TemporaryDirectory"
        ):
            findings.append(f"line {node.lineno}: {func.value.id}.TemporaryDirectory(...)")
        elif isinstance(func, ast.Name) and func.id in temporary_directory_aliases:
            findings.append(f"line {node.lineno}: {func.id}(...)")

    return findings


def test_api_filesystem_repository_workspaces_use_pytest_owned_tmp_path() -> None:
    """Owner/boundary/exit: keep repository workspaces under pytest tmp_path."""
    findings = {
        _relative(path): uses
        for path in API_FILESYSTEM_REPOSITORY_TESTS
        if (uses := _temporary_directory_uses(path))
    }

    assert not findings, (
        "API filesystem repository behavior suites must not import or call "
        "tempfile.TemporaryDirectory for repository workspaces. Accept pytest's "
        "tmp_path fixture and build workspaces under it instead:\n"
        + "\n".join(f"  - {path}: {', '.join(uses)}" for path, uses in findings.items())
    )
