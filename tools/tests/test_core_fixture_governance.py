"""Table-driven governance for core test fixture ownership.

Owner: tools/tests owns compact static governance for core test fixture cleanup.
Boundary: this suite inspects checked-in packages/core test sources and package
fixture directories only. It must not inspect repo-root runtime/user state.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_TESTS = REPO_ROOT / "packages" / "core" / "tests"
CORE_FIXTURES = CORE_TESTS / "fixtures"

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class WorkflowConstantTarget:
    name: str
    source: Path
    fixture_hint: str


@dataclass(frozen=True)
class TmpPathTarget:
    name: str
    source: Path


@dataclass(frozen=True)
class ModuleWorkflowConstant:
    source: Path
    name: str
    line_number: int
    workflow_id: str
    workflow_name: str


@dataclass(frozen=True)
class TemporaryDirectoryReference:
    source: Path
    line_number: int
    kind: str
    detail: str


@dataclass(frozen=True)
class InlineYamlWrite:
    source: Path
    line_number: int
    test_name: str
    asset_kind: str


@dataclass(frozen=True)
class InlineWorkflowPayload:
    source: Path
    line_number: int
    helper_name: str
    workflow_id: str
    workflow_name: str


@dataclass(frozen=True)
class ModuleYamlSectionConstant:
    name: str
    line_number: int
    top_level_key: str
    entry_names: tuple[str, ...]


WORKFLOW_CONSTANT_TARGETS = (
    WorkflowConstantTarget(
        "code block parser",
        CORE_TESTS / "test_code_block_parser_and_achat.py",
        "packages/core/tests/fixtures/workflows or workflow_fixture_helpers.py",
    ),
    WorkflowConstantTarget(
        "migrated block round trip",
        CORE_TESTS / "test_migrate_blocks.py",
        "packages/core/tests/fixtures/workflows or workflow_fixture_helpers.py",
    ),
    WorkflowConstantTarget(
        "step wrapper assertions",
        CORE_TESTS / "test_step_wrapper_assertions.py",
        "packages/core/tests/fixtures/workflows or workflow_fixture_helpers.py",
    ),
    WorkflowConstantTarget(
        "YAML assertions config",
        CORE_TESTS / "test_yaml_assertions_config.py",
        "packages/core/tests/fixtures/workflows or workflow_fixture_helpers.py",
    ),
)

TMP_PATH_TARGETS = (
    TmpPathTarget("soul scanner", CORE_TESTS / "test_soul_scanner.py"),
    TmpPathTarget("tool scanner", CORE_TESTS / "test_tool_scanner.py"),
    TmpPathTarget("workflow scanner", CORE_TESTS / "test_workflow_scanner.py"),
    TmpPathTarget(
        "parser soul field forwarding", CORE_TESTS / "test_parser_soul_field_forwarding.py"
    ),
    TmpPathTarget("step wrapper assertions", CORE_TESTS / "test_step_wrapper_assertions.py"),
    TmpPathTarget("wire soul_ref library", CORE_TESTS / "test_wire_soul_ref_to_library.py"),
    TmpPathTarget("observer", CORE_TESTS / "test_observer.py"),
    TmpPathTarget("observer soul extension", CORE_TESTS / "test_observer_soul_extension.py"),
    TmpPathTarget("tool pydantic validation", CORE_TESTS / "test_tool_pydantic_validation.py"),
)

DISCOVERY_SCANNER_SUITES = (
    CORE_TESTS / "test_soul_scanner.py",
    CORE_TESTS / "test_tool_scanner.py",
    CORE_TESTS / "test_workflow_scanner.py",
)

DISCOVERY_FIXTURE_HELPERS = CORE_TESTS / "discovery_fixtures.py"
EVAL_RUNNER_TEST = CORE_TESTS / "test_eval_runner.py"
EVAL_FIXTURE_DIR = CORE_FIXTURES / "eval"
PARSER_SOUL_FIELD_FORWARDING_TEST = CORE_TESTS / "test_parser_soul_field_forwarding.py"
PARSER_YAML_HELPERS = CORE_TESTS / "parser_yaml_helpers.py"
STEP_WRAPPER_ASSERTION_TEST = CORE_TESTS / "test_step_wrapper_assertions.py"
WIRE_SOUL_REF_LIBRARY_TEST = CORE_TESTS / "test_wire_soul_ref_to_library.py"

EXPECTED_EVAL_RUNNER_FIXTURES = (
    "eval-runner-two-case.yaml",
    "eval-runner-fixture-case.yaml",
    "eval-runner-low-threshold.yaml",
    "eval-runner-two-block.yaml",
    "eval-runner-no-expected-case.yaml",
    "eval-runner-no-fixtures-no-executor.yaml",
)

MODULE_LEVEL_YAML_CONSTANT = re.compile(r"^_[A-Z0-9_]*YAML$")
WORKFLOW_WRITER_HELPERS = frozenset({"_write_workflow_file", "write_workflow_file"})


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=_relative(path))


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _assignment_targets(statement: ast.stmt) -> list[str]:
    if isinstance(statement, ast.Assign):
        return [target.id for target in statement.targets if isinstance(target, ast.Name)]
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return [statement.target.id]
    return []


def _string_assignment_value(statement: ast.stmt) -> str | None:
    if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
        return None
    return _literal_string(statement.value)


def _workflow_details(text: str) -> tuple[str, str] | None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict) or parsed.get("kind") != "workflow":
        return None
    workflow = parsed.get("workflow")
    blocks = parsed.get("blocks")
    if not isinstance(workflow, dict) or not isinstance(blocks, dict):
        return None

    workflow_id = parsed.get("id")
    workflow_name = workflow.get("name")
    return (
        workflow_id if isinstance(workflow_id, str) else "<missing id>",
        workflow_name if isinstance(workflow_name, str) else "<missing workflow.name>",
    )


def _module_level_workflow_constants(path: Path) -> list[ModuleWorkflowConstant]:
    constants: list[ModuleWorkflowConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        details = _workflow_details(value)
        if details is None:
            continue

        workflow_id, workflow_name = details
        constants.extend(
            ModuleWorkflowConstant(
                source=path,
                name=name,
                line_number=statement.lineno,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
            )
            for name in _assignment_targets(statement)
        )
    return constants


def _temporary_directory_references(path: Path) -> list[TemporaryDirectoryReference]:
    tree = _source_tree(path)
    aliases: dict[str, str] = {}
    references: list[TemporaryDirectoryReference] = []

    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name == "tempfile":
                    aliases[alias.asname or alias.name] = "tempfile"
        elif isinstance(statement, ast.ImportFrom) and statement.module == "tempfile":
            for alias in statement.names:
                if alias.name == "TemporaryDirectory":
                    imported_name = alias.asname or alias.name
                    aliases[imported_name] = "TemporaryDirectory"
                    references.append(
                        TemporaryDirectoryReference(
                            source=path,
                            line_number=statement.lineno,
                            kind="import",
                            detail=f"from tempfile import {alias.name}",
                        )
                    )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == "TemporaryDirectory":
            if (
                isinstance(node.func.value, ast.Name)
                and aliases.get(node.func.value.id) == "tempfile"
            ):
                references.append(
                    TemporaryDirectoryReference(
                        source=path,
                        line_number=node.lineno,
                        kind="call",
                        detail=f"{node.func.value.id}.TemporaryDirectory()",
                    )
                )
        elif isinstance(node.func, ast.Name) and aliases.get(node.func.id) == "TemporaryDirectory":
            references.append(
                TemporaryDirectoryReference(
                    source=path,
                    line_number=node.lineno,
                    kind="call",
                    detail=f"{node.func.id}()",
                )
            )

    return references


def _dedent_literal_arg(call: ast.Call) -> str | None:
    if _call_name(call.func) != "dedent" or not call.args:
        return None
    return _literal_string(call.args[0])


def _inline_structured_yaml_writes(path: Path) -> list[InlineYamlWrite]:
    writes: list[InlineYamlWrite] = []

    for function in (
        node for node in ast.walk(_source_tree(path)) if isinstance(node, ast.FunctionDef)
    ):
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

            normalized = text.lower()
            asset_kind: str | None = None
            if "kind: soul" in normalized:
                asset_kind = "soul"
            elif "kind: tool" in normalized or (
                "version:" in normalized and "kind:" in normalized and "executor:" in normalized
            ):
                asset_kind = "tool"
            if asset_kind is None:
                continue

            writes.append(
                InlineYamlWrite(
                    source=path,
                    line_number=node.lineno,
                    test_name=function.name,
                    asset_kind=asset_kind,
                )
            )
    return writes


def _workflow_writer_payload_arg(call: ast.Call) -> ast.AST | None:
    helper_name = _call_name(call.func)
    if helper_name not in WORKFLOW_WRITER_HELPERS:
        return None
    if len(call.args) >= 2:
        return call.args[1]
    for keyword in call.keywords:
        if keyword.arg in {"yaml_content", "content", "workflow_yaml"}:
            return keyword.value
    return None


def _inline_workflow_payloads(path: Path) -> list[InlineWorkflowPayload]:
    payloads: list[InlineWorkflowPayload] = []
    for node in ast.walk(_source_tree(path)):
        if not isinstance(node, ast.Call):
            continue

        payload_arg = _workflow_writer_payload_arg(node)
        if payload_arg is None:
            continue
        text = _literal_string(payload_arg)
        if text is None:
            continue

        details = _workflow_details(text)
        if details is None:
            continue

        workflow_id, workflow_name = details
        payloads.append(
            InlineWorkflowPayload(
                source=path,
                line_number=node.lineno,
                helper_name=_call_name(node.func) or "<unknown helper>",
                workflow_id=workflow_id,
                workflow_name=workflow_name,
            )
        )
    return payloads


def _structured_yaml_section_details(text: str) -> tuple[str, tuple[str, ...]] | None:
    try:
        parsed = yaml.safe_load(dedent(text))
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None
    section = parsed.get("souls")
    if not isinstance(section, dict):
        return None

    entry_names = tuple(sorted(name for name in section if isinstance(name, str)))
    return "souls", entry_names


def _module_level_yaml_section_constants(path: Path) -> list[ModuleYamlSectionConstant]:
    constants: list[ModuleYamlSectionConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue
        details = _structured_yaml_section_details(value)
        if details is None:
            continue

        top_level_key, entry_names = details
        constants.extend(
            ModuleYamlSectionConstant(
                name=name,
                line_number=statement.lineno,
                top_level_key=top_level_key,
                entry_names=entry_names,
            )
            for name in _assignment_targets(statement)
        )
    return constants


def _function_named(path: Path, function_name: str) -> ast.FunctionDef | None:
    for statement in _source_tree(path).body:
        if isinstance(statement, ast.FunctionDef) and statement.name == function_name:
            return statement
    return None


def _argument_names(function: ast.FunctionDef) -> list[str]:
    return [argument.arg for argument in function.args.args]


@pytest.mark.parametrize(
    "target",
    WORKFLOW_CONSTANT_TARGETS,
    ids=lambda target: target.name,
)
def test_core_reusable_workflow_payloads_are_fixture_owned(
    target: WorkflowConstantTarget,
) -> None:
    constants = _module_level_workflow_constants(target.source)

    assert constants == [], (
        f"{_relative(target.source)} must not define reusable module-level "
        f"workflow-shaped YAML constants. Use {target.fixture_hint}. Found:\n"
        + "\n".join(
            f"  - {constant.name} at line {constant.line_number} "
            f"(id={constant.workflow_id}, workflow={constant.workflow_name})"
            for constant in constants
        )
    )


@pytest.mark.parametrize("target", TMP_PATH_TARGETS, ids=lambda target: target.name)
def test_core_workspace_suites_do_not_use_temporarydirectory(target: TmpPathTarget) -> None:
    references = _temporary_directory_references(target.source)

    assert references == [], (
        f"{_relative(target.source)} must use pytest tmp_path or package-owned "
        "fixtures for test workspaces, not tempfile.TemporaryDirectory. Found:\n"
        + "\n".join(
            f"  - {reference.kind} at line {reference.line_number}: {reference.detail}"
            for reference in references
        )
    )


def test_core_discovery_scanner_fixture_contract_uses_split_owner_suites() -> None:
    missing = [
        path
        for path in (*DISCOVERY_SCANNER_SUITES, DISCOVERY_FIXTURE_HELPERS)
        if not path.is_file()
    ]
    assert missing == [], (
        "Core discovery scanner ownership should stay in split package suites/helpers. Missing:\n"
        + "\n".join(f"  - {_relative(path)}" for path in missing)
    )

    helper_source = DISCOVERY_FIXTURE_HELPERS.read_text(encoding="utf-8")
    for helper_name in ("write_soul_yaml", "write_tool_yaml"):
        assert f"def {helper_name}(" in helper_source, (
            f"{_relative(DISCOVERY_FIXTURE_HELPERS)} must expose {helper_name} "
            "for package-local scanner fixture setup."
        )

    suite_imports = "\n".join(path.read_text(encoding="utf-8") for path in DISCOVERY_SCANNER_SUITES)
    assert "write_soul_yaml" in suite_imports and "write_tool_yaml" in suite_imports, (
        "Scanner behavior suites should use package-local discovery_fixtures helpers "
        "for repeated custom/souls and custom/tools YAML setup."
    )


def test_eval_runner_reusable_workflow_fixtures_live_in_eval_fixture_directory() -> None:
    missing = [
        EVAL_FIXTURE_DIR / fixture_name
        for fixture_name in EXPECTED_EVAL_RUNNER_FIXTURES
        if not (EVAL_FIXTURE_DIR / fixture_name).is_file()
    ]

    assert missing == [], "Missing eval runner workflow fixture files:\n" + "\n".join(
        f"  - {_relative(path)}" for path in missing
    )


def test_eval_runner_loads_external_workflow_fixtures_through_helper() -> None:
    imports_helper = any(
        isinstance(statement, ast.ImportFrom)
        and statement.module == "eval_fixture_helpers"
        and any(alias.name == "eval_fixture_text" for alias in statement.names)
        for statement in _source_tree(EVAL_RUNNER_TEST).body
    )

    assert imports_helper, (
        f"{_relative(EVAL_RUNNER_TEST)} must import eval_fixture_text from "
        "eval_fixture_helpers to load reusable eval workflow fixtures."
    )


def test_eval_runner_does_not_define_reusable_module_level_yaml_constants() -> None:
    constants = [
        name
        for statement in _source_tree(EVAL_RUNNER_TEST).body
        for name in _assignment_targets(statement)
        if MODULE_LEVEL_YAML_CONSTANT.match(name)
        and isinstance(statement, (ast.Assign, ast.AnnAssign))
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    ]

    assert constants == [], (
        f"{_relative(EVAL_RUNNER_TEST)} must not define reusable module-level "
        "_...YAML string constants. Move reusable eval runner workflow YAML to "
        "packages/core/tests/fixtures/eval and load it with eval_fixture_text. "
        f"Found: {', '.join(constants)}"
    )


def test_parser_soul_field_forwarding_uses_package_owned_workflow_fixtures() -> None:
    payloads = _inline_workflow_payloads(PARSER_SOUL_FIELD_FORWARDING_TEST)

    assert payloads == [], (
        f"{_relative(PARSER_SOUL_FIELD_FORWARDING_TEST)} must not pass inline "
        "workflow-shaped YAML payloads to workflow-writing helpers. Load reusable "
        "payloads through package-owned workflow fixtures. Found:\n"
        + "\n".join(
            f"  - {payload.helper_name} at line {payload.line_number} "
            f"(id={payload.workflow_id}, workflow={payload.workflow_name})"
            for payload in payloads
        )
    )


def test_parser_yaml_helpers_use_builders_for_reusable_yaml_sections() -> None:
    constants = _module_level_yaml_section_constants(PARSER_YAML_HELPERS)

    assert constants == [], (
        f"{_relative(PARSER_YAML_HELPERS)} must not define reusable module-level "
        "structured YAML section constants. Use helper functions or package fixtures. Found:\n"
        + "\n".join(
            f"  - {constant.name} at line {constant.line_number} "
            f"(top-level {constant.top_level_key}: {', '.join(constant.entry_names)})"
            for constant in constants
        )
    )


def test_step_wrapper_parser_workspace_accepts_tmp_path() -> None:
    parse_with_souls = _function_named(STEP_WRAPPER_ASSERTION_TEST, "_parse_with_souls")
    assert parse_with_souls is not None, (
        f"{_relative(STEP_WRAPPER_ASSERTION_TEST)} should keep _parse_with_souls "
        "as the owning parser workspace helper."
    )
    assert "tmp_path" in _argument_names(parse_with_souls), (
        f"{_relative(STEP_WRAPPER_ASSERTION_TEST)} _parse_with_souls must accept "
        "pytest tmp_path so parser workspace ownership is explicit."
    )


def test_wire_soul_ref_library_soul_yaml_setup_uses_helpers() -> None:
    writes = [
        write
        for write in _inline_structured_yaml_writes(WIRE_SOUL_REF_LIBRARY_TEST)
        if write.asset_kind == "soul"
    ]

    assert writes == [], (
        f"{_relative(WIRE_SOUL_REF_LIBRARY_TEST)} must not write structured "
        "custom/souls YAML inline via .write_text(dedent(... kind: soul ...)). "
        "Use _write_soul_file or parser_yaml_helpers. Found:\n"
        + "\n".join(
            f"  - line {write.line_number}: {write.test_name} writes soul YAML" for write in writes
        )
    )
