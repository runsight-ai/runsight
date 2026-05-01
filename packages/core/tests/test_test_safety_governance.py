"""Test safety governance boundary.

Owner: core runtime test safety maintainers.
Boundary: test naming, isolation, and fixture-governance checks for core/API
test workspaces and browser harness tests.
Exit criteria: delete this suite only after repo test ownership, isolation, and
naming policies are enforced by package-local tooling or pre-commit checks.
"""

from __future__ import annotations

import ast
import re
import tokenize
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class PolicyPattern:
    id: str
    regex: re.Pattern[str]
    search_roots: tuple[Path, ...]
    message: str


@dataclass(frozen=True)
class AllowlistEntry:
    pattern_id: str
    path: Path
    reason: str
    expires: date


E2E_TEST_ROOT = REPO_ROOT / "testing" / "gui-e2e" / "tests"
API_TEST_ROOT = REPO_ROOT / "apps" / "api" / "tests"
CORE_TEST_ROOT = REPO_ROOT / "packages" / "core" / "tests"
GUI_ROOT = REPO_ROOT / "apps" / "gui"
SHARED_ROOT = REPO_ROOT / "packages" / "shared"
UI_ROOT = REPO_ROOT / "packages" / "ui"
E2E_RUNTIME_ROOT_HELPER = E2E_TEST_ROOT / "helpers" / "runtimeRoot.ts"

TEST_FILE_NAME_TICKET_RE = re.compile(
    r"(?:^|[^A-Za-z0-9])"
    r"(?:RUN-\d+|test[_-]?run[_-]?\d{3,}|run[_-]?\d{3,}|"
    r"test[_-]?iso[_-]?\d{3,}|iso[_-]?\d{3,})",
    re.IGNORECASE,
)
PYTHON_SYMBOL_TICKET_RE = re.compile(
    r"(?:^|_)(?:test_)?(?:run_?\d{3,}|iso_?\d{3,})|Run\d{3,}|RUN_?\d{3,}",
)
PYTHON_GOVERNANCE_DOCSTRING_FIELD_RES = (
    re.compile(r"\bowner\b", re.IGNORECASE),
    re.compile(r"\bboundary\b", re.IGNORECASE),
    re.compile(r"\bexit\s+criteria\b", re.IGNORECASE),
)
NON_BROWSER_E2E_WORDING_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:e2e|E2E)(?![A-Za-z0-9])|"
    r"E2E(?=[A-Z])|"
    r"(?<![A-Za-z0-9])(?i:end(?:[-_]|\s+)to(?:[-_]|\s+)end)(?![A-Za-z0-9])",
)
TICKET_FIXTURE_IDENTITY_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:[A-Za-z0-9]+[-_])*run[-_]\d{3,}(?:[-_][A-Za-z0-9]+)*(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
STRUCTURAL_TITLE_TICKET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:RUN-\d+|test[_-]?run[_-]?\d{3,}|run[_-]?\d{3,}|AC\d+)",
    re.IGNORECASE,
)
TEST_FILE_ROOTS = (API_TEST_ROOT, CORE_TEST_ROOT, E2E_TEST_ROOT, GUI_ROOT, SHARED_ROOT, UI_ROOT)
PYTHON_TEST_ROOTS = (API_TEST_ROOT, CORE_TEST_ROOT)
TYPESCRIPT_TEST_ROOTS = (E2E_TEST_ROOT, GUI_ROOT, SHARED_ROOT, UI_ROOT)
GOVERNANCE_TEST_FILE = Path(__file__).resolve()
SELF_POLICY_CONSTANT_NAMES = (
    "TEST_FILE_NAME_TICKET_RE",
    "PYTHON_SYMBOL_TICKET_RE",
    "STRUCTURAL_TITLE_TICKET_RE",
    "TICKET_FIXTURE_IDENTITY_RE",
    "NON_BROWSER_E2E_WORDING_RE",
)


POLICY_PATTERNS = (
    PolicyPattern(
        id="e2e-runtime-root-discovery",
        regex=re.compile(
            r"lsof|process\.cwd\(\)|detectApiProjectRoot|"
            r"RUNSIGHT_E2E_PROJECT_ROOT\s*(?:\?\?|\|\|)|"
            r"RUNSIGHT_BASE_PATH\s*(?:\?\?|\|\|)"
        ),
        search_roots=(E2E_TEST_ROOT,),
        message=(
            "E2E tests must use the shared runtime-root helper instead of process cwd, "
            "server cwd discovery, or env fallback."
        ),
    ),
    PolicyPattern(
        id="e2e-runtime-env-direct-read",
        regex=re.compile(r"process\.env\.(RUNSIGHT_E2E_PROJECT_ROOT|RUNSIGHT_BASE_PATH)"),
        search_roots=(E2E_TEST_ROOT,),
        message="Only the shared runtime-root helper may read E2E runtime-root env vars.",
    ),
    PolicyPattern(
        id="repo-root-runtime-asset",
        regex=re.compile(
            r"\b_?REPO_ROOT\b\s*/\s*['\"](?:custom|\.runsight)['\"]|"
            r"Path\.cwd\(\)\s*/\s*['\"](?:custom|\.runsight)['\"]|"
            r"parents\[[0-9]+\]\s*/\s*['\"](?:custom|\.runsight)['\"]"
        ),
        search_roots=(API_TEST_ROOT, CORE_TEST_ROOT),
        message=(
            "Tests must not derive repo-root custom/ or .runsight paths. Use tmp_path or "
            "package-owned fixtures instead."
        ),
    ),
    PolicyPattern(
        id="e2e-repo-root-runtime-asset",
        regex=re.compile(
            r"\b(?:REPO_ROOT|repoRoot)\b\s*,\s*['\"](?:custom|\.runsight)['\"]|"
            r"\b(?:REPO_ROOT|repoRoot)\b\s*/\s*['\"](?:custom|\.runsight)['\"]"
        ),
        search_roots=(E2E_TEST_ROOT,),
        message=(
            "E2E specs must not build repo-root custom/ or .runsight paths. Use "
            "getE2ERuntimeRoot() or resolveE2ERuntimePath() instead."
        ),
    ),
    PolicyPattern(
        id="api-to-core-test-fixture",
        regex=re.compile(
            r"packages[/\\]core[/\\]tests[/\\]fixtures|packages.*core.*tests.*fixtures"
        ),
        search_roots=(API_TEST_ROOT,),
        message="API tests must own their fixtures instead of reaching into core test fixtures.",
    ),
)


ALLOWLIST = (
    AllowlistEntry(
        pattern_id="e2e-runtime-env-direct-read",
        path=E2E_RUNTIME_ROOT_HELPER,
        reason="Central guard owns the only direct env read and rejects unsafe roots.",
        expires=date(2026, 10, 1),
    ),
)


def _iter_source_files(root: Path) -> list[Path]:
    suffixes = {".py", ".ts", ".tsx"}
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in suffixes
        and "__pycache__" not in path.parts
        and "test-results" not in path.parts
        and "playwright-report" not in path.parts
    )


def _is_test_source_file(path: Path) -> bool:
    if path.suffix == ".py":
        return any(root in path.parents or path == root for root in PYTHON_TEST_ROOTS)
    if path.suffix not in {".ts", ".tsx"}:
        return False
    return (
        path.name.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx"))
        or "__tests__" in path.parts
    )


def _iter_test_source_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in _iter_source_files(root) if _is_test_source_file(path))


def _allowed(pattern_id: str, path: Path) -> bool:
    resolved = path.resolve()
    return any(
        entry.pattern_id == pattern_id and entry.path.resolve() == resolved for entry in ALLOWLIST
    )


def _find_policy_violations(pattern: PolicyPattern) -> list[str]:
    violations: list[str] = []
    for root in pattern.search_roots:
        for source_file in _iter_source_files(root):
            if _allowed(pattern.id, source_file):
                continue
            for line_number, line in enumerate(
                source_file.read_text(encoding="utf-8").splitlines(), 1
            ):
                if pattern.regex.search(line):
                    relative = source_file.relative_to(REPO_ROOT)
                    violations.append(f"{relative}:{line_number}: {line.strip()}")
    return violations


def _python_tree_and_source(source_file: Path) -> tuple[ast.Module, str]:
    source = source_file.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(source_file)), source


def _python_module_is_marked_or_named_governance_or_migration(
    source_file: Path, tree: ast.Module, source: str
) -> bool:
    stem = source_file.stem
    if stem.endswith(("_governance", "_migration")):
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


def _iter_python_comments(source: str) -> list[tuple[int, str]]:
    comments: list[tuple[int, str]] = []
    for token in tokenize.generate_tokens(StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            comments.append((token.start[0], token.string))
    return comments


def _iter_python_docstrings(tree: ast.Module) -> list[tuple[int, str, str]]:
    docstrings: list[tuple[int, str, str]] = []
    module_docstring = ast.get_docstring(tree, clean=False)
    if module_docstring is not None and tree.body:
        docstrings.append((tree.body[0].lineno, "module docstring", module_docstring))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        docstring = ast.get_docstring(node, clean=False)
        if docstring is None or not node.body:
            continue
        docstrings.append((node.body[0].lineno, f"{node.name} docstring", docstring))
    return docstrings


def _python_docstring_line_numbers(tree: ast.Module) -> set[int]:
    line_numbers: set[int] = set()
    docstring_owners: list[ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef] = [
        tree
    ]
    docstring_owners.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )

    for owner in docstring_owners:
        if not owner.body:
            continue
        first_statement = owner.body[0]
        if not (
            isinstance(first_statement, ast.Expr)
            and isinstance(first_statement.value, ast.Constant)
            and isinstance(first_statement.value.value, str)
        ):
            continue
        end_lineno = first_statement.end_lineno or first_statement.lineno
        line_numbers.update(range(first_statement.lineno, end_lineno + 1))
    return line_numbers


def _is_self_governance_policy_source(source_file: Path) -> bool:
    return source_file.resolve() == GOVERNANCE_TEST_FILE


def _is_self_e2e_policy_name(source_file: Path, node_name: str) -> bool:
    if not _is_self_governance_policy_source(source_file):
        return False
    return node_name in {
        "_is_self_e2e_policy_name",
        "test_non_browser_python_tests_do_not_use_e2e_wording",
    }


def _is_self_ticket_fixture_policy_line(
    source_file: Path, line_number: int, line: str, docstring_lines: set[int]
) -> bool:
    if not _is_self_governance_policy_source(source_file):
        return False
    stripped = line.lstrip()
    return (
        line_number in docstring_lines
        or stripped.startswith("#")
        or any(policy_name in line for policy_name in SELF_POLICY_CONSTANT_NAMES)
    )


def _line_number(source: str, index: int) -> int:
    return source.count("\n", 0, index) + 1


def _is_identifier_start(char: str) -> bool:
    return char.isalpha() or char in {"_", "$"}


def _is_identifier_part(char: str) -> bool:
    return char.isalnum() or char in {"_", "$"}


def _skip_ws_and_comments(source: str, index: int) -> int:
    length = len(source)
    while index < length:
        if source[index].isspace():
            index += 1
            continue
        if source.startswith("//", index):
            next_newline = source.find("\n", index + 2)
            index = length if next_newline == -1 else next_newline + 1
            continue
        if source.startswith("/*", index):
            comment_end = source.find("*/", index + 2)
            index = length if comment_end == -1 else comment_end + 2
            continue
        break
    return index


def _read_identifier(source: str, index: int) -> tuple[str, int]:
    if index >= len(source) or not _is_identifier_start(source[index]):
        return "", index
    start = index
    index += 1
    while index < len(source) and _is_identifier_part(source[index]):
        index += 1
    return source[start:index], index


def _read_quoted_string(source: str, index: int) -> tuple[str, int]:
    quote = source[index]
    index += 1
    value: list[str] = []
    while index < len(source):
        char = source[index]
        if char == "\\":
            if index + 1 < len(source):
                value.append(source[index + 1])
            index += 2
            continue
        if char == quote:
            return "".join(value), index + 1
        value.append(char)
        index += 1
    return "".join(value), index


def _skip_balanced_parentheses(source: str, index: int) -> int:
    depth = 0
    while index < len(source):
        if source.startswith("//", index):
            next_newline = source.find("\n", index + 2)
            index = len(source) if next_newline == -1 else next_newline + 1
            continue
        if source.startswith("/*", index):
            comment_end = source.find("*/", index + 2)
            index = len(source) if comment_end == -1 else comment_end + 2
            continue
        char = source[index]
        if char in {"'", '"', "`"}:
            _, index = _read_quoted_string(source, index)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            index += 1
            if depth == 0:
                return index
            continue
        index += 1
    return index


def _typescript_test_titles(source: str) -> list[tuple[int, str]]:
    titles: list[tuple[int, str]] = []
    index = 0
    while index < len(source):
        if source.startswith("//", index):
            next_newline = source.find("\n", index + 2)
            index = len(source) if next_newline == -1 else next_newline + 1
            continue
        if source.startswith("/*", index):
            comment_end = source.find("*/", index + 2)
            index = len(source) if comment_end == -1 else comment_end + 2
            continue
        char = source[index]
        if char in {"'", '"', "`"}:
            _, index = _read_quoted_string(source, index)
            continue
        if not _is_identifier_start(char):
            index += 1
            continue

        identifier_start = index
        identifier, index = _read_identifier(source, index)
        previous = source[identifier_start - 1] if identifier_start > 0 else ""
        if identifier not in {"describe", "it", "test"} or previous == ".":
            continue

        callee_end = _skip_ws_and_comments(source, index)
        while callee_end < len(source) and source[callee_end] == ".":
            modifier_start = _skip_ws_and_comments(source, callee_end + 1)
            modifier, modifier_end = _read_identifier(source, modifier_start)
            if not modifier:
                break
            callee_end = _skip_ws_and_comments(source, modifier_end)
            if modifier == "each" and callee_end < len(source) and source[callee_end] == "(":
                callee_end = _skip_balanced_parentheses(source, callee_end)
                callee_end = _skip_ws_and_comments(source, callee_end)

        if callee_end >= len(source) or source[callee_end] != "(":
            continue
        title_start = _skip_ws_and_comments(source, callee_end + 1)
        if title_start < len(source) and source[title_start] in {"'", '"', "`"}:
            title, _ = _read_quoted_string(source, title_start)
            titles.append((_line_number(source, title_start), title))
    return titles


def test_test_safety_policy_allowlist_entries_are_documented_and_current() -> None:
    for entry in ALLOWLIST:
        assert entry.reason.strip(), f"{entry.path} allowlist entry must explain why it exists"
        assert entry.expires >= date.today(), (
            f"{entry.path} allowlist entry for {entry.pattern_id} expired on {entry.expires}"
        )
        assert entry.path.exists(), f"{entry.path} allowlist entry points at a missing file"
        assert any(pattern.id == entry.pattern_id for pattern in POLICY_PATTERNS), (
            f"{entry.path} allowlist entry references unknown pattern {entry.pattern_id!r}"
        )


@pytest.mark.parametrize("pattern", POLICY_PATTERNS, ids=lambda pattern: pattern.id)
def test_test_safety_policy_patterns_do_not_reappear(pattern: PolicyPattern) -> None:
    violations = _find_policy_violations(pattern)
    assert violations == [], pattern.message + "\n" + "\n".join(violations)


def test_test_file_names_use_behavioral_owners_not_ticket_ids() -> None:
    violations: list[str] = []
    for root in TEST_FILE_ROOTS:
        for source_file in _iter_test_source_files(root):
            if TEST_FILE_NAME_TICKET_RE.search(source_file.name):
                violations.append(str(source_file.relative_to(REPO_ROOT)))

    assert violations == [], (
        "Test files should be named after the behavior, module, feature, flow, "
        "or governance boundary they own, not the ticket that introduced them.\n"
        + "\n".join(violations)
    )


def test_python_test_symbols_use_behavioral_names_not_ticket_ids() -> None:
    violations: list[str] = []
    for root in PYTHON_TEST_ROOTS:
        for source_file in _iter_test_source_files(root):
            tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if PYTHON_SYMBOL_TICKET_RE.search(node.name):
                    relative = source_file.relative_to(REPO_ROOT)
                    violations.append(f"{relative}:{node.lineno}: {node.name}")

    assert violations == [], (
        "Python test classes/functions should describe behavior instead of ticket IDs.\n"
        + "\n".join(violations)
    )


def test_python_governance_and_migration_modules_document_owner_boundary_and_exit() -> None:
    violations: list[str] = []
    for root in PYTHON_TEST_ROOTS:
        for source_file in _iter_test_source_files(root):
            tree, source = _python_tree_and_source(source_file)
            if not _python_module_is_marked_or_named_governance_or_migration(
                source_file, tree, source
            ):
                continue

            module_docstring = ast.get_docstring(tree, clean=False) or ""
            missing_fields = [
                field.pattern.replace("\\b", "").replace("\\s+", " ")
                for field in PYTHON_GOVERNANCE_DOCSTRING_FIELD_RES
                if not field.search(module_docstring)
            ]
            if missing_fields:
                relative = source_file.relative_to(REPO_ROOT)
                violations.append(f"{relative}: missing {', '.join(missing_fields)}")

    assert violations == [], (
        "Governance and migration Python test modules must state Owner, Boundary, "
        "and Exit criteria in the top module docstring so temporary guards have a "
        "clear owner and removal path.\n" + "\n".join(violations)
    )


def test_non_browser_python_tests_do_not_use_e2e_wording() -> None:
    violations: list[str] = []
    for root in PYTHON_TEST_ROOTS:
        for source_file in _iter_test_source_files(root):
            tree, source = _python_tree_and_source(source_file)
            relative = source_file.relative_to(REPO_ROOT)

            for line_number, label, text in _iter_python_docstrings(tree):
                if NON_BROWSER_E2E_WORDING_RE.search(text):
                    violations.append(f"{relative}:{line_number}: {label}")

            for line_number, comment in _iter_python_comments(source):
                if NON_BROWSER_E2E_WORDING_RE.search(comment):
                    violations.append(f"{relative}:{line_number}: {comment.strip()}")

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if _is_self_e2e_policy_name(source_file, node.name):
                    continue
                if NON_BROWSER_E2E_WORDING_RE.search(node.name):
                    violations.append(f"{relative}:{node.lineno}: {node.name}")

    assert violations == [], (
        "Python tests in apps/api/tests and packages/core/tests are not browser E2E "
        "suites; reserve E2E/end-to-end wording for testing/gui-e2e.\n" + "\n".join(violations)
    )


def test_test_fixture_identities_use_behavioral_names_not_ticket_ids() -> None:
    violations: list[str] = []
    for root in PYTHON_TEST_ROOTS:
        for source_file in _iter_test_source_files(root):
            tree, source = _python_tree_and_source(source_file)
            docstring_lines = (
                _python_docstring_line_numbers(tree)
                if _is_self_governance_policy_source(source_file)
                else set()
            )
            for line_number, line in enumerate(source.splitlines(), 1):
                if _is_self_ticket_fixture_policy_line(
                    source_file, line_number, line, docstring_lines
                ):
                    continue
                if TICKET_FIXTURE_IDENTITY_RE.search(line):
                    relative = source_file.relative_to(REPO_ROOT)
                    violations.append(f"{relative}:{line_number}: {line.strip()}")

    assert violations == [], (
        "Test fixture identities should describe the behavior under test, not the "
        "ticket that introduced them.\n" + "\n".join(violations)
    )


def test_typescript_test_titles_use_behavioral_names_not_ticket_ids_or_ac_labels() -> None:
    violations: list[str] = []
    for root in TYPESCRIPT_TEST_ROOTS:
        for source_file in _iter_test_source_files(root):
            source = source_file.read_text(encoding="utf-8")
            for line_number, title in _typescript_test_titles(source):
                if STRUCTURAL_TITLE_TICKET_RE.search(title):
                    relative = source_file.relative_to(REPO_ROOT)
                    violations.append(f"{relative}:{line_number}: {title}")

    assert violations == [], (
        "TypeScript describe/it/test titles should name behavior, not ticket IDs or AC labels.\n"
        + "\n".join(violations)
    )
