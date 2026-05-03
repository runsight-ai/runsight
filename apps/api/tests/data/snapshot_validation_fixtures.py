"""Workflow graph fixture builders for snapshot validation tests."""

from __future__ import annotations

from textwrap import dedent

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository


def write_workflow(repo: WorkflowRepository, *, workflow_id: str, yaml_text: str) -> None:
    repo.workflows_dir.mkdir(parents=True, exist_ok=True)
    (repo.workflows_dir / f"{workflow_id}.yaml").write_text(
        with_identity(workflow_id, yaml_text),
        encoding="utf-8",
    )


def with_identity(workflow_id: str, yaml_text: str) -> str:
    """Return yaml_text with id and kind identity fields prepended."""
    return f"id: {workflow_id}\nkind: workflow\n" + dedent(yaml_text).strip() + "\n"


def terminal_workflow_yaml(
    name: str,
    *,
    inputs: str | None = None,
    config_max_depth: int | None = None,
) -> str:
    lines = ['version: "1.0"']
    if inputs:
        lines.append("inputs:")
        lines.extend(f"  {line}" for line in dedent(inputs).strip().splitlines())
    lines.extend(
        [
            "workflow:",
            f"  name: {name}",
            "  entry: finish",
            "  transitions: []",
        ]
    )
    if config_max_depth is not None:
        lines.extend(["config:", f"  max_workflow_depth: {config_max_depth}"])
    return "\n".join(lines) + "\n"


def workflow_call_yaml(
    *,
    name: str,
    block_name: str,
    workflow_ref: str,
    max_depth: int | None = None,
    inputs: str | None = None,
    outputs: str | None = None,
    config_max_depth: int | None = None,
) -> str:
    lines = [
        'version: "1.0"',
        "blocks:",
        f"  {block_name}:",
        "    type: workflow",
        f"    workflow_ref: {workflow_ref}",
    ]
    if max_depth is not None:
        lines.append(f"    max_depth: {max_depth}")
    if inputs:
        lines.append("    inputs:")
        lines.extend(f"      {line}" for line in dedent(inputs).strip().splitlines())
    if outputs:
        lines.append("    outputs:")
        lines.extend(f"      {line}" for line in dedent(outputs).strip().splitlines())
    lines.extend(
        [
            "workflow:",
            f"  name: {name}",
            f"  entry: {block_name}",
            "  transitions:",
            f"    - from: {block_name}",
            "      to: null",
        ]
    )
    if config_max_depth is not None:
        lines.extend(["config:", f"  max_workflow_depth: {config_max_depth}"])
    return "\n".join(lines) + "\n"
