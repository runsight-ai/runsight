"""Step wrapper assertion delegation through parser and execution-service config building."""

from pathlib import Path
from textwrap import dedent

from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml
from workflow_fixture_helpers import workflow_fixture_text

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
# Step .assertions delegation
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
# Parser integration for inputs plus assertions
# ===========================================================================


INPUTS_AND_ASSERTIONS_FIXTURE = "step-wrapper-inputs-and-assertions.yaml"
INPUTS_NO_ASSERTIONS_FIXTURE = "step-wrapper-inputs-no-assertions.yaml"


def _parse_with_souls(tmp_path: Path, fixture_name: str) -> object:
    """Parse workflow fixture YAML using pytest-owned workspace soul files."""
    _write_soul_file(
        tmp_path,
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
        tmp_path,
        "analyst",
        """\
        id: analyst
        kind: soul
        name: Analyst
        role: Analyst
        system_prompt: You analyze data.
        """,
    )
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(workflow_fixture_text(fixture_name), encoding="utf-8")
    return parse_workflow_yaml(str(workflow_file))


class TestParserPreservesAssertionsWithInputs:
    """Parser must preserve assertions on blocks that also have inputs (Step-wrapped)."""

    def test_block_with_inputs_and_assertions_retains_assertions_after_parse(self, tmp_path: Path):
        """A parsed block with both inputs and assertions must expose assertions."""
        wf = _parse_with_souls(tmp_path, INPUTS_AND_ASSERTIONS_FIXTURE)

        block = wf._blocks["analyze"]
        # The block is Step-wrapped because it has inputs.
        # Assertions must still be accessible.
        assert block.assertions is not None
        assert len(block.assertions) == 2

    def test_block_with_inputs_and_assertions_preserves_assertion_fields(self, tmp_path: Path):
        """Assertion config fields from YAML must survive Step wrapping."""
        wf = _parse_with_souls(tmp_path, INPUTS_AND_ASSERTIONS_FIXTURE)

        block = wf._blocks["analyze"]
        assert block.assertions is not None
        assert block.assertions[0]["type"] == "contains"
        assert block.assertions[0]["value"] == "analysis"
        assert block.assertions[1]["type"] == "cost"
        assert block.assertions[1]["threshold"] == 0.05

    def test_block_with_inputs_but_no_assertions_returns_none(self, tmp_path: Path):
        """A Step-wrapped block without assertions must return None."""
        wf = _parse_with_souls(tmp_path, INPUTS_NO_ASSERTIONS_FIXTURE)

        block = wf._blocks["analyze"]
        assert getattr(block, "assertions", None) is None

    def test_block_without_inputs_still_works(self, tmp_path: Path):
        """A block without inputs is not wrapped in Step — assertions work as before."""
        wf = _parse_with_souls(tmp_path, INPUTS_AND_ASSERTIONS_FIXTURE)

        # 'fetch' has no inputs, so it should be a raw block, not Step-wrapped
        fetch_block = wf._blocks["fetch"]
        assert not isinstance(fetch_block, Step)
