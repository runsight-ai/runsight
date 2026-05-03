from __future__ import annotations

from pathlib import Path


def write_soul_yaml(
    base_dir: Path,
    filename: str,
    *,
    soul_id: str,
    name: str,
    role: str,
    system_prompt: str,
    tools: list[str] | None = None,
) -> Path:
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    soul_file = souls_dir / filename
    soul_file.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"id: {soul_id}",
        "kind: soul",
        f"name: {name}",
        f"role: {role}",
        f"system_prompt: {system_prompt}",
    ]
    if tools:
        lines.append("tools:")
        lines.extend(f"  - {tool}" for tool in tools)

    soul_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return soul_file


def write_tool_yaml(
    base_dir: Path,
    filename: str,
    *,
    tool_id: str = "fixture_tool",
    type_: str = "custom",
    executor: str | None = None,
    name: str | None = None,
    description: str | None = None,
    parameters: list[str] | None = None,
    code: str | None = None,
    code_file: str | None = None,
    request: list[str] | None = None,
    extra_lines: list[str] | None = None,
    raw_content: str | None = None,
) -> Path:
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    tool_file = tools_dir / filename
    tool_file.parent.mkdir(parents=True, exist_ok=True)

    if raw_content is not None:
        tool_file.write_text(raw_content, encoding="utf-8")
        return tool_file

    lines = [
        'version: "1.0"',
        f"id: {tool_id}",
        "kind: tool",
        f"type: {type_}",
    ]
    if executor is not None:
        lines.append(f"executor: {executor}")
    if name is not None:
        lines.append(f"name: {name}")
    if description is not None:
        lines.append(f"description: {description}")
    if parameters is not None:
        lines.append("parameters:")
        lines.extend(f"  {line}" for line in parameters)
    if code is not None:
        lines.append("code: |")
        lines.extend(f"  {line}" if line else "" for line in code.splitlines())
    if code_file is not None:
        lines.append(f"code_file: {code_file}")
    if request is not None:
        lines.append("request:")
        lines.extend(f"  {line}" for line in request)
    if extra_lines is not None:
        lines.extend(extra_lines)

    tool_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tool_file
