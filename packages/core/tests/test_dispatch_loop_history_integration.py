"""
Integration coverage for stateful dispatch branches inside LoopBlock.

Owner decision: this suite owns per-exit conversation history behavior across
loop rounds. Dispatch-to-synthesize wiring and context inheritance live in
separate suites.
"""

import pytest
from conftest import execute_loop_for_test
from dispatch_synthesize_helpers import (
    make_dispatch_block,
    make_exec_result,
    make_mock_runner,
    patch_fixture_model_budget,
)
from runsight_core.blocks.loop import LoopBlock
from runsight_core.state import WorkflowState


@pytest.fixture(autouse=True)
def _fixture_model_budget(monkeypatch):
    patch_fixture_model_budget(monkeypatch)


def _stateful_dispatch(runner):
    dispatch = make_dispatch_block(
        runner,
        researcher_task="Find papers",
        coder_task="Write code",
    )
    dispatch.stateful = True
    return dispatch


def _two_round_loop() -> LoopBlock:
    return LoopBlock(
        block_id="loop_dispatch",
        inner_block_refs=["dispatch_work"],
        max_rounds=2,
    )


def _message_text(messages) -> str:
    return " ".join(
        message.get("content", "")
        for message in messages
        if isinstance(message.get("content"), str)
    )


class TestStatefulDispatchLoopHistory:
    """Stateful dispatch branches preserve independent history across loop rounds."""

    @pytest.mark.asyncio
    async def test_per_exit_histories_accumulate_across_loop_rounds(self):
        runner = make_mock_runner()
        runner.execute.side_effect = [
            make_exec_result(
                "dispatch_work_researcher", "researcher", "Round 1 research", 0.02, 50
            ),
            make_exec_result("dispatch_work_coder", "coder", "Round 1 code", 0.03, 60),
            make_exec_result(
                "dispatch_work_researcher", "researcher", "Round 2 research", 0.02, 50
            ),
            make_exec_result("dispatch_work_coder", "coder", "Round 2 code", 0.03, 60),
        ]
        dispatch = _stateful_dispatch(runner)

        final_state = await execute_loop_for_test(
            _two_round_loop(),
            WorkflowState(),
            blocks={"dispatch_work": dispatch},
        )

        histories = final_state.conversation_histories
        assert "dispatch_work_researcher" in histories
        assert "dispatch_work_coder" in histories
        assert len(histories["dispatch_work_researcher"]) >= 4
        assert len(histories["dispatch_work_coder"]) >= 4

    @pytest.mark.asyncio
    async def test_second_loop_round_receives_first_round_history(self):
        runner = make_mock_runner()
        runner.execute.side_effect = [
            make_exec_result("dispatch_work_researcher", "researcher", "R1 research", 0.01, 20),
            make_exec_result("dispatch_work_coder", "coder", "R1 code", 0.01, 20),
            make_exec_result("dispatch_work_researcher", "researcher", "R2 research", 0.01, 20),
            make_exec_result("dispatch_work_coder", "coder", "R2 code", 0.01, 20),
        ]
        dispatch = _stateful_dispatch(runner)

        await execute_loop_for_test(
            _two_round_loop(),
            WorkflowState(),
            blocks={"dispatch_work": dispatch},
        )

        round2_research_call, round2_code_call = runner.execute.call_args_list[2:4]

        for call in (round2_research_call, round2_code_call):
            messages = call.kwargs.get("messages")
            if messages is None and len(call.args) > 2:
                messages = call.args[2]

            assert messages is not None
            assert len(messages) >= 2

        research_messages = round2_research_call.kwargs.get("messages")
        code_messages = round2_code_call.kwargs.get("messages")
        assert research_messages is not None
        assert code_messages is not None
        research_history_text = _message_text(research_messages)
        code_history_text = _message_text(code_messages)
        assert "R1 research" in research_history_text
        assert "R1 code" not in research_history_text
        assert "R1 code" in code_history_text
        assert "R1 research" not in code_history_text

    @pytest.mark.asyncio
    async def test_branch_histories_do_not_bleed_across_exits(self):
        runner = make_mock_runner()
        runner.execute.side_effect = [
            make_exec_result(
                "dispatch_work_researcher", "researcher", "RESEARCH_ONLY_R1", 0.01, 20
            ),
            make_exec_result("dispatch_work_coder", "coder", "CODE_ONLY_R1", 0.01, 20),
            make_exec_result(
                "dispatch_work_researcher", "researcher", "RESEARCH_ONLY_R2", 0.01, 20
            ),
            make_exec_result("dispatch_work_coder", "coder", "CODE_ONLY_R2", 0.01, 20),
        ]
        dispatch = _stateful_dispatch(runner)

        final_state = await execute_loop_for_test(
            _two_round_loop(),
            WorkflowState(),
            blocks={"dispatch_work": dispatch},
        )

        researcher_text = " ".join(
            m.get("content", "")
            for m in final_state.conversation_histories["dispatch_work_researcher"]
            if isinstance(m.get("content"), str)
        )
        coder_text = " ".join(
            m.get("content", "")
            for m in final_state.conversation_histories["dispatch_work_coder"]
            if isinstance(m.get("content"), str)
        )
        assert "RESEARCH_ONLY" in researcher_text
        assert "CODE_ONLY" not in researcher_text
        assert "CODE_ONLY" in coder_text
        assert "RESEARCH_ONLY" not in coder_text
