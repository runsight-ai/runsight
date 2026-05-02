"""Tools-owned repo governance for API source and workspace boundaries.

Owner: tools/tests owns compact static and tooling checks that scan repo files
instead of exercising API runtime behavior.
Boundary: these checks protect current API layout, CI/tooling wiring, tracked
artifact guardrails, and static router conventions without reading runtime user
state such as repo-root .runsight, runsight.db, custom/, env files, or secrets.
Exit criteria: delete or narrow this suite once the guarded policies are
generated from a single repo manifest or replaced by dedicated lint rules.
"""

from __future__ import annotations

import ast
import json
import re
import shlex
import shutil
import subprocess
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[2]
API_SRC = REPO_ROOT / "apps" / "api" / "src" / "runsight_api"
API_ROUTERS = API_SRC / "transport" / "routers"
API_SCHEMAS = API_SRC / "transport" / "schemas"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"
ROOT_PACKAGE_JSON = REPO_ROOT / "package.json"
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"
ROOT_GITIGNORE = REPO_ROOT / ".gitignore"
README = REPO_ROOT / "README.md"
TOOLS_README = REPO_ROOT / "tools" / "README.md"
CORE_SCHEMA_SCRIPT = REPO_ROOT / "packages" / "core" / "scripts" / "generate_schema.py"

SOURCE_WORKSPACES = ("apps/api", "apps/gui", "packages", "testing")
AUDITED_INVALID_TRACKED_ARTIFACTS = (
    "apps/api/skeleton.xml",
    "apps/gui/skeleton.xml",
    "packages/ui/components.json.bak",
)
EXPECTED_GITIGNORE_PATTERNS = (
    "*.xml",
    "*.bak",
    "*.db",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".DS_Store",
)

pytestmark = pytest.mark.governance


@dataclass(frozen=True)
class RouterConvention:
    router_name: str
    expected_tag: str
    prefix_must_start_with_slash: bool


@dataclass(frozen=True)
class InlineSchemaRouter:
    router_name: str


ROUTER_CONVENTIONS = (
    RouterConvention("eval", "Eval", False),
    RouterConvention("models", "Models", True),
)
ASYNC_ENDPOINT_ROUTERS = ("eval", "models")
INLINE_SCHEMA_ROUTERS = (
    InlineSchemaRouter("eval"),
    InlineSchemaRouter("models"),
    InlineSchemaRouter("settings"),
    InlineSchemaRouter("git"),
)
DEAD_SETTINGS_SCHEMA_NAMES = ("ProviderResponse", "FallbackTargetResponse", "SettingsResponse")


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _read_text(path: Path) -> str:
    assert path.exists(), f"Expected file to exist: {_relative(path)}"
    return path.read_text(encoding="utf-8")


def _source_tree(path: Path) -> ast.Module:
    return ast.parse(_read_text(path), filename=_relative(path))


def _router_path(router_name: str) -> Path:
    return API_ROUTERS / f"{router_name}.py"


def _router_tree(router_name: str) -> ast.Module:
    return _source_tree(_router_path(router_name))


def _name_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _parse_router_call(tree: ast.Module) -> ast.Call | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _name_of(node.func) == "APIRouter":
            return node
    return None


def _get_kwarg(call: ast.Call, name: str) -> ast.expr | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def _string_literal(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _list_string_literals(node: ast.expr | None) -> tuple[str, ...]:
    if not isinstance(node, ast.List):
        return ()
    return tuple(
        element.value
        for element in node.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    )


def _tag_literals(call: ast.Call) -> tuple[str, ...]:
    tags_node = _get_kwarg(call, "tags")
    if tag := _string_literal(tags_node):
        return (tag,)
    return _list_string_literals(tags_node)


def _route_decorated_functions(tree: ast.Module) -> tuple[tuple[str, bool], ...]:
    endpoints: list[tuple[str, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            if isinstance(decorator.func.value, ast.Name) and decorator.func.value.id == "router":
                endpoints.append((node.name, isinstance(node, ast.AsyncFunctionDef)))
                break
    return tuple(endpoints)


def _inline_basemodel_classes(tree: ast.Module) -> tuple[str, ...]:
    class_names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "BaseModel":
                class_names.append(node.name)
            elif isinstance(base, ast.Attribute) and base.attr == "BaseModel":
                class_names.append(node.name)
    return tuple(class_names)


def _function_def(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"Function {name!r} not found")


def _is_router_get_decorator(decorator: ast.expr, route_path: str) -> bool:
    if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
        return False
    if not isinstance(decorator.func.value, ast.Name) or decorator.func.value.id != "router":
        return False
    if decorator.func.attr != "get":
        return False
    return bool(decorator.args and _string_literal(decorator.args[0]) == route_path)


def _imports_from_schema_module(tree: ast.Module, expected_names: set[str]) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module == "schemas.models" and node.level == 2:
            imported_names = {alias.name for alias in node.names}
            if expected_names <= imported_names:
                return True
    return False


def _ci_run_commands() -> tuple[str, ...]:
    yaml = YAML(typ="safe")
    workflow = yaml.load(CI_WORKFLOW)
    commands: list[str] = []

    def collect(node: object) -> None:
        if isinstance(node, dict):
            run = node.get("run")
            if isinstance(run, str):
                commands.append(run.rstrip())
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for item in node:
                collect(item)

    collect(workflow)
    return tuple(commands)


def _has_python_workspace_install_command(command: str) -> bool:
    if "uv sync" in command:
        return True
    return "install" in command and "apps/api" in command and "packages/core" in command


def _pytest_commands(commands: Iterable[str]) -> tuple[str, ...]:
    return tuple(command for command in commands if re.search(r"(^|\s)pytest(\s|$)", command))


def _is_root_scoped_pytest(command: str) -> bool:
    tokens = shlex.split(command.replace("\n", " "))
    try:
        pytest_index = tokens.index("pytest")
    except ValueError:
        return False

    option_takes_value = {
        "-c",
        "-k",
        "-m",
        "-o",
        "--basetemp",
        "--confcutdir",
        "--deselect",
        "--durations",
        "--ignore",
        "--ignore-glob",
        "--junitxml",
        "--log-level",
        "--maxfail",
        "--rootdir",
    }
    positional_args: list[str] = []
    expects_value = False

    for token in tokens[pytest_index + 1 :]:
        if expects_value:
            expects_value = False
            continue
        if token == "--":
            positional_args.extend(tokens[pytest_index + 2 :])
            break
        if token.startswith("--") and "=" in token:
            continue
        if token in option_takes_value:
            expects_value = True
            continue
        if token.startswith("-"):
            continue
        positional_args.append(token)

    return positional_args == []


def _covers_current_python_test_roots(commands: Iterable[str]) -> bool:
    mentioned_roots: set[str] = set()
    for command in commands:
        mentions_api = "apps/api/tests" in command
        mentions_core = "packages/core/tests" in command
        if mentions_api:
            mentioned_roots.add("apps/api/tests")
        if mentions_core:
            mentioned_roots.add("packages/core/tests")
        if not mentions_api and not mentions_core and _is_root_scoped_pytest(command):
            return True
    return mentioned_roots == {"apps/api/tests", "packages/core/tests"}


def _has_repo_root_lint_invocation(command: str) -> bool:
    for line in command.splitlines():
        stripped = line.strip()
        if stripped.startswith("pnpm -C "):
            continue
        if re.match(r"^pnpm\s+(run\s+)?lint(\s|$)", stripped):
            return True
    return False


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)


def _codebones_executable() -> str:
    executable = shutil.which("codebones")
    assert executable, (
        "codebones CLI must be available for code index lifecycle coverage. "
        "Run `uv sync --dev` from the repo root so the managed dev dependency is on PATH."
    )
    return executable


def _codebones_index(cwd: Path) -> None:
    result = _run([_codebones_executable(), "index", "."], cwd=cwd)
    assert result.returncode == 0, (
        f"codebones index . failed unexpectedly\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _codebones_search(cwd: Path, query: str) -> tuple[str, ...]:
    result = _run([_codebones_executable(), "search", query], cwd=cwd)
    assert result.returncode == 0, (
        f"codebones search {query!r} failed unexpectedly\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return tuple(line for line in result.stdout.splitlines() if line.strip())


def _seed_codebones_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_result = _run(["git", "init", "-q"], cwd=repo)
    assert init_result.returncode == 0, init_result.stderr
    (repo / "alpha.py").write_text("def alpha_symbol():\n    return 1\n", encoding="utf-8")
    return repo


def _combined_codebones_doc_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in (README, TOOLS_README)).lower()


def _tracked_source_workspace_files() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files", "--", *SOURCE_WORKSPACES],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(line for line in result.stdout.splitlines() if line)


def _tracked_invalid_artifacts() -> tuple[str, ...]:
    invalid: list[str] = []
    for relative_path in _tracked_source_workspace_files():
        path = Path(relative_path)
        if path.name == "skeleton.xml":
            invalid.append(relative_path)
        elif path.suffix in {".bak", ".pyc", ".pyo", ".pyd"}:
            invalid.append(relative_path)
        elif any(part in {"__pycache__", ".pytest_cache", ".ruff_cache"} for part in path.parts):
            invalid.append(relative_path)
        elif path.name == ".DS_Store":
            invalid.append(relative_path)
    return tuple(invalid)


def test_removed_api_dead_code_stays_out_of_runtime_source() -> None:
    observer_file = API_SRC / "logic" / "observers" / "artifact_cleanup_observer.py"
    di_file = API_SRC / "core" / "di.py"

    assert not observer_file.exists(), f"Dead file still present: {_relative(observer_file)}"
    assert "setup_app_state" not in _read_text(di_file), (
        "No-op method setup_app_state still present in apps/api/src/runsight_api/core/di.py"
    )

    offenders = [
        _relative(path)
        for path in sorted(API_SRC.rglob("*.py"))
        if "ArtifactCleanupObserver" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        "ArtifactCleanupObserver still referenced in API runtime source:\n"
        + "\n".join(f"  - {path}" for path in offenders)
    )


def test_root_workspace_metadata_keeps_current_python_and_lint_coverage() -> None:
    pyproject = tomllib.loads(ROOT_PYPROJECT.read_text(encoding="utf-8"))
    package_json = json.loads(ROOT_PACKAGE_JSON.read_text(encoding="utf-8"))

    assert pyproject["tool"]["uv"]["workspace"]["members"] == ["apps/api", "packages/core"]
    assert package_json["scripts"]["lint"] == "pnpm run lint:js && pnpm run lint:py"

    lint_js_script = package_json["scripts"]["lint:js"]
    for workspace in ("apps/gui", "packages/ui", "packages/shared", "testing/gui-e2e"):
        assert workspace in lint_js_script, f"root lint:js script no longer covers {workspace}"

    lint_py_script = package_json["scripts"]["lint:py"]
    for workspace in ("apps/api", "packages/core"):
        assert workspace in lint_py_script, f"root lint:py script no longer covers {workspace}"


def test_publish_ci_targets_current_workspace_layout() -> None:
    assert CI_WORKFLOW.exists(), f"CI workflow not found at {_relative(CI_WORKFLOW)}"
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    commands = _ci_run_commands()

    assert "libs/core" not in text, "CI still references removed libs/core paths"
    assert any(_has_python_workspace_install_command(command) for command in commands), (
        "CI must install or sync apps/api and packages/core, or use uv workspace sync."
    )
    assert any(
        "packages/core/scripts/generate_schema.py" in command and "--check" in command
        for command in commands
    ), "CI must run packages/core/scripts/generate_schema.py --check"
    assert _covers_current_python_test_roots(_pytest_commands(commands)), (
        "CI must cover both apps/api/tests and packages/core/tests, either through repo-root "
        "pytest using pyproject testpaths or through deliberate explicit steps."
    )
    assert any(_has_repo_root_lint_invocation(command) for command in commands), (
        "CI must invoke repo-root pnpm lint coverage so current JS/Python workspaces stay covered."
    )


def test_contributor_tooling_docs_and_help_text_use_current_tool_paths() -> None:
    tools_readme = TOOLS_README.read_text(encoding="utf-8")
    core_schema_help = CORE_SCHEMA_SCRIPT.read_text(encoding="utf-8")

    assert "Current legacy tooling still exists in `scripts/`." not in tools_readme
    assert "python scripts/generate_schema.py" not in core_schema_help
    assert "Run `python scripts/generate_schema.py` to regenerate." not in core_schema_help
    assert "packages/core/scripts/generate_schema.py" in core_schema_help


def test_codebones_reindex_removes_deleted_file_symbols(tmp_path: Path) -> None:
    repo = _seed_codebones_repo(tmp_path)

    _codebones_index(repo)
    initial_hits = _codebones_search(repo, "alpha_symbol")
    assert any("alpha_symbol" in line and "alpha.py" in line for line in initial_hits), (
        "sanity check failed: initial index did not include alpha_symbol from alpha.py"
    )

    (repo / "alpha.py").unlink()
    _codebones_index(repo)

    named_hits_after_delete = _codebones_search(repo, "alpha_symbol")
    empty_hits_after_delete = _codebones_search(repo, "")
    assert all("alpha_symbol" not in line for line in named_hits_after_delete), (
        "Reindexing after deleting alpha.py should remove alpha_symbol from named search "
        f"results, but got: {named_hits_after_delete}"
    )
    assert all(
        "alpha_symbol" not in line and "alpha.py" not in line for line in empty_hits_after_delete
    ), (
        "Empty-query search should not surface stale rows for deleted alpha.py after reindex, "
        f"but got: {empty_hits_after_delete}"
    )


def test_codebones_contributor_guidance_covers_install_reindex_and_cache_reset() -> None:
    text = _combined_codebones_doc_text()

    has_uv_install_flow = any(marker in text for marker in ("uv tool install", "uv tool upgrade"))
    has_verification_step = any(
        marker in text for marker in ("uv tool list", "codebones --version")
    )
    mentions_reindex = "codebones index" in text and any(
        word in text for word in ("reindex", "rebuild")
    )
    mentions_cache_artifact = "codebones.db" in text
    mentions_reset_action = any(word in text for word in ("delete", "remove", "rm ", "invalidate"))
    mentions_checkout_scope = any(word in text for word in ("worktree", "checkout", "clone"))

    assert has_uv_install_flow and has_verification_step, (
        "Contributor docs must describe how to install or upgrade codebones via uv and how "
        "to verify the usable CLI."
    )
    assert (
        mentions_reindex
        and mentions_cache_artifact
        and mentions_reset_action
        and mentions_checkout_scope
    ), (
        "Contributor docs must explain reindexing, codebones.db cache ownership, cache "
        "invalidation, and checkout/worktree scope."
    )


def test_root_gitignore_covers_generated_and_local_artifact_guardrails() -> None:
    text = ROOT_GITIGNORE.read_text(encoding="utf-8")

    missing = [pattern for pattern in EXPECTED_GITIGNORE_PATTERNS if pattern not in text]
    assert missing == [], f"Root .gitignore is missing artifact guardrails: {missing}"


def test_source_workspaces_do_not_track_invalid_artifact_classes() -> None:
    invalid = _tracked_invalid_artifacts()
    tracked = set(_tracked_source_workspace_files())
    remaining_audited_artifacts = [
        path for path in AUDITED_INVALID_TRACKED_ARTIFACTS if path in tracked
    ]

    assert invalid == (), (
        "Tracked source workspaces still contain generated/backup/compiled/local-data detritus:\n"
        + "\n".join(f"  - {path}" for path in invalid)
    )
    assert remaining_audited_artifacts == [], (
        "Audited invalid tracked artifacts still exist in source workspaces:\n"
        + "\n".join(f"  - {path}" for path in remaining_audited_artifacts)
    )


@pytest.mark.parametrize("target", ROUTER_CONVENTIONS, ids=lambda target: target.router_name)
def test_static_router_declarations_keep_explicit_prefixes_and_pascal_case_tags(
    target: RouterConvention,
) -> None:
    call = _parse_router_call(_router_tree(target.router_name))
    assert call is not None, f"APIRouter() call not found in {target.router_name}.py"

    prefix = _string_literal(_get_kwarg(call, "prefix"))
    assert prefix is not None, f"{target.router_name}.py APIRouter() must declare prefix="
    if target.prefix_must_start_with_slash:
        assert prefix.startswith("/"), (
            f"{target.router_name}.py prefix must start with '/'. Got: {prefix!r}"
        )

    tags = _tag_literals(call)
    assert tags == (target.expected_tag,), (
        f"{target.router_name}.py tags must be [{target.expected_tag!r}], got {tags!r}"
    )


@pytest.mark.parametrize("router_name", ASYNC_ENDPOINT_ROUTERS)
def test_static_router_endpoints_are_async(router_name: str) -> None:
    endpoints = _route_decorated_functions(_router_tree(router_name))
    assert endpoints, f"No route-decorated functions found in {router_name}.py"

    sync_endpoints = [name for name, is_async in endpoints if not is_async]
    assert sync_endpoints == [], (
        f"{router_name}.py has sync endpoints: {sync_endpoints}. "
        "All endpoint functions must use async def."
    )


@pytest.mark.parametrize("target", INLINE_SCHEMA_ROUTERS, ids=lambda target: target.router_name)
def test_routers_do_not_define_inline_pydantic_schemas(target: InlineSchemaRouter) -> None:
    inline = _inline_basemodel_classes(_router_tree(target.router_name))
    assert inline == (), (
        f"{target.router_name}.py defines inline Pydantic schemas: {inline}. "
        f"Move them to transport/schemas/{target.router_name}.py."
    )


def test_models_router_uses_wrapped_list_response_contract() -> None:
    tree = _router_tree("models")
    list_models = _function_def(tree, "list_models")

    get_decorators = [
        decorator
        for decorator in list_models.decorator_list
        if _is_router_get_decorator(decorator, "")
    ]
    assert get_decorators, "models.py list_models must be decorated with @router.get('')"
    assert any(
        isinstance(response_model := _get_kwarg(decorator, "response_model"), ast.Name)
        and response_model.id == "ModelListResponse"
        for decorator in get_decorators
        if isinstance(decorator, ast.Call)
    ), "GET /api/models must declare response_model=ModelListResponse"

    returns = [node.value for node in ast.walk(list_models) if isinstance(node, ast.Return)]
    wrapped_returns = [
        node
        for node in returns
        if isinstance(node, ast.Call) and _name_of(node.func) == "ModelListResponse"
    ]
    assert wrapped_returns, "list_models must return ModelListResponse(items=..., total=...)"

    keyword_names = {keyword.arg for node in wrapped_returns for keyword in node.keywords}
    assert {"items", "total"} <= keyword_names, (
        "ModelListResponse return must include both items= and total= keywords"
    )
    assert any(
        keyword.arg == "total"
        and isinstance(keyword.value, ast.Call)
        and _name_of(keyword.value.func) == "len"
        and len(keyword.value.args) == 1
        and isinstance(keyword.value.args[0], ast.Name)
        and keyword.value.args[0].id == "items"
        for node in wrapped_returns
        for keyword in node.keywords
    ), "GET /api/models total must be derived from len(items)"


def test_model_catalog_schemas_live_in_transport_schema_module() -> None:
    router_tree = _router_tree("models")
    schema_tree = _source_tree(API_SCHEMAS / "models.py")
    class_names = {node.name for node in ast.walk(schema_tree) if isinstance(node, ast.ClassDef)}

    expected = {"ModelListResponse", "ModelResponse", "ProviderSummary"}
    assert expected <= class_names
    assert _imports_from_schema_module(router_tree, expected), (
        "models.py router must import model catalog schemas from transport/schemas/models.py"
    )


def test_dead_settings_schema_classes_stay_removed() -> None:
    tree = _source_tree(API_SCHEMAS / "settings.py")
    class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    remaining = sorted(set(DEAD_SETTINGS_SCHEMA_NAMES) & class_names)

    assert remaining == [], (
        "transport/schemas/settings.py still contains dead schema classes: " + ", ".join(remaining)
    )
