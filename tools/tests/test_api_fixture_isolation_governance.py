"""Table-driven governance for API test fixture ownership and isolation.

Owner: tools/tests owns compact static governance for API test fixture cleanup.
Boundary: this suite inspects only checked-in API test sources and
apps/api/tests/fixtures. It must not read runtime/user state such as repo-root
.runsight, runsight.db, or custom/.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
API_TESTS = REPO_ROOT / "apps" / "api" / "tests"
API_FIXTURES = API_TESTS / "fixtures"
UNMANAGED_TEMPFILE_FACTORIES = frozenset({"mkdtemp", "TemporaryDirectory", "NamedTemporaryFile"})

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class FixtureOwnershipTarget:
    name: str
    source: Path
    fixture_root: Path


@dataclass(frozen=True)
class RuntimeWorkspaceTarget:
    name: str
    source: Path
    fixture_name: str


@dataclass(frozen=True)
class DbHelperTarget:
    name: str
    source: Path
    helper_name: str
    requires_tmp_path: bool


@dataclass(frozen=True)
class ModuleWorkflowConstant:
    source: Path
    name: str
    line_number: int
    workflow_id: str


@dataclass(frozen=True)
class ModuleFixtureTextAlias:
    source: Path
    name: str
    line_number: int
    fixture_path: str


@dataclass(frozen=True)
class TempfileImport:
    module_name: str
    imported_name: str


@dataclass(frozen=True)
class TempfileUsage:
    source: Path
    function_name: str
    line_number: int
    factory_name: str


@dataclass(frozen=True)
class UnmanagedDbPathUsage:
    source: Path
    test_name: str
    line_number: int
    factory_name: str
    db_name: str


API_FIXTURE_TARGETS = (
    FixtureOwnershipTarget(
        "assertion wiring",
        API_TESTS / "logic" / "test_wire_assertion_configs.py",
        API_FIXTURES / "assertion_wiring",
    ),
    FixtureOwnershipTarget(
        "branch aware execution",
        API_TESTS / "logic" / "test_branch_aware_exec.py",
        API_FIXTURES / "branch_aware_execution",
    ),
    FixtureOwnershipTarget(
        "budget run status",
        API_TESTS / "logic" / "test_budget_run_status.py",
        API_FIXTURES / "budget_run_status",
    ),
    FixtureOwnershipTarget(
        "eval observer custom assertion",
        API_TESTS / "logic" / "test_eval_observer_custom_assertion.py",
        API_FIXTURES / "eval_observer_custom_assertion",
    ),
    FixtureOwnershipTarget(
        "execution assertions",
        API_TESTS / "test_execution_assertion_evaluation.py",
        API_FIXTURES / "execution_assertions",
    ),
    FixtureOwnershipTarget(
        "execution preparation",
        API_TESTS / "logic" / "test_execution_preparation.py",
        API_FIXTURES / "execution_preparation",
    ),
    FixtureOwnershipTarget(
        "execution service",
        API_TESTS / "logic" / "test_execution_service.py",
        API_FIXTURES / "execution_service",
    ),
    FixtureOwnershipTarget(
        "execution transport",
        API_TESTS / "test_execution_transport_integration.py",
        API_FIXTURES / "execution_transport",
    ),
    FixtureOwnershipTarget(
        "parser warning run snapshots",
        API_TESTS / "test_parser_warning_run_snapshots.py",
        API_FIXTURES / "parser_warning_run_snapshots",
    ),
    FixtureOwnershipTarget(
        "run creation execution",
        API_TESTS / "test_run_creation_execution_integration.py",
        API_FIXTURES / "run_creation_execution",
    ),
    FixtureOwnershipTarget(
        "simulation branches",
        API_TESTS / "logic" / "test_sim_branches.py",
        API_FIXTURES / "sim_branches",
    ),
    FixtureOwnershipTarget(
        "workflow input redaction",
        API_TESTS / "test_workflow_input_redaction_integration.py",
        API_FIXTURES / "workflow_input_redaction",
    ),
    FixtureOwnershipTarget(
        "workflow repository tool governance",
        API_TESTS / "unit" / "data" / "filesystem" / "test_workflow_repo_tool_governance.py",
        API_FIXTURES / "workflow_repo_tool_governance",
    ),
)

RUNTIME_WORKSPACE_TARGETS = (
    RuntimeWorkspaceTarget(
        "assertion wiring",
        API_TESTS / "logic" / "test_wire_assertion_configs.py",
        "assertion_wiring_workspace",
    ),
    RuntimeWorkspaceTarget(
        "eval observer custom assertion",
        API_TESTS / "logic" / "test_eval_observer_custom_assertion.py",
        "base_dir",
    ),
    RuntimeWorkspaceTarget(
        "execution assertions",
        API_TESTS / "test_execution_assertion_evaluation.py",
        "base_dir",
    ),
    RuntimeWorkspaceTarget(
        "execution transport",
        API_TESTS / "test_execution_transport_integration.py",
        "base_dir",
    ),
    RuntimeWorkspaceTarget(
        "parser warning run snapshots",
        API_TESTS / "test_parser_warning_run_snapshots.py",
        "base_dir",
    ),
    RuntimeWorkspaceTarget(
        "run creation execution",
        API_TESTS / "test_run_creation_execution_integration.py",
        "base_dir",
    ),
    RuntimeWorkspaceTarget(
        "workflow input redaction",
        API_TESTS / "test_workflow_input_redaction_integration.py",
        "base_dir",
    ),
)

DB_HELPER_TARGETS = (
    DbHelperTarget(
        "execution preparation",
        API_TESTS / "logic" / "test_execution_preparation.py",
        "_db_engine",
        True,
    ),
    DbHelperTarget(
        "execution transport",
        API_TESTS / "test_execution_transport_integration.py",
        "db_engine",
        True,
    ),
)

RUNS_ROUTER_TEST = API_TESTS / "transport" / "test_runs_router.py"
WORKFLOW_INPUT_REDACTION_TEST = API_TESTS / "test_workflow_input_redaction_integration.py"


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=_relative(path))


def _assignment_targets(statement: ast.Assign | ast.AnnAssign) -> list[str]:
    if isinstance(statement, ast.Assign):
        return [target.id for target in statement.targets if isinstance(target, ast.Name)]
    if isinstance(statement.target, ast.Name):
        return [statement.target.id]
    return []


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _string_assignment_value(statement: ast.stmt) -> str | None:
    if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
        return None
    return _literal_string(statement.value)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _decorator_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return _call_name(node)


def _argument_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    return {argument.arg for argument in function.args.args}


def _workflow_document_id(text: str) -> str | None:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(parsed, dict):
        return None
    if parsed.get("kind") != "workflow":
        return None
    if not isinstance(parsed.get("workflow"), dict) or not isinstance(parsed.get("blocks"), dict):
        return None

    workflow_id = parsed.get("id")
    return workflow_id if isinstance(workflow_id, str) else "<missing id>"


def _module_level_workflow_constants(path: Path) -> list[ModuleWorkflowConstant]:
    constants: list[ModuleWorkflowConstant] = []
    for statement in _source_tree(path).body:
        value = _string_assignment_value(statement)
        if value is None:
            continue

        workflow_id = _workflow_document_id(value)
        if workflow_id is None:
            continue

        constants.extend(
            ModuleWorkflowConstant(
                source=path,
                name=name,
                line_number=statement.lineno,
                workflow_id=workflow_id,
            )
            for name in _assignment_targets(statement)
        )
    return constants


def _fixture_text_call_path(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or _call_name(node.func) != "_fixture_text":
        return None
    if len(node.args) != 1:
        return "<dynamic path>"
    return _literal_string(node.args[0]) or "<dynamic path>"


def _module_fixture_text_aliases(path: Path) -> list[ModuleFixtureTextAlias]:
    aliases: list[ModuleFixtureTextAlias] = []
    for statement in _source_tree(path).body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue

        fixture_path = _fixture_text_call_path(statement.value)
        if fixture_path is None:
            continue

        aliases.extend(
            ModuleFixtureTextAlias(
                source=path,
                name=name,
                line_number=statement.lineno,
                fixture_path=fixture_path,
            )
            for name in _assignment_targets(statement)
        )
    return aliases


def _is_pytest_fixture(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        _decorator_name(decorator) == "pytest.fixture" for decorator in function.decorator_list
    )


def _pytest_fixture_function(
    path: Path,
    fixture_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for statement in _source_tree(path).body:
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if statement.name == fixture_name and _is_pytest_fixture(statement):
            return statement
    return None


def _function_named(
    path: Path,
    function_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for statement in _source_tree(path).body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if statement.name == function_name:
                return statement
    return None


def _tempfile_imports(tree: ast.Module) -> tuple[TempfileImport, ...]:
    imports: list[TempfileImport] = []
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            imports.extend(
                TempfileImport(module_name=alias.name, imported_name=alias.asname or alias.name)
                for alias in statement.names
                if alias.name == "tempfile"
            )
        elif isinstance(statement, ast.ImportFrom) and statement.module == "tempfile":
            imports.extend(
                TempfileImport(module_name=alias.name, imported_name=alias.asname or alias.name)
                for alias in statement.names
                if alias.name in UNMANAGED_TEMPFILE_FACTORIES
            )
    return tuple(imports)


def _called_tempfile_factory(
    call: ast.Call,
    tempfile_imports: tuple[TempfileImport, ...],
) -> str | None:
    module_aliases = {
        imported.imported_name
        for imported in tempfile_imports
        if imported.module_name == "tempfile"
    }
    direct_factory_aliases = {
        imported.imported_name: imported.module_name
        for imported in tempfile_imports
        if imported.module_name in UNMANAGED_TEMPFILE_FACTORIES
    }

    if isinstance(call.func, ast.Attribute):
        if isinstance(call.func.value, ast.Name):
            if (
                call.func.value.id in module_aliases
                and call.func.attr in UNMANAGED_TEMPFILE_FACTORIES
            ):
                return f"{call.func.value.id}.{call.func.attr}"

    if isinstance(call.func, ast.Name):
        factory_name = direct_factory_aliases.get(call.func.id)
        if factory_name is not None:
            return (
                call.func.id if call.func.id == factory_name else f"{call.func.id} ({factory_name})"
            )

    return None


def _tempfile_usages_in_function(path: Path, function: ast.AST, name: str) -> list[TempfileUsage]:
    tempfile_imports = _tempfile_imports(_source_tree(path))
    usages: list[TempfileUsage] = []
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        factory_name = _called_tempfile_factory(node, tempfile_imports)
        if factory_name is None:
            continue
        usages.append(
            TempfileUsage(
                source=path,
                function_name=name,
                line_number=node.lineno,
                factory_name=factory_name,
            )
        )
    return usages


def _contains_tempfile_factory(
    node: ast.AST,
    tempfile_imports: tuple[TempfileImport, ...],
) -> str | None:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            factory_name = _called_tempfile_factory(child, tempfile_imports)
            if factory_name is not None:
                return factory_name
    return None


def _file_backed_db_name(node: ast.AST) -> str | None:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            if child.value == "runsight.db":
                return child.value
    return None


def _test_function_unmanaged_db_path_usages(path: Path) -> list[UnmanagedDbPathUsage]:
    tree = _source_tree(path)
    tempfile_imports = _tempfile_imports(tree)
    usages: list[UnmanagedDbPathUsage] = []

    for statement in tree.body:
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not statement.name.startswith("test_"):
            continue

        for node in ast.walk(statement):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            factory_name = _contains_tempfile_factory(node, tempfile_imports)
            db_name = _file_backed_db_name(node)
            if factory_name is None or db_name is None:
                continue
            usages.append(
                UnmanagedDbPathUsage(
                    source=path,
                    test_name=statement.name,
                    line_number=node.lineno,
                    factory_name=factory_name,
                    db_name=db_name,
                )
            )
    return usages


def _owned_fixture_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


@pytest.mark.parametrize(
    "target",
    API_FIXTURE_TARGETS,
    ids=lambda target: target.name,
)
def test_api_reusable_workflow_payloads_are_fixture_owned(
    target: FixtureOwnershipTarget,
) -> None:
    assert target.source.is_file(), f"Missing API test source: {_relative(target.source)}"
    assert target.fixture_root.is_dir(), (
        f"{target.name} reusable fixtures must live under {_relative(target.fixture_root)}"
    )
    assert _owned_fixture_files(target.fixture_root), (
        f"{_relative(target.fixture_root)} should contain the package-owned fixtures "
        f"for {target.name}."
    )

    constants = _module_level_workflow_constants(target.source)
    assert constants == [], (
        f"{_relative(target.source)} must not define reusable module-level workflow "
        f"YAML constants. Keep shared API payloads under {_relative(target.fixture_root)}. "
        "Found:\n"
        + "\n".join(
            f"  - {constant.name} at line {constant.line_number} "
            f"(workflow id: {constant.workflow_id})"
            for constant in constants
        )
    )


@pytest.mark.parametrize(
    "target",
    RUNTIME_WORKSPACE_TARGETS,
    ids=lambda target: f"{target.name}:{target.fixture_name}",
)
def test_api_runtime_workspaces_use_pytest_tmp_path(
    target: RuntimeWorkspaceTarget,
) -> None:
    fixture = _pytest_fixture_function(target.source, target.fixture_name)
    assert fixture is not None, (
        f"{_relative(target.source)} must keep explicit pytest fixture "
        f"{target.fixture_name!r} for runtime workspace setup."
    )
    assert "tmp_path" in _argument_names(fixture), (
        f"{_relative(target.source)} {target.fixture_name} must accept pytest tmp_path "
        "so API runtime workspaces are pytest-owned."
    )

    usages = _tempfile_usages_in_function(target.source, fixture, target.fixture_name)
    assert usages == [], (
        f"{_relative(target.source)} {target.fixture_name} must not allocate "
        "runtime workspaces with unmanaged tempfile factories. Found:\n"
        + "\n".join(
            f"  - {usage.function_name} calls {usage.factory_name} at line {usage.line_number}"
            for usage in usages
        )
    )


@pytest.mark.parametrize(
    "target",
    DB_HELPER_TARGETS,
    ids=lambda target: f"{target.name}:{target.helper_name}",
)
def test_api_db_helpers_use_pytest_owned_isolation(target: DbHelperTarget) -> None:
    helper = _function_named(target.source, target.helper_name)
    assert helper is not None, (
        f"{_relative(target.source)} must keep DB setup helper {target.helper_name!r}."
    )
    if target.requires_tmp_path:
        assert "tmp_path" in _argument_names(helper), (
            f"{_relative(target.source)} {target.helper_name} must accept pytest tmp_path "
            "for file-backed test DB ownership."
        )

    usages = _tempfile_usages_in_function(target.source, helper, target.helper_name)
    assert usages == [], (
        f"{_relative(target.source)} {target.helper_name} must not create "
        "file-backed test databases through unmanaged tempfile factories. Found:\n"
        + "\n".join(
            f"  - {usage.function_name} calls {usage.factory_name} at line {usage.line_number}"
            for usage in usages
        )
    )


def test_runs_router_real_read_model_db_path_uses_pytest_owned_isolation() -> None:
    usages = _test_function_unmanaged_db_path_usages(RUNS_ROUTER_TEST)

    assert usages == [], (
        f"{_relative(RUNS_ROUTER_TEST)} test functions must not create file-backed "
        'runs router databases from unmanaged tempfile factories. Use tmp_path / "runsight.db". '
        "Found:\n"
        + "\n".join(
            f"  - {usage.test_name} builds {usage.db_name} with {usage.factory_name} "
            f"at line {usage.line_number}"
            for usage in usages
        )
    )


def test_workflow_input_redaction_loads_fixtures_on_demand() -> None:
    aliases = _module_fixture_text_aliases(WORKFLOW_INPUT_REDACTION_TEST)

    assert aliases == [], (
        f"{_relative(WORKFLOW_INPUT_REDACTION_TEST)} must not cache reusable "
        "fixture payloads as module-level _fixture_text(...) aliases. Load them "
        "inside the API-owned builder/fixture so test state is explicit. Found:\n"
        + "\n".join(
            f"  - {alias.name} at line {alias.line_number} (fixture: {alias.fixture_path})"
            for alias in aliases
        )
    )
