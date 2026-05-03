"""Core and repo governance migrated out of packages/core behavior tests.

Owner: tools/tests owns compact static governance that scans repo policy,
container packaging files, and test-source ownership boundaries.
Boundary: this suite may inspect checked-in source, docs, Docker packaging, and
test files across workspaces. It must not inspect repo-root runtime state such
as .runsight/, runsight.db, custom/, secrets, or user configuration.
Exit criteria: delete or narrow this suite once equivalent repo-layout,
container-hardening, and test-safety checks are enforced by dedicated tooling.
"""

from __future__ import annotations

import ast
import re
import subprocess
import tokenize
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.governance

REPO_ROOT = Path(__file__).resolve().parents[2]

AGENTS_POLICY = REPO_ROOT / "AGENTS.md"
DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENTRYPOINT = REPO_ROOT / "docker-entrypoint.sh"
PROCESS_ISOLATION_DOC = (
    REPO_ROOT
    / "apps"
    / "site"
    / "src"
    / "content"
    / "docs"
    / "docs"
    / "execution"
    / "process-isolation.md"
)

API_TEST_ROOT = REPO_ROOT / "apps" / "api" / "tests"
CORE_TEST_ROOT = REPO_ROOT / "packages" / "core" / "tests"
E2E_TEST_ROOT = REPO_ROOT / "testing" / "gui-e2e" / "tests"
GUI_ROOT = REPO_ROOT / "apps" / "gui"
SHARED_ROOT = REPO_ROOT / "packages" / "shared"
UI_ROOT = REPO_ROOT / "packages" / "ui"
E2E_RUNTIME_ROOT_HELPER = E2E_TEST_ROOT / "helpers" / "runtimeRoot.ts"

TEST_FILE_ROOTS = (API_TEST_ROOT, CORE_TEST_ROOT, E2E_TEST_ROOT, GUI_ROOT, SHARED_ROOT, UI_ROOT)
PYTHON_TEST_ROOTS = (API_TEST_ROOT, CORE_TEST_ROOT)
TYPESCRIPT_TEST_ROOTS = (E2E_TEST_ROOT, GUI_ROOT, SHARED_ROOT, UI_ROOT)

TEST_FILE_NAME_TICKET_RE = re.compile(
    r"(?:^|[^A-Za-z0-9])"
    r"(?:RUN-\d+|test[_-]?run[_-]?\d{3,}|run[_-]?\d{3,}|"
    r"test[_-]?iso[_-]?\d{3,}|iso[_-]?\d{3,})",
    re.IGNORECASE,
)
PYTHON_SYMBOL_TICKET_RE = re.compile(
    r"(?:^|_)(?:test_)?(?:run_?\d{3,}|iso_?\d{3,})|Run\d{3,}|RUN_?\d{3,}",
)
GOVERNANCE_DOCSTRING_FIELD_RES = (
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
    r"(?<![A-Za-z0-9_-])(?:[A-Za-z0-9]+[-_])*"
    r"(?:run|wf|corr|req|secret|idem)[-_]?\d{3,}(?:[-_][A-Za-z0-9]+)*"
    r"(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)
STRUCTURAL_TITLE_TICKET_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:RUN-\d+|test[_-]?run[_-]?\d{3,}|run[_-]?\d{3,}|AC\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuntimeStagePattern:
    id: str
    regex: re.Pattern[str]
    message: str


@dataclass(frozen=True)
class ComposeExpectation:
    id: str
    service_name: str
    message: str
    validator: str


@dataclass(frozen=True)
class DocsLineExpectation:
    id: str
    line_match: re.Pattern[str]
    required: tuple[str, ...]
    forbidden: tuple[str, ...] = ()


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


@dataclass(frozen=True)
class WorkspaceReferenceRule:
    id: str
    search_root: Path
    forbidden_reference: re.Pattern[str]
    message: str


DOCKER_RUNTIME_PATTERNS = (
    RuntimeStagePattern(
        id="runtime-user",
        regex=re.compile(r"^\s*USER\s+(?:runsight|1000)\b", re.MULTILINE),
        message="Dockerfile runtime stage must switch to the runsight user or UID 1000.",
    ),
    RuntimeStagePattern(
        id="group-gid",
        regex=re.compile(r"groupadd\b.*(?:--gid|-g)\s+1000\b.*runsight"),
        message="Dockerfile runtime stage must create the runsight group with GID 1000.",
    ),
    RuntimeStagePattern(
        id="user-uid",
        regex=re.compile(r"useradd\b.*(?:--uid|-u)\s+1000\b.*runsight"),
        message="Dockerfile runtime stage must create the runsight user with UID 1000.",
    ),
    RuntimeStagePattern(
        id="git-safe-directory",
        regex=re.compile(r"git\s+config\s+--global\s+--add\s+safe\.directory\s+/workspace"),
        message="Dockerfile runtime stage must configure git safe.directory for /workspace.",
    ),
)

COMPOSE_EXPECTATIONS = (
    ComposeExpectation(
        id="init-permissions",
        service_name="init-permissions",
        validator="init_permissions",
        message="init-permissions must chown /workspace with only CAP_CHOWN restored.",
    ),
    ComposeExpectation(
        id="runsight-service",
        service_name="runsight",
        validator="runsight",
        message="runsight service must drop privileges and enforce resource limits.",
    ),
)

PROCESS_ISOLATION_DOC_EXPECTATIONS = (
    DocsLineExpectation(
        id="layer-1-container-hardening",
        line_match=re.compile(r"Layer 1", re.IGNORECASE),
        required=("container", "hardening"),
        forbidden=("future",),
    ),
    DocsLineExpectation(
        id="layer-1-unprivileged-user",
        line_match=re.compile(r"Layer 1", re.IGNORECASE),
        required=("unprivileged", "non-root"),
        forbidden=("future",),
    ),
    DocsLineExpectation(
        id="cpu-memory-container-limits",
        line_match=re.compile(r"cpu.*memory|memory.*cpu", re.IGNORECASE),
        required=("container",),
        forbidden=("not enforced",),
    ),
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

WORKSPACE_REFERENCE_RULES = (
    WorkspaceReferenceRule(
        id="api-tests-do-not-scan-core-source-or-tests",
        search_root=API_TEST_ROOT,
        forbidden_reference=re.compile(
            r'["\']packages["\']\s*/\s*["\']core["\']\s*/\s*["\'](?:src|tests)["\']|'
            r"packages[/\\]core[/\\](?:src|tests)"
        ),
        message="API tests must not source-scan packages/core source or tests.",
    ),
    WorkspaceReferenceRule(
        id="core-tests-do-not-scan-api-source-or-tests",
        search_root=CORE_TEST_ROOT,
        forbidden_reference=re.compile(
            r'["\']apps["\']\s*/\s*["\']api["\']\s*/\s*["\'](?:src|tests)["\']|'
            r"apps[/\\]api[/\\](?:src|tests)"
        ),
        message="Core tests must not source-scan apps/api source or tests.",
    ),
)

RETIRED_CORE_GOVERNANCE_SUITES = (
    CORE_TEST_ROOT / "test_discovery_repo_policy_governance.py",
    CORE_TEST_ROOT / "test_docker_hardening.py",
    CORE_TEST_ROOT / "test_interceptors_extract.py",
    CORE_TEST_ROOT / "test_ipc_models_extract.py",
    CORE_TEST_ROOT / "test_parser_decomposition.py",
    CORE_TEST_ROOT / "test_source_scan_ownership_governance.py",
    CORE_TEST_ROOT / "test_test_safety_governance.py",
)

RETIRED_CROSS_OWNER_SCAN_TESTS = (
    API_TEST_ROOT / "test_stale_soul_assertion_refs.py",
    API_TEST_ROOT / "test_soul_assertion_field_removal_governance.py",
    CORE_TEST_ROOT / "test_soul_assertion_field_removal_governance.py",
    API_TEST_ROOT / "test_scan_index_usage_governance.py",
    CORE_TEST_ROOT / "test_scan_index_ids_cleanup.py",
)


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _runtime_stage_text() -> str:
    lines = _read(DOCKERFILE).splitlines()
    in_runtime = False
    runtime_lines: list[str] = []
    for line in lines:
        if re.search(r"FROM\s+\S+\s+AS\s+runtime", line, re.IGNORECASE):
            in_runtime = True
            continue
        if in_runtime and re.match(r"FROM\s+", line, re.IGNORECASE):
            break
        if in_runtime:
            runtime_lines.append(line)
    return "\n".join(runtime_lines)


def _load_compose() -> dict:
    compose = yaml.safe_load(_read(COMPOSE_FILE))
    assert isinstance(compose, dict), f"{_relative(COMPOSE_FILE)} must parse as a mapping"
    return compose


def _compose_services() -> dict:
    services = _load_compose().get("services", {})
    assert isinstance(services, dict), f"{_relative(COMPOSE_FILE)} services must be a mapping"
    return services


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
            for line_number, line in enumerate(_read(source_file).splitlines(), 1):
                if pattern.regex.search(line):
                    violations.append(f"{_relative(source_file)}:{line_number}: {line.strip()}")
    return violations


def _python_tree_and_source(source_file: Path) -> tuple[ast.Module, str]:
    source = _read(source_file)
    return ast.parse(source, filename=str(source_file)), source


def _python_module_is_marked_or_named_governance_or_migration(
    source_file: Path, tree: ast.Module
) -> bool:
    if source_file.stem.endswith(("_governance", "_migration")):
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


def test_agents_policy_keeps_custom_tools_under_custom_runtime_assets() -> None:
    policy = _read(AGENTS_POLICY)

    assert "custom/" in policy and "custom/tools/" in policy, (
        "AGENTS.md must keep custom/tools/ under the custom runtime asset policy "
        "so package-local discovery tests can use package-owned tool fixtures "
        "without reading repo-root runtime state."
    )


@pytest.mark.parametrize("case", DOCKER_RUNTIME_PATTERNS, ids=lambda case: case.id)
def test_dockerfile_runtime_stage_preserves_container_hardening(case: RuntimeStagePattern) -> None:
    runtime_stage = _runtime_stage_text()

    assert case.regex.search(runtime_stage), case.message


def test_dockerfile_runtime_stage_prepares_workspace_for_non_root_user() -> None:
    runtime_stage = _runtime_stage_text()

    assert re.search(r"mkdir\s+-p\s+/workspace", runtime_stage), (
        "Dockerfile runtime stage must create /workspace before switching to non-root."
    )
    assert re.search(r"chown\s+(?:runsight:runsight|1000:1000)\s+/workspace", runtime_stage), (
        "Dockerfile runtime stage must chown /workspace to runsight:runsight or 1000:1000."
    )


@pytest.mark.parametrize("case", COMPOSE_EXPECTATIONS, ids=lambda case: case.id)
def test_docker_compose_preserves_container_hardening(case: ComposeExpectation) -> None:
    services = _compose_services()
    service = services.get(case.service_name)

    assert isinstance(service, dict), f"{case.service_name} service is missing. {case.message}"
    if case.validator == "init_permissions":
        assert "busybox" in str(service.get("image", "")).lower(), case.message
        assert str(service.get("user", "")) == "0", case.message
        assert "ALL" in service.get("cap_drop", []), case.message
        assert service.get("cap_add") == ["CHOWN"], case.message
        assert service.get("command") == ["chown", "-R", "1000:1000", "/workspace"], case.message
        return

    if case.validator == "runsight":
        assert "ALL" in service.get("cap_drop", []), case.message
        assert service.get("cap_add") in (None, []), case.message
        assert "no-new-privileges:true" in service.get("security_opt", []), case.message
        assert str(service.get("mem_limit", "")).lower() in {"4g", "4096m", "4294967296"}
        assert str(service.get("memswap_limit", "")).lower() in {"4g", "4096m", "4294967296"}
        assert float(service.get("cpus", 0)) == 2.0
        assert service.get("init") is True, case.message
        depends_on = service.get("depends_on", {})
        assert isinstance(depends_on, dict) and "init-permissions" in depends_on, case.message
        assert (
            depends_on["init-permissions"].get("condition") == "service_completed_successfully"
        ), case.message
        return

    raise AssertionError(f"Unknown compose validator: {case.validator}")


def test_docker_entrypoint_fails_fast_without_runtime_mkdir(tmp_path: Path) -> None:
    entrypoint = _read(ENTRYPOINT)
    missing_workspace = tmp_path / "missing-workspace"

    assert "mkdir" not in entrypoint, "docker-entrypoint.sh must not create runtime workspaces."
    result = subprocess.run(
        ["sh", str(ENTRYPOINT), "true"],
        env={
            "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "RUNSIGHT_BASE_PATH": str(missing_workspace),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "does not exist" in result.stderr


def test_docker_entrypoint_execs_with_existing_workspace(tmp_path: Path) -> None:
    result = subprocess.run(
        ["sh", str(ENTRYPOINT), "true"],
        env={
            "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "RUNSIGHT_BASE_PATH": str(tmp_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_docker_entrypoint_announces_empty_workspace_scaffolding(tmp_path: Path) -> None:
    result = subprocess.run(
        ["sh", str(ENTRYPOINT), "true"],
        env={
            "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "RUNSIGHT_BASE_PATH": str(tmp_path),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "scaffold" in (result.stdout + result.stderr).lower()


@pytest.mark.parametrize("case", PROCESS_ISOLATION_DOC_EXPECTATIONS, ids=lambda case: case.id)
def test_process_isolation_docs_describe_active_container_hardening(
    case: DocsLineExpectation,
) -> None:
    matching_lines = [
        line for line in _read(PROCESS_ISOLATION_DOC).splitlines() if case.line_match.search(line)
    ]
    assert matching_lines, f"{_relative(PROCESS_ISOLATION_DOC)} has no line for {case.id}."

    combined = " ".join(matching_lines).lower()
    assert any(required in combined for required in case.required), (
        f"{case.id} must mention one of: {', '.join(case.required)}."
    )
    forbidden_hits = [forbidden for forbidden in case.forbidden if forbidden in combined]
    assert forbidden_hits == [], f"{case.id} still mentions: {', '.join(forbidden_hits)}."


def test_moved_core_governance_suites_stay_out_of_core_behavior_tests() -> None:
    remaining = [_relative(path) for path in RETIRED_CORE_GOVERNANCE_SUITES if path.exists()]

    assert remaining == [], (
        "Repo/tooling governance should stay under tools/tests, not packages/core/tests.\n"
        + "\n".join(remaining)
    )


def test_retired_cross_owner_source_scan_tests_stay_removed() -> None:
    remaining = [_relative(path) for path in RETIRED_CROSS_OWNER_SCAN_TESTS if path.exists()]

    assert remaining == [], (
        "Retired cross-workspace source-scan cleanup suites should stay removed or be "
        "rebuilt under tools/tests with explicit ownership.\n" + "\n".join(remaining)
    )


@pytest.mark.parametrize("rule", WORKSPACE_REFERENCE_RULES, ids=lambda rule: rule.id)
def test_package_tests_do_not_source_scan_sibling_workspace_internals(
    rule: WorkspaceReferenceRule,
) -> None:
    violations: list[str] = []
    for source_file in _iter_test_source_files(rule.search_root):
        tree, source = _python_tree_and_source(source_file)
        if not _python_module_is_marked_or_named_governance_or_migration(source_file, tree):
            continue
        for line_number, line in enumerate(source.splitlines(), 1):
            if rule.forbidden_reference.search(line):
                violations.append(f"{_relative(source_file)}:{line_number}: {line.strip()}")

    assert violations == [], rule.message + "\n" + "\n".join(violations)


def test_test_safety_policy_allowlist_entries_are_documented_and_current() -> None:
    for entry in ALLOWLIST:
        assert entry.reason.strip(), f"{_relative(entry.path)} allowlist entry needs a reason"
        assert entry.expires >= date.today(), (
            f"{_relative(entry.path)} allowlist entry for {entry.pattern_id} expired on "
            f"{entry.expires}"
        )
        assert entry.path.exists(), (
            f"{_relative(entry.path)} allowlist entry points at a missing file"
        )
        assert any(pattern.id == entry.pattern_id for pattern in POLICY_PATTERNS), (
            f"{_relative(entry.path)} references unknown pattern {entry.pattern_id!r}"
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
                violations.append(_relative(source_file))

    assert violations == [], (
        "Test files should be named after the behavior, module, feature, flow, "
        "or governance boundary they own, not the ticket that introduced them.\n"
        + "\n".join(violations)
    )


def test_python_test_symbols_use_behavioral_names_not_ticket_ids() -> None:
    violations: list[str] = []
    for root in PYTHON_TEST_ROOTS:
        for source_file in _iter_test_source_files(root):
            tree = ast.parse(_read(source_file), filename=str(source_file))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if PYTHON_SYMBOL_TICKET_RE.search(node.name):
                    violations.append(f"{_relative(source_file)}:{node.lineno}: {node.name}")

    assert violations == [], (
        "Python test classes/functions should describe behavior instead of ticket IDs.\n"
        + "\n".join(violations)
    )


def test_python_governance_and_migration_modules_document_owner_boundary_and_exit() -> None:
    violations: list[str] = []
    for root in PYTHON_TEST_ROOTS:
        for source_file in _iter_test_source_files(root):
            tree, _ = _python_tree_and_source(source_file)
            if not _python_module_is_marked_or_named_governance_or_migration(source_file, tree):
                continue

            module_docstring = ast.get_docstring(tree, clean=False) or ""
            missing_fields = [
                field.pattern.replace("\\b", "").replace("\\s+", " ")
                for field in GOVERNANCE_DOCSTRING_FIELD_RES
                if not field.search(module_docstring)
            ]
            if missing_fields:
                violations.append(f"{_relative(source_file)}: missing {', '.join(missing_fields)}")

    assert violations == [], (
        "Governance and migration Python test modules must state Owner, Boundary, "
        "and Exit criteria in the top module docstring.\n" + "\n".join(violations)
    )


def test_non_browser_python_tests_do_not_use_e2e_wording() -> None:
    violations: list[str] = []
    for root in PYTHON_TEST_ROOTS:
        for source_file in _iter_test_source_files(root):
            tree, source = _python_tree_and_source(source_file)
            relative = _relative(source_file)

            for line_number, label, text in _iter_python_docstrings(tree):
                if NON_BROWSER_E2E_WORDING_RE.search(text):
                    violations.append(f"{relative}:{line_number}: {label}")

            for line_number, comment in _iter_python_comments(source):
                if NON_BROWSER_E2E_WORDING_RE.search(comment):
                    violations.append(f"{relative}:{line_number}: {comment.strip()}")

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if NON_BROWSER_E2E_WORDING_RE.search(node.name):
                    violations.append(f"{relative}:{node.lineno}: {node.name}")

    assert violations == [], (
        "Python tests in apps/api/tests and packages/core/tests are not browser E2E "
        "suites; reserve E2E/end-to-end wording for testing/gui-e2e.\n" + "\n".join(violations)
    )


def test_test_fixture_identities_use_behavioral_names_not_ticket_ids() -> None:
    violations: list[str] = []
    for root in TEST_FILE_ROOTS:
        for source_file in _iter_test_source_files(root):
            if source_file.suffix == ".py":
                tree, source = _python_tree_and_source(source_file)
                docstring_lines = _python_docstring_line_numbers(tree)
            else:
                source = source_file.read_text(encoding="utf-8")
                docstring_lines = set()
            for line_number, line in enumerate(source.splitlines(), 1):
                stripped = line.lstrip()
                if line_number in docstring_lines or stripped.startswith(("#", "//", "/*", "*")):
                    continue
                if TICKET_FIXTURE_IDENTITY_RE.search(line):
                    violations.append(f"{_relative(source_file)}:{line_number}: {line.strip()}")

    assert violations == [], (
        "Test fixture identities should describe the behavior under test, not the "
        "ticket that introduced them.\n" + "\n".join(violations)
    )


def test_typescript_test_titles_use_behavioral_names_not_ticket_ids_or_ac_labels() -> None:
    violations: list[str] = []
    for root in TYPESCRIPT_TEST_ROOTS:
        for source_file in _iter_test_source_files(root):
            for line_number, title in _typescript_test_titles(_read(source_file)):
                if STRUCTURAL_TITLE_TICKET_RE.search(title):
                    violations.append(f"{_relative(source_file)}:{line_number}: {title}")

    assert violations == [], (
        "TypeScript describe/it/test titles should name behavior, not ticket IDs or AC labels.\n"
        + "\n".join(violations)
    )
