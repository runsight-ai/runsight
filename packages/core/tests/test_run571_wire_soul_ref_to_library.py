"""
Failing tests for RUN-571: Wire ``soul_ref`` to library discovery.

After implementation:
1. ``parse_workflow_yaml()`` calls ``_discover_souls(custom/souls/)`` to build souls_map
2. ``soul_ref`` in linear, gate, synthesize, and fanout blocks resolves against library souls
3. Missing soul produces error with available souls listed and guidance to create the file
4. Discovery is called once per parse (not per block)
5. Existing block builder signatures unchanged (``_resolve_soul(ref, souls_map)``)

All tests should FAIL until the parser wires library discovery.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Helpers: write workflow YAML + soul YAML files to a temp directory
# ---------------------------------------------------------------------------


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    """Write workflow YAML to a file so parse_workflow_yaml infers workflow_base_dir."""
    workflow_file = base_dir / "workflow.yaml"
    workflow_file.write_text(dedent(yaml_content), encoding="utf-8")
    return str(workflow_file)


def _write_soul_file(base_dir: Path, name: str, *, soul_id: str, role: str, prompt: str) -> None:
    """Create a soul YAML file at custom/souls/<name>.yaml."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(
        dedent(f"""\
        id: {soul_id}
        role: {role}
        system_prompt: {prompt}
        """),
        encoding="utf-8",
    )


# ===========================================================================
# AC1: soul_ref in linear, gate, synthesize, and fanout blocks resolves
#      against custom/souls/
# ===========================================================================


class TestSoulRefResolvesFromLibrary:
    """soul_ref must resolve against custom/souls/ for all block types."""

    def test_linear_block_resolves_soul_ref_from_library(self):
        """A linear block's soul_ref should resolve to a soul in custom/souls/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base, "researcher", soul_id="r1", role="Researcher", prompt="You research."
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: researcher
                workflow:
                  name: linear_library_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            # The block should have resolved the soul from library
            block = wf.blocks["step"]
            # Unwrap IsolatedBlockWrapper if present
            inner = getattr(block, "inner_block", block)
            assert inner.soul.role == "Researcher"
            assert inner.soul.id == "r1"

    def test_gate_block_resolves_soul_ref_from_library(self):
        """A gate block's soul_ref should resolve to a soul in custom/souls/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base, "evaluator", soul_id="e1", role="Evaluator", prompt="You evaluate."
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  check:
                    type: gate
                    soul_ref: evaluator
                    eval_key: quality
                workflow:
                  name: gate_library_test
                  entry: check
                  transitions:
                    - from: check
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["check"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.role == "Evaluator"
            assert inner.soul.id == "e1"

    def test_synthesize_block_resolves_soul_ref_from_library(self):
        """A synthesize block's soul_ref should resolve to a soul in custom/souls/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(
                base, "summarizer", soul_id="s1", role="Summarizer", prompt="You summarize."
            )
            _write_soul_file(base, "worker", soul_id="w1", role="Worker", prompt="You work.")
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  work:
                    type: linear
                    soul_ref: worker
                  merge:
                    type: synthesize
                    soul_ref: summarizer
                    input_block_ids:
                      - work
                workflow:
                  name: synth_library_test
                  entry: work
                  transitions:
                    - from: work
                      to: merge
                    - from: merge
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            # Synthesize block may be wrapped in a Step (due to inputs) or IsolatedBlockWrapper
            block = wf.blocks["merge"]
            inner = getattr(block, "inner_block", block)
            inner = getattr(inner, "block", inner)  # Step wraps .block
            assert inner.soul.role == "Summarizer"
            assert inner.soul.id == "s1"

    def test_fanout_exit_soul_ref_resolves_from_library(self):
        """A fanout block's per-exit soul_ref should resolve to souls in custom/souls/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(base, "agent_a", soul_id="a1", role="Agent A", prompt="You are A.")
            _write_soul_file(base, "agent_b", soul_id="b1", role="Agent B", prompt="You are B.")
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  fan:
                    type: fanout
                    exits:
                      - id: branch_a
                        label: Branch A
                        soul_ref: agent_a
                        task: Do task A
                      - id: branch_b
                        label: Branch B
                        soul_ref: agent_b
                        task: Do task B
                workflow:
                  name: fanout_library_test
                  entry: fan
                  transitions:
                    - from: fan
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["fan"]
            inner = getattr(block, "inner_block", block)
            assert inner.branches[0].soul.role == "Agent A"
            assert inner.branches[1].soul.role == "Agent B"


# ===========================================================================
# AC2: Resolution is by filename stem
# ===========================================================================


class TestResolutionByFilenameStem:
    """soul_ref must match the YAML filename stem, not the soul's internal id."""

    def test_soul_ref_matches_filename_stem_not_internal_id(self):
        """soul_ref 'web_researcher' -> custom/souls/web_researcher.yaml, regardless of internal id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            souls_dir = base / "custom" / "souls"
            souls_dir.mkdir(parents=True, exist_ok=True)
            # Filename stem is "web_researcher" but internal id is "wr_v2"
            (souls_dir / "web_researcher.yaml").write_text(
                dedent("""\
                id: wr_v2
                role: Web Researcher
                system_prompt: You research the web.
                """),
                encoding="utf-8",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: web_researcher
                workflow:
                  name: stem_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.id == "wr_v2"
            assert inner.soul.role == "Web Researcher"

    def test_yml_extension_not_discovered(self):
        """Only .yaml files are discovered; .yml files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            souls_dir = base / "custom" / "souls"
            souls_dir.mkdir(parents=True, exist_ok=True)
            # Write a .yaml soul that IS discoverable
            _write_soul_file(base, "visible", soul_id="v1", role="Visible", prompt="I am visible.")
            # Write with .yml extension — should NOT be discovered
            (souls_dir / "hidden_soul.yml").write_text(
                dedent("""\
                id: hidden_1
                role: Hidden
                system_prompt: You are hidden.
                """),
                encoding="utf-8",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: hidden_soul
                workflow:
                  name: yml_ext_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            # hidden_soul.yml is NOT discovered; error should list 'visible' but not 'hidden_soul'
            with pytest.raises(ValueError, match="hidden_soul") as exc_info:
                parse_workflow_yaml(path)
            error_msg = str(exc_info.value)
            assert "visible" in error_msg


# ===========================================================================
# AC3: Missing soul produces error with available souls and guidance
# ===========================================================================


class TestMissingSoulErrorMessage:
    """Missing soul_ref must produce an actionable error with guidance."""

    def test_missing_soul_lists_available_souls(self):
        """Error must list the available souls from custom/souls/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(base, "alpha", soul_id="a1", role="Alpha", prompt="A.")
            _write_soul_file(base, "beta", soul_id="b1", role="Beta", prompt="B.")
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: gamma
                workflow:
                  name: missing_soul_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            with pytest.raises(ValueError, match="alpha") as exc_info:
                parse_workflow_yaml(path)
            error_msg = str(exc_info.value)
            assert "beta" in error_msg

    def test_missing_soul_mentions_custom_souls_directory(self):
        """Error must mention custom/souls/ as the directory to create soul files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(base, "existing", soul_id="e1", role="Existing", prompt="I exist.")
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: nonexistent
                workflow:
                  name: guidance_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            with pytest.raises(ValueError, match=r"custom/souls/"):
                parse_workflow_yaml(path)

    def test_missing_soul_suggests_creating_the_file(self):
        """Error must suggest creating the missing soul YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: my_agent
                workflow:
                  name: suggest_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            # Error should mention creating the file, e.g. "custom/souls/my_agent.yaml"
            with pytest.raises(ValueError, match=r"custom/souls/"):
                parse_workflow_yaml(path)

    def test_no_custom_souls_dir_gives_clear_error(self):
        """When custom/souls/ doesn't exist, any soul_ref fails with clear error mentioning custom/souls/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Do NOT create custom/souls/ directory
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: phantom
                workflow:
                  name: no_dir_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            with pytest.raises(ValueError, match=r"custom/souls/"):
                parse_workflow_yaml(path)


# ===========================================================================
# AC4: Discovery is called once per parse (not per block)
# ===========================================================================


class TestDiscoveryCalledOnce:
    """_discover_souls must be called exactly once per parse_workflow_yaml call."""

    def test_discover_souls_called_once_for_multi_block_workflow(self):
        """Even with multiple blocks referencing different souls, discovery runs once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(base, "soul_a", soul_id="a1", role="A", prompt="A.")
            _write_soul_file(base, "soul_b", soul_id="b1", role="B", prompt="B.")
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  block_a:
                    type: linear
                    soul_ref: soul_a
                  block_b:
                    type: linear
                    soul_ref: soul_b
                workflow:
                  name: multi_block_test
                  entry: block_a
                  transitions:
                    - from: block_a
                      to: block_b
                    - from: block_b
                      to: null
                """,
            )
            from runsight_core.yaml import discovery as discovery_module

            original_discover = discovery_module._discover_souls
            with patch.object(
                discovery_module,
                "_discover_souls",
                wraps=original_discover,
            ) as mock_discover:
                parse_workflow_yaml(path)
                assert mock_discover.call_count == 1


# ===========================================================================
# AC5: Existing block builder signatures unchanged
# ===========================================================================


class TestBlockBuilderSignaturesUnchanged:
    """Block builders still accept (block_id, block_def, souls_map, runner, all_blocks)."""

    def test_resolve_soul_still_accepts_ref_and_souls_map(self):
        """_resolve_soul(ref, souls_map) signature must be unchanged."""
        from runsight_core.blocks._helpers import resolve_soul
        from runsight_core.primitives import Soul

        souls_map = {
            "test_soul": Soul(id="t1", role="Tester", system_prompt="You test."),
        }
        soul = resolve_soul("test_soul", souls_map)
        assert soul.id == "t1"

    def test_resolve_soul_raises_on_missing_ref(self):
        """_resolve_soul must still raise ValueError for missing ref."""
        from runsight_core.blocks._helpers import resolve_soul

        with pytest.raises(ValueError, match="unknown_soul"):
            resolve_soul("unknown_soul", {})


# ===========================================================================
# Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases for library discovery wiring."""

    def test_malformed_soul_yaml_raises_error(self):
        """A soul YAML with invalid content should raise an error at parse time.

        The error must come from the malformed soul file (ValidationError from
        Soul.model_validate), NOT from soul_ref resolution failure (which would
        mean discovery didn't even attempt to load the file).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            souls_dir = base / "custom" / "souls"
            souls_dir.mkdir(parents=True, exist_ok=True)
            # Also write a valid soul to prove discovery actually runs
            _write_soul_file(base, "good_soul", soul_id="g1", role="Good", prompt="I am good.")
            # Missing required field 'role'
            (souls_dir / "bad_soul.yaml").write_text(
                dedent("""\
                id: bad_1
                system_prompt: Missing role field.
                """),
                encoding="utf-8",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: good_soul
                workflow:
                  name: malformed_soul_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            # Should fail during discovery (loading bad_soul.yaml), not during resolution.
            # The error must mention 'role' (the missing field) to confirm it's from
            # Soul validation, NOT from "not found" resolution.
            from pydantic import ValidationError

            with pytest.raises((ValidationError, ValueError), match="role"):
                parse_workflow_yaml(path)

    def test_multiple_blocks_share_same_soul(self):
        """Two blocks referencing the same soul_ref should both resolve correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            _write_soul_file(base, "shared", soul_id="s1", role="Shared Agent", prompt="Shared.")
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  first:
                    type: linear
                    soul_ref: shared
                  second:
                    type: linear
                    soul_ref: shared
                workflow:
                  name: shared_soul_test
                  entry: first
                  transitions:
                    - from: first
                      to: second
                    - from: second
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block_first = wf.blocks["first"]
            block_second = wf.blocks["second"]
            inner_first = getattr(block_first, "inner_block", block_first)
            inner_second = getattr(block_second, "inner_block", block_second)
            assert inner_first.soul.role == "Shared Agent"
            assert inner_second.soul.role == "Shared Agent"

    def test_soul_file_with_extra_fields_still_loads(self):
        """Soul YAML with unknown extra keys should still load (Soul model allows extras)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            souls_dir = base / "custom" / "souls"
            souls_dir.mkdir(parents=True, exist_ok=True)
            (souls_dir / "flexible.yaml").write_text(
                dedent("""\
                id: flex_1
                role: Flexible Soul
                system_prompt: I am flexible.
                unknown_future_field: true
                """),
                encoding="utf-8",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: flexible
                workflow:
                  name: extra_fields_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.role == "Flexible Soul"

    def test_soul_with_model_and_provider_overrides(self):
        """Soul YAML with model_name and provider should preserve those fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            souls_dir = base / "custom" / "souls"
            souls_dir.mkdir(parents=True, exist_ok=True)
            (souls_dir / "custom_model.yaml").write_text(
                dedent("""\
                id: cm_1
                role: Custom Model Soul
                system_prompt: I use a custom model.
                model_name: claude-3-opus
                provider: anthropic
                temperature: 0.3
                """),
                encoding="utf-8",
            )
            path = _write_workflow_file(
                base,
                """\
                version: "1.0"
                config:
                  model_name: gpt-4o
                blocks:
                  step:
                    type: linear
                    soul_ref: custom_model
                workflow:
                  name: model_override_test
                  entry: step
                  transitions:
                    - from: step
                      to: null
                """,
            )
            wf = parse_workflow_yaml(path)
            block = wf.blocks["step"]
            inner = getattr(block, "inner_block", block)
            assert inner.soul.model_name == "claude-3-opus"
            assert inner.soul.provider == "anthropic"
            assert inner.soul.temperature == 0.3
