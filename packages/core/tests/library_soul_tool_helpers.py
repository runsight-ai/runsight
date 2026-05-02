"""Isolated workflow fixtures for library soul tool governance tests."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    workflow_file = base_dir / "workflow.yaml"
    content = dedent(yaml_content)
    lines = content.lstrip().splitlines()
    first_key = lines[0].split(":")[0].strip() if lines else ""
    if first_key != "id":
        content = "id: test-workflow\nkind: workflow\n" + content
    workflow_file.write_text(content, encoding="utf-8")
    return str(workflow_file)


def write_soul_file(
    base_dir: Path,
    name: str,
    *,
    role: str,
    prompt: str,
    tools: list[str] | None = None,
) -> None:
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"id: {name}",
        "kind: soul",
        f"name: {role}",
        f"role: {role}",
        f"system_prompt: {prompt}",
    ]
    if tools is not None:
        lines.append(f"tools: [{', '.join(tools)}]")
    (souls_dir / f"{name}.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def linear_workflow_yaml(*, soul_ref: str, tools_section: str = "") -> str:
    return f"""\
    version: "1.0"
    config:
      model_name: gpt-4o
    {tools_section}
    blocks:
      step:
        type: linear
        soul_ref: {soul_ref}
    workflow:
      name: library_soul_tool_test
      entry: step
      transitions:
        - from: step
          to: null
    """
