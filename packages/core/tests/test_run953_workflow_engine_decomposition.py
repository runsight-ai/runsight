"""Red tests for RUN-953: workflow-engine collaborator split.

Existing workflow-runtime tests already cover behavioral parity for nested
workflows, loops, retries, limits, and observer events. This file adds the
remaining architecture guardrails for RUN-953: the workflow module should act
as a thin state-machine facade over focused collaborators rather than keeping
every concern centralized in ``workflow.py``.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from runsight_core.workflow import Workflow, execute_block


def _count_non_blank_non_comment_lines(fn) -> int:
    source = inspect.getsource(fn)
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def _type_names(expr: ast.expr) -> list[str]:
    if isinstance(expr, ast.Name):
        return [expr.id]
    if isinstance(expr, ast.Attribute):
        return [expr.attr]
    if isinstance(expr, ast.Tuple):
        names: list[str] = []
        for item in expr.elts:
            names.extend(_type_names(item))
        return names
    return []


def _concrete_type_branches(fn) -> list[str]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    branch_types: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "isinstance":
            continue
        if len(node.args) < 2:
            continue

        for type_name in _type_names(node.args[1]):
            if type_name == "BaseBlock":
                continue
            if type_name.endswith("Block") or type_name in {"Step", "StepType"}:
                branch_types.add(type_name)

    return sorted(branch_types)


WORKFLOW_FACADE_THRESHOLDS = [
    ("validate", 30, "graph validation and transition integrity"),
    ("_detect_cycle", 30, "cycle detection / graph validation"),
    ("_resolve_next", 30, "next-step resolution and output-condition routing"),
    ("_handle_block_error", 25, "error-route handling"),
    ("_resolve_injected_steps", 18, "dynamic step injection"),
    ("_run_with_timeout", 15, "timeout wrapping"),
    ("_run_main_loop", 30, "main loop orchestration"),
    ("run", 30, "workflow lifecycle and budget wrapping"),
]


def test_workflow_methods_shrink_to_facade_sized_orchestrators():
    offenders: list[str] = []

    for method_name, max_lines, concern in WORKFLOW_FACADE_THRESHOLDS:
        method = getattr(Workflow, method_name)
        line_count = _count_non_blank_non_comment_lines(method)
        if line_count > max_lines:
            offenders.append(
                f"{method_name}={line_count} lines for {concern} (expected <= {max_lines})"
            )

    assert not offenders, (
        "RUN-953 keeps Workflow as the state-machine facade. These methods still own too much "
        "runtime logic and should delegate to focused collaborators:\n- " + "\n- ".join(offenders)
    )


def test_execute_block_is_materially_smaller_than_the_old_centralized_dispatcher():
    line_count = _count_non_blank_non_comment_lines(execute_block)

    assert line_count <= 80, (
        f"RUN-953 requires execute_block to shrink after collaborator extraction; got "
        f"{line_count} non-blank/non-comment lines, expected <= 80."
    )


def test_execute_block_no_longer_switches_on_multiple_concrete_execution_types():
    concrete_types = _concrete_type_branches(execute_block)

    assert len(concrete_types) <= 1, (
        "RUN-953 requires block-type-specific execution behavior to move behind focused "
        "collaborators. execute_block still branches on multiple concrete execution types: "
        f"{concrete_types}"
    )
