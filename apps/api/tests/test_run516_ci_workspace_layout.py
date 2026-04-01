"""
Red tests for RUN-516: align CI workflows with the current workspace layout.

These tests verify that CI:
- no longer references removed workspace paths such as libs/core
- installs or syncs the current Python workspaces (apps/api + packages/core)
- runs schema verification from packages/core/scripts/generate_schema.py
- runs pytest against both current Python test roots
- invokes the repo-root lint coverage that fans out across the current JS workspaces
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
ROOT_PACKAGE_JSON = REPO_ROOT / "package.json"
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"


def _ci_run_commands() -> list[str]:
    """Return every shell command executed by the CI workflow."""
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    commands: list[str] = []
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        match = re.match(r"^(\s*)-\s+run:\s*(.*)$", line)
        if not match:
            i += 1
            continue

        indent = len(match.group(1))
        value = match.group(2).strip()

        if value and value not in {"|", ">"}:
            commands.append(value)
            i += 1
            continue

        i += 1
        block_lines: list[str] = []
        while i < len(lines):
            next_line = lines[i]
            if next_line.strip() and len(next_line) - len(next_line.lstrip()) <= indent + 1:
                break
            block_lines.append(next_line[indent + 2 :])
            i += 1

        commands.append("\n".join(block_lines).rstrip())

    return commands


def _has_python_workspace_install_command(command: str) -> bool:
    """Accept either uv workspace sync or an explicit install of both workspaces."""
    if "uv sync" in command:
        return True

    if "install" not in command:
        return False

    return "apps/api" in command and "packages/core" in command


def _pytest_commands() -> list[str]:
    """Return workflow commands that invoke pytest."""
    return [command for command in _ci_run_commands() if re.search(r"(^|\s)pytest(\s|$)", command)]


def _is_root_scoped_pytest(command: str) -> bool:
    """Accept pytest only when it has no positional path arguments."""
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

    expects_value = False
    positional_args: list[str] = []

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


def _covers_current_python_test_roots(commands: list[str]) -> bool:
    """Accept repo-root pytest or deliberate explicit coverage across commands."""
    mentioned_roots: set[str] = set()

    for command in commands:
        mentions_api = "apps/api/tests" in command
        mentions_core = "packages/core/tests" in command

        if mentions_api:
            mentioned_roots.add("apps/api/tests")
        if mentions_core:
            mentioned_roots.add("packages/core/tests")

        # Repo-root pytest is valid because pyproject.toml defines both testpaths.
        if not mentions_api and not mentions_core and _is_root_scoped_pytest(command):
            return True

    return mentioned_roots == {"apps/api/tests", "packages/core/tests"}


def _has_repo_root_lint_invocation(command: str) -> bool:
    """Detect repo-root pnpm lint without requiring an exact single-line step."""
    for line in command.splitlines():
        stripped = line.strip()
        if stripped.startswith("pnpm -C "):
            continue
        if re.match(r"^pnpm\s+(run\s+)?lint(\s|$)", stripped):
            return True
    return False


class TestWorkspaceMetadataPreconditions:
    """Preconditions describing the current canonical layout."""

    def test_root_uv_workspace_members_are_api_and_core(self):
        text = ROOT_PYPROJECT.read_text(encoding="utf-8")
        assert 'members = ["apps/api", "packages/core"]' in text

    def test_root_lint_script_covers_current_js_and_python_workspaces(self):
        package_json = json.loads(ROOT_PACKAGE_JSON.read_text(encoding="utf-8"))
        lint_script = package_json["scripts"]["lint"]
        lint_js_script = package_json["scripts"]["lint:js"]
        lint_py_script = package_json["scripts"]["lint:py"]

        assert lint_script == "pnpm run lint:js && pnpm run lint:py"
        for workspace in ["apps/gui", "packages/ui", "packages/shared", "testing/gui-e2e"]:
            assert workspace in lint_js_script, f"root lint:js script no longer covers {workspace}"
        for workspace in ["apps/api", "packages/core"]:
            assert workspace in lint_py_script, f"root lint:py script no longer covers {workspace}"


class TestCiWorkflowLayout:
    """CI should target current workspaces and avoid deleted trees."""

    def test_ci_workflow_exists(self):
        assert CI_WORKFLOW.exists(), f"CI workflow not found at {CI_WORKFLOW}"

    def test_ci_does_not_reference_removed_libs_core_layout(self):
        text = CI_WORKFLOW.read_text(encoding="utf-8")
        assert "libs/core" not in text, "CI still references removed libs/core paths"

    def test_ci_installs_or_syncs_current_python_workspaces(self):
        commands = _ci_run_commands()
        assert any(_has_python_workspace_install_command(command) for command in commands), (
            "CI must install or sync the current Python workspaces "
            "(apps/api and packages/core), or use uv workspace sync."
        )

    def test_ci_schema_check_uses_packages_core_script(self):
        commands = _ci_run_commands()
        assert any(
            "packages/core/scripts/generate_schema.py" in command and "--check" in command
            for command in commands
        ), "CI must run packages/core/scripts/generate_schema.py --check"

    def test_ci_pytest_targets_api_and_core_test_roots(self):
        commands = _pytest_commands()
        assert _covers_current_python_test_roots(commands), (
            "CI must cover both apps/api/tests and packages/core/tests, either through "
            "repo-root pytest using pyproject testpaths or through deliberate explicit steps."
        )

    def test_ci_invokes_repo_root_lint_coverage(self):
        commands = _ci_run_commands()
        assert any(_has_repo_root_lint_invocation(command) for command in commands), (
            "CI must invoke repo-root pnpm lint coverage so GUI, shared packages, "
            "E2E workspace, API, and core runtime stay covered intentionally."
        )
