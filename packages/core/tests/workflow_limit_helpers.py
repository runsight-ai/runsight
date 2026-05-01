from pathlib import Path
from unittest.mock import MagicMock

from runsight_core.yaml.parser import parse_workflow_yaml

FIXTURE_LIMIT_MODEL = "fixture-workflow-limit-model"
FIXTURE_WORKFLOW_DIR = Path(__file__).parent / "fixtures" / "workflows"
FIXTURE_BASE_DIR = FIXTURE_WORKFLOW_DIR.parent


def parse_workflow_fixture(name: str):
    return parse_workflow_yaml(
        (FIXTURE_WORKFLOW_DIR / name).read_text(encoding="utf-8"),
        _base_dir=str(FIXTURE_BASE_DIR),
    )


def patch_fixture_model_budget(monkeypatch) -> None:
    from runsight_core.memory import budget as budget_module

    original_get_model_info = budget_module.get_model_info

    def _get_model_info(model: str):
        if model == FIXTURE_LIMIT_MODEL:
            return {"max_input_tokens": 8192}
        return original_get_model_info(model)

    monkeypatch.setattr(budget_module, "get_model_info", _get_model_info)


def make_litellm_response(
    content: str = "done",
    prompt_tokens: int = 50,
    completion_tokens: int = 30,
    total_tokens: int = 80,
):
    """Build the patched client response shape returned by acompletion."""
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
