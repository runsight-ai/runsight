"""
Integration tests for RUN-287: Dispatch v2 + SynthesizeBlock end-to-end pipeline.

Tests the full integration chain:
1. Full pipeline: parse YAML -> DispatchBlock (per-exit tasks) -> SynthesizeBlock -> verify
2. Per-exit references: SynthesizeBlock reads individual branch outputs via dotted keys
3. Stateful + loop: Dispatch with stateful=true inside LoopBlock -> histories preserved
4. Context inheritance: workflow current_task context -> each branch inherits context

All tests mock LiteLLMClient.achat to return different outputs per branch.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from conftest import execute_block_for_test, execute_loop_for_test
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.loop import LoopBlock
from runsight_core.blocks.synthesize import SynthesizeBlock
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml

# ---------------------------------------------------------------------------
# Shared YAML fixture
# ---------------------------------------------------------------------------

DISPATCH_SYNTHESIZE_YAML = """\
version: "1.0"
id: dispatch_v2_test
kind: workflow
souls:
  researcher:
    id: researcher
    kind: soul
    name: Senior Researcher
    role: Senior Researcher
    system_prompt: "You research topics."
    provider: openai
    model_name: gpt-4o
  coder:
    id: coder
    kind: soul
    name: Software Engineer
    role: Software Engineer
    system_prompt: "You write code."
    provider: openai
    model_name: gpt-4o
  synthesizer:
    id: synthesizer
    kind: soul
    name: Synthesis Agent
    role: Synthesis Agent
    system_prompt: "You synthesize inputs."
    provider: openai
    model_name: gpt-4o

blocks:
  dispatch_work:
    type: dispatch
    exits:
      - id: researcher
        label: Research Agent
        soul_ref: researcher
        task: "Find papers on quantum computing"
      - id: coder
        label: Code Agent
        soul_ref: coder
        task: "Implement Grover's algorithm"

  merge_results:
    type: synthesize
    soul_ref: synthesizer
    input_block_ids: [dispatch_work]

workflow:
  id: dispatch_v2_test
  kind: workflow
  name: dispatch_v2_test
  entry: dispatch_work
  transitions:
    - from: dispatch_work
      to: merge_results
    - from: merge_results
      to: null
"""

PER_EXIT_REF_YAML = """\
version: "1.0"
id: dispatch_v2_per_exit_test
kind: workflow
souls:
  researcher:
    id: researcher
    kind: soul
    name: Senior Researcher
    role: Senior Researcher
    system_prompt: "You research topics."
    provider: openai
    model_name: gpt-4o
  coder:
    id: coder
    kind: soul
    name: Software Engineer
    role: Software Engineer
    system_prompt: "You write code."
    provider: openai
    model_name: gpt-4o
  synthesizer:
    id: synthesizer
    kind: soul
    name: Synthesis Agent
    role: Synthesis Agent
    system_prompt: "You synthesize inputs."
    provider: openai
    model_name: gpt-4o

blocks:
  dispatch_work:
    type: dispatch
    exits:
      - id: researcher
        label: Research Agent
        soul_ref: researcher
        task: "Find papers on quantum computing"
      - id: coder
        label: Code Agent
        soul_ref: coder
        task: "Implement Grover's algorithm"

  merge_results:
    type: synthesize
    soul_ref: synthesizer
    input_block_ids: ["dispatch_work.researcher", "dispatch_work.coder"]

workflow:
  id: dispatch_v2_per_exit_test
  kind: workflow
  name: dispatch_v2_per_exit_test
  entry: dispatch_work
  transitions:
    - from: dispatch_work
      to: merge_results
    - from: merge_results
      to: null
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_exec_result(task_id, soul_id, output, cost=0.0, tokens=0):
    """Create an ExecutionResult with controlled values."""
    return ExecutionResult(
        task_id=task_id,
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


def _mock_runner():
    """Build a MagicMock runner."""
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = "gpt-4o"
    return runner


# ===========================================================================
# Scenario 1: Full pipeline — parse YAML, run Dispatch, run Synthesize
# ===========================================================================


class TestFullPipeline:
    """Parse YAML with Dispatch v2 (per-exit tasks) -> SynthesizeBlock -> verify
    each branch got its own task, synthesize got combined output."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion")
    async def test_full_pipeline_parse_and_run(self, mock_acompletion):
        """Full YAML -> parse -> run workflow -> verify Dispatch per-exit + Synthesize."""
        call_count = 0

        async def _mock_acompletion(**kwargs):
            nonlocal call_count
            call_count += 1
            messages = kwargs.get("messages", [])
            # Determine which branch by inspecting the prompt content
            prompt_text = " ".join(m.get("content", "") for m in messages)

            if "quantum computing" in prompt_text.lower():
                content = "Research: Found 3 papers on quantum computing applications."
                cost_tokens = 100
            elif "grover" in prompt_text.lower():
                content = (
                    "Code: Implemented Grover's algorithm in Python with O(sqrt(N)) complexity."
                )
                cost_tokens = 120
            else:
                # Synthesize call
                content = (
                    "Synthesis: Quantum computing research identified 3 key papers. "
                    "Grover's algorithm was implemented with optimal complexity."
                )
                cost_tokens = 150

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = content
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = cost_tokens
            mock_response.usage.completion_tokens = cost_tokens
            mock_response.usage.total_tokens = cost_tokens * 2
            return mock_response

        mock_acompletion.side_effect = _mock_acompletion

        with patch("runsight_core.llm.client.completion_cost", return_value=0.01):
            wf = parse_workflow_yaml(DISPATCH_SYNTHESIZE_YAML)
            state = WorkflowState()
            final_state = await wf.run(state)

        # Dispatch per-exit results keyed correctly
        assert "dispatch_work.researcher" in final_state.results
        assert "dispatch_work.coder" in final_state.results
        assert "dispatch_work" in final_state.results

        # Each branch got different output
        researcher_output = final_state.results["dispatch_work.researcher"].output
        coder_output = final_state.results["dispatch_work.coder"].output
        assert "Research" in researcher_output
        assert "quantum computing" in researcher_output.lower()
        assert "Code" in coder_output or "Grover" in coder_output

        # SynthesizeBlock produced a result
        assert "merge_results" in final_state.results
        synth_output = final_state.results["merge_results"].output
        assert "Synthesis" in synth_output or "quantum" in synth_output.lower()

        # Cost and tokens accumulated from all 3 LLM calls
        assert final_state.total_cost_usd > 0
        assert final_state.total_tokens > 0

        # At least 3 LLM calls: 2 dispatch branches + 1 synthesize
        assert call_count >= 3

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion")
    async def test_dispatch_branches_receive_different_tasks(self, mock_acompletion):
        """Verify each Dispatch branch receives its own task instruction, not a shared one."""
        captured_prompts = []

        async def _mock_acompletion(**kwargs):
            messages = kwargs.get("messages", [])
            # Capture user messages (prompts)
            for m in messages:
                if m.get("role") == "user":
                    captured_prompts.append(m["content"])

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "OK"
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 50
            mock_response.usage.completion_tokens = 50
            mock_response.usage.total_tokens = 100
            return mock_response

        mock_acompletion.side_effect = _mock_acompletion

        with patch("runsight_core.llm.client.completion_cost", return_value=0.001):
            wf = parse_workflow_yaml(DISPATCH_SYNTHESIZE_YAML)
            state = WorkflowState()
            await wf.run(state)

        # The first two LLM calls are the Dispatch branches. Prompts must differ.
        assert len(captured_prompts) >= 2
        # One prompt mentions quantum computing / papers, the other mentions Grover's
        dispatch_prompts = captured_prompts[:2]
        assert dispatch_prompts[0] != dispatch_prompts[1], (
            f"Dispatch branches must get different prompts, got identical: {dispatch_prompts[0]}"
        )

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion")
    async def test_synthesize_receives_combined_dispatch_output(self, mock_acompletion):
        """SynthesizeBlock with input_block_ids: [dispatch_work] reads the combined JSON output."""
        captured_synth_context = []

        async def _mock_acompletion(**kwargs):
            messages = kwargs.get("messages", [])
            prompt_text = " ".join(m.get("content", "") for m in messages)

            # Identify synthesize call by checking for "Synthesize" instruction
            if "synthesize" in prompt_text.lower() or "=== Output from" in prompt_text:
                for m in messages:
                    if m.get("role") == "user":
                        captured_synth_context.append(m["content"])

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Synthesized result"
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 50
            mock_response.usage.completion_tokens = 50
            mock_response.usage.total_tokens = 100
            return mock_response

        mock_acompletion.side_effect = _mock_acompletion

        with patch("runsight_core.llm.client.completion_cost", return_value=0.001):
            wf = parse_workflow_yaml(DISPATCH_SYNTHESIZE_YAML)
            state = WorkflowState()
            await wf.run(state)

        # The synthesize call should have received the combined Dispatch output
        assert len(captured_synth_context) >= 1
        synth_prompt = captured_synth_context[0]
        # The SynthesizeBlock prefixes each input with "=== Output from {bid} ==="
        assert "dispatch_work" in synth_prompt

    @pytest.mark.asyncio
    async def test_cost_tokens_accumulated_correctly(self):
        """Verify cost and tokens from all branches + synthesize are summed in final state."""
        runner = _mock_runner()

        # Dispatch branch results
        runner.execute.side_effect = [
            _make_exec_result(
                "dispatch_work_researcher", "researcher", "Research output", 0.05, 100
            ),
            _make_exec_result("dispatch_work_coder", "coder", "Code output", 0.08, 150),
            # Synthesize result
            _make_exec_result(
                "merge_results_synthesis", "synthesizer", "Synthesis output", 0.10, 200
            ),
        ]

        # Build blocks manually (unit-level integration)
        researcher_soul = Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research.",
        )
        coder_soul = Soul(
            id="coder", kind="soul", name="Coder", role="Coder", system_prompt="Code."
        )
        synth_soul = Soul(
            id="synthesizer",
            kind="soul",
            name="Synthesizer",
            role="Synthesizer",
            system_prompt="Synthesize.",
        )

        dispatch = DispatchBlock(
            "dispatch_work",
            [
                DispatchBranch("researcher", "Research Agent", researcher_soul, "Find papers"),
                DispatchBranch("coder", "Code Agent", coder_soul, "Implement algorithm"),
            ],
            runner,
        )
        synthesize = SynthesizeBlock(
            "merge_results",
            input_block_ids=["dispatch_work"],
            synthesizer_soul=synth_soul,
            runner=runner,
        )

        state = WorkflowState()

        # Execute Dispatch
        state = await execute_block_for_test(dispatch, state)
        # Execute Synthesize
        state = await execute_block_for_test(synthesize, state)

        # Total cost = 0.05 + 0.08 + 0.10 = 0.23
        assert state.total_cost_usd == pytest.approx(0.23)
        # Total tokens = 100 + 150 + 200 = 450
        assert state.total_tokens == 450


# ===========================================================================
# Scenario 2: Per-exit references — SynthesizeBlock reads individual branch outputs
# ===========================================================================


class TestPerExitReferences:
    """SynthesizeBlock with input_block_ids: ["dispatch_work.researcher", "dispatch_work.coder"]
    reads individual branch outputs rather than the combined JSON."""

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion")
    async def test_per_exit_ref_yaml_parses(self, mock_acompletion):
        """YAML with input_block_ids referencing per-exit keys parses without error."""

        async def _mock_acompletion(**kwargs):
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "output"
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 10
            mock_response.usage.total_tokens = 20
            return mock_response

        mock_acompletion.side_effect = _mock_acompletion

        with patch("runsight_core.llm.client.completion_cost", return_value=0.001):
            wf = parse_workflow_yaml(PER_EXIT_REF_YAML)
            assert wf.name == "dispatch_v2_per_exit_test"

            state = WorkflowState()
            final_state = await wf.run(state)

        # Synthesize should have run successfully
        assert "merge_results" in final_state.results

    @pytest.mark.asyncio
    async def test_synthesize_reads_per_exit_keys(self):
        """SynthesizeBlock with per-exit input_block_ids reads each branch output individually."""
        runner = _mock_runner()
        synth_soul = Soul(
            id="synthesizer",
            kind="soul",
            name="Synthesizer",
            role="Synthesizer",
            system_prompt="Synthesize.",
        )

        runner.execute.return_value = _make_exec_result(
            "merge_synthesis", "synthesizer", "Synthesized from individual branches", 0.05, 100
        )

        synthesize = SynthesizeBlock(
            "merge_results",
            input_block_ids=["dispatch_work.researcher", "dispatch_work.coder"],
            synthesizer_soul=synth_soul,
            runner=runner,
        )

        # Pre-populate state with per-exit results (as Dispatch v2 would produce)
        state = WorkflowState(
            results={
                "dispatch_work.researcher": BlockResult(
                    output="Research: Found 3 papers.", exit_handle="researcher"
                ),
                "dispatch_work.coder": BlockResult(
                    output="Code: Implemented Grover's algorithm.", exit_handle="coder"
                ),
                "dispatch_work": BlockResult(output='[{"exit_id":"researcher","output":"..."}]'),
            }
        )

        final_state = await execute_block_for_test(synthesize, state)

        assert "merge_results" in final_state.results

        # Verify the synthesize task received both per-exit outputs as context
        call_args = runner.execute.call_args
        context_arg = call_args[0][1]  # 2nd positional arg is context
        assert "Research: Found 3 papers." in (context_arg or "")
        assert "Code: Implemented Grover's algorithm." in (context_arg or "")
        # Both per-exit keys should be referenced in the context
        assert "dispatch_work.researcher" in (context_arg or "")
        assert "dispatch_work.coder" in (context_arg or "")

    @pytest.mark.asyncio
    async def test_synthesize_fails_if_per_exit_key_missing(self):
        """SynthesizeBlock raises ValueError if a per-exit key is missing from state.results."""
        runner = _mock_runner()
        synth_soul = Soul(
            id="synthesizer",
            kind="soul",
            name="Synthesizer",
            role="Synthesizer",
            system_prompt="Synthesize.",
        )

        synthesize = SynthesizeBlock(
            "merge_results",
            input_block_ids=["dispatch_work.researcher", "dispatch_work.coder"],
            synthesizer_soul=synth_soul,
            runner=runner,
        )

        # Only researcher result is present, coder is missing
        state = WorkflowState(
            results={
                "dispatch_work.researcher": BlockResult(output="Research output"),
            }
        )

        with pytest.raises(ValueError, match="dispatch_work\\.coder.*source result missing"):
            await execute_block_for_test(synthesize, state)


# ===========================================================================
# Scenario 3: Stateful + loop — Dispatch with stateful=true inside LoopBlock
# ===========================================================================


class TestStatefulDispatchInLoop:
    """Dispatch with stateful=true inside a LoopBlock: per-exit histories preserved across rounds."""

    @pytest.mark.asyncio
    async def test_stateful_dispatch_preserves_histories_across_loop_rounds(self):
        """Per-exit conversation histories accumulate across LoopBlock rounds."""
        runner = _mock_runner()

        researcher_soul = Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research.",
        )
        coder_soul = Soul(
            id="coder", kind="soul", name="Coder", role="Coder", system_prompt="Code."
        )

        dispatch = DispatchBlock(
            "dispatch_work",
            [
                DispatchBranch("researcher", "Research Agent", researcher_soul, "Find papers"),
                DispatchBranch("coder", "Code Agent", coder_soul, "Write code"),
            ],
            runner,
        )
        dispatch.stateful = True

        # Round 1 results
        round1_results = [
            _make_exec_result(
                "dispatch_work_researcher", "researcher", "Round 1 research", 0.02, 50
            ),
            _make_exec_result("dispatch_work_coder", "coder", "Round 1 code", 0.03, 60),
        ]
        # Round 2 results
        round2_results = [
            _make_exec_result(
                "dispatch_work_researcher", "researcher", "Round 2 research", 0.02, 50
            ),
            _make_exec_result("dispatch_work_coder", "coder", "Round 2 code", 0.03, 60),
        ]

        runner.execute.side_effect = round1_results + round2_results

        loop = LoopBlock(
            block_id="loop_dispatch",
            inner_block_refs=["dispatch_work"],
            max_rounds=2,
        )

        state = WorkflowState()

        # Execute the loop with the dispatch block in the blocks dict
        final_state = await execute_loop_for_test(loop, state, blocks={"dispatch_work": dispatch})

        # After 2 rounds, conversation histories should exist for each branch
        histories = final_state.conversation_histories
        researcher_key = "dispatch_work_researcher"
        coder_key = "dispatch_work_coder"

        assert researcher_key in histories, (
            f"Expected history key '{researcher_key}' in {list(histories.keys())}"
        )
        assert coder_key in histories, (
            f"Expected history key '{coder_key}' in {list(histories.keys())}"
        )

        # Each branch history should have grown across rounds
        # Round 1 adds user+assistant (2 messages on top of any prior)
        # Round 2 reads round 1 history, adds user+assistant (so total = 4)
        researcher_hist = histories[researcher_key]
        coder_hist = histories[coder_key]
        assert len(researcher_hist) >= 4, (
            f"Expected researcher history >= 4 messages after 2 rounds, got {len(researcher_hist)}"
        )
        assert len(coder_hist) >= 4, (
            f"Expected coder history >= 4 messages after 2 rounds, got {len(coder_hist)}"
        )

    @pytest.mark.asyncio
    async def test_stateful_dispatch_round2_receives_round1_history(self):
        """In round 2, runner.execute is called with messages from round 1."""
        runner = _mock_runner()

        researcher_soul = Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research.",
        )
        coder_soul = Soul(
            id="coder", kind="soul", name="Coder", role="Coder", system_prompt="Code."
        )

        dispatch = DispatchBlock(
            "dispatch_work",
            [
                DispatchBranch("researcher", "Research Agent", researcher_soul, "Find papers"),
                DispatchBranch("coder", "Code Agent", coder_soul, "Write code"),
            ],
            runner,
        )
        dispatch.stateful = True

        runner.execute.side_effect = [
            # Round 1
            _make_exec_result("dispatch_work_researcher", "researcher", "R1 research", 0.01, 20),
            _make_exec_result("dispatch_work_coder", "coder", "R1 code", 0.01, 20),
            # Round 2
            _make_exec_result("dispatch_work_researcher", "researcher", "R2 research", 0.01, 20),
            _make_exec_result("dispatch_work_coder", "coder", "R2 code", 0.01, 20),
        ]

        loop = LoopBlock(
            block_id="loop_dispatch",
            inner_block_refs=["dispatch_work"],
            max_rounds=2,
        )

        state = WorkflowState()

        await execute_loop_for_test(loop, state, blocks={"dispatch_work": dispatch})

        # Inspect calls to runner.execute
        all_calls = runner.execute.call_args_list

        # Round 2 calls (calls 2 and 3, since round 1 was calls 0 and 1)
        # Each should have messages= containing the round 1 conversation
        round2_calls = all_calls[2:4]
        for call in round2_calls:
            # messages kwarg or positional arg
            kwargs = call.kwargs
            positional = call.args
            if "messages" in kwargs:
                messages = kwargs["messages"]
            elif len(positional) > 2:
                messages = positional[2]
            else:
                messages = None

            assert messages is not None, "Round 2 calls must include messages from round 1"
            assert len(messages) >= 2, (
                f"Round 2 should have prior history, got {len(messages)} messages"
            )

    @pytest.mark.asyncio
    async def test_histories_are_independent_per_exit(self):
        """Each branch's history is independent -- researcher doesn't see coder's history."""
        runner = _mock_runner()

        researcher_soul = Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research.",
        )
        coder_soul = Soul(
            id="coder", kind="soul", name="Coder", role="Coder", system_prompt="Code."
        )

        dispatch = DispatchBlock(
            "dispatch_work",
            [
                DispatchBranch("researcher", "Research Agent", researcher_soul, "Find papers"),
                DispatchBranch("coder", "Code Agent", coder_soul, "Write code"),
            ],
            runner,
        )
        dispatch.stateful = True

        runner.execute.side_effect = [
            _make_exec_result(
                "dispatch_work_researcher", "researcher", "RESEARCH_ONLY_R1", 0.01, 20
            ),
            _make_exec_result("dispatch_work_coder", "coder", "CODE_ONLY_R1", 0.01, 20),
            _make_exec_result(
                "dispatch_work_researcher", "researcher", "RESEARCH_ONLY_R2", 0.01, 20
            ),
            _make_exec_result("dispatch_work_coder", "coder", "CODE_ONLY_R2", 0.01, 20),
        ]

        loop = LoopBlock(
            block_id="loop_dispatch",
            inner_block_refs=["dispatch_work"],
            max_rounds=2,
        )

        state = WorkflowState()

        final_state = await execute_loop_for_test(loop, state, blocks={"dispatch_work": dispatch})

        # Researcher history should contain RESEARCH_ONLY, not CODE_ONLY
        researcher_hist = final_state.conversation_histories["dispatch_work_researcher"]
        researcher_text = " ".join(
            m.get("content", "") for m in researcher_hist if isinstance(m.get("content"), str)
        )
        assert "RESEARCH_ONLY" in researcher_text
        assert "CODE_ONLY" not in researcher_text

        # Coder history should contain CODE_ONLY, not RESEARCH_ONLY
        coder_hist = final_state.conversation_histories["dispatch_work_coder"]
        coder_text = " ".join(
            m.get("content", "") for m in coder_hist if isinstance(m.get("content"), str)
        )
        assert "CODE_ONLY" in coder_text
        assert "RESEARCH_ONLY" not in coder_text


# ===========================================================================
# Scenario 4: Context inheritance — current_task context flows to branches
# ===========================================================================


class TestContextInheritance:
    """DispatchBlock context flows from shared_memory['_resolved_inputs']['context']
    to all branches. Each branch has its own task_instruction."""

    @pytest.mark.asyncio
    async def test_branches_inherit_current_task_context(self):
        """Context from shared_memory['_resolved_inputs'] flows to all branches as 2nd arg."""
        runner = _mock_runner()

        researcher_soul = Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research.",
        )
        coder_soul = Soul(
            id="coder", kind="soul", name="Coder", role="Coder", system_prompt="Code."
        )

        dispatch = DispatchBlock(
            "dispatch_work",
            [
                DispatchBranch("researcher", "Research Agent", researcher_soul, "Find papers"),
                DispatchBranch("coder", "Code Agent", coder_soul, "Write code"),
            ],
            runner,
        )
        dispatch.declared_inputs = {"context": "shared_memory._resolved_inputs.context"}

        runner.execute.side_effect = [
            _make_exec_result("dispatch_work_researcher", "researcher", "Research done", 0.01, 20),
            _make_exec_result("dispatch_work_coder", "coder", "Code done", 0.01, 20),
        ]

        shared_context = "Project: Quantum Computing Initiative, Budget: $50k, Deadline: Q2 2026"
        state = WorkflowState(shared_memory={"_resolved_inputs": {"context": shared_context}})

        await execute_block_for_test(dispatch, state)

        # Both calls to runner.execute should have the context as 2nd positional arg
        assert runner.execute.call_count == 2

        for call in runner.execute.call_args_list:
            context_arg = call.args[1]  # 2nd positional arg is context
            assert context_arg is not None, "Branch context should be set"
            assert shared_context in (context_arg or ""), (
                f"Branch context should contain the shared_context, got '{context_arg}'"
            )

    @pytest.mark.asyncio
    async def test_branches_have_different_instructions_same_context(self):
        """Each branch has its own task_instruction but shares the same context."""
        runner = _mock_runner()

        researcher_soul = Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research.",
        )
        coder_soul = Soul(
            id="coder", kind="soul", name="Coder", role="Coder", system_prompt="Code."
        )

        dispatch = DispatchBlock(
            "dispatch_work",
            [
                DispatchBranch(
                    "researcher", "Research Agent", researcher_soul, "Find papers on QC"
                ),
                DispatchBranch("coder", "Code Agent", coder_soul, "Implement Grover's algorithm"),
            ],
            runner,
        )

        runner.execute.side_effect = [
            _make_exec_result("dispatch_work_researcher", "researcher", "Research done", 0.01, 20),
            _make_exec_result("dispatch_work_coder", "coder", "Code done", 0.01, 20),
        ]

        context = "Focus on efficiency"
        state = WorkflowState(shared_memory={"_resolved_inputs": {"context": context}})

        await execute_block_for_test(dispatch, state)

        calls = runner.execute.call_args_list
        instruction_0 = calls[0].args[0]  # 1st positional arg
        instruction_1 = calls[1].args[0]
        context_0 = calls[0].args[1]  # 2nd positional arg
        context_1 = calls[1].args[1]

        # Different instructions
        assert instruction_0 != instruction_1
        # Same context on both
        assert context_0 == context_1

    @pytest.mark.asyncio
    async def test_no_context_when_current_task_is_none(self):
        """When _resolved_inputs has no context, branches execute with context=None."""
        runner = _mock_runner()

        researcher_soul = Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research.",
        )

        dispatch = DispatchBlock(
            "dispatch_work",
            [DispatchBranch("researcher", "Research Agent", researcher_soul, "Find papers")],
            runner,
        )

        runner.execute.return_value = _make_exec_result(
            "dispatch_work_researcher", "researcher", "Done", 0.01, 20
        )

        # No context in shared_memory
        state = WorkflowState()

        final_state = await execute_block_for_test(dispatch, state)

        # Should complete without error
        assert "dispatch_work.researcher" in final_state.results
        # The context passed to runner should be None
        context_arg = runner.execute.call_args.args[1]
        assert context_arg is None

    @pytest.mark.asyncio
    @patch("runsight_core.llm.client.acompletion")
    async def test_context_inheritance_through_full_yaml_pipeline(self, mock_acompletion):
        """Full YAML pipeline: context set on WorkflowState.current_task flows to Dispatch branches."""
        captured_messages = []

        async def _mock_acompletion(**kwargs):
            messages = kwargs.get("messages", [])
            captured_messages.append(messages)

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Done"
            mock_response.choices[0].message.tool_calls = None
            mock_response.choices[0].finish_reason = "stop"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 10
            mock_response.usage.total_tokens = 20
            return mock_response

        mock_acompletion.side_effect = _mock_acompletion

        with patch("runsight_core.llm.client.completion_cost", return_value=0.001):
            wf = parse_workflow_yaml(DISPATCH_SYNTHESIZE_YAML)
            dispatch_block = wf.blocks["dispatch_work"]
            dispatch_block.declared_inputs = {"context": "shared_memory._resolved_inputs.context"}
            inner_dispatch = getattr(dispatch_block, "inner_block", None)
            if inner_dispatch is not None:
                inner_dispatch.declared_inputs = dict(dispatch_block.declared_inputs)
            important_context = "IMPORTANT_PROJECT_CONTEXT_XYZ"
            state = WorkflowState(
                shared_memory={"_resolved_inputs": {"context": important_context}}
            )
            await wf.run(state)

        # The first two LLM calls (Dispatch branches) should contain the context
        assert len(captured_messages) >= 2
        for branch_messages in captured_messages[:2]:
            all_content = " ".join(m.get("content", "") for m in branch_messages)
            assert important_context in all_content, (
                f"Branch LLM call should contain context '{important_context}', "
                f"got: {all_content[:200]}"
            )
