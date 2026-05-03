"""Shared YAML fixture builders for parser-focused tests."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Sequence

RESEARCHER_SOUL_DICT = {
    "id": "researcher",
    "kind": "soul",
    "name": "Senior Researcher",
    "role": "Senior Researcher",
    "system_prompt": "You research topics.",
}

REVIEWER_SOUL_DICT = {
    "id": "reviewer",
    "kind": "soul",
    "name": "Peer Reviewer",
    "role": "Peer Reviewer",
    "system_prompt": "You review topics.",
}


def soul_entry_yaml(
    soul_id: str,
    *,
    name: str | None = None,
    role: str | None = None,
    prompt: str = "Do things.",
    tools: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Build one indented soul mapping entry for an inline `souls:` block."""
    soul_name = name or role or soul_id
    soul_role = role or soul_name
    lines = [
        f"  {soul_id}:",
        f"    id: {soul_id}",
        "    kind: soul",
        f"    name: {soul_name}",
        f"    role: {soul_role}",
        f"    system_prompt: {prompt}",
    ]
    if tools is not None:
        lines.append("    tools:")
        lines.extend(f"      - {tool}" for tool in tools)
    return "\n".join(lines)


def souls_yaml(*entries: str) -> str:
    """Build a top-level inline `souls:` YAML section from soul entries."""
    return "souls:\n" + "\n".join(entry.rstrip("\n") for entry in entries)


def researcher_soul_yaml() -> str:
    """Build the canonical single-researcher souls YAML section."""
    return souls_yaml(
        soul_entry_yaml(
            "researcher",
            name="Senior Researcher",
            role="Senior Researcher",
            prompt="You research topics.",
        )
    )


def researcher_reviewer_souls_yaml() -> str:
    """Build the canonical researcher/reviewer souls YAML section."""
    return souls_yaml(
        soul_entry_yaml(
            "researcher",
            name="Senior Researcher",
            role="Senior Researcher",
            prompt="You research topics.",
        ),
        soul_entry_yaml(
            "reviewer",
            name="Peer Reviewer",
            role="Peer Reviewer",
            prompt="You review topics.",
        ),
    )


def tools_yaml(*tool_ids: str) -> str:
    """Build a top-level workflow `tools:` list."""
    if not tool_ids:
        return "tools: []"
    return "tools:\n" + "\n".join(f"  - {tool_id}" for tool_id in tool_ids)


def workflow_yaml(
    *,
    workflow_id: str,
    workflow_name: str | None = None,
    blocks: str = "",
    entry: str,
    transitions: str = "",
    tools: str = "",
    souls: str = "",
    config: str = "",
) -> str:
    """Build a complete workflow YAML string from already-indented sections."""
    sections = [
        f"id: {workflow_id}",
        "kind: workflow",
        'version: "1.0"',
    ]
    for section in (config, tools, souls):
        if section:
            sections.append(section.rstrip("\n"))

    sections.append(f"blocks:\n{blocks.rstrip()}")

    workflow_lines = [
        "workflow:",
        f"  name: {workflow_name or workflow_id}",
        f"  entry: {entry}",
    ]
    if transitions:
        workflow_lines.append(f"  transitions:\n{transitions.rstrip()}")
    sections.append("\n".join(workflow_lines))
    return "\n".join(sections) + "\n"


def tool_validation_workflow_yaml(
    *,
    tools: str = "",
    souls: str = "",
    blocks: str = "",
    transitions: str = "",
    entry: str = "tool_validation_block",
) -> str:
    """Build the canonical workflow shell used by tool-validation parser tests."""
    return workflow_yaml(
        workflow_id="tool-validation-workflow",
        workflow_name="tool_validation",
        config="""\
config:
  model_name: gpt-4o""",
        tools=tools,
        souls=souls,
        blocks=blocks,
        entry=entry,
        transitions=transitions,
    )


def linear_block_yaml(
    block_id: str,
    *,
    soul_ref: str,
    exits: Sequence[tuple[str, str]] | None = None,
) -> str:
    """Build one indented linear block entry for parser workflow fixtures."""
    lines = [
        f"  {block_id}:",
        "    type: linear",
        f"    soul_ref: {soul_ref}",
    ]
    if exits is not None:
        lines.append("    exits:")
        for exit_id, label in exits:
            lines.extend(
                [
                    f"      - id: {exit_id}",
                    f"        label: {label}",
                ]
            )
    return "\n".join(lines)


def transitions_yaml(*edges: tuple[str, str | None]) -> str:
    """Build workflow transition entries for parser fixtures."""
    return "\n".join(
        [
            f"    - from: {source}",
            f"      to: {target if target is not None else 'null'}",
        ][line_index]
        for source, target in edges
        for line_index in range(2)
    )


def tool_validation_soul_workflow_yaml(
    *,
    tool_ids: Sequence[str] | None = None,
    soul_id: str = "tool_enabled_agent",
    soul_name: str = "Agent",
    soul_role: str = "Agent",
    soul_prompt: str = "Do things.",
    soul_tools: Sequence[str] | None = None,
    block_id: str = "tool_validation_block",
    exits: Sequence[tuple[str, str]] | None = None,
    entry: str | None = None,
) -> str:
    """Build the common one-soul workflow used by parser tool validation tests."""
    tools_section = "" if tool_ids is None else tools_yaml(*tool_ids)
    return tool_validation_workflow_yaml(
        tools=tools_section,
        souls=souls_yaml(
            soul_entry_yaml(
                soul_id,
                name=soul_name,
                role=soul_role,
                prompt=soul_prompt,
                tools=list(soul_tools) if soul_tools is not None else None,
            )
        ),
        blocks=linear_block_yaml(block_id, soul_ref=soul_id, exits=exits),
        entry=entry or block_id,
        transitions=transitions_yaml((block_id, None)),
    )


def tool_validation_two_soul_workflow_yaml(
    *,
    tool_ids: Sequence[str],
    first_soul_id: str,
    first_soul_tools: Sequence[str] | None,
    second_soul_id: str,
    second_soul_tools: Sequence[str] | None,
) -> str:
    """Build a two-block workflow where each block uses a different soul."""
    return tool_validation_workflow_yaml(
        tools=tools_yaml(*tool_ids),
        souls=souls_yaml(
            soul_entry_yaml(
                first_soul_id,
                name=first_soul_id,
                role=first_soul_id,
                prompt="Use tools.",
                tools=list(first_soul_tools) if first_soul_tools is not None else None,
            ),
            soul_entry_yaml(
                second_soul_id,
                name=second_soul_id,
                role=second_soul_id,
                prompt="No tools.",
                tools=list(second_soul_tools) if second_soul_tools is not None else None,
            ),
        ),
        blocks="\n".join(
            [
                linear_block_yaml("block_a", soul_ref=first_soul_id),
                linear_block_yaml("block_b", soul_ref=second_soul_id),
            ]
        ),
        entry="block_a",
        transitions=transitions_yaml(("block_a", "block_b"), ("block_b", None)),
    )


def workflow_with_raw_tools_section_yaml(
    tools_section: str,
    *,
    soul_id: str = "tool_enabled_agent",
    soul_tools: Sequence[str] = ("http",),
) -> str:
    """Build a workflow that preserves an intentionally invalid raw tools section."""
    return tool_validation_workflow_yaml(
        tools=dedent(tools_section).strip(),
        souls=souls_yaml(
            soul_entry_yaml(
                soul_id,
                name="Agent",
                role="Agent",
                prompt="Do things.",
                tools=list(soul_tools),
            )
        ),
        blocks=linear_block_yaml("tool_validation_block", soul_ref=soul_id),
        transitions=transitions_yaml(("tool_validation_block", None)),
    )


def shadow_builtin_tool_yaml() -> str:
    """Build custom metadata that illegally collides with a reserved builtin ID."""
    return """
    version: "1.0"
    type: custom
    executor: python
    name: Shadow HTTP
    description: Shadows the builtin http tool id.
    parameters:
      type: object
    code: |
      def main(args):
          return {"shadowed": True}
    """


def blocked_import_tool_yaml() -> str:
    """Build Python custom tool metadata with a blocked import."""
    return """
    version: "1.0"
    type: custom
    executor: python
    name: Blocked Import Tool
    description: Imports a blocked module.
    parameters:
      type: object
    code: |
      import os

      def main(args):
          return {}
    """


def missing_main_tool_yaml() -> str:
    """Build Python custom tool metadata without the required entrypoint."""
    return """
    version: "1.0"
    type: custom
    executor: python
    name: Missing Main Tool
    description: Omits the required main(args) entrypoint.
    parameters:
      type: object
    code: |
      def helper(args):
          return {}
    """


def corrupt_python_tool_yaml(*, name: str = "Bad Tool") -> str:
    """Build syntactically corrupt Python custom tool metadata."""
    return f"""
    version: "1.0"
    type: custom
    executor: python
    name: {name}
    description: Corrupt metadata should warn and skip.
    parameters:
      type: object
    code: |
      def main(args):
          return {{"broken":
    """


def valid_python_tool_yaml(*, name: str = "Good Tool") -> str:
    """Build valid Python custom tool metadata."""
    return f"""
    version: "1.0"
    type: custom
    executor: python
    name: {name}
    description: Valid metadata should resolve.
    parameters:
      type: object
    code: |
      def main(args):
          return {{"ok": True}}
    """


def request_tool_yaml() -> str:
    """Build valid request-executor custom tool metadata."""
    return """
    version: "1.0"
    type: custom
    executor: request
    name: Fetch Answer
    description: Fetches an answer by item id.
    parameters:
      type: object
      properties:
        item_id:
          type: integer
      required:
        - item_id
    request:
      method: GET
      url: https://tool-catalog.test/items/{{ item_id }}
      headers:
        X-Test: runsight
      response_path: data.answer
    timeout_seconds: 9
    """


def invalid_custom_tool_metadata_yaml(case: str) -> str:
    """Build custom tool metadata for file-specific parser error cases."""
    cases = {
        "legacy_http": """
            version: "1.0"
            type: http
            """,
        "missing_request_url": """
            version: "1.0"
            type: custom
            executor: request
            name: Missing Request URL
            description: Missing nested request.url.
            parameters:
              type: object
            request:
              method: GET
            """,
        "python_with_request": """
            version: "1.0"
            type: custom
            executor: python
            name: Python With Request
            description: Python executors must reject request metadata.
            parameters:
              type: object
            request:
              method: GET
              url: https://tool-catalog.test/items/{{ item_id }}
            code: |
              def main(args):
                  return args
            """,
    }
    return cases[case]


def write_workflow_file(
    base_dir: Path,
    yaml_content: str,
    name: str = "workflow.yaml",
    *,
    default_id: str | None = None,
    default_kind: str | None = None,
) -> str:
    """Write workflow YAML to a package-owned temp fixture file."""
    workflow_file = base_dir / name
    content = dedent(yaml_content)
    lines = content.lstrip().splitlines()
    top_level_keys = {
        line.split(":", 1)[0].strip()
        for line in lines
        if line and not line.startswith((" ", "\t")) and ":" in line
    }

    prefix = ""
    if default_id is not None and "id" not in top_level_keys:
        prefix += f"id: {default_id}\n"
    if default_kind is not None and "kind" not in top_level_keys:
        prefix += f"kind: {default_kind}\n"

    workflow_file.write_text(prefix + content, encoding="utf-8")
    return str(workflow_file)


def write_custom_soul_file(
    base_dir: Path,
    name: str,
    *,
    role: str,
    prompt: str,
    soul_id: str | None = None,
    display_name: str | None = None,
    model_name: str | None = None,
    provider: str | None = None,
) -> None:
    """Create an isolated custom/souls fixture file."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    extra_lines = []
    if model_name is not None:
        extra_lines.append(f"model_name: {model_name}")
    if provider is not None:
        extra_lines.append(f"provider: {provider}")
    extra = "\n".join(extra_lines)
    if extra:
        extra = "\n" + extra

    (souls_dir / f"{name}.yaml").write_text(
        dedent(
            f"""\
            id: {soul_id or name}
            kind: soul
            name: {display_name or role}
            role: {role}
            system_prompt: {prompt}{extra}
            """
        ),
        encoding="utf-8",
    )


def write_custom_tool_file(base_dir: Path, slug: str, contents: str) -> None:
    """Create a custom tool metadata file under custom/tools for parser tests."""
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    content = dedent(contents)
    lines = content.lstrip().splitlines()
    first_key = lines[0].split(":")[0].strip() if lines else ""
    if first_key != "id":
        content = f"id: {slug}\nkind: tool\n" + content
    (tools_dir / f"{slug}.yaml").write_text(content, encoding="utf-8")


class SnapshotGitService:
    """Read YAML fixtures from a temp directory through the parser snapshot API."""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir

    def list_files(self, ref: str, path_prefix: str) -> list[str]:
        del ref
        root = self._base_dir / path_prefix.rstrip("/")
        if not root.exists():
            return []
        return sorted(
            path.relative_to(self._base_dir).as_posix()
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".yaml", ".yml"}
        )

    def read_file(self, path: str, ref: str) -> str:
        del ref
        return (self._base_dir / path).read_text(encoding="utf-8")
