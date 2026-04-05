"""Tests for RUN-468: parse_workflow_yaml forwards all SoulDef fields to Soul.

Verifies that library soul fields (provider, temperature, max_tokens, avatar_color)
are forwarded through to runtime Soul objects during parsing.
"""

import tempfile
from pathlib import Path
from textwrap import dedent

from runsight_core.yaml.parser import parse_workflow_yaml


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    """Write workflow YAML to a file so parse_workflow_yaml infers workflow_base_dir."""
    workflow_file = base_dir / "workflow.yaml"
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _write_soul_file(base_dir: Path, name: str, content: str) -> None:
    """Create a soul YAML file at custom/souls/<name>.yaml."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(dedent(content), encoding="utf-8")


class TestParserSoulFieldForwarding:
    def test_parse_workflow_yaml_forwards_extended_soul_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "researcher",
                """\
                id: researcher_1
                role: Researcher
                system_prompt: Investigate thoroughly.
                provider: openai
                temperature: 0.5
                max_tokens: 4096
                avatar_color: "#3399ff"
                """,
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                workflow:
                  name: parser-forwarding
                  entry: step1
                  transitions:
                    - from: step1
                      to: null
                blocks:
                  step1:
                    type: linear
                    soul_ref: researcher
                config:
                  model_name: gpt-4o
                """,
            )
            workflow = parse_workflow_yaml(path)
            soul = workflow.blocks["step1"].soul

            assert soul.provider == "openai"
            assert soul.temperature == 0.5
            assert soul.max_tokens == 4096
            assert soul.avatar_color == "#3399ff"

    def test_parse_workflow_yaml_keeps_new_fields_optional(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base,
                "reviewer",
                """\
                id: reviewer_1
                role: Reviewer
                system_prompt: Review carefully.
                """,
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                workflow:
                  name: parser-forwarding-minimal
                  entry: step1
                  transitions:
                    - from: step1
                      to: null
                blocks:
                  step1:
                    type: linear
                    soul_ref: reviewer
                config:
                  model_name: gpt-4o
                """,
            )
            workflow = parse_workflow_yaml(path)
            soul = workflow.blocks["step1"].soul

            assert soul.provider is None
            assert soul.temperature is None
            assert soul.max_tokens is None
            assert soul.avatar_color is None
