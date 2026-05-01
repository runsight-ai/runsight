"""Task API governance coverage.

These tests protect the boundary that workflow execution no longer exposes
task oriented primitives or runner APIs.

Owner: packages/core public runtime API.
Boundary: removed Task/current_task symbols must stay absent from primitives,
state, YAML parser/schema, runner, and package exports.
Exit criteria: remove when the Task API removal is old enough to be enforced by
public API compatibility checks.

The suite verifies:
- Task class does not exist in primitives.py.
- WorkflowState has no current_task field.
- parse_task_yaml() does not exist in runsight_core.yaml.parser.
- TaskDef and RunsightTaskFile do not exist in runsight_core.yaml.schema.
- execute_task() and _build_prompt() do not exist on RunsightTeamRunner.
- runsight_core.__init__ does not export Task.
- runner.py source has no Task import.
- state.py source has no current_task.
"""

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SRC = Path(__file__).parents[1] / "src" / "runsight_core"


def _source(rel: str) -> str:
    return (_SRC / rel).read_text()


def _ast_names(rel: str) -> set[str]:
    """Return all top-level and nested class/function names defined in a file."""
    tree = ast.parse(_source(rel))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def _ast_imported_names(rel: str) -> set[str]:
    """Return all names brought in via import statements in a file."""
    tree = ast.parse(_source(rel))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


# ---------------------------------------------------------------------------
# primitives.py does not define Task
# ---------------------------------------------------------------------------


class TestPrimitivesTaskDeleted:
    def test_task_class_not_defined_in_primitives_source(self):
        """AST check: 'class Task' must not appear in primitives.py."""
        defined = _ast_names("primitives.py")
        assert "Task" not in defined, (
            "primitives.py still defines a 'Task' class. "
            "The task API boundary requires it to be deleted."
        )

    def test_task_not_importable_from_primitives_module(self):
        """Runtime check: importing Task from runsight_core.primitives must fail."""
        import runsight_core.primitives as prims

        assert not hasattr(prims, "Task"), (
            "runsight_core.primitives still exports 'Task'. "
            "The task API boundary requires it to be removed."
        )


# ---------------------------------------------------------------------------
# runsight_core.__init__ does not export Task
# ---------------------------------------------------------------------------


class TestInitTaskNotExported:
    def test_task_not_in_dunder_all(self):
        """runsight_core.__all__ must not contain 'Task'."""
        import runsight_core

        all_exports = getattr(runsight_core, "__all__", [])
        assert "Task" not in all_exports, (
            "runsight_core.__all__ still lists 'Task'. "
            "the task API boundary requires it to be removed from __all__."
        )

    def test_task_not_importable_from_runsight_core(self):
        """Runtime check: Task must not be accessible from the top-level package."""
        import runsight_core

        assert not hasattr(runsight_core, "Task"), (
            "runsight_core still exposes 'Task' at package level. "
            "the task API boundary requires this export to be removed."
        )


# ---------------------------------------------------------------------------
# state.py has no WorkflowState.current_task field
# ---------------------------------------------------------------------------


class TestWorkflowStateNoCurrentTask:
    def test_current_task_not_in_state_source(self):
        """AST/text check: 'current_task' must not appear in state.py."""
        source = _source("state.py")
        assert "current_task" not in source, (
            "state.py still references 'current_task'. "
            "the task API boundary requires this field to be removed from WorkflowState."
        )

    def test_current_task_not_on_workflow_state_model(self):
        """Runtime check: WorkflowState must have no 'current_task' field."""
        from runsight_core.state import WorkflowState

        fields = WorkflowState.model_fields if hasattr(WorkflowState, "model_fields") else {}
        assert "current_task" not in fields, (
            "WorkflowState still has a 'current_task' field. "
            "The task API boundary requires it to be deleted."
        )

    def test_task_not_imported_in_state_source(self):
        """AST check: state.py must not import 'Task' from primitives."""
        imported = _ast_imported_names("state.py")
        assert "Task" not in imported, (
            "state.py still imports 'Task'. "
            "The task API boundary requires this import to be removed."
        )


# ---------------------------------------------------------------------------
# yaml/parser.py does not expose parse_task_yaml
# ---------------------------------------------------------------------------


class TestParserNoParseTaskYaml:
    def test_parse_task_yaml_not_defined_in_parser_source(self):
        """AST check: 'parse_task_yaml' must not be defined in yaml/parser.py."""
        defined = _ast_names("yaml/parser.py")
        assert "parse_task_yaml" not in defined, (
            "yaml/parser.py still defines 'parse_task_yaml'. "
            "the task API boundary requires this function to be deleted."
        )

    def test_parse_task_yaml_not_importable_from_parser_module(self):
        """Runtime check: parse_task_yaml must not exist on the parser module."""
        from runsight_core.yaml import parser

        assert not hasattr(parser, "parse_task_yaml"), (
            "runsight_core.yaml.parser still exposes 'parse_task_yaml'. "
            "the task API boundary requires it to be removed."
        )


# ---------------------------------------------------------------------------
# yaml/schema.py does not define task file schemas
# ---------------------------------------------------------------------------


class TestSchemaTaskDefsDeleted:
    def test_taskdef_not_defined_in_schema_source(self):
        """AST check: 'TaskDef' must not appear in yaml/schema.py."""
        defined = _ast_names("yaml/schema.py")
        assert "TaskDef" not in defined, (
            "yaml/schema.py still defines 'TaskDef'. "
            "The task API boundary requires it to be deleted."
        )

    def test_runsight_task_file_not_defined_in_schema_source(self):
        """AST check: 'RunsightTaskFile' must not appear in yaml/schema.py."""
        defined = _ast_names("yaml/schema.py")
        assert "RunsightTaskFile" not in defined, (
            "yaml/schema.py still defines 'RunsightTaskFile'. "
            "The task API boundary requires it to be deleted."
        )

    def test_taskdef_not_importable_from_schema_module(self):
        """Runtime check: TaskDef must not exist on the schema module."""
        from runsight_core.yaml import schema

        assert not hasattr(schema, "TaskDef"), (
            "runsight_core.yaml.schema still exposes 'TaskDef'. "
            "The task API boundary requires it to be removed."
        )

    def test_runsight_task_file_not_importable_from_schema_module(self):
        """Runtime check: RunsightTaskFile must not exist on the schema module."""
        from runsight_core.yaml import schema

        assert not hasattr(schema, "RunsightTaskFile"), (
            "runsight_core.yaml.schema still exposes 'RunsightTaskFile'. "
            "the task API boundary requires it to be removed."
        )


# ---------------------------------------------------------------------------
# runner.py has no task oriented runner API
# ---------------------------------------------------------------------------


class TestRunnerTaskMethodsDeleted:
    def test_execute_task_not_defined_in_runner_source(self):
        """AST check: 'execute_task' must not be defined in runner.py."""
        defined = _ast_names("runner.py")
        assert "execute_task" not in defined, (
            "runner.py still defines 'execute_task'. "
            "The task API boundary requires this method to be deleted."
        )

    def test_build_prompt_not_defined_in_runner_source(self):
        """AST check: '_build_prompt' must not be defined in runner.py."""
        defined = _ast_names("runner.py")
        assert "_build_prompt" not in defined, (
            "runner.py still defines '_build_prompt'. "
            "The task API boundary requires this method to be deleted."
        )

    def test_task_not_imported_in_runner_source(self):
        """AST check: runner.py must not import 'Task'."""
        imported = _ast_imported_names("runner.py")
        assert "Task" not in imported, (
            "runner.py still imports 'Task'. "
            "The task API boundary requires this import to be removed."
        )

    def test_execute_task_not_on_runner_class(self):
        """Runtime check: RunsightTeamRunner must have no 'execute_task' method."""
        from runsight_core.runner import RunsightTeamRunner

        assert not hasattr(RunsightTeamRunner, "execute_task"), (
            "RunsightTeamRunner still has an 'execute_task' method. "
            "the task API boundary requires it to be deleted."
        )

    def test_build_prompt_not_on_runner_class(self):
        """Runtime check: RunsightTeamRunner must have no '_build_prompt' method."""
        from runsight_core.runner import RunsightTeamRunner

        assert not hasattr(RunsightTeamRunner, "_build_prompt"), (
            "RunsightTeamRunner still has a '_build_prompt' method. "
            "the task API boundary requires it to be deleted."
        )
