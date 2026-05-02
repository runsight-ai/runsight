"""Fixture builders for custom tool validation tests."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent


def valid_tool_dict() -> dict:
    return {
        "version": "1.0",
        "id": "profile_lookup_tool",
        "kind": "tool",
        "type": "custom",
        "executor": "python",
        "name": "Profile Lookup",
        "description": "Returns profile data.",
        "parameters": {"type": "object"},
        "code": "def main(args):\n    return args\n",
    }


def valid_request_dict() -> dict:
    return {"method": "GET", "url": "http://127.0.0.1:18080/api"}


def write_tool_yaml(base_dir: Path, name: str, yaml_content: str) -> Path:
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True)
    tool_yaml = tools_dir / name
    tool_yaml.write_text(dedent(yaml_content).lstrip(), encoding="utf-8")
    return tool_yaml
