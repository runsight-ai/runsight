"""Discovery suite ownership governance.

Owner: packages/core discovery scanner test owners.
Boundary: public discovery API, soul scanner behavior, tool scanner behavior,
and AGENTS/custom tools policy coverage must live in behavior-owner suites with
package-local YAML fixture writers instead of one broad discovery suite.
Exit criteria: delete this governance guard once the split owner suites and
shared discovery fixture helper are the durable behavior owners.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

CORE_TEST_ROOT = Path(__file__).resolve().parent
LEGACY_DISCOVERY_SUITE = CORE_TEST_ROOT / "test_discovery.py"
DISCOVERY_FIXTURE_HELPER = CORE_TEST_ROOT / "discovery_fixtures.py"

EXPECTED_OWNER_SUITES = {
    CORE_TEST_ROOT / "test_discovery_public_api.py": {
        "owner": "public discovery exports and retired legacy symbols",
        "required_test_name_fragments": (
            "scanner_public_api",
            "legacy",
            "discover_custom_assets",
        ),
        "required_imports": (),
        "must_be_governance": False,
    },
    CORE_TEST_ROOT / "test_soul_scanner.py": {
        "owner": "SoulScanner file discovery, ignore behavior, and Soul model output",
        "required_test_name_fragments": (
            "discover_single_soul",
            "discover_multiple_souls",
            "discover_soul_with_tools",
            "ignore",
        ),
        "required_imports": ("write_soul_yaml",),
        "must_be_governance": False,
    },
    CORE_TEST_ROOT / "test_tool_scanner.py": {
        "owner": "ToolScanner metadata, executor validation, duplicate, and reserved-id behavior",
        "required_test_name_fragments": (
            "python_and_request_executor",
            "legacy_type_http",
            "duplicate",
            "reserved_builtin",
        ),
        "required_imports": ("write_tool_yaml",),
        "must_be_governance": False,
    },
    CORE_TEST_ROOT / "test_discovery_repo_policy_governance.py": {
        "owner": "AGENTS/custom tools repo policy governance",
        "required_test_name_fragments": ("agents_policy_allows_custom_tools",),
        "required_imports": (),
        "must_be_governance": True,
    },
}

EXPECTED_HELPER_FUNCTIONS = {"write_soul_yaml", "write_tool_yaml"}
PROHIBITED_LEGACY_CLASS_NAMES = {
    "TestPublicDiscoverySurface",
    "TestDiscoverSouls",
    "TestDiscoverCustomTools",
    "TestRepoPolicyForCustomTools",
}
PROHIBITED_INLINE_HELPER_NAMES = {"_write_soul_yaml", "_write_tool_yaml"}
YAML_WRITER_CALL_NAMES = {"write_soul_yaml", "write_tool_yaml"}


def _parse_source(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_test_names(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def _defined_class_names(tree: ast.Module) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def _defined_function_names(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _imported_names(tree: ast.Module) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.asname or alias.name.partition(".")[0] for alias in node.names)
    return imported


def _is_pytest_governance_marked(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        ):
            continue
        value = node.value
        if (
            isinstance(value, ast.Attribute)
            and value.attr == "governance"
            and isinstance(value.value, ast.Attribute)
            and value.value.attr == "mark"
        ):
            return True
        if isinstance(value, (ast.List, ast.Tuple)):
            for item in value.elts:
                if (
                    isinstance(item, ast.Attribute)
                    and item.attr == "governance"
                    and isinstance(item.value, ast.Attribute)
                    and item.value.attr == "mark"
                ):
                    return True
    return False


def _called_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def _relative(path: Path) -> str:
    return str(path.relative_to(CORE_TEST_ROOT))


def _missing_test_fragments(tree: ast.Module, fragments: tuple[str, ...]) -> list[str]:
    test_names = _defined_test_names(tree)
    return [
        fragment
        for fragment in fragments
        if not any(fragment in test_name for test_name in test_names)
    ]


def _metadata_violations(path: Path, tree: ast.Module) -> list[str]:
    if not ast.get_docstring(tree):
        return [f"{_relative(path)} must document Owner, Boundary, and Exit criteria"]

    docstring = ast.get_docstring(tree) or ""
    required_fragments = ("Owner:", "Boundary:", "Exit criteria:")
    return [
        f"{_relative(path)} module docstring is missing {fragment}"
        for fragment in required_fragments
        if fragment not in docstring
    ]


def test_discovery_suite_governance_requires_owner_split_and_shared_yaml_fixtures() -> None:
    """Owner: discovery tests. Exit: split owner suites replace this guard."""
    violations: list[str] = []

    if not DISCOVERY_FIXTURE_HELPER.exists():
        violations.append(
            "missing fixture helper for soul/tool YAML writers: "
            f"{_relative(DISCOVERY_FIXTURE_HELPER)}"
        )
    else:
        helper_tree = _parse_source(DISCOVERY_FIXTURE_HELPER)
        missing_helpers = EXPECTED_HELPER_FUNCTIONS - _defined_function_names(helper_tree)
        if missing_helpers:
            violations.append(
                f"{_relative(DISCOVERY_FIXTURE_HELPER)} is missing helper(s): "
                + ", ".join(sorted(missing_helpers))
            )

    for path, expectation in EXPECTED_OWNER_SUITES.items():
        owner = expectation["owner"]
        if not path.exists():
            violations.append(f"missing owner suite for {owner}: {_relative(path)}")
            continue

        tree = _parse_source(path)
        missing_fragments = _missing_test_fragments(
            tree,
            expectation["required_test_name_fragments"],
        )
        if missing_fragments:
            violations.append(
                f"{_relative(path)} is missing representative test names for {owner}: "
                + ", ".join(missing_fragments)
            )

        imported_names = _imported_names(tree)
        missing_imports = set(expectation["required_imports"]) - imported_names
        if missing_imports:
            violations.append(
                f"{_relative(path)} must import shared discovery fixture helper(s): "
                + ", ".join(sorted(missing_imports))
            )

        called_names = _called_names(tree)
        missing_calls = set(expectation["required_imports"]) - called_names
        if missing_calls:
            violations.append(
                f"{_relative(path)} must use shared discovery fixture helper(s): "
                + ", ".join(sorted(missing_calls))
            )

        if expectation["must_be_governance"]:
            if not _is_pytest_governance_marked(tree):
                violations.append(f"{_relative(path)} must set pytestmark = pytest.mark.governance")
            violations.extend(_metadata_violations(path, tree))

    if LEGACY_DISCOVERY_SUITE.exists():
        legacy_tree = _parse_source(LEGACY_DISCOVERY_SUITE)
        legacy_classes = _defined_class_names(legacy_tree)
        remaining_owner_classes = sorted(legacy_classes & PROHIBITED_LEGACY_CLASS_NAMES)
        if remaining_owner_classes:
            violations.append(
                f"{_relative(LEGACY_DISCOVERY_SUITE)} still owns broad discovery classes: "
                + ", ".join(remaining_owner_classes)
            )

        inline_helpers = sorted(
            _defined_function_names(legacy_tree) & PROHIBITED_INLINE_HELPER_NAMES
        )
        if inline_helpers:
            violations.append(
                f"{_relative(LEGACY_DISCOVERY_SUITE)} still defines inline YAML writers: "
                + ", ".join(inline_helpers)
            )

    owner_files_using_yaml = [
        path
        for path, expectation in EXPECTED_OWNER_SUITES.items()
        if path.exists() and expectation["required_imports"]
    ]
    used_yaml_writers = {
        name
        for path in owner_files_using_yaml
        for name in _called_names(_parse_source(path))
        if name in YAML_WRITER_CALL_NAMES
    }
    missing_writer_usage = YAML_WRITER_CALL_NAMES - used_yaml_writers
    if owner_files_using_yaml and missing_writer_usage:
        violations.append(
            "split scanner suites must preserve positive YAML fixture coverage through helper use: "
            + ", ".join(sorted(missing_writer_usage))
        )

    assert violations == [], (
        "Discovery suite governance requires behavior-owner suites, a governance-marked "
        "repo policy suite, removed/reduced legacy ownership classes, and shared package-local "
        "YAML fixture writers.\n" + "\n".join(violations)
    )
