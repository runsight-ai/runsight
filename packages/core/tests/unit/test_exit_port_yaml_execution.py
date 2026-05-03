"""Exit-port YAML execution and round-trip coverage."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from conftest import block_output_from_state
from runsight_core.blocks.base import BaseBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult, RunsightTeamRunner
from runsight_core.state import BlockResult, WorkflowState

# ---------------------------------------------------------------------------
# Helpers: mock runner and blocks
# ---------------------------------------------------------------------------


def _mock_runner(output: str, cost: float = 0.01, tokens: int = 100) -> RunsightTeamRunner:
    runner = MagicMock(spec=RunsightTeamRunner)
    runner.model_name = "gpt-4o"
    runner.execute = AsyncMock(
        return_value=ExecutionResult(
            task_id="test", soul_id="test", output=output, cost_usd=cost, total_tokens=tokens
        )
    )
    return runner


def _make_soul(soul_id: str = "test_soul") -> Soul:
    return Soul(id=soul_id, kind="soul", name="Test", role="Test", system_prompt="Test prompt")


class StubBlock(BaseBlock):
    """Minimal block that stores a fixed output."""

    def __init__(self, block_id: str, output: str = "done"):
        super().__init__(block_id)
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=self._output),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class ExitHandleBlock(BaseBlock):
    """Block whose execute() stores a BlockResult with a specific exit_handle."""

    def __init__(self, block_id: str, exit_handle: str, output: str = "done"):
        super().__init__(block_id)
        self._exit_handle = exit_handle
        self._output = output

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(
                        output=self._output,
                        exit_handle=self._exit_handle,
                    ),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


class JsonOutputBlock(BaseBlock):
    """Block that stores a JSON-string BlockResult (no exit_handle set)."""

    def __init__(self, block_id: str, data: dict):
        super().__init__(block_id)
        self._data = data

    async def execute(self, ctx):
        state = ctx.state_snapshot
        next_state = state.model_copy(
            update={
                "results": {
                    **state.results,
                    self.block_id: BlockResult(output=json.dumps(self._data)),
                },
            }
        )
        return block_output_from_state(self.block_id, state, next_state)


def _fresh_state(**kwargs) -> WorkflowState:
    return WorkflowState(**kwargs)


class TestFullWorkflowBranchingFromYAML:
    """Full integration: parse a YAML workflow that uses exit ports, then run it."""

    @pytest.mark.asyncio
    async def test_full_yaml_gate_workflow_pass_path(self):
        """Parse a complete YAML workflow with gate + conditional_transitions,
        mock the runner to PASS, verify correct execution path."""
        from unittest.mock import patch

        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
id: test-workflow
kind: workflow
workflow:
  name: test_gate_integration
  entry: content_block
  transitions:
    - from: content_block
      to: quality_gate
  conditional_transitions:
    - from: quality_gate
      pass: publish
      fail: revise
      default: revise

souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: "Write content"
    provider: openai
    model_name: gpt-4o
  reviewer:
    id: reviewer
    kind: soul
    name: Reviewer
    role: Reviewer
    system_prompt: "Evaluate quality. Respond PASS or FAIL: reason"
    provider: openai
    model_name: gpt-4o

blocks:
  content_block:
    type: linear
    soul_ref: writer
  quality_gate:
    type: gate
    soul_ref: reviewer
    eval_key: content_block
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  publish:
    type: linear
    soul_ref: writer
  revise:
    type: linear
    soul_ref: writer
"""
        wf = parse_workflow_yaml(yaml_content)

        # Mock the LLM to return predictable outputs
        with patch("runsight_core.runner.LiteLLMClient.achat") as mock_achat:
            call_count = {"n": 0}

            async def _side_effect(**kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    # content_block output
                    return {
                        "content": "Great article about AI agents.",
                        "cost_usd": 0.01,
                        "total_tokens": 50,
                    }
                elif call_count["n"] == 2:
                    # quality_gate evaluation -> PASS
                    return {
                        "content": "PASS",
                        "cost_usd": 0.01,
                        "total_tokens": 30,
                    }
                else:
                    # publish block
                    return {
                        "content": "Published successfully.",
                        "cost_usd": 0.01,
                        "total_tokens": 20,
                    }

            mock_achat.side_effect = _side_effect

            state = WorkflowState()

            final = await wf.run(state)

        # Verify the correct execution path: content_block -> gate (PASS) -> publish
        assert "content_block" in final.results
        assert "quality_gate" in final.results
        assert final.results["quality_gate"].exit_handle == "pass"
        assert "publish" in final.results, (
            "Gate PASS should route to 'publish' block via conditional_transition"
        )
        assert "revise" not in final.results, "Gate PASS should not route to 'revise' block"

    @pytest.mark.asyncio
    async def test_full_yaml_gate_workflow_fail_path(self):
        """Parse a complete YAML workflow, mock runner to FAIL, verify fail path."""
        from unittest.mock import patch

        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
id: test-workflow
kind: workflow
workflow:
  name: test_gate_fail_integration
  entry: content_block
  transitions:
    - from: content_block
      to: quality_gate
  conditional_transitions:
    - from: quality_gate
      pass: publish
      fail: revise
      default: revise

souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: "Write content"
    provider: openai
    model_name: gpt-4o
  reviewer:
    id: reviewer
    kind: soul
    name: Reviewer
    role: Reviewer
    system_prompt: "Evaluate quality. Respond PASS or FAIL: reason"
    provider: openai
    model_name: gpt-4o

blocks:
  content_block:
    type: linear
    soul_ref: writer
  quality_gate:
    type: gate
    soul_ref: reviewer
    eval_key: content_block
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  publish:
    type: linear
    soul_ref: writer
  revise:
    type: linear
    soul_ref: writer
"""
        wf = parse_workflow_yaml(yaml_content)

        with patch("runsight_core.runner.LiteLLMClient.achat") as mock_achat:
            call_count = {"n": 0}

            async def _side_effect(**kwargs):
                call_count["n"] += 1
                if call_count["n"] == 1:
                    return {
                        "content": "Rough draft about AI.",
                        "cost_usd": 0.01,
                        "total_tokens": 50,
                    }
                elif call_count["n"] == 2:
                    # quality_gate -> FAIL
                    return {
                        "content": "FAIL: needs more detail",
                        "cost_usd": 0.01,
                        "total_tokens": 30,
                    }
                else:
                    # revise block
                    return {
                        "content": "Revised with more detail.",
                        "cost_usd": 0.01,
                        "total_tokens": 40,
                    }

            mock_achat.side_effect = _side_effect

            state = WorkflowState()

            final = await wf.run(state)

        assert "content_block" in final.results
        assert "quality_gate" in final.results
        assert final.results["quality_gate"].exit_handle == "fail"
        assert "revise" in final.results, (
            "Gate FAIL should route to 'revise' block via conditional_transition"
        )
        assert "publish" not in final.results, "Gate FAIL should not route to 'publish' block"


# ==============================================================================
# YAML round-trip: exit port declarations survive parse -> dump -> parse
# ==============================================================================


class TestYamlExitPortRoundTrip:
    """Exit port declarations in YAML survive a parse -> model_dump -> re-parse cycle."""

    def test_gate_exits_survive_schema_round_trip(self):
        """Parse a YAML with gate exits, dump to dict, verify exits are present."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        yaml_content = """
id: test-workflow
kind: workflow
version: "1.0"

config:
  model_name: gpt-4o

souls:
  reviewer:
    id: reviewer
    kind: soul
    name: Reviewer
    role: Reviewer
    system_prompt: "Evaluate quality"

blocks:
  gate:
    type: gate
    soul_ref: reviewer
    eval_key: content
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail

workflow:
  name: roundtrip_test
  entry: gate
  transitions:
    - from: gate
      to: null
"""
        data = yaml.safe_load(yaml_content)

        # Trigger block type registration
        import runsight_core.blocks  # noqa: F401
        from runsight_core.yaml.schema import rebuild_block_def_union

        rebuild_block_def_union()

        file_def = RunsightWorkflowFile.model_validate(data)
        gate_def = file_def.blocks["gate"]

        assert gate_def.exits is not None, "Exits should parse from YAML"
        assert len(gate_def.exits) == 2
        exit_ids = [e.id for e in gate_def.exits]
        assert "pass" in exit_ids
        assert "fail" in exit_ids

    def test_loop_break_on_exit_survives_schema_round_trip(self):
        """Parse a YAML with loop break_on_exit, dump, verify field is present."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        yaml_content = """
id: test-workflow
kind: workflow
version: "1.0"

config:
  model_name: gpt-4o

souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: "Write content"
  reviewer:
    id: reviewer
    kind: soul
    name: Reviewer
    role: Reviewer
    system_prompt: "Evaluate quality"

blocks:
  writer:
    type: linear
    soul_ref: writer
  gate:
    type: gate
    soul_ref: reviewer
    eval_key: writer
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  review_loop:
    type: loop
    inner_block_refs:
      - writer
      - gate
    max_rounds: 3
    break_on_exit: pass
    retry_on_exit: fail

workflow:
  name: loop_exit_roundtrip
  entry: review_loop
  transitions:
    - from: review_loop
      to: null
"""
        data = yaml.safe_load(yaml_content)

        import runsight_core.blocks  # noqa: F401
        from runsight_core.yaml.schema import rebuild_block_def_union

        rebuild_block_def_union()

        file_def = RunsightWorkflowFile.model_validate(data)
        loop_def = file_def.blocks["review_loop"]

        assert loop_def.break_on_exit == "pass", "break_on_exit should survive YAML -> schema parse"
        assert loop_def.retry_on_exit == "fail", "retry_on_exit should survive YAML -> schema parse"


# ==============================================================================
# External soul file resolution via _discover_external_souls
# ==============================================================================


class TestExternalSoulFileResolution:
    """parse_workflow_yaml resolves soul_refs from isolated soul fixture files."""

    def test_external_soul_file_resolves_for_linear_block(self, tmp_path):
        """A workflow YAML with no inline souls resolves soul_ref from tmp_path fixtures."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        souls_dir = tmp_path / "custom" / "souls"
        souls_dir.mkdir(parents=True)

        (souls_dir / "narrator.yaml").write_text(
            "id: narrator\nkind: soul\nname: Narrator\nrole: Narrator\nsystem_prompt: Tell the story.\n"
            "provider: openai\nmodel_name: gpt-4o\n"
        )

        yaml_content = """
id: test-workflow
kind: workflow
workflow:
  name: external_soul_linear
  entry: story_block
  transitions:
    - from: story_block
      to: null

blocks:
  story_block:
    type: linear
    soul_ref: narrator
"""
        wf = parse_workflow_yaml(yaml_content, _base_dir=str(tmp_path))
        assert wf is not None
        assert wf.name == "external_soul_linear"
        assert "story_block" in wf.blocks

    def test_external_soul_file_resolves_for_gate_block(self, tmp_path):
        """A gate workflow YAML with no inline souls resolves soul_refs from tmp_path fixtures."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        souls_dir = tmp_path / "custom" / "souls"
        souls_dir.mkdir(parents=True)

        (souls_dir / "author.yaml").write_text(
            "id: author\nkind: soul\nname: Author\nrole: Author\nsystem_prompt: Write content.\n"
            "provider: openai\nmodel_name: gpt-4o\n"
        )
        (souls_dir / "judge.yaml").write_text(
            "id: judge\nkind: soul\nname: Judge\nrole: Judge\nsystem_prompt: Evaluate content. Respond PASS or FAIL.\n"
            "provider: openai\nmodel_name: gpt-4o\n"
        )

        yaml_content = """
id: test-workflow
kind: workflow
workflow:
  name: external_soul_gate
  entry: draft
  transitions:
    - from: draft
      to: quality_check
  conditional_transitions:
    - from: quality_check
      pass: done
      fail: done
      default: done

blocks:
  draft:
    type: linear
    soul_ref: author
  quality_check:
    type: gate
    soul_ref: judge
    eval_key: draft
    exits:
      - id: pass
        label: Pass
      - id: fail
        label: Fail
  done:
    type: linear
    soul_ref: author
"""
        wf = parse_workflow_yaml(yaml_content, _base_dir=str(tmp_path))
        assert wf is not None
        assert wf.name == "external_soul_gate"
        gate = wf.blocks["quality_check"]
        declared_ids = {e.id for e in gate._declared_exits}
        assert "pass" in declared_ids
        assert "fail" in declared_ids
