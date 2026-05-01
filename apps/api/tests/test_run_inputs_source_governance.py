"""
Governance boundary for the task_data to inputs API source removal.

Owner: apps/api transport, service, and docs-integration owners.
Boundary: source files, deleted legacy modules, service signatures, and the
execution guide must not reintroduce the retired tasks API or task_data field.
Exit criteria: remove these source-inspection checks once the route contract,
service behavior, and docs workspace each own equivalent behavior coverage.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

API_SRC = Path(__file__).parents[1] / "src" / "runsight_api"
REPO_ROOT = Path(__file__).parents[3]
RUNNING_WORKFLOWS_DOC = (
    REPO_ROOT
    / "apps"
    / "site"
    / "src"
    / "content"
    / "docs"
    / "docs"
    / "execution"
    / "running-workflows.md"
)


def _source_path(*parts: str) -> Path:
    return API_SRC.joinpath(*parts)


def _read_source(path: Path) -> str:
    assert path.exists(), f"Expected source file to exist: {path}"
    return path.read_text(encoding="utf-8")


def _tasks_import_removed(source: str) -> bool:
    """Return True only if any remaining tasks mention is not an import/router reference."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "tasks" or alias.asname == "tasks":
                    return False
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "tasks":
                return False
    return True


class TestDeletedTasksApiFilesGovernance:
    """Owner: apps/api transport/data. Exit: deleted files stay gone for one release."""

    def test_tasks_router_file_does_not_exist(self):
        path = _source_path("transport", "routers", "tasks.py")
        assert not path.exists(), f"tasks.py router should have been deleted: {path}"

    def test_tasks_schema_file_does_not_exist(self):
        path = _source_path("transport", "schemas", "tasks.py")
        assert not path.exists(), f"tasks.py schema should have been deleted: {path}"

    def test_task_repo_file_does_not_exist(self):
        path = _source_path("data", "filesystem", "task_repo.py")
        assert not path.exists(), f"task_repo.py should have been deleted: {path}"


class TestRunInputsSourceGovernance:
    """Owner: apps/api transport. Exit: schema contract tests cover the rename fully."""

    def test_runs_schema_source_has_no_task_data(self):
        source = _read_source(_source_path("transport", "schemas", "runs.py"))
        assert "task_data" not in source, (
            "schemas/runs.py still mentions 'task_data'; rename it to 'inputs'"
        )

    def test_main_does_not_import_tasks_module(self):
        source = _read_source(_source_path("main.py"))
        assert "tasks" not in source or _tasks_import_removed(source), (
            "main.py still imports the tasks router; remove it from the import block "
            "and include_router call"
        )


class TestRunInputsServiceGovernance:
    """Owner: apps/api service layer. Exit: behavior tests cover service call contracts."""

    def test_execution_service_launch_execution_uses_inputs_param(self):
        from runsight_api.logic.services.execution_service import ExecutionService

        sig = inspect.signature(ExecutionService.launch_execution)
        params = list(sig.parameters.keys())
        assert "inputs" in params, (
            f"ExecutionService.launch_execution must have an 'inputs' parameter; got {params}"
        )
        assert "task_data" not in params, (
            f"ExecutionService.launch_execution must not have 'task_data' parameter; got {params}"
        )

    def test_execution_service_source_has_no_task_data(self):
        source = _read_source(_source_path("logic", "services", "execution_service.py"))
        assert "task_data" not in source, (
            "execution_service.py still mentions 'task_data'; rename all occurrences to 'inputs'"
        )

    def test_run_service_create_run_uses_inputs_param(self):
        from runsight_api.logic.services.run_service import RunService

        sig = inspect.signature(RunService.create_run)
        params = list(sig.parameters.keys())
        assert "inputs" in params, (
            f"RunService.create_run must have an 'inputs' parameter; got {params}"
        )
        assert "task_data" not in params, (
            f"RunService.create_run must not have 'task_data' parameter; got {params}"
        )

    def test_run_service_source_has_no_task_data(self):
        source = _read_source(_source_path("logic", "services", "run_service.py"))
        assert "task_data" not in source, (
            "run_service.py still mentions 'task_data'; rename all occurrences to 'inputs'"
        )


class TestExecutionDocsInputsGovernance:
    """Owner: apps/site docs. Exit: move to docs tests once docs examples are owned there."""

    def test_running_workflows_md_has_no_task_data(self):
        assert RUNNING_WORKFLOWS_DOC.exists(), (
            f"running-workflows.md not found at {RUNNING_WORKFLOWS_DOC}"
        )
        source = RUNNING_WORKFLOWS_DOC.read_text(encoding="utf-8")
        assert "task_data" not in source, (
            "running-workflows.md still mentions 'task_data'; update all occurrences to 'inputs'"
        )

    def test_running_workflows_md_mentions_inputs(self):
        assert RUNNING_WORKFLOWS_DOC.exists(), (
            f"running-workflows.md not found at {RUNNING_WORKFLOWS_DOC}"
        )
        source = RUNNING_WORKFLOWS_DOC.read_text(encoding="utf-8")
        assert "inputs" in source, (
            "running-workflows.md must mention 'inputs' after the task_data to inputs rename"
        )
