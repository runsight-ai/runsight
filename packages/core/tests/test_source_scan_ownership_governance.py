"""Source scan ownership governance.

Owner: core runtime test safety maintainers.
Boundary: cleanup and governance Python tests that inspect source files must
stay within the workspace that owns the inspected source, or move to an
explicit repo-level governance suite with documented ownership.
Exit criteria: delete this suite after source-scan cleanup tests have been split
by workspace owner and the boundary is enforced by package-local tooling.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[3]
API_TEST_ROOT = REPO_ROOT / "apps" / "api" / "tests"
CORE_TEST_ROOT = REPO_ROOT / "packages" / "core" / "tests"

GOVERNANCE_DOCSTRING_FIELD_RES = (
    re.compile(r"\bowner\b", re.IGNORECASE),
    re.compile(r"\bboundary\b", re.IGNORECASE),
    re.compile(r"\bexit\s+criteria\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class ForbiddenWorkspaceReference:
    label: str
    regex: re.Pattern[str]


@dataclass(frozen=True)
class CleanupSourceScanCase:
    test_file: Path
    owner: str
    forbidden_references: tuple[ForbiddenWorkspaceReference, ...]


KNOWN_CLEANUP_SOURCE_SCAN_TESTS = (
    CleanupSourceScanCase(
        test_file=API_TEST_ROOT / "test_soul_assertion_field_removal_governance.py",
        owner="apps/api",
        forbidden_references=(
            ForbiddenWorkspaceReference(
                label="packages/core tests",
                regex=re.compile(r'["\']packages["\']\s*/\s*["\']core["\']|packages[/\\]core'),
            ),
        ),
    ),
    CleanupSourceScanCase(
        test_file=CORE_TEST_ROOT / "test_soul_assertion_field_removal_governance.py",
        owner="packages/core",
        forbidden_references=(
            ForbiddenWorkspaceReference(
                label="apps/api tests",
                regex=re.compile(
                    r'["\']apps["\']\s*/\s*["\']api["\']\s*/\s*["\']tests["\']|'
                    r"apps[/\\]api[/\\]tests"
                ),
            ),
        ),
    ),
    CleanupSourceScanCase(
        test_file=API_TEST_ROOT / "test_scan_index_usage_governance.py",
        owner="apps/api",
        forbidden_references=(
            ForbiddenWorkspaceReference(
                label="packages/core source",
                regex=re.compile(
                    r'["\']packages["\']\s*/\s*["\']core["\']\s*/\s*["\']src["\']|'
                    r"packages[/\\]core[/\\]src"
                ),
            ),
        ),
    ),
    CleanupSourceScanCase(
        test_file=CORE_TEST_ROOT / "test_scan_index_ids_cleanup.py",
        owner="packages/core",
        forbidden_references=(
            ForbiddenWorkspaceReference(
                label="apps/api source",
                regex=re.compile(
                    r'["\']apps["\']\s*/\s*["\']api["\']\s*/\s*["\']src["\']|'
                    r"apps[/\\]api[/\\]src"
                ),
            ),
        ),
    ),
)

RETIRED_CROSS_OWNER_SCAN_TESTS = (API_TEST_ROOT / "test_stale_soul_assertion_refs.py",)


def _source_if_present(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _module_has_governance_marker_or_name(test_file: Path, tree: ast.Module) -> bool:
    if test_file.stem.endswith(("_governance", "_migration")):
        return True

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        ):
            continue
        if any(
            isinstance(child, ast.Attribute) and child.attr in {"governance", "migration"}
            for child in ast.walk(node.value)
        ):
            return True
    return False


def test_cleanup_source_scan_tests_stay_with_their_workspace_owner() -> None:
    violations: list[str] = []
    for case in KNOWN_CLEANUP_SOURCE_SCAN_TESTS:
        source = _source_if_present(case.test_file)
        if source is None:
            violations.append(
                f"{case.test_file.relative_to(REPO_ROOT)}: expected split owner suite"
            )
            continue

        for line_number, line in enumerate(source.splitlines(), 1):
            for forbidden in case.forbidden_references:
                if forbidden.regex.search(line):
                    relative = case.test_file.relative_to(REPO_ROOT)
                    violations.append(
                        f"{relative}:{line_number}: {case.owner} test scans "
                        f"{forbidden.label}: {line.strip()}"
                    )

    assert violations == [], (
        "Python source-inspection cleanup tests must stay within their workspace owner. "
        "Move cross-workspace scans to the owning workspace or an explicit repo-level "
        "governance suite.\n" + "\n".join(violations)
    )


def test_retired_cross_owner_source_scan_tests_stay_removed() -> None:
    violations = [
        str(path.relative_to(REPO_ROOT)) for path in RETIRED_CROSS_OWNER_SCAN_TESTS if path.exists()
    ]

    assert violations == [], (
        "Retired cross-workspace source-scan tests should stay removed after owner "
        "specific suites replace them.\n" + "\n".join(violations)
    )


def test_cleanup_source_scan_tests_document_owner_boundary_and_exit() -> None:
    violations: list[str] = []
    for case in KNOWN_CLEANUP_SOURCE_SCAN_TESTS:
        source = _source_if_present(case.test_file)
        if source is None:
            violations.append(
                f"{case.test_file.relative_to(REPO_ROOT)}: expected split owner suite"
            )
            continue

        tree = ast.parse(source, filename=str(case.test_file))
        relative = case.test_file.relative_to(REPO_ROOT)

        if not _module_has_governance_marker_or_name(case.test_file, tree):
            violations.append(
                f"{relative}: cleanup source-scan test must be named/marked as governance"
            )

        module_docstring = ast.get_docstring(tree, clean=False) or ""
        missing_fields = [
            field.pattern.replace("\\b", "").replace("\\s+", " ")
            for field in GOVERNANCE_DOCSTRING_FIELD_RES
            if not field.search(module_docstring)
        ]
        if missing_fields:
            violations.append(f"{relative}: missing {', '.join(missing_fields)}")

    assert violations == [], (
        "Cleanup source-scan governance tests must state Owner, Boundary, and Exit criteria "
        "so temporary source inspections have clear ownership and a removal path.\n"
        + "\n".join(violations)
    )
