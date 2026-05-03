"""Smoke governance for the API SSE streaming test-suite boundary.

Owner: tools/tests owns static repo-layout governance for cross-workspace test
structure.
Boundary: apps/api/tests/logic owns StreamingObserver and subscribe_stream
service behavior; apps/api/tests/transport owns HTTP SSE chunk transport
behavior. Shared workflow YAML fixtures must stay in apps/api/tests/fixtures.
Exit criteria: delete this suite once a broader repo test-layout checker
enforces equivalent split-suite and fixture-owner rules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_TESTS = REPO_ROOT / "apps" / "api" / "tests"
LEGACY_OMNIBUS_SUITE = API_TESTS / "test_sse_streaming_integration.py"
HELPER_MODULE = API_TESTS / "sse_streaming_helpers.py"

SSE_STREAMING_SPLIT_SUITES = (
    API_TESTS / "logic" / "test_sse_streaming_service_events.py",
    API_TESTS / "transport" / "test_sse_streaming_http_chunks.py",
)

SSE_STREAMING_FIXTURES = (
    API_TESTS / "fixtures" / "sse_streaming" / "single-block.yaml",
    API_TESTS / "fixtures" / "sse_streaming" / "two-block.yaml",
    API_TESTS / "fixtures" / "sse_streaming" / "parent-workflow.yaml",
    API_TESTS / "fixtures" / "sse_streaming" / "child-workflow.yaml",
)

pytestmark = pytest.mark.governance


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=_relative(path))


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return [target.id for target in targets if isinstance(target, ast.Name)]


def _imports_sse_helper(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.endswith("sse_streaming_helpers") for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.endswith("sse_streaming_helpers"):
                return True
            if any(alias.name == "sse_streaming_helpers" for alias in node.names):
                return True

    return False


def _module_level_yaml_constants(tree: ast.Module) -> list[str]:
    constants: list[str] = []

    for node in tree.body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        if not isinstance(node.value, ast.Constant | ast.JoinedStr):
            continue
        if isinstance(node.value, ast.Constant) and not isinstance(node.value.value, str):
            continue
        constants.extend(name for name in _assigned_names(node) if name.endswith("_YAML"))

    return constants


def test_api_sse_streaming_split_uses_owned_workflow_fixtures() -> None:
    """Owner/boundary/exit: keep SSE behavior split and API fixtures local."""
    failures: list[str] = []

    if LEGACY_OMNIBUS_SUITE.exists():
        failures.append(f"{_relative(LEGACY_OMNIBUS_SUITE)} must stay deleted.")

    for suite_path in SSE_STREAMING_SPLIT_SUITES:
        if not suite_path.is_file():
            failures.append(f"{_relative(suite_path)} is missing.")
            continue

        tree = _parsed(suite_path)
        if not _imports_sse_helper(tree):
            failures.append(
                f"{_relative(suite_path)} must import shared SSE setup from "
                f"{_relative(HELPER_MODULE)}."
            )

        inline_yaml = _module_level_yaml_constants(tree)
        if inline_yaml:
            failures.append(
                f"{_relative(suite_path)} must load API-owned workflow fixture files "
                "instead of declaring module-level *_YAML strings: " + ", ".join(inline_yaml)
            )

    if not HELPER_MODULE.is_file():
        failures.append(f"{_relative(HELPER_MODULE)} is missing.")

    missing_fixtures = [
        _relative(fixture_path)
        for fixture_path in SSE_STREAMING_FIXTURES
        if not fixture_path.is_file()
    ]
    if missing_fixtures:
        failures.append(
            "API-owned SSE workflow fixtures are missing:\n"
            + "\n".join(f"  - {path}" for path in missing_fixtures)
        )

    assert not failures, "\n".join(failures)
