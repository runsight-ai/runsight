"""Exit-port routing suite ownership governance.

Owner: packages/core exit-port and workflow-routing behavior test owners.
Boundary: package-local fixture contracts, Workflow exit-handle routing,
LoopBlock exit-handle propagation, output_conditions exit handles, and YAML
exit-port parsing/roundtrip behavior must live in focused owner suites with
shared package-local helpers instead of the broad legacy integration suite.
Exit criteria: delete this guard once the owner suites and exit_port_helpers.py
are the durable behavior owners and the legacy umbrella suite is removed or a
tiny residual suite with no broad inline fixtures.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance

CORE_TEST_ROOT = Path(__file__).resolve().parent
UNIT_TEST_ROOT = CORE_TEST_ROOT / "unit"
LEGACY_EXIT_PORT_SUITE = UNIT_TEST_ROOT / "test_exit_ports_integration.py"
EXIT_PORT_HELPERS = CORE_TEST_ROOT / "exit_port_helpers.py"

LEGACY_MAX_LINES = 180
LEGACY_MAX_TEST_FUNCTIONS = 4
LEGACY_MAX_TEST_CLASSES = 0
INLINE_YAML_LITERAL_MAX_NONBLANK_LINES = 8

EXPECTED_HELPER_EXPORT_GROUPS = {
    "mock runner builder": {"make_mock_runner", "mock_runner", "build_mock_runner"},
    "test soul builder": {"make_test_soul", "make_soul", "test_soul"},
    "workflow state builder": {"fresh_workflow_state", "make_workflow_state", "fresh_state"},
    "stub output block": {"StubBlock", "OutputBlock"},
    "explicit exit-handle block": {"ExitHandleBlock", "ExplicitExitBlock"},
    "JSON output block": {"JsonOutputBlock", "JsonResultBlock"},
    "YAML fixture loader": {"load_workflow_yaml_fixture", "load_yaml_fixture"},
    "YAML fixture builder": {"build_workflow_yaml", "write_workflow_yaml_fixture"},
}
EXPECTED_HELPER_REFERENCES = {
    "BaseBlock",
    "BlockResult",
    "ExecutionResult",
    "RunsightTeamRunner",
    "Soul",
    "WorkflowState",
    "yaml",
}

PLACEHOLDER_TEXT_MARKERS = ("not implemented", "placeholder", "todo")
SKIP_OR_XFAIL_CALL_NAMES = {"skip", "xfail"}
ASSERT_CALL_NAMES = {
    "all",
    "any",
    "raises",
}


@dataclass(frozen=True)
class OwnerSuiteExpectation:
    owner: str
    required_test_name_fragments: tuple[str, ...]
    required_helper_symbols: tuple[str, ...]
    required_references: tuple[str, ...]
    minimum_test_count: int
    minimum_assertive_test_count: int


EXPECTED_OWNER_SUITES = {
    CORE_TEST_ROOT / "test_exit_port_fixture_contracts.py": OwnerSuiteExpectation(
        owner="package-local YAML workflow fixture structure",
        required_test_name_fragments=(
            "workflow_fixture_directory",
            "yaml_files",
            "mockup_pipeline",
        ),
        required_helper_symbols=("load_workflow_yaml_fixture",),
        required_references=(
            "fixtures/custom/workflows",
            "mockup_pipeline.yaml",
            "workflow",
            "blocks",
        ),
        minimum_test_count=3,
        minimum_assertive_test_count=3,
    ),
    CORE_TEST_ROOT / "test_workflow_exit_handle_routing.py": OwnerSuiteExpectation(
        owner="standalone Workflow exit-handle conditional routing",
        required_test_name_fragments=(
            "exit_handle_routes",
            "default_fallback",
            "missing_exit_handle",
            "resolve_next",
        ),
        required_helper_symbols=("ExitHandleBlock", "StubBlock", "fresh_workflow_state"),
        required_references=(
            "Workflow",
            "add_conditional_transition",
            "conditional_transitions",
            "exit_handle",
            "_resolve_next",
        ),
        minimum_test_count=4,
        minimum_assertive_test_count=4,
    ),
    CORE_TEST_ROOT / "test_loop_exit_handle_propagation.py": OwnerSuiteExpectation(
        owner="LoopBlock break_on_exit/retry_on_exit propagation across block types",
        required_test_name_fragments=(
            "break_on_exit",
            "retry_on_exit",
            "fail_then_pass",
            "without_break_or_retry",
        ),
        required_helper_symbols=("make_mock_runner", "make_test_soul", "StubBlock"),
        required_references=(
            "GateBlock",
            "LoopBlock",
            "break_on_exit",
            "retry_on_exit",
            "exit_handle",
        ),
        minimum_test_count=4,
        minimum_assertive_test_count=4,
    ),
    CORE_TEST_ROOT / "test_output_conditions_exit_handles.py": OwnerSuiteExpectation(
        owner="output_conditions producing, preserving, and routing exit handles",
        required_test_name_fragments=(
            "output_conditions_match",
            "output_conditions_default",
            "preserve_exit_handle",
        ),
        required_helper_symbols=("ExitHandleBlock", "JsonOutputBlock", "StubBlock"),
        required_references=(
            "set_output_conditions",
            "conditional_transitions",
            "exit_handle",
            "output_conditions",
        ),
        minimum_test_count=3,
        minimum_assertive_test_count=3,
    ),
    CORE_TEST_ROOT / "test_yaml_exit_port_roundtrip.py": OwnerSuiteExpectation(
        owner="YAML exit-port parse, validation, roundtrip, and full workflow behavior",
        required_test_name_fragments=(
            "bad_transition_key",
            "valid_exits",
            "auto_injects_exits",
            "roundtrip",
            "full_yaml",
            "external_soul",
        ),
        required_helper_symbols=("build_workflow_yaml", "load_workflow_yaml_fixture"),
        required_references=(
            "RunsightWorkflowFile",
            "conditional_transitions",
            "exits",
            "parse_workflow_yaml",
            "safe_load",
            "soul_ref",
        ),
        minimum_test_count=6,
        minimum_assertive_test_count=6,
    ),
}

PROHIBITED_LEGACY_CLASS_NAMES = {
    "TestWorkflowFixtureStructure",
    "TestGateStandaloneRoutingIntegration",
    "TestGateInLoopRoutingIntegration",
    "TestOutputConditionsExitHandleChainIntegration",
    "TestValidationCatchesInvalidConfigs",
    "TestFullWorkflowBranchingFromYAML",
    "TestYamlExitPortRoundTrip",
    "TestExternalSoulFileResolution",
}
PROHIBITED_INLINE_HELPER_NAMES = {
    "_fresh_state",
    "_make_soul",
    "_mock_runner",
}
PROHIBITED_ROUTING_FIXTURE_CALLS = {
    "GateBlock",
    "LoopBlock",
    "Workflow",
    "add_conditional_transition",
    "parse_workflow_yaml",
    "set_output_conditions",
}
PROHIBITED_FILE_FIXTURE_CALLS = {
    "open",
    "safe_load",
    "write_text",
}
YAML_FIXTURE_CONTENT_MARKERS = (
    "blocks:",
    "conditional_transitions:",
    "eval_key:",
    "exits:",
    "output_conditions:",
    "soul_ref:",
    "type: gate",
    "type: linear",
    "workflow:",
)


def _parse_source(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _relative(path: Path) -> str:
    return str(path.relative_to(CORE_TEST_ROOT))


def _iter_test_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]


def _defined_test_names(tree: ast.AST) -> set[str]:
    return {node.name for node in _iter_test_functions(tree)}


def _defined_function_names(tree: ast.AST) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _defined_class_names(tree: ast.AST) -> set[str]:
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def _test_class_names(tree: ast.AST) -> set[str]:
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test")
    }


def _baseblock_stub_class_names(tree: ast.AST) -> set[str]:
    stub_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if any(_node_name(base) == "BaseBlock" for base in node.bases):
            stub_names.add(node.name)
    return stub_names


def _node_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _call_name(node: ast.Call) -> str:
    return _node_name(node.func)


def _called_names(tree: ast.AST) -> set[str]:
    return {_call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}


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


def _imported_names(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.asname or alias.name.partition(".")[0] for alias in node.names)
    return imported


def _exit_port_helper_imported_names(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.endswith("exit_port_helpers"):
                imported.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith("exit_port_helpers"):
                    imported.add(alias.asname or alias.name.rpartition(".")[2])
    return imported


def _exit_port_helper_called_names(tree: ast.AST) -> set[str]:
    helper_aliases = _exit_port_helper_imported_names(tree)
    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in helper_aliases
        ):
            calls.add(node.func.attr)
    return calls


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


def _function_uses_placeholder_or_skip(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    constants = [
        value.lower()
        for value in _string_constants(node)
        if any(marker in value.lower() for marker in PLACEHOLDER_TEXT_MARKERS)
    ]
    calls = _called_names(node)
    return bool(constants) or bool(calls & SKIP_OR_XFAIL_CALL_NAMES)


def _statement_has_assertion(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Assert):
        return True
    for node in ast.walk(stmt):
        if isinstance(node, ast.With):
            for item in node.items:
                if (
                    isinstance(item.context_expr, ast.Call)
                    and _call_name(item.context_expr) in ASSERT_CALL_NAMES
                ):
                    return True
        if isinstance(node, ast.Call) and _call_name(node) in ASSERT_CALL_NAMES:
            return True
    return False


def _assertive_test_count(tree: ast.AST) -> int:
    count = 0
    for test_func in _iter_test_functions(tree):
        if _function_uses_placeholder_or_skip(test_func):
            continue
        if any(_statement_has_assertion(stmt) for stmt in _effective_test_body(test_func)):
            count += 1
    return count


def _missing_test_fragments(
    tree: ast.AST,
    fragments: tuple[str, ...],
) -> list[str]:
    test_names = _defined_test_names(tree)
    return [
        fragment
        for fragment in fragments
        if not any(fragment in test_name for test_name in test_names)
    ]


def _missing_references(tree: ast.AST, fragments: tuple[str, ...]) -> list[str]:
    references = _referenced_symbols(tree)
    return [
        fragment
        for fragment in fragments
        if not any(fragment in reference for reference in references)
    ]


def _module_docstring_violations(path: Path, tree: ast.Module) -> list[str]:
    docstring = ast.get_docstring(tree) or ""
    if not docstring:
        return [f"{_relative(path)} must document Owner, Boundary, and Exit criteria"]

    required_fragments = ("Owner:", "Boundary:", "Exit criteria:")
    return [
        f"{_relative(path)} module docstring is missing {fragment}"
        for fragment in required_fragments
        if fragment not in docstring
    ]


def _large_inline_yaml_literals(path: Path) -> list[str]:
    tree = _parse_source(path)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        nonblank_lines = [line for line in node.value.splitlines() if line.strip()]
        if len(nonblank_lines) <= INLINE_YAML_LITERAL_MAX_NONBLANK_LINES:
            continue

        matched_markers = [
            marker for marker in YAML_FIXTURE_CONTENT_MARKERS if marker in node.value
        ]
        if len(matched_markers) < 2:
            continue

        line_number = getattr(node, "lineno", "?")
        violations.append(
            f"{_relative(path)}:{line_number}: {len(nonblank_lines)} inline YAML "
            f"fixture lines ({', '.join(matched_markers)})"
        )

    return violations


def _helper_export_violations() -> list[str]:
    if not EXIT_PORT_HELPERS.exists():
        return [f"missing shared helper module: {_relative(EXIT_PORT_HELPERS)}"]

    tree = _parse_source(EXIT_PORT_HELPERS)
    exported_names = _defined_function_names(tree) | _defined_class_names(tree)
    references = _referenced_symbols(tree) | _imported_names(tree)
    violations: list[str] = []

    for group, acceptable_names in EXPECTED_HELPER_EXPORT_GROUPS.items():
        if not exported_names & acceptable_names:
            violations.append(
                f"{_relative(EXIT_PORT_HELPERS)} must export a {group}; "
                f"expected one of {sorted(acceptable_names)}"
            )

    missing_references = sorted(EXPECTED_HELPER_REFERENCES - references)
    if missing_references:
        violations.append(
            f"{_relative(EXIT_PORT_HELPERS)} must reference helper contracts: "
            + ", ".join(missing_references)
        )

    return violations


def _owner_suite_violations(path: Path, expectation: OwnerSuiteExpectation) -> list[str]:
    if not path.exists():
        return [f"missing owner suite for {expectation.owner}: {_relative(path)}"]

    tree = _parse_source(path)
    test_count = len(_iter_test_functions(tree))
    assertive_count = _assertive_test_count(tree)
    helper_imports = _exit_port_helper_imported_names(tree)
    helper_calls = _exit_port_helper_called_names(tree)
    missing_fragments = _missing_test_fragments(tree, expectation.required_test_name_fragments)
    missing_helper_symbols = [
        name
        for name in expectation.required_helper_symbols
        if name not in helper_imports or name not in helper_calls
    ]
    missing_references = _missing_references(tree, expectation.required_references)

    violations: list[str] = []
    violations.extend(_module_docstring_violations(path, tree))

    if test_count < expectation.minimum_test_count:
        violations.append(
            f"{_relative(path)} has {test_count} tests; "
            f"expected >= {expectation.minimum_test_count}"
        )
    if assertive_count < expectation.minimum_assertive_test_count:
        violations.append(
            f"{_relative(path)} has {assertive_count} non-placeholder assertive tests; "
            f"expected >= {expectation.minimum_assertive_test_count}"
        )
    if missing_fragments:
        violations.append(
            f"{_relative(path)} is missing behavior-named tests containing: "
            + ", ".join(missing_fragments)
        )
    if missing_helper_symbols:
        violations.append(
            f"{_relative(path)} must import and call helper(s) from exit_port_helpers.py: "
            + ", ".join(missing_helper_symbols)
        )
    if missing_references:
        violations.append(
            f"{_relative(path)} is missing relevant references: " + ", ".join(missing_references)
        )

    return violations


def _legacy_suite_violations() -> list[str]:
    if not LEGACY_EXIT_PORT_SUITE.exists():
        return []

    source = LEGACY_EXIT_PORT_SUITE.read_text(encoding="utf-8")
    tree = _parse_source(LEGACY_EXIT_PORT_SUITE)
    line_count = len(source.splitlines())
    test_count = len(_iter_test_functions(tree))
    test_classes = sorted(_test_class_names(tree))
    broad_classes = sorted(set(test_classes) & PROHIBITED_LEGACY_CLASS_NAMES)
    inline_helpers = sorted(_defined_function_names(tree) & PROHIBITED_INLINE_HELPER_NAMES)
    stub_classes = sorted(_baseblock_stub_class_names(tree))
    routing_fixture_calls = sorted(_called_names(tree) & PROHIBITED_ROUTING_FIXTURE_CALLS)
    file_fixture_calls = sorted(_called_names(tree) & PROHIBITED_FILE_FIXTURE_CALLS)
    inline_yaml_literals = _large_inline_yaml_literals(LEGACY_EXIT_PORT_SUITE)

    violations: list[str] = []
    legacy_label = _relative(LEGACY_EXIT_PORT_SUITE)

    if line_count > LEGACY_MAX_LINES:
        violations.append(f"{legacy_label} has {line_count} lines; expected <= {LEGACY_MAX_LINES}")
    if test_count > LEGACY_MAX_TEST_FUNCTIONS:
        violations.append(
            f"{legacy_label} has {test_count} test functions; "
            f"expected <= {LEGACY_MAX_TEST_FUNCTIONS}"
        )
    if len(test_classes) > LEGACY_MAX_TEST_CLASSES:
        violations.append(
            f"{legacy_label} has {len(test_classes)} test classes; "
            f"expected <= {LEGACY_MAX_TEST_CLASSES}"
        )
    if broad_classes:
        violations.append(
            f"{legacy_label} still owns broad behavior classes: " + ", ".join(broad_classes)
        )
    if inline_helpers:
        violations.append(
            f"{legacy_label} still defines inline exit-port helper/builders: "
            + ", ".join(inline_helpers)
        )
    if stub_classes:
        violations.append(
            f"{legacy_label} still defines inline BaseBlock stub classes: "
            + ", ".join(stub_classes)
        )
    if routing_fixture_calls:
        violations.append(
            f"{legacy_label} still constructs broad routing fixtures inline: "
            + ", ".join(routing_fixture_calls)
        )
    if file_fixture_calls:
        violations.append(
            f"{legacy_label} still loads or writes YAML/file fixtures inline: "
            + ", ".join(file_fixture_calls)
        )
    if inline_yaml_literals:
        violations.append(
            "large inline YAML workflow fixtures should move to package-local "
            "builders or checked-in fixture files:\n" + "\n".join(inline_yaml_literals)
        )

    return violations


def test_exit_port_governance_requires_owner_suites_helpers_and_legacy_cleanup() -> None:
    """Owner: exit-port behavior tests. Exit: split suites replace this guard."""
    violations: list[str] = []

    violations.extend(_helper_export_violations())

    for path, expectation in EXPECTED_OWNER_SUITES.items():
        violations.extend(_owner_suite_violations(path, expectation))

    violations.extend(_legacy_suite_violations())

    assert violations == [], (
        "Exit-port governance requires focused owner suites with assertive "
        "behavior tests that import/call shared exit_port_helpers.py builders, "
        "plus a removed or tiny legacy umbrella suite with no inline fixtures.\n"
        + "\n".join(violations)
    )


def test_legacy_exit_ports_integration_is_absent_or_tiny_residual_without_inline_fixtures() -> None:
    """Owner: exit-port legacy cleanup. Exit: umbrella suite removed or tiny."""
    violations = _legacy_suite_violations()

    assert violations == [], (
        "The legacy exit-port integration umbrella must stop owning routing, "
        "loop, output_conditions, YAML, and fixture-construction behavior.\n"
        + "\n".join(violations)
    )
