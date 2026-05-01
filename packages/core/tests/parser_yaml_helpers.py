"""Shared YAML fixture builders for parser-focused tests."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

RESEARCHER_SOUL_YAML = """\
souls:
  researcher:
    id: researcher
    kind: soul
    name: Senior Researcher
    role: Senior Researcher
    system_prompt: You research topics.
"""

RESEARCHER_REVIEWER_SOULS_YAML = """\
souls:
  researcher:
    id: researcher
    kind: soul
    name: Senior Researcher
    role: Senior Researcher
    system_prompt: You research topics.
  reviewer:
    id: reviewer
    kind: soul
    name: Peer Reviewer
    role: Peer Reviewer
    system_prompt: You review topics.
"""

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
