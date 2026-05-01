"""
Governance tests for the API SSE streaming test-suite ownership boundary.

Owner: tools/tests owns static repo-layout governance for cross-workspace test
structure.
Boundary: apps/api/tests/logic owns StreamingObserver and subscribe_stream
service behavior; apps/api/tests/transport owns HTTP SSE chunk transport
behavior. This suite only checks that the old omnibus has been replaced by
behavior-named split suites, API-owned workflow fixtures, and shared API test
helpers.
Exit criteria: delete this suite once the SSE streaming split is complete and
a broader repo test-layout checker enforces equivalent suite and fixture
ownership rules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_TESTS = REPO_ROOT / "apps" / "api" / "tests"
LEGACY_OMNIBUS_SUITE = API_TESTS / "test_sse_streaming_integration.py"
HELPER_MODULE = API_TESTS / "sse_streaming_helpers.py"

REQUIRED_SPLIT_SUITES = (
    API_TESTS / "logic" / "test_sse_streaming_service_events.py",
    API_TESTS / "transport" / "test_sse_streaming_http_chunks.py",
)

REQUIRED_WORKFLOW_FIXTURES = (
    API_TESTS / "fixtures" / "sse_streaming" / "single-block.yaml",
    API_TESTS / "fixtures" / "sse_streaming" / "two-block.yaml",
    API_TESTS / "fixtures" / "sse_streaming" / "parent-workflow.yaml",
    API_TESTS / "fixtures" / "sse_streaming" / "child-workflow.yaml",
)

pytestmark = pytest.mark.governance


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parsed(path: Path) -> ast.Module:
    return ast.parse(_read(path), filename=_relative(path))


def _has_active_test(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_")
        for node in ast.walk(tree)
    )


def _decorator_name(decorator: ast.AST) -> str:
    if isinstance(decorator, ast.Call):
        return _decorator_name(decorator.func)
    if isinstance(decorator, ast.Attribute):
        return f"{_decorator_name(decorator.value)}.{decorator.attr}".strip(".")
    if isinstance(decorator, ast.Name):
        return decorator.id
    return ""


def _is_pytest_skip_marker(node: ast.AST) -> bool:
    return _decorator_name(node) in {"pytest.mark.skip", "pytest.mark.skipif"}


def _contains_pytest_skip_marker(node: ast.AST) -> bool:
    return any(_is_pytest_skip_marker(child) for child in ast.walk(node))


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names: list[str] = []

    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)

    return names


def _pytestmark_assignments(nodes: list[ast.stmt]) -> list[ast.Assign | ast.AnnAssign]:
    return [
        node
        for node in nodes
        if isinstance(node, ast.Assign | ast.AnnAssign)
        and "pytestmark" in _assigned_names(node)
        and node.value is not None
        and _contains_pytest_skip_marker(node.value)
    ]


def _skip_or_todo_tests(tree: ast.Module) -> list[str]:
    skipped_or_todo: list[str] = []

    if _pytestmark_assignments(tree.body):
        skipped_or_todo.append("module pytestmark")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if any(_contains_pytest_skip_marker(decorator) for decorator in node.decorator_list):
                skipped_or_todo.append(node.name)
                continue
            if _pytestmark_assignments(node.body):
                skipped_or_todo.append(node.name)
            continue

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test_"
        ):
            if any(_contains_pytest_skip_marker(decorator) for decorator in node.decorator_list):
                skipped_or_todo.append(node.name)
                continue
            if "todo" in node.name.lower():
                skipped_or_todo.append(node.name)

    return skipped_or_todo


def _module_level_inline_workflow_yaml(tree: ast.Module) -> list[str]:
    inline_yaml: list[str] = []

    for node in tree.body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        value = node.value
        if not isinstance(value, ast.Constant | ast.JoinedStr):
            continue
        if isinstance(value, ast.Constant) and not isinstance(value.value, str):
            continue

        inline_yaml.extend(name for name in _assigned_names(node) if name.endswith("_YAML"))

    return inline_yaml


def _imports_helper(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.endswith("sse_streaming_helpers") for alias in node.names):
                return True
            continue

        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "sse_streaming_helpers" or module.endswith(".sse_streaming_helpers"):
                return True
            if any(alias.name == "sse_streaming_helpers" for alias in node.names):
                return True

    return False


def test_api_sse_streaming_suite_uses_split_suites_and_owned_fixtures() -> None:
    failures: list[str] = []

    if LEGACY_OMNIBUS_SUITE.exists():
        failures.append(
            f"{_relative(LEGACY_OMNIBUS_SUITE)} must be deleted after its "
            "coverage moves into behavior-named service and transport suites."
        )

    for suite_path in REQUIRED_SPLIT_SUITES:
        if not suite_path.exists():
            failures.append(f"{_relative(suite_path)} is missing.")
            continue

        tree = _parsed(suite_path)
        if not _has_active_test(tree):
            failures.append(f"{_relative(suite_path)} must contain at least one active test_.")

        skipped_or_todo = _skip_or_todo_tests(tree)
        if skipped_or_todo:
            failures.append(
                f"{_relative(suite_path)} must not use skipped or todo tests: "
                + ", ".join(skipped_or_todo)
            )

        if not _imports_helper(tree):
            failures.append(
                f"{_relative(suite_path)} must import shared SSE setup from "
                f"{_relative(HELPER_MODULE)}."
            )

        inline_yaml_constants = _module_level_inline_workflow_yaml(tree)
        if inline_yaml_constants:
            failures.append(
                f"{_relative(suite_path)} must load API-owned workflow fixture files "
                "instead of declaring module-level *_YAML string constants: "
                + ", ".join(inline_yaml_constants)
            )

    if not HELPER_MODULE.exists():
        failures.append(
            f"{_relative(HELPER_MODULE)} must define shared API SSE streaming test setup helpers."
        )

    missing_fixtures = [
        _relative(fixture_path)
        for fixture_path in REQUIRED_WORKFLOW_FIXTURES
        if not fixture_path.is_file()
    ]
    if missing_fixtures:
        failures.append(
            "API-owned SSE workflow fixture files are missing:\n"
            + "\n".join(f"  - {path}" for path in missing_fixtures)
        )

    assert not failures, "\n".join(failures)
