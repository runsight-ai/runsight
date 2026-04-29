"""Shared helpers for tool integration test suites."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml


def _text_response(
    content: str = "Done.",
    cost_usd: float = 0.001,
    total_tokens: int = 10,
) -> Dict[str, Any]:
    return {
        "content": content,
        "cost_usd": cost_usd,
        "prompt_tokens": 5,
        "completion_tokens": 5,
        "total_tokens": total_tokens,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


def _tool_call_response(
    tool_name: str,
    arguments: str = "{}",
    call_id: str = "call_001",
    cost_usd: float = 0.002,
    total_tokens: int = 20,
) -> Dict[str, Any]:
    tc = {
        "id": call_id,
        "type": "function",
        "function": {"name": tool_name, "arguments": arguments},
    }
    return {
        "content": "",
        "cost_usd": cost_usd,
        "prompt_tokens": 10,
        "completion_tokens": 10,
        "total_tokens": total_tokens,
        "tool_calls": [tc],
        "finish_reason": "tool_calls",
        "raw_message": {"role": "assistant", "content": "", "tool_calls": [tc]},
    }


# ---------------------------------------------------------------------------
# Minimal YAML dict builder (avoids file-on-disk requirement)
# ---------------------------------------------------------------------------


def _workflow_dict(
    *,
    tools: List[str] | None = None,
    souls: Dict[str, Any] | None = None,
    blocks: Dict[str, Any] | None = None,
    transitions: List[Dict[str, Any]] | None = None,
    entry: str = "step",
    model_name: str = "gpt-4o",
) -> Dict[str, Any]:
    """Build a minimal workflow raw-dict for parse_workflow_yaml()."""
    d: Dict[str, Any] = {
        "version": "1.0",
        "id": "integration_test_workflow",
        "kind": "workflow",
        "config": {"model_name": model_name},
        "workflow": {
            "name": "integration_test_workflow",
            "entry": entry,
            "transitions": transitions or [{"from": entry, "to": None}],
        },
    }
    if tools:
        d["tools"] = tools
    if souls:
        # Inject identity fields into each soul dict if missing
        patched_souls: Dict[str, Any] = {}
        for key, soul_data in souls.items():
            soul_copy = dict(soul_data)
            if "kind" not in soul_copy:
                soul_copy["kind"] = "soul"
            if "name" not in soul_copy:
                soul_copy["name"] = soul_copy.get("role", key)
            patched_souls[key] = soul_copy
        d["souls"] = patched_souls
    if blocks:
        d["blocks"] = blocks
    return d


# ---------------------------------------------------------------------------
# File helpers for checkout-local custom tool workflows
# ---------------------------------------------------------------------------


def _write_custom_tool_yaml(tmp_path: Path, slug: str, yaml_body: str) -> None:
    tools_dir = tmp_path / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / f"{slug}.yaml").write_text(yaml_body, encoding="utf-8")


def _write_workflow_file(tmp_path: Path, yaml_body: str) -> Path:
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(yaml_body, encoding="utf-8")
    return workflow_path


def _write_workflow_dict_file(tmp_path: Path, workflow_data: Dict[str, Any]) -> Path:
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(yaml.safe_dump(workflow_data, sort_keys=False), encoding="utf-8")
    return workflow_path


# ---------------------------------------------------------------------------
# Safe custom tool fixtures used by integration scenarios
# ---------------------------------------------------------------------------

_ECHO_TOOL_ID = "echo_tool"


def _write_echo_tool_yaml(tmp_path: Path, slug: str = _ECHO_TOOL_ID) -> str:
    _write_custom_tool_yaml(
        tmp_path,
        slug,
        f"""\
version: "1.0"
id: {slug}
kind: tool
type: custom
executor: python
name: Echo Tool
description: Echo values back to the caller.
parameters:
  type: object
  properties:
    message:
      type: string
  required:
    - message
code: |
  def main(args):
      return {{"echo": args}}
""",
    )
    return slug


def _write_raising_tool_yaml(
    tmp_path: Path,
    slug: str,
    *,
    error_type: str,
    message: str,
) -> str:
    _write_custom_tool_yaml(
        tmp_path,
        slug,
        f"""\
version: "1.0"
id: {slug}
kind: tool
type: custom
executor: python
name: {slug.replace("_", " ").title()}
description: Raises an error for integration coverage.
parameters:
  type: object
code: |
  def main(args):
      raise {error_type}({message!r})
""",
    )
    return slug
