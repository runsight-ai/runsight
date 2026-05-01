"""Governance tests for core discovery scanner fixture ownership.

Owner: tools/tests owns temporary static checks for core test fixture ownership
migrations.
Boundary: discovery scanner behavior tests should build custom/souls and
custom/tools workspaces with pytest tmp_path plus owning-suite helpers such as
_write_soul_yaml and _write_tool_yaml, or package-local fixtures. This suite
inspects only repo-owned test source, not runtime or user state. Small scalar
strings and source-policy assertions are intentionally outside this check.
Exit criteria: delete this suite once discovery scanner tests use pytest-owned
workspaces and local helpers or package-owned fixtures for repeated structured
soul and tool YAML setup.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_SCANNER_TEST = REPO_ROOT / "packages" / "core" / "tests" / "test_discovery.py"
ALLOWED_YAML_BUILDER_HELPERS = frozenset({"_write_soul_yaml", "_write_tool_yaml"})

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class TemporaryDirectoryUse:
    line_number: int
    reason: str


@dataclass(frozen=True)
class InlineScannerYamlWrite:
    line_number: int
    test_name: str
    asset_kind: str
    yaml_marker: str


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


def _structured_scanner_yaml_marker(text: str) -> tuple[str, str] | None:
    normalized = text.lower()
    if "kind: soul" in normalized:
        return "soul", "kind: soul"
    if "kind: tool" in normalized:
        return "tool", "kind: tool"
    if "version:" in normalized and "kind:" in normalized and "executor:" in normalized:
        return "tool", "version/kind/executor"
    return None


def _tempfile_temporary_directory_uses(path: Path) -> list[TemporaryDirectoryUse]:
    tree = _source_tree(path)
    uses: list[TemporaryDirectoryUse] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tempfile":
                    uses.append(
                        TemporaryDirectoryUse(
                            line_number=node.lineno,
                            reason="imports tempfile for unmanaged discovery workspaces",
                        )
                    )
        elif isinstance(node, ast.ImportFrom) and node.module == "tempfile":
            for alias in node.names:
                if alias.name == "TemporaryDirectory":
                    uses.append(
                        TemporaryDirectoryUse(
                            line_number=node.lineno,
                            reason="imports TemporaryDirectory for unmanaged discovery workspaces",
                        )
                    )
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            if call_name in {"tempfile.TemporaryDirectory", "TemporaryDirectory"}:
                uses.append(
                    TemporaryDirectoryUse(
                        line_number=node.lineno,
                        reason="creates scanner workspace with tempfile.TemporaryDirectory",
                    )
                )

    return sorted(uses, key=lambda use: use.line_number)


def _inline_scanner_yaml_writes(path: Path) -> list[InlineScannerYamlWrite]:
    payloads: list[InlineScannerYamlWrite] = []

    for function in (
        node for node in ast.walk(_source_tree(path)) if isinstance(node, ast.FunctionDef)
    ):
        if function.name in ALLOWED_YAML_BUILDER_HELPERS:
            continue

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
            marker = _structured_scanner_yaml_marker(text)
            if marker is None:
                continue

            asset_kind, yaml_marker = marker
            payloads.append(
                InlineScannerYamlWrite(
                    line_number=node.lineno,
                    test_name=function.name,
                    asset_kind=asset_kind,
                    yaml_marker=yaml_marker,
                )
            )

    return sorted(payloads, key=lambda payload: payload.line_number)


def test_discovery_scanner_fixture_ownership_boundary() -> None:
    """Discovery scanner fixture setup should stay pytest-owned and helper-built."""
    temporary_directory_uses = _tempfile_temporary_directory_uses(DISCOVERY_SCANNER_TEST)
    inline_yaml_writes = _inline_scanner_yaml_writes(DISCOVERY_SCANNER_TEST)

    violations: list[str] = []
    if temporary_directory_uses:
        violations.append(
            "uses tempfile.TemporaryDirectory instead of pytest tmp_path for "
            "discovery scanner workspaces:\n"
            + "\n".join(
                f"  - line {use.line_number}: {use.reason}" for use in temporary_directory_uses
            )
        )
    if inline_yaml_writes:
        violations.append(
            "writes repeated structured custom/souls or custom/tools YAML inline "
            'with .write_text(dedent("""...""")) instead of local builders:\n'
            + "\n".join(
                "  - "
                f"line {payload.line_number}: {payload.test_name} writes "
                f"{payload.asset_kind} YAML ({payload.yaml_marker})"
                for payload in inline_yaml_writes
            )
        )

    assert violations == [], (
        f"{_relative(DISCOVERY_SCANNER_TEST)} must use pytest's tmp_path for "
        "discovery scanner workspaces and local owning-suite helpers such as "
        "_write_soul_yaml/_write_tool_yaml, or package-local fixtures, for "
        "repeated structured custom/souls and custom/tools YAML setup. Small "
        "scalar strings and source-policy assertions may remain inline. Found:\n"
        + "\n".join(f"- {violation}" for violation in violations)
    )


def test_discovery_scanner_workspaces_use_pytest_tmp_path() -> None:
    """Discovery scanner workspaces should be visible to pytest-owned cleanup."""
    temporary_directory_uses = _tempfile_temporary_directory_uses(DISCOVERY_SCANNER_TEST)

    assert temporary_directory_uses == [], (
        f"{_relative(DISCOVERY_SCANNER_TEST)} must not import or call "
        "tempfile.TemporaryDirectory for discovery scanner workspaces. Use "
        "pytest's tmp_path fixture and build custom/souls plus custom/tools "
        "under that pytest-owned path. Found:\n"
        + "\n".join(f"  - line {use.line_number}: {use.reason}" for use in temporary_directory_uses)
    )


def test_discovery_scanner_structured_yaml_setup_uses_local_builders() -> None:
    """Repeated scanner YAML setup should be centralized in owning-suite helpers."""
    inline_yaml_writes = _inline_scanner_yaml_writes(DISCOVERY_SCANNER_TEST)

    assert inline_yaml_writes == [], (
        f"{_relative(DISCOVERY_SCANNER_TEST)} must not keep repeated structured "
        "custom/souls or custom/tools YAML blobs inline via "
        '.write_text(dedent("""...""")). Use local helpers such as '
        "_write_soul_yaml/_write_tool_yaml or package-local fixtures so scanner "
        "behavior tests describe behavior instead of rebuilding YAML by hand. "
        "Small scalar strings and source-policy assertions may remain inline. "
        "Found:\n"
        + "\n".join(
            "  - "
            f"line {payload.line_number}: {payload.test_name} writes "
            f"{payload.asset_kind} YAML ({payload.yaml_marker})"
            for payload in inline_yaml_writes
        )
    )
