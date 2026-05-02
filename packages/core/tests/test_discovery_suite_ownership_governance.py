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
        "required_references": (
            "BaseScanner",
            "ScanIndex",
            "ScanResult",
            "SoulScanner",
            "ToolScanner",
            "WorkflowScanner",
            "discover_custom_assets",
        ),
        "minimum_test_count": 3,
        "minimum_assertive_test_count": 3,
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
        "required_references": ("SoulScanner", "Soul", "scan", "ids", "write_soul_yaml"),
        "minimum_test_count": 5,
        "minimum_assertive_test_count": 5,
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
        "required_references": (
            "RESERVED_BUILTIN_TOOL_IDS",
            "ToolMeta",
            "ToolScanner",
            "ids",
            "raises",
            "scan",
            "write_tool_yaml",
        ),
        "minimum_test_count": 10,
        "minimum_assertive_test_count": 10,
        "must_be_governance": False,
    },
    CORE_TEST_ROOT / "test_discovery_repo_policy_governance.py": {
        "owner": "AGENTS/custom tools repo policy governance",
        "required_test_name_fragments": ("agents_policy_allows_custom_tools",),
        "required_imports": (),
        "required_references": ("AGENTS.md", "custom/tools"),
        "minimum_test_count": 1,
        "minimum_assertive_test_count": 1,
        "must_be_governance": True,
    },
}

EXPECTED_HELPER_FUNCTIONS = {"write_soul_yaml", "write_tool_yaml"}
LEGACY_RESIDUAL_LINE_CAP = 120
LEGACY_RESIDUAL_TEST_CAP = 2
LEGACY_RESIDUAL_CLASS_CAP = 0
PROHIBITED_LEGACY_CLASS_NAMES = {
    "TestPublicDiscoverySurface",
    "TestDiscoverSouls",
    "TestDiscoverCustomTools",
    "TestRepoPolicyForCustomTools",
}
PROHIBITED_INLINE_HELPER_NAMES = {"_write_soul_yaml", "_write_tool_yaml"}
YAML_WRITER_CALL_NAMES = {"write_soul_yaml", "write_tool_yaml"}
YAML_FIXTURE_CONTENT_MARKERS = (
    "code: |",
    "executor:",
    "kind: soul",
    "kind: tool",
    "parameters:",
    "request:",
    "system_prompt:",
    'version: "1.0"',
)
PLACEHOLDER_TEXT_MARKERS = ("not implemented", "placeholder", "todo")
SKIP_OR_XFAIL_CALL_NAMES = {"skip", "xfail"}


def _parse_source(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_test_names(tree: ast.Module) -> set[str]:
    return {node.name for node in _iter_test_functions(tree)}


def _iter_test_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]


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


def _string_constants(tree: ast.AST) -> list[str]:
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _referenced_symbols(tree: ast.AST) -> set[str]:
    references = set(_string_constants(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            references.add(node.id)
        elif isinstance(node, ast.Attribute):
            references.add(node.attr)
    return references


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


def _missing_required_references(tree: ast.Module, fragments: tuple[str, ...]) -> list[str]:
    references = _referenced_symbols(tree)
    return [
        fragment
        for fragment in fragments
        if not any(fragment in reference for reference in references)
    ]


def _effective_test_body(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.stmt]:
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _is_ellipsis_expr(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and node.value.value is Ellipsis
    )


def _is_skip_or_xfail_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id in SKIP_OR_XFAIL_CALL_NAMES
    if isinstance(node.func, ast.Attribute):
        return node.func.attr in SKIP_OR_XFAIL_CALL_NAMES
    return False


def _has_skip_or_xfail(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    decorated = any(
        isinstance(decorator, ast.Attribute) and decorator.attr in SKIP_OR_XFAIL_CALL_NAMES
        for decorator in node.decorator_list
    )
    return decorated or any(
        isinstance(child, ast.Call) and _is_skip_or_xfail_call(child) for child in ast.walk(node)
    )


def _is_trivial_assertion(node: ast.Assert) -> bool:
    if isinstance(node.test, ast.Constant):
        return True
    if isinstance(node.test, ast.Compare):
        compared_values = [node.test.left, *node.test.comparators]
        return all(isinstance(value, ast.Constant) for value in compared_values)
    return False


def _meaningful_assertion_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert) and not _is_trivial_assertion(child):
            count += 1
        elif isinstance(child, ast.Call) and _is_pytest_raises_call(child):
            count += 1
    return count


def _is_pytest_raises_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr == "raises"


def _placeholder_test_names(tree: ast.Module) -> list[str]:
    placeholders: list[str] = []
    for node in _iter_test_functions(tree):
        body = _effective_test_body(node)
        lower_constants = [value.lower() for value in _string_constants(node)]
        if not body:
            placeholders.append(node.name)
        elif any(
            isinstance(statement, ast.Pass) or _is_ellipsis_expr(statement) for statement in body
        ):
            placeholders.append(node.name)
        elif _has_skip_or_xfail(node):
            placeholders.append(node.name)
        elif any(
            marker in value for marker in PLACEHOLDER_TEXT_MARKERS for value in lower_constants
        ):
            placeholders.append(node.name)
        elif _meaningful_assertion_count(node) == 0:
            placeholders.append(node.name)
    return sorted(placeholders)


def _contains_custom_asset_path(node: ast.AST) -> bool:
    constants = _string_constants(node)
    if any("custom/souls" in value or "custom/tools" in value for value in constants):
        return True
    return "custom" in constants and ("souls" in constants or "tools" in constants)


def _contains_yaml_fixture_content(node: ast.AST) -> bool:
    return any(
        marker in value
        for marker in YAML_FIXTURE_CONTENT_MARKERS
        for value in _string_constants(node)
    )


def _is_yaml_writer_like_name(name: str) -> bool:
    normalized = name.lower()
    return "yaml" in normalized and any(
        verb in normalized for verb in ("build", "create", "make", "write")
    )


def _constructs_inline_discovery_fixture(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    called_names = _called_names(node)
    has_custom_asset_path = _contains_custom_asset_path(node)
    has_yaml_content = _contains_yaml_fixture_content(node)
    writes_file = "write_text" in called_names
    creates_dir = "mkdir" in called_names
    return (
        (_is_yaml_writer_like_name(node.name) and (writes_file or has_custom_asset_path))
        or (writes_file and has_yaml_content)
        or (has_custom_asset_path and (creates_dir or writes_file))
    )


def _inline_discovery_fixture_violations(path: Path, tree: ast.Module) -> list[str]:
    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _constructs_inline_discovery_fixture(node)
    ]
    if not offenders:
        return []

    shown_offenders = ", ".join(sorted(offenders)[:8])
    if len(offenders) > 8:
        shown_offenders += f", and {len(offenders) - 8} more"
    return [f"{_relative(path)} constructs custom discovery fixtures inline: {shown_offenders}"]


def _owner_suite_violations(path: Path, expectation: dict[str, object]) -> list[str]:
    owner = expectation["owner"]
    if not path.exists():
        return [f"missing owner suite for {owner}: {_relative(path)}"]

    violations: list[str] = []
    tree = _parse_source(path)
    test_names = _defined_test_names(tree)
    minimum_test_count = expectation["minimum_test_count"]
    if len(test_names) < minimum_test_count:
        violations.append(
            f"{_relative(path)} has {len(test_names)} test(s) for {owner}; "
            f"expected at least {minimum_test_count}"
        )

    meaningful_test_count = len(test_names) - len(_placeholder_test_names(tree))
    minimum_assertive_test_count = expectation["minimum_assertive_test_count"]
    if meaningful_test_count < minimum_assertive_test_count:
        violations.append(
            f"{_relative(path)} has {meaningful_test_count} non-placeholder "
            f"assertive test(s) for {owner}; expected at least "
            f"{minimum_assertive_test_count}"
        )

    placeholder_tests = _placeholder_test_names(tree)
    if placeholder_tests:
        violations.append(
            f"{_relative(path)} contains placeholder or non-assertive tests: "
            + ", ".join(placeholder_tests)
        )

    missing_fragments = _missing_test_fragments(
        tree,
        expectation["required_test_name_fragments"],
    )
    if missing_fragments:
        violations.append(
            f"{_relative(path)} is missing representative test names for {owner}: "
            + ", ".join(missing_fragments)
        )

    missing_references = _missing_required_references(
        tree,
        expectation["required_references"],
    )
    if missing_references:
        violations.append(
            f"{_relative(path)} is missing owner behavior references for {owner}: "
            + ", ".join(missing_references)
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

    return violations


def _legacy_suite_violations() -> list[str]:
    if not LEGACY_DISCOVERY_SUITE.exists():
        return []

    violations: list[str] = []
    source = LEGACY_DISCOVERY_SUITE.read_text(encoding="utf-8")
    legacy_tree = ast.parse(source, filename=str(LEGACY_DISCOVERY_SUITE))
    line_count = len(source.splitlines())
    if line_count > LEGACY_RESIDUAL_LINE_CAP:
        violations.append(
            f"{_relative(LEGACY_DISCOVERY_SUITE)} has {line_count} lines; "
            f"legacy residual cap is {LEGACY_RESIDUAL_LINE_CAP}"
        )

    test_names = _defined_test_names(legacy_tree)
    if len(test_names) > LEGACY_RESIDUAL_TEST_CAP:
        violations.append(
            f"{_relative(LEGACY_DISCOVERY_SUITE)} still owns {len(test_names)} "
            f"test(s); legacy residual cap is {LEGACY_RESIDUAL_TEST_CAP}"
        )

    legacy_classes = _defined_class_names(legacy_tree)
    if len(legacy_classes) > LEGACY_RESIDUAL_CLASS_CAP:
        violations.append(
            f"{_relative(LEGACY_DISCOVERY_SUITE)} still defines "
            f"{len(legacy_classes)} class(es); legacy residual cap is "
            f"{LEGACY_RESIDUAL_CLASS_CAP}"
        )

    remaining_owner_classes = sorted(legacy_classes & PROHIBITED_LEGACY_CLASS_NAMES)
    if remaining_owner_classes:
        violations.append(
            f"{_relative(LEGACY_DISCOVERY_SUITE)} still owns broad discovery classes: "
            + ", ".join(remaining_owner_classes)
        )

    inline_helpers = sorted(_defined_function_names(legacy_tree) & PROHIBITED_INLINE_HELPER_NAMES)
    if inline_helpers:
        violations.append(
            f"{_relative(LEGACY_DISCOVERY_SUITE)} still defines inline YAML writers: "
            + ", ".join(inline_helpers)
        )

    violations.extend(_inline_discovery_fixture_violations(LEGACY_DISCOVERY_SUITE, legacy_tree))
    return violations


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
        violations.extend(_owner_suite_violations(path, expectation))

    violations.extend(_legacy_suite_violations())

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
        "repo policy suite, removed/tiny legacy residuals, no inline discovery fixture "
        "construction in the legacy suite, and shared package-local YAML fixture writers.\n"
        + "\n".join(violations)
    )
