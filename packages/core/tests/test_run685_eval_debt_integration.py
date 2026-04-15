"""
RUN-685 — Epic-level integration tests: Eval Debt Cleanup & Wiring Fixes.

Verifies the full chain after six implementation tickets:
  1. Soul YAML files have no `assertions:` key (RUN-688)
  2. Parser has no duplicate `_resolve_soul()` (RUN-690)
  3. Stale `soul.assertions` refs replaced in tests (RUN-689)
  4. `SoulEntity` has no explicit `assertions` field (RUN-691)
  5. Inline-soul fixtures migrated to library soul refs (RUN-692)
  6. `Step` wrapper exposes `.assertions` from inner block (RUN-693 P0 fix)

User flows:
  UF-1: Block with inputs + assertions -> eval fires through Step wrapper
  UF-2: Soul YAML round-trip — no assertions key, clean SoulDef parse
  UF-3: Parser + library soul resolution with block assertions

Architectural invariants:
  AI-1: No soul-level assertions anywhere (Soul, SoulDef, SoulEntity)
  AI-2: Step delegates assertions to wrapped block
  AI-3: Parser bridge is idempotent — parsing same YAML twice yields same configs
"""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
import yaml
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul, Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_core.yaml.schema import SoulDef

# ---------------------------------------------------------------------------
# Repo root and paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CUSTOM_SOULS = _REPO_ROOT / "custom" / "souls"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubBlock(BaseBlock):
    """Minimal concrete block for integration tests."""

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={"results": {**state.results, self.block_id: BlockResult(output="ok")}}
        )


def _write_soul_file(base_dir: Path, name: str, content: str) -> None:
    """Create a soul YAML file at custom/souls/<name>.yaml."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(dedent(content), encoding="utf-8")


def _make_temp_workspace_with_souls(
    soul_specs: dict[str, dict[str, str]],
) -> tempfile.TemporaryDirectory:
    """Create a temp workspace with library soul files.

    Args:
        soul_specs: Mapping of soul_name -> {id, kind, name, role, system_prompt}.
    """
    tmpdir = tempfile.TemporaryDirectory()
    base = Path(tmpdir.name)
    for soul_name, fields in soul_specs.items():
        _write_soul_file(
            base,
            soul_name,
            f"""\
            id: {fields["id"]}
            kind: {fields["kind"]}
            name: {fields["name"]}
            role: {fields["role"]}
            system_prompt: {fields["system_prompt"]}
            """,
        )
    return tmpdir


# ---------------------------------------------------------------------------
# YAML fixtures
# ---------------------------------------------------------------------------

YAML_TWO_BLOCKS_WITH_INPUT_AND_ASSERTIONS = """\
version: "1.0"
id: input_assertion_flow
kind: workflow
config:
  model_name: gpt-4o
blocks:
  fetch:
    type: linear
    soul_ref: researcher
  analyze:
    type: linear
    soul_ref: analyst
    inputs:
      data:
        from: fetch.output
    assertions:
      - type: contains
        value: analysis
      - type: cost
        threshold: 0.05
workflow:
  name: input_assertion_flow
  entry: fetch
  transitions:
    - from: fetch
      to: analyze
    - from: analyze
      to: null
"""

YAML_MULTI_BLOCK_ASSERTIONS = """\
version: "1.0"
id: multi_block_assertions
kind: workflow
config:
  model_name: gpt-4o
blocks:
  research:
    type: linear
    soul_ref: researcher
    assertions:
      - type: contains
        value: findings
  summarize:
    type: linear
    soul_ref: analyst
    inputs:
      data:
        from: research.output
    assertions:
      - type: contains
        value: summary
  review:
    type: linear
    soul_ref: reviewer
    inputs:
      text:
        from: summarize.output
    assertions:
      - type: contains
        value: approved
      - type: cost
        threshold: 0.10
workflow:
  name: multi_block_assertions
  entry: research
  transitions:
    - from: research
      to: summarize
    - from: summarize
      to: review
    - from: review
      to: null
"""

YAML_SOUL_REF_WITH_ASSERTIONS = """\
version: "1.0"
id: soul_ref_assertions
kind: workflow
config:
  model_name: gpt-4o
blocks:
  analyze:
    type: linear
    soul_ref: researcher
    assertions:
      - type: contains
        value: result
workflow:
  name: soul_ref_assertions
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""

STANDARD_SOUL_SPECS = {
    "researcher": {
        "id": "researcher",
        "kind": "soul",
        "name": "Researcher",
        "role": "Researcher",
        "system_prompt": "You research.",
    },
    "analyst": {
        "id": "analyst",
        "kind": "soul",
        "name": "Analyst",
        "role": "Analyst",
        "system_prompt": "You analyze.",
    },
    "reviewer": {
        "id": "reviewer",
        "kind": "soul",
        "name": "Reviewer",
        "role": "Reviewer",
        "system_prompt": "You review.",
    },
}


def _parse_in_workspace(yaml_content: str, soul_specs: dict | None = None) -> Any:
    """Parse workflow YAML in a temporary workspace with library souls."""
    specs = soul_specs or STANDARD_SOUL_SPECS
    with _make_temp_workspace_with_souls(specs) as tmpdir:
        base = Path(tmpdir)
        wf_file = base / "workflow.yaml"
        wf_file.write_text(yaml_content, encoding="utf-8")
        return parse_workflow_yaml(str(wf_file))


# ===========================================================================
# UF-1: Block with inputs + assertions -> eval fires
# ===========================================================================


class TestUF1BlockInputsAssertionsEvalFires:
    """End-to-end: parse YAML with inputs + assertions, verify assertions
    survive Step wrapping, are visible to _build_assertion_configs, and
    the config dict is non-empty."""

    def test_assertions_survive_step_wrapping(self):
        """Assertions must be accessible on the Step-wrapped block after parsing."""
        wf = _parse_in_workspace(YAML_TWO_BLOCKS_WITH_INPUT_AND_ASSERTIONS)

        analyze_block = wf._blocks["analyze"]
        # The block has inputs, so it must be wrapped in a Step
        assert isinstance(analyze_block, Step), (
            f"Expected Step wrapper for block with inputs, got {type(analyze_block).__name__}"
        )
        # Assertions must be accessible through the Step wrapper
        assert analyze_block.assertions is not None
        assert len(analyze_block.assertions) == 2

    def test_assertion_config_fields_preserved(self):
        """Assertion config dict fields from YAML must survive Step wrapping."""
        wf = _parse_in_workspace(YAML_TWO_BLOCKS_WITH_INPUT_AND_ASSERTIONS)

        block = wf._blocks["analyze"]
        assert block.assertions[0]["type"] == "contains"
        assert block.assertions[0]["value"] == "analysis"
        assert block.assertions[1]["type"] == "cost"
        assert block.assertions[1]["threshold"] == 0.05

    def test_build_assertion_configs_returns_nonempty_for_step_wrapped(self):
        """_build_assertion_configs must find assertions through Step wrappers."""
        ExecutionService = pytest.importorskip(
            "runsight_api.logic.services.execution_service", reason="runsight_api not installed"
        ).ExecutionService

        wf = _parse_in_workspace(YAML_TWO_BLOCKS_WITH_INPUT_AND_ASSERTIONS)
        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is not None, (
            "_build_assertion_configs returned None — assertions lost in Step wrapping"
        )
        assert "analyze" in configs
        assert len(configs["analyze"]) == 2

    def test_multi_block_assertions_all_visible_to_build_configs(self):
        """When multiple blocks have assertions (some Step-wrapped, some not),
        _build_assertion_configs must see all of them."""
        ExecutionService = pytest.importorskip(
            "runsight_api.logic.services.execution_service", reason="runsight_api not installed"
        ).ExecutionService

        wf = _parse_in_workspace(YAML_MULTI_BLOCK_ASSERTIONS)
        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is not None
        # research: raw block with assertions (no inputs)
        assert "research" in configs
        assert len(configs["research"]) == 1
        # summarize: Step-wrapped (has inputs) with assertions
        assert "summarize" in configs
        assert len(configs["summarize"]) == 1
        # review: Step-wrapped (has inputs) with 2 assertions
        assert "review" in configs
        assert len(configs["review"]) == 2

    def test_getattr_pattern_on_step_matches_build_configs_usage(self):
        """The exact getattr pattern used by _build_assertion_configs must work
        on Step-wrapped blocks — this is the P0 bug regression test."""
        wf = _parse_in_workspace(YAML_TWO_BLOCKS_WITH_INPUT_AND_ASSERTIONS)

        for block_id, block in wf._blocks.items():
            block_assertions = getattr(block, "assertions", None)
            if block_id == "analyze":
                assert block_assertions is not None, (
                    f"getattr(block, 'assertions', None) returned None for "
                    f"Step-wrapped block '{block_id}'"
                )
            # For fetch: no assertions defined, so None is expected


# ===========================================================================
# UF-2: Soul YAML round-trip — no assertions, clean SoulDef parse
# ===========================================================================


class TestUF2SoulYamlRoundTrip:
    """Load real soul YAML files, verify no assertions key, and verify
    they parse through SoulDef schema cleanly."""

    def test_no_soul_file_contains_assertions_key(self):
        """Scan all soul YAML files: none should have a top-level assertions key."""
        assert _CUSTOM_SOULS.exists(), f"Directory not found: {_CUSTOM_SOULS}"
        soul_files = sorted(_CUSTOM_SOULS.glob("*.yaml"))
        assert len(soul_files) > 0, "No soul YAML files found"

        violations = []
        for soul_file in soul_files:
            try:
                data = yaml.safe_load(soul_file.read_text())
            except yaml.YAMLError:
                continue
            if isinstance(data, dict) and "assertions" in data:
                violations.append(soul_file.name)

        assert violations == [], (
            "Soul YAML files still contain stale `assertions` key:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_all_soul_files_parse_through_souldef(self):
        """Every soul YAML file must validate cleanly through the SoulDef schema.

        This verifies that removing assertions: null did not break parsing,
        and that SoulDef(extra='forbid') rejects any lingering unknown fields.
        """
        assert _CUSTOM_SOULS.exists()
        soul_files = sorted(_CUSTOM_SOULS.glob("*.yaml"))
        assert len(soul_files) > 0

        failures = []
        for soul_file in soul_files:
            try:
                data = yaml.safe_load(soul_file.read_text())
            except yaml.YAMLError:
                continue
            if not isinstance(data, dict):
                continue
            try:
                SoulDef.model_validate(data)
            except Exception as exc:
                failures.append(f"{soul_file.name}: {exc}")

        assert failures == [], "Soul YAML files failed SoulDef validation:\n" + "\n".join(
            f"  - {f}" for f in failures
        )

    def test_souldef_rejects_assertions_field(self):
        """SoulDef(extra='forbid') must reject a soul dict with assertions key."""
        from pydantic import ValidationError

        soul_data = {
            "id": "test_soul",
            "kind": "soul",
            "name": "Test",
            "role": "Test",
            "system_prompt": "Test prompt.",
            "assertions": [{"type": "contains", "value": "test"}],
        }
        try:
            SoulDef.model_validate(soul_data)
            raise AssertionError(
                "SoulDef accepted an assertions field — extra='forbid' should reject it"
            )
        except ValidationError:
            pass  # Expected: SoulDef rejects unknown fields


# ===========================================================================
# UF-3: Parser + library soul resolution with block assertions
# ===========================================================================


class TestUF3ParserLibrarySoulResolutionWithAssertions:
    """Parse a workflow using soul_ref: with block assertions. Verify the
    full chain: soul resolved from library, block built, assertions bridged,
    Step wrapping preserves assertions."""

    def test_soul_ref_resolves_from_library(self):
        """A workflow with soul_ref: <name> must resolve the soul from library files."""
        wf = _parse_in_workspace(YAML_SOUL_REF_WITH_ASSERTIONS)

        # Workflow must have the block
        assert "analyze" in wf._blocks

    def test_assertions_bridged_on_library_soul_block(self):
        """Block assertions must be bridged onto the runtime block even when
        the soul comes from a library soul ref."""
        wf = _parse_in_workspace(YAML_SOUL_REF_WITH_ASSERTIONS)

        block = wf._blocks["analyze"]
        assert block.assertions is not None
        assert block.assertions[0]["type"] == "contains"
        assert block.assertions[0]["value"] == "result"

    def test_full_chain_library_soul_with_inputs_and_assertions(self):
        """Full chain: soul_ref resolved, block built, assertions bridged,
        Step wrapping preserves assertions, _build_assertion_configs sees them."""
        ExecutionService = pytest.importorskip(
            "runsight_api.logic.services.execution_service", reason="runsight_api not installed"
        ).ExecutionService

        wf = _parse_in_workspace(YAML_TWO_BLOCKS_WITH_INPUT_AND_ASSERTIONS)

        # Verify soul resolution (fetch block should have been built)
        assert "fetch" in wf._blocks
        assert "analyze" in wf._blocks

        # Verify analyze is Step-wrapped (has inputs)
        assert isinstance(wf._blocks["analyze"], Step)

        # Verify assertions bridged and visible through Step
        assert wf._blocks["analyze"].assertions is not None

        # Verify _build_assertion_configs finds them
        configs = ExecutionService._build_assertion_configs(wf)
        assert configs is not None
        assert "analyze" in configs
        assert configs["analyze"][0]["type"] == "contains"


# ===========================================================================
# AI-1: No soul-level assertions anywhere
# ===========================================================================


class TestAI1NoSoulLevelAssertions:
    """Soul.model_fields, SoulDef.model_fields must not contain 'assertions'.
    SoulEntity must not have an explicit 'assertions' field."""

    def test_soul_model_fields_no_assertions(self):
        """Soul primitive must not have an 'assertions' field."""
        assert "assertions" not in Soul.model_fields, (
            "Soul.model_fields still contains 'assertions' — "
            "soul-level assertions must be fully removed"
        )

    def test_souldef_model_fields_no_assertions(self):
        """SoulDef schema must not have an 'assertions' field."""
        assert "assertions" not in SoulDef.model_fields, (
            "SoulDef.model_fields still contains 'assertions' — "
            "soul-level assertions must be fully removed from the schema"
        )

    def test_soul_entity_no_explicit_assertions_field(self):
        """SoulEntity API domain model must not have an explicit 'assertions' field."""
        SoulEntity = pytest.importorskip(
            "runsight_api.domain.value_objects", reason="runsight_api not installed"
        ).SoulEntity

        # Check model_fields (explicit Pydantic fields)
        assert "assertions" not in SoulEntity.model_fields, (
            "SoulEntity.model_fields still contains 'assertions' — the compat shim must be removed"
        )

    def test_soul_entity_source_has_no_assertions_definition(self):
        """SoulEntity source code must not define an assertions field.

        This catches facade implementations where the field might be hidden
        behind a computed property or validator instead of model_fields."""
        value_objects = pytest.importorskip(
            "runsight_api.domain", reason="runsight_api not installed"
        ).value_objects

        source = inspect.getsource(value_objects.SoulEntity)
        assert "assertions" not in source, (
            "SoulEntity source still references 'assertions' — "
            "the field or property must be completely removed"
        )

    def test_parser_has_no_resolve_soul_function(self):
        """parser.py must not contain the duplicate _resolve_soul function."""
        from runsight_core.yaml import parser

        assert not hasattr(parser, "_resolve_soul"), (
            "parser module still has _resolve_soul attribute — "
            "the duplicate function must be deleted"
        )


# ===========================================================================
# AI-2: Step delegates assertions to wrapped block
# ===========================================================================


class TestAI2StepDelegatesAssertions:
    """Any Step wrapping a block with .assertions must expose them via step.assertions."""

    def test_step_property_delegates_to_inner_block(self):
        """Step.assertions property must delegate to the wrapped block."""
        block = _StubBlock("inner")
        block.assertions = [{"type": "contains", "value": "test"}]

        step = Step(block=block, declared_inputs={"x": "prev.output"})

        assert step.assertions is block.assertions

    def test_step_returns_none_when_block_has_no_assertions(self):
        """Step.assertions returns None when the inner block has assertions=None."""
        block = _StubBlock("inner")
        assert block.assertions is None  # default

        step = Step(block=block, declared_inputs={"x": "prev.output"})
        assert step.assertions is None

    def test_step_assertions_is_property_not_instance_attribute(self):
        """Step.assertions must be a property (not an instance attribute set in __init__),
        so it always reflects the current state of the inner block."""
        # Verify it's a property on the class
        assert isinstance(Step.__dict__.get("assertions"), property), (
            "Step.assertions must be a @property, not an instance attribute"
        )

    def test_step_assertions_reflects_live_mutations(self):
        """If the inner block's assertions list is mutated after Step construction,
        the Step must reflect the change — proving it's a live delegation."""
        block = _StubBlock("inner")
        block.assertions = [{"type": "contains", "value": "original"}]
        step = Step(block=block, declared_inputs={"x": "prev.output"})

        # Mutate the inner block
        block.assertions.append({"type": "cost", "threshold": 0.01})

        assert len(step.assertions) == 2
        assert step.assertions[1]["type"] == "cost"

    def test_step_also_delegates_block_id(self):
        """Step.block_id must delegate to the wrapped block (sanity check)."""
        block = _StubBlock("my_block_id")
        step = Step(block=block, declared_inputs={"x": "prev.output"})
        assert step.block_id == "my_block_id"


# ===========================================================================
# AI-3: Parser bridge is idempotent
# ===========================================================================


class TestAI3ParserBridgeIdempotent:
    """Parsing the same YAML twice must produce identical assertion configs."""

    def test_parsing_same_yaml_twice_yields_identical_configs(self):
        """Parse the same YAML content twice in separate temp workspaces.
        The assertion configs extracted by _build_assertion_configs must be equal."""
        ExecutionService = pytest.importorskip(
            "runsight_api.logic.services.execution_service", reason="runsight_api not installed"
        ).ExecutionService

        wf1 = _parse_in_workspace(YAML_TWO_BLOCKS_WITH_INPUT_AND_ASSERTIONS)
        wf2 = _parse_in_workspace(YAML_TWO_BLOCKS_WITH_INPUT_AND_ASSERTIONS)

        configs1 = ExecutionService._build_assertion_configs(wf1)
        configs2 = ExecutionService._build_assertion_configs(wf2)

        assert configs1 == configs2, (
            f"Parsing the same YAML twice produced different configs:\n"
            f"  first:  {configs1}\n"
            f"  second: {configs2}"
        )

    def test_parsing_same_yaml_twice_yields_identical_assertion_types(self):
        """Each assertion type string must be identical across parses."""
        wf1 = _parse_in_workspace(YAML_MULTI_BLOCK_ASSERTIONS)
        wf2 = _parse_in_workspace(YAML_MULTI_BLOCK_ASSERTIONS)

        for block_id in ["research", "summarize", "review"]:
            a1 = wf1._blocks[block_id].assertions
            a2 = wf2._blocks[block_id].assertions
            assert a1 == a2, (
                f"Block '{block_id}' assertions differ between parses:\n"
                f"  first:  {a1}\n"
                f"  second: {a2}"
            )

    def test_parser_bridge_does_not_accumulate_assertions(self):
        """Assertions on a block must be exactly what the YAML defines.
        They must not grow or accumulate if re-parsed."""
        ExecutionService = pytest.importorskip(
            "runsight_api.logic.services.execution_service", reason="runsight_api not installed"
        ).ExecutionService

        yaml_content = YAML_SOUL_REF_WITH_ASSERTIONS

        wf1 = _parse_in_workspace(yaml_content)
        c1 = ExecutionService._build_assertion_configs(wf1)

        wf2 = _parse_in_workspace(yaml_content)
        c2 = ExecutionService._build_assertion_configs(wf2)

        # Exactly one assertion on 'analyze'
        assert c1 is not None
        assert len(c1["analyze"]) == 1
        assert c2 is not None
        assert len(c2["analyze"]) == 1
        assert c1 == c2
