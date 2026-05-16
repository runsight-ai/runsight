"""Source governance for the PromptEnvelope isolation rename.

Owner: packages/core subprocess isolation boundary.
Boundary: isolation envelope source must expose PromptEnvelope naming and must
not retain TaskEnvelope/current_task compatibility shims.
Exit criteria: delete once public subprocess isolation behavior tests fail on
TaskEnvelope compatibility reintroduction.
"""

from __future__ import annotations

import ast

from prompt_envelope_helpers import ENVELOPE_PY, INIT_PY, WORKER_SUPPORT_PY, WRAPPER_PY


def _parse(path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_envelope_source_defines_prompt_envelope_not_task_envelope() -> None:
    tree = _parse(ENVELOPE_PY)
    class_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    assert "PromptEnvelope" in class_names
    assert "TaskEnvelope" not in class_names
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ContextEnvelope":
            task_fields = [
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
                and item.target.id == "task"
            ]
            assert task_fields == []


def test_worker_support_has_no_task_import_or_current_task_reference() -> None:
    tree = _parse(WORKER_SUPPORT_PY)
    source = WORKER_SUPPORT_PY.read_text(encoding="utf-8")

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert "Task" not in [alias.name for alias in node.names]
            assert "TaskEnvelope" not in [alias.name for alias in node.names]
        elif isinstance(node, ast.Import):
            assert "Task" not in [alias.name for alias in node.names]
    assert "current_task" not in source


def test_wrapper_uses_prompt_envelope_not_task_envelope() -> None:
    tree = _parse(WRAPPER_PY)
    imported_names = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]
    source = WRAPPER_PY.read_text(encoding="utf-8")

    assert "PromptEnvelope" in imported_names
    assert "TaskEnvelope" not in imported_names
    assert "TaskEnvelope" not in source
    assert "PromptEnvelope" in source


def test_isolation_init_exports_prompt_envelope_not_task_envelope() -> None:
    source = INIT_PY.read_text(encoding="utf-8")

    assert "PromptEnvelope" in source
    assert "TaskEnvelope" not in source
