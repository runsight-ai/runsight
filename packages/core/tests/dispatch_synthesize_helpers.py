from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.primitives import Soul
from runsight_core.runner import ExecutionResult

FIXTURE_RUNNER_MODEL = "fixture-dispatch-synthesize-model"
FIXTURE_WORKFLOW_DIR = Path(__file__).parent / "fixtures" / "workflows"


def workflow_fixture_text(name: str) -> str:
    return (FIXTURE_WORKFLOW_DIR / name).read_text(encoding="utf-8")


def make_exec_result(
    task_id: str,
    soul_id: str,
    output: str,
    cost: float = 0.0,
    tokens: int = 0,
) -> ExecutionResult:
    return ExecutionResult(
        task_id=task_id,
        soul_id=soul_id,
        output=output,
        cost_usd=cost,
        total_tokens=tokens,
    )


def make_mock_runner():
    runner = MagicMock()
    runner.execute = AsyncMock()
    runner.model_name = FIXTURE_RUNNER_MODEL
    return runner


def patch_fixture_model_budget(monkeypatch) -> None:
    from runsight_core.memory import budget as budget_module

    original_get_model_info = budget_module.get_model_info

    def _get_model_info(model: str):
        if model == FIXTURE_RUNNER_MODEL:
            return {"max_input_tokens": 8192}
        return original_get_model_info(model)

    monkeypatch.setattr(budget_module, "get_model_info", _get_model_info)


def make_soul(soul_id: str, role: str, prompt: str) -> Soul:
    return Soul(
        id=soul_id,
        kind="soul",
        name=role,
        role=role,
        system_prompt=prompt,
    )


def make_researcher_soul() -> Soul:
    return make_soul("researcher", "Researcher", "Research.")


def make_coder_soul() -> Soul:
    return make_soul("coder", "Coder", "Code.")


def make_synthesizer_soul() -> Soul:
    return make_soul("synthesizer", "Synthesizer", "Synthesize.")


def make_dispatch_block(runner, *, researcher_task: str, coder_task: str) -> DispatchBlock:
    return DispatchBlock(
        "dispatch_work",
        [
            DispatchBranch(
                "researcher",
                "Research Agent",
                make_researcher_soul(),
                researcher_task,
            ),
            DispatchBranch("coder", "Code Agent", make_coder_soul(), coder_task),
        ],
        runner,
    )


def make_completion_response(
    content: str = "completed",
    prompt_tokens: int = 50,
    completion_tokens: int = 50,
    total_tokens: int = 100,
):
    message = MagicMock()
    message.content = content
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response
