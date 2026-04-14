"""Red tests for RUN-693: Step wrapper silently swallowing block assertions.

The bug: When a block has both `inputs:` and `assertions:` in YAML, the parser
sets `.assertions` on the BaseBlock (step 6.5b), then wraps it in a Step for
input resolution (step 6.6). Step has no `.assertions` property, so
`getattr(step, "assertions", None)` returns None — assertions are silently lost.

Tests cover:
- Group 1: Step unit tests — accessing .assertions on a Step-wrapped block
- Group 2: Parser integration — YAML with both inputs and assertions parsed correctly
- Group 3: _build_assertion_configs pipeline — assertions visible through Step wrapper
"""

import tempfile
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class DummyBlock(BaseBlock):
    """Minimal concrete block for unit tests."""

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state.model_copy(
            update={"results": {**state.results, self.block_id: BlockResult(output="ok")}}
        )


def _write_soul_file(base_dir: Path, name: str, content: str) -> None:
    """Create a soul YAML file at custom/souls/<name>.yaml."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(dedent(content), encoding="utf-8")


# ===========================================================================
# Group 1: Step unit tests — .assertions delegation
# ===========================================================================


class TestStepDelegatesAssertions:
    """Step wrapper must delegate .assertions to the inner block."""

    def test_step_exposes_inner_block_assertions(self):
        """A Step wrapping a block with assertions should return them via .assertions."""
        block = DummyBlock("analyze")
        block.assertions = [{"type": "contains", "value": "analysis"}]

        step = Step(block=block, declared_inputs={"data": "fetch.output"})

        assert step.assertions is not None
        assert step.assertions == [{"type": "contains", "value": "analysis"}]

    def test_step_returns_none_when_inner_block_has_no_assertions(self):
        """A Step wrapping a block without assertions should return None."""
        block = DummyBlock("summarize")
        # block.assertions defaults to None (set in BaseBlock.__init__)

        step = Step(block=block, declared_inputs={"text": "analyze.output"})

        assert step.assertions is None

    def test_step_assertions_reflects_mutations_on_inner_block(self):
        """If the inner block's assertions are updated, Step.assertions should reflect it."""
        block = DummyBlock("review")
        block.assertions = [{"type": "cost", "threshold": 0.05}]

        step = Step(block=block, declared_inputs={"input": "draft.output"})

        # Mutate the inner block's assertions
        block.assertions.append({"type": "contains", "value": "conclusion"})

        assert len(step.assertions) == 2
        assert step.assertions[1]["type"] == "contains"

    def test_getattr_assertions_on_step_does_not_return_none_fallback(self):
        """getattr(step, 'assertions', None) must return the block's assertions, not None."""
        block = DummyBlock("check")
        block.assertions = [{"type": "contains", "value": "result"}]

        step = Step(block=block, declared_inputs={"x": "prev.output"})

        # This is the exact pattern _build_assertion_configs uses
        result = getattr(step, "assertions", None)
        assert result is not None
        assert result == [{"type": "contains", "value": "result"}]


# ===========================================================================
# Group 2: Parser integration — YAML with both inputs and assertions
# ===========================================================================


YAML_INPUTS_AND_ASSERTIONS = """\
id: test-workflow
kind: workflow
version: "1.0"
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
  name: inputs_and_assertions
  entry: fetch
  transitions:
    - from: fetch
      to: analyze
    - from: analyze
      to: null
"""


YAML_INPUTS_NO_ASSERTIONS = """\
id: test-workflow
kind: workflow
version: "1.0"
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
workflow:
  name: inputs_no_assertions
  entry: fetch
  transitions:
    - from: fetch
      to: analyze
    - from: analyze
      to: null
"""


def _parse_with_souls(yaml_content: str) -> object:
    """Parse workflow YAML using a temp directory with required soul files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _write_soul_file(
            base,
            "researcher",
            """\
            id: researcher
            kind: soul
            name: Researcher
            role: Researcher
            system_prompt: You research topics.
            """,
        )
        _write_soul_file(
            base,
            "analyst",
            """\
            id: analyst
            kind: soul
            name: Analyst
            role: Analyst
            system_prompt: You analyze data.
            """,
        )
        workflow_file = base / "workflow.yaml"
        workflow_file.write_text(yaml_content, encoding="utf-8")
        return parse_workflow_yaml(str(workflow_file))


class TestParserPreservesAssertionsWithInputs:
    """Parser must preserve assertions on blocks that also have inputs (Step-wrapped)."""

    def test_block_with_inputs_and_assertions_retains_assertions_after_parse(self):
        """A parsed block with both inputs and assertions must expose assertions."""
        wf = _parse_with_souls(YAML_INPUTS_AND_ASSERTIONS)

        block = wf._blocks["analyze"]
        # The block is Step-wrapped because it has inputs.
        # Assertions must still be accessible.
        assert block.assertions is not None
        assert len(block.assertions) == 2

    def test_block_with_inputs_and_assertions_preserves_assertion_fields(self):
        """Assertion config fields from YAML must survive Step wrapping."""
        wf = _parse_with_souls(YAML_INPUTS_AND_ASSERTIONS)

        block = wf._blocks["analyze"]
        assert block.assertions is not None
        assert block.assertions[0]["type"] == "contains"
        assert block.assertions[0]["value"] == "analysis"
        assert block.assertions[1]["type"] == "cost"
        assert block.assertions[1]["threshold"] == 0.05

    def test_block_with_inputs_but_no_assertions_returns_none(self):
        """A Step-wrapped block without assertions must return None."""
        wf = _parse_with_souls(YAML_INPUTS_NO_ASSERTIONS)

        block = wf._blocks["analyze"]
        assert getattr(block, "assertions", None) is None

    def test_block_without_inputs_still_works(self):
        """A block without inputs is not wrapped in Step — assertions work as before."""
        wf = _parse_with_souls(YAML_INPUTS_AND_ASSERTIONS)

        # 'fetch' has no inputs, so it should be a raw block, not Step-wrapped
        fetch_block = wf._blocks["fetch"]
        assert not isinstance(fetch_block, Step)


# ===========================================================================
# Group 3: _build_assertion_configs pipeline — Step-wrapped blocks
# ===========================================================================


class TestBuildAssertionConfigsWithStepWrappedBlocks:
    """_build_assertion_configs must see assertions through Step wrappers."""

    def test_build_assertion_configs_sees_assertions_through_step_wrapper(self):
        """When _blocks contains a Step-wrapped block with assertions,
        _build_assertion_configs must include them in the config dict."""
        from runsight_api.logic.services.execution_service import ExecutionService

        inner_block = SimpleNamespace(assertions=[{"type": "contains", "value": "analysis"}])
        step = Step(block=inner_block, declared_inputs={"data": "fetch.output"})

        wf = SimpleNamespace(_blocks={"analyze": step})

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is not None
        assert "analyze" in configs
        assert configs["analyze"] == [{"type": "contains", "value": "analysis"}]

    def test_build_assertion_configs_returns_none_for_step_without_assertions(self):
        """When all Step-wrapped blocks have no assertions, return None."""
        from runsight_api.logic.services.execution_service import ExecutionService

        inner_block = SimpleNamespace(assertions=None)
        step = Step(block=inner_block, declared_inputs={"data": "fetch.output"})

        wf = SimpleNamespace(_blocks={"analyze": step})

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is None

    def test_build_assertion_configs_full_pipeline_parse_then_build(self):
        """End-to-end: parse YAML with inputs+assertions, then build configs."""
        from runsight_api.logic.services.execution_service import ExecutionService

        wf = _parse_with_souls(YAML_INPUTS_AND_ASSERTIONS)

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is not None
        assert "analyze" in configs
        assert len(configs["analyze"]) == 2
        assert configs["analyze"][0]["type"] == "contains"
        assert configs["analyze"][1]["type"] == "cost"
