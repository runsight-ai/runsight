"""Governance tests for core wire soul_ref library fixture ownership.

Owner: tools/tests owns temporary static checks for core test fixture ownership
migrations.
Boundary: wire soul_ref library parser behavior tests should build parser
workspaces with pytest tmp_path and should centralize custom/souls YAML setup
through the existing local _write_soul_file helper or parser_yaml_helpers. This
suite inspects only repo-owned test source, not runtime or user state. Inline
workflow snippets passed to _write_workflow_file may remain local for this
checkpoint.
Exit criteria: delete this suite once wire soul_ref library behavior tests use
pytest-owned workspaces and helper-built custom/souls setup.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WIRE_SOUL_REF_LIBRARY_TEST = (
    REPO_ROOT / "packages" / "core" / "tests" / "test_wire_soul_ref_to_library.py"
)

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class TemporaryDirectoryUse:
    line_number: int
    reason: str


@dataclass(frozen=True)
class InlineSoulYamlWrite:
    line_number: int
    test_name: str


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        if parent is None:
            return node.attr
        return f"{parent}.{node.attr}"
    return None


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dedent_literal_arg(call: ast.Call) -> str | None:
    if _call_name(call.func) != "dedent" or not call.args:
        return None
    return _literal_string(call.args[0])


def _tempfile_temporary_directory_uses(path: Path) -> list[TemporaryDirectoryUse]:
    uses: list[TemporaryDirectoryUse] = []

    for node in ast.walk(_source_tree(path)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tempfile":
                    uses.append(
                        TemporaryDirectoryUse(
                            line_number=node.lineno,
                            reason="imports tempfile for unmanaged parser workspaces",
                        )
                    )
        elif isinstance(node, ast.ImportFrom) and node.module == "tempfile":
            for alias in node.names:
                if alias.name == "TemporaryDirectory":
                    uses.append(
                        TemporaryDirectoryUse(
                            line_number=node.lineno,
                            reason="imports TemporaryDirectory for unmanaged parser workspaces",
                        )
                    )
        elif isinstance(node, ast.Call):
            if _call_name(node.func) in {"tempfile.TemporaryDirectory", "TemporaryDirectory"}:
                uses.append(
                    TemporaryDirectoryUse(
                        line_number=node.lineno,
                        reason="creates parser workspace with tempfile.TemporaryDirectory",
                    )
                )

    return sorted(uses, key=lambda use: use.line_number)


def _inline_soul_yaml_writes(path: Path) -> list[InlineSoulYamlWrite]:
    writes: list[InlineSoulYamlWrite] = []

    for function in (
        node for node in ast.walk(_source_tree(path)) if isinstance(node, ast.FunctionDef)
    ):
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node.func) != "write_text" or not node.args:
                continue
            first_arg = node.args[0]
            if not isinstance(first_arg, ast.Call):
                continue
            text = _dedent_literal_arg(first_arg)
            if text is None:
                continue
            if "kind: soul" not in text.lower():
                continue

            writes.append(
                InlineSoulYamlWrite(
                    line_number=node.lineno,
                    test_name=function.name,
                )
            )

    return sorted(writes, key=lambda write: write.line_number)


def test_wire_soul_ref_library_fixture_ownership_boundary() -> None:
    """Wire soul_ref library parser fixtures should stay pytest-owned and helper-built."""
    temporary_directory_uses = _tempfile_temporary_directory_uses(WIRE_SOUL_REF_LIBRARY_TEST)
    inline_soul_writes = _inline_soul_yaml_writes(WIRE_SOUL_REF_LIBRARY_TEST)

    violations: list[str] = []
    if temporary_directory_uses:
        violations.append(
            "uses tempfile.TemporaryDirectory instead of pytest tmp_path for "
            "parser workspaces:\n"
            + "\n".join(
                f"  - line {use.line_number}: {use.reason}" for use in temporary_directory_uses
            )
        )
    if inline_soul_writes:
        violations.append(
            "writes structured custom/souls YAML inline with "
            '.write_text(dedent("""... kind: soul ...""")) instead of helpers:\n'
            + "\n".join(
                f"  - line {write.line_number}: {write.test_name} writes soul YAML"
                for write in inline_soul_writes
            )
        )

    assert violations == [], (
        f"{_relative(WIRE_SOUL_REF_LIBRARY_TEST)} must use pytest's tmp_path "
        "for parser workspaces and the existing local _write_soul_file helper "
        "or parser_yaml_helpers for custom/souls setup. Inline workflow "
        "snippets passed to _write_workflow_file may remain local for this "
        "checkpoint. Found:\n" + "\n".join(f"- {violation}" for violation in violations)
    )


def test_wire_soul_ref_library_workspaces_use_pytest_tmp_path() -> None:
    """Parser workspaces should be visible to pytest-owned cleanup."""
    temporary_directory_uses = _tempfile_temporary_directory_uses(WIRE_SOUL_REF_LIBRARY_TEST)

    assert temporary_directory_uses == [], (
        f"{_relative(WIRE_SOUL_REF_LIBRARY_TEST)} must not import or call "
        "tempfile.TemporaryDirectory for parser workspaces. Use pytest's "
        "tmp_path fixture and build custom/souls plus workflow files under "
        "that pytest-owned path. Found:\n"
        + "\n".join(f"  - line {use.line_number}: {use.reason}" for use in temporary_directory_uses)
    )


def test_wire_soul_ref_library_soul_yaml_setup_uses_helpers() -> None:
    """Structured custom/souls setup should stay in local/parser YAML helpers."""
    inline_soul_writes = _inline_soul_yaml_writes(WIRE_SOUL_REF_LIBRARY_TEST)

    assert inline_soul_writes == [], (
        f"{_relative(WIRE_SOUL_REF_LIBRARY_TEST)} must not write structured "
        "custom/souls YAML inline via "
        '.write_text(dedent("""... kind: soul ...""")). Use _write_soul_file '
        "or parser_yaml_helpers.write_custom_soul_file so soul library behavior "
        "tests describe behavior instead of rebuilding YAML by hand. Inline "
        "workflow snippets passed to _write_workflow_file may remain local for "
        "this checkpoint. Found:\n"
        + "\n".join(
            f"  - line {write.line_number}: {write.test_name} writes soul YAML"
            for write in inline_soul_writes
        )
    )
