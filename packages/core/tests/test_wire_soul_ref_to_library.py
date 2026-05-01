"""Library soul_ref discovery coverage for workflow parsing.

Behavior boundary: parse_workflow_yaml discovers isolated library souls,
resolves soul_ref on block definitions, reports actionable missing-soul errors,
runs discovery once per parse, and preserves the block-builder soul resolution
contract.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from parser_yaml_helpers import write_custom_soul_file, write_workflow_file
from runsight_core.primitives import Soul
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Helpers: write workflow YAML + soul YAML files to a temp directory
# ---------------------------------------------------------------------------


def _write_workflow_file(base_dir: Path, yaml_content: str) -> str:
    """Write workflow YAML to a file so parse_workflow_yaml infers workflow_base_dir."""
    return write_workflow_file(
        base_dir,
        yaml_content,
        default_id="library-soul-fixture-workflow",
        default_kind="workflow",
    )


def _write_soul_file(
    base_dir: Path,
    name: str,
    *,
    role: str,
    prompt: str,
    soul_id: str | None = None,
    display_name: str | None = None,
    model_name: str | None = None,
    provider: str | None = None,
    temperature: float | None = None,
    unknown_future_field: bool | None = None,
    extension: str = "yaml",
) -> Path:
    """Create an isolated custom/souls fixture file."""
    write_custom_soul_file(
        base_dir,
        name,
        soul_id=soul_id or name,
        display_name=display_name,
        role=role,
        prompt=prompt,
    )
    soul_path = base_dir / "custom" / "souls" / f"{name}.yaml"
    extra_lines = []
    if model_name is not None:
        extra_lines.append(f"model_name: {model_name}")
    if provider is not None:
        extra_lines.append(f"provider: {provider}")
    if temperature is not None:
        extra_lines.append(f"temperature: {temperature}")
    if unknown_future_field is not None:
        extra_lines.append(f"unknown_future_field: {str(unknown_future_field).lower()}")
    if extra_lines:
        soul_path.write_text(
            soul_path.read_text(encoding="utf-8") + "\n".join(extra_lines) + "\n",
            encoding="utf-8",
        )
    if extension != "yaml":
        target_path = soul_path.with_suffix(f".{extension}")
        soul_path.replace(target_path)
        return target_path
    return soul_path


def _remove_soul_role_field(soul_path: Path, role: str) -> None:
    """Make a helper-built soul fixture invalid by removing the role field."""
    soul_path.write_text(
        soul_path.read_text(encoding="utf-8").replace(f"role: {role}\n", ""),
        encoding="utf-8",
    )


def _souls_map() -> dict[str, Soul]:
    return {
        "research_soul": Soul(
            id="research_soul",
            kind="soul",
            name="Research Agent",
            role="Research Agent",
            system_prompt="Research.",
        ),
        "review_soul": Soul(
            id="review_soul",
            kind="soul",
            name="Review Agent",
            role="Review Agent",
            system_prompt="Review.",
        ),
    }


# ===========================================================================
# soul_ref resolves against isolated custom/souls fixtures
# ===========================================================================


class TestSoulRefResolvesFromLibrary:
    """soul_ref resolves against isolated custom/souls fixtures for block types."""

    def test_linear_block_resolves_soul_ref_from_library(self, tmp_path: Path):
        """A linear block's soul_ref should resolve to an isolated library soul."""
        base = tmp_path
        _write_soul_file(base, "researcher", role="Researcher", prompt="You research.")
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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
        assert inner.soul.id == "researcher"

    def test_gate_block_resolves_soul_ref_from_library(self, tmp_path: Path):
        """A gate block's soul_ref should resolve to an isolated library soul."""
        base = tmp_path
        _write_soul_file(base, "evaluator", role="Evaluator", prompt="You evaluate.")
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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
        assert inner.soul.id == "evaluator"

    def test_synthesize_block_resolves_soul_ref_from_library(self, tmp_path: Path):
        """A synthesize block's soul_ref should resolve to an isolated library soul."""
        base = tmp_path
        _write_soul_file(base, "summarizer", role="Summarizer", prompt="You summarize.")
        _write_soul_file(base, "worker", role="Worker", prompt="You work.")
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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
        assert inner.soul.id == "summarizer"

    def test_dispatch_exit_soul_ref_resolves_from_library(self, tmp_path: Path):
        """A dispatch block's per-exit soul_ref should resolve to isolated library souls."""
        base = tmp_path
        _write_soul_file(base, "agent_a", role="Agent A", prompt="You are A.")
        _write_soul_file(base, "agent_b", role="Agent B", prompt="You are B.")
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
            blocks:
              fan:
                type: dispatch
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
              name: dispatch_library_test
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
# Resolution is by filename stem
# ===========================================================================


class TestResolutionByFilenameStem:
    """soul_ref must match the YAML filename stem, not the soul's internal id."""

    def test_soul_ref_matches_filename_stem_not_internal_id(self, tmp_path: Path):
        """soul_ref 'web_researcher' resolves by isolated fixture filename stem."""
        base = tmp_path
        _write_soul_file(
            base,
            "web_researcher",
            role="Web Researcher",
            prompt="You research the web.",
        )
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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
        assert inner.soul.id == "web_researcher"
        assert inner.soul.role == "Web Researcher"

    def test_yml_extension_not_discovered(self, tmp_path: Path):
        """Only .yaml files are discovered; .yml files are ignored."""
        base = tmp_path
        # Write a .yaml soul that is discoverable.
        _write_soul_file(base, "visible", role="Visible", prompt="I am visible.")
        # Write with .yml extension; it should not be discovered.
        _write_soul_file(
            base,
            "hidden_soul",
            soul_id="hidden-1",
            role="Hidden",
            prompt="You are hidden.",
            extension="yml",
        )
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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
        # hidden_soul.yml is not discovered; error should list only visible souls.
        with pytest.raises(ValueError, match="hidden_soul") as exc_info:
            parse_workflow_yaml(path)
        error_msg = str(exc_info.value)
        assert "visible" in error_msg


# ===========================================================================
# Missing soul errors include available souls and guidance
# ===========================================================================


class TestMissingSoulErrorMessage:
    """Missing soul_ref must produce an actionable error with guidance."""

    def test_missing_soul_lists_available_souls(self, tmp_path: Path):
        """Error must list the available souls from the isolated custom/souls fixture."""
        base = tmp_path
        _write_soul_file(base, "alpha", role="Alpha", prompt="A.")
        _write_soul_file(base, "beta", role="Beta", prompt="B.")
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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

    def test_missing_soul_mentions_custom_souls_directory(self, tmp_path: Path):
        """Error must mention custom/souls/ as the directory to create soul files."""
        base = tmp_path
        _write_soul_file(base, "existing", role="Existing", prompt="I exist.")
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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

    def test_missing_soul_suggests_creating_the_file(self, tmp_path: Path):
        """Error must suggest creating the missing soul YAML file."""
        base = tmp_path
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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

    def test_no_custom_souls_dir_gives_clear_error(self, tmp_path: Path):
        """When custom/souls does not exist, soul_ref fails with a clear error."""
        base = tmp_path
        # Do not create the isolated custom/souls fixture directory.
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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
# Discovery is called once per parse
# ===========================================================================


class TestDiscoveryCalledOnce:
    """Soul discovery must run exactly once per parse_workflow_yaml call."""

    def test_discover_souls_called_once_for_multi_block_workflow(self, tmp_path: Path):
        """Even with multiple blocks referencing different souls, discovery runs once."""
        base = tmp_path
        _write_soul_file(base, "research_soul", role="Research Agent", prompt="Research.")
        _write_soul_file(base, "review_soul", role="Review Agent", prompt="Review.")
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
            blocks:
              research_step:
                type: linear
                soul_ref: research_soul
              review_step:
                type: linear
                soul_ref: review_soul
            workflow:
              name: multi_block_test
              entry: research_step
              transitions:
                - from: research_step
                  to: review_step
                - from: review_step
                  to: null
            """,
        )
        with patch("runsight_core.yaml.parser.SoulScanner") as mock_scanner:
            mock_scanner.return_value.scan.return_value.ids.return_value = _souls_map()
            parse_workflow_yaml(path)
            mock_scanner.assert_called_once()
            mock_scanner.return_value.scan.assert_called_once()
            mock_scanner.return_value.scan.return_value.ids.assert_called_once()


# ===========================================================================
# Block builder soul-resolution contract remains unchanged
# ===========================================================================


class TestBlockBuilderSignaturesUnchanged:
    """Block builders still accept (block_id, block_def, souls_map, runner, all_blocks)."""

    def test_resolve_soul_still_accepts_ref_and_souls_map(self):
        """_resolve_soul(ref, souls_map) signature must be unchanged."""
        from runsight_core.blocks._helpers import resolve_soul
        from runsight_core.primitives import Soul

        souls_map = {
            "tester_soul": Soul(
                id="tester_soul",
                kind="soul",
                name="Tester",
                role="Tester",
                system_prompt="You test.",
            ),
        }
        soul = resolve_soul("tester_soul", souls_map)
        assert soul.id == "tester_soul"

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

    def test_malformed_soul_yaml_raises_error(self, tmp_path: Path):
        """A soul YAML with invalid content should raise an error at parse time.

        The error must come from the malformed soul file (ValidationError from
        Soul.model_validate), not from soul_ref resolution failure (which would
        mean discovery didn't even attempt to load the file).
        """
        base = tmp_path
        # Also write a valid soul to prove discovery actually runs
        _write_soul_file(base, "good_soul", role="Good", prompt="I am good.")
        bad_soul_path = _write_soul_file(
            base,
            "bad_soul",
            role="Bad Soul",
            prompt="Missing role field.",
        )
        _remove_soul_role_field(bad_soul_path, "Bad Soul")
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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
        # Soul validation, not "not found" resolution.
        from pydantic import ValidationError

        with pytest.raises((ValidationError, ValueError), match="role"):
            parse_workflow_yaml(path)

    def test_multiple_blocks_share_same_soul(self, tmp_path: Path):
        """Two blocks referencing the same soul_ref should both resolve correctly."""
        base = tmp_path
        _write_soul_file(base, "shared", role="Shared Agent", prompt="Shared.")
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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

    def test_soul_file_with_extra_fields_still_loads(self, tmp_path: Path):
        """Soul YAML with unknown extra keys should still load (Soul model allows extras)."""
        base = tmp_path
        _write_soul_file(
            base,
            "flexible",
            role="Flexible Soul",
            prompt="I am flexible.",
            unknown_future_field=True,
        )
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
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

    def test_soul_with_model_and_provider_overrides(self, tmp_path: Path):
        """Soul YAML with model_name and provider should preserve those fields."""
        base = tmp_path
        _write_soul_file(
            base,
            "model_override_soul",
            role="Custom Model Soul",
            prompt="I use a custom model.",
            model_name="fixture-model-override",
            provider="fixture-provider",
            temperature=0.3,
        )
        path = _write_workflow_file(
            base,
            """\
            version: "1.0"
            id: library_soul_resolution_workflow
            kind: workflow
            config:
              model_name: fixture-model
            blocks:
              step:
                type: linear
                soul_ref: model_override_soul
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
        assert inner.soul.model_name == "fixture-model-override"
        assert inner.soul.provider == "fixture-provider"
        assert inner.soul.temperature == 0.3
