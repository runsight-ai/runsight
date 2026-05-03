"""
Governance tests for test ownership boundaries.

Owner: tools/tests owns repo-wide static governance that scans multiple
workspaces for misplaced test responsibilities.
Boundary: package tests may verify their own workspace contracts and behavior,
but must not reach into app-owned source, docs, live app internals, or repo
tooling that belongs to another workspace.
Exit criteria: delete or narrow this suite once the flagged legacy tests have
been moved to their owning workspaces or replaced by package-local contract
fixtures/snapshots.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_TESTS = REPO_ROOT / "packages" / "shared" / "src" / "__tests__"
API_OPENAPI_CODEGEN_TEST = REPO_ROOT / "apps" / "api" / "tests" / "test_openapi_codegen.py"


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _line_snippets(path: Path, patterns: Iterable[re.Pattern[str]]) -> list[str]:
    snippets: list[str] = []
    source = path.read_text(encoding="utf-8")

    for line_number, line in enumerate(source.splitlines(), start=1):
        if any(pattern.search(line) for pattern in patterns):
            snippets.append(f"{_relative(path)}:{line_number}: {line.strip()}")

    return snippets


def _shared_app_source_violations() -> list[str]:
    forbidden_patterns = [
        re.compile(r"\bapps[\"'/, ]+gui\b"),
        re.compile(r"\bapps[\"'/, ]+site\b"),
        re.compile(r"\bapps/gui\b"),
        re.compile(r"\bapps/site\b"),
        re.compile(r"\brunsApiSource\b"),
        re.compile(r"\bgetRunContextAudit\b"),
        re.compile(r"\bcontext-governance\.mdx\b"),
    ]

    return [
        snippet
        for path in sorted(SHARED_TESTS.glob("*"))
        if path.is_file()
        for snippet in _line_snippets(path, forbidden_patterns)
    ]


def _shared_live_api_violations() -> list[str]:
    forbidden_patterns = [
        re.compile(r"\bfrom\s+runsight_api\.main\s+import\s+app\b"),
        re.compile(r"\brunsight_api\.main\b"),
        re.compile(r"\bapp\.openapi\(\)"),
    ]

    return [
        snippet
        for path in sorted(SHARED_TESTS.glob("*"))
        if path.is_file()
        for snippet in _line_snippets(path, forbidden_patterns)
    ]


def _api_cross_workspace_violations() -> list[str]:
    forbidden_patterns = [
        re.compile(r"\bSHARED_ROOT\b"),
        re.compile(r"\bGENERATED_TYPES_DIR\b"),
        re.compile(r"\bpackages[\"'/ ]+shared\b"),
        re.compile(r"\bpackages/shared\b"),
        re.compile(r"\bgenerate-types\.(?:sh|ts)\b"),
        re.compile(r"\bcodegen\.sh\b"),
        re.compile(r"\bcheck-types-fresh\.sh\b"),
        re.compile(r"\bci-check-types\.sh\b"),
        re.compile(r"\bcheck-types\.yml\b"),
        re.compile(r"\bcodegen\.yml\b"),
        re.compile(r"\bREPO_ROOT\s*/\s*[\"']openapi\.json[\"']"),
        re.compile(r"\bOPENAPI_(?:SCHEMA|SNAPSHOT)\b"),
        re.compile(r"\bread_text\(\).*openapi\.json\b"),
        re.compile(r"\bopenapi\.json\b.*read_text\(\)"),
        re.compile(r"\bTestCodegenScriptExists\b"),
        re.compile(r"\bTestGeneratedTypesExist\b"),
        re.compile(r"\bTestCIFreshnessCheck\b"),
        re.compile(r"\bopenapi-typescript\b"),
        re.compile(r"\bgenerate:types\b"),
    ]

    return _line_snippets(API_OPENAPI_CODEGEN_TEST, forbidden_patterns)


def test_test_ownership_boundaries_are_enforced() -> None:
    """Cross-workspace ownership leaks should be moved to the owning workspace."""
    violation_groups = [
        (
            "packages/shared/src/__tests__ must not read app-owned sources/docs "
            "or assert GUI adapter behavior.",
            _shared_app_source_violations(),
        ),
        (
            "packages/shared/src/__tests__ must not import the live FastAPI app "
            "or synthesize OpenAPI from runsight_api.main.",
            _shared_live_api_violations(),
        ),
        (
            "apps/api/tests/test_openapi_codegen.py should cover the live API "
            "OpenAPI schema only; generated files, packages/shared scripts, "
            "repo codegen scripts, and CI freshness checks belong outside API tests.",
            _api_cross_workspace_violations(),
        ),
    ]

    failure_sections = [
        heading + "\n" + "\n".join(violations)
        for heading, violations in violation_groups
        if violations
    ]

    assert not failure_sections, "\n\n".join(failure_sections)
