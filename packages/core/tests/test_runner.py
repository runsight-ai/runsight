import pytest
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner


@pytest.fixture
def sample_soul():
    return Soul(
        id="test_soul",
        kind="soul",
        name="Test Agent",
        role="Test Agent",
        system_prompt="You are a helpful test agent.",
        provider="openai",
        model_name="gpt-4o",
    )


def test_runner_requires_explicit_model_name():
    with pytest.raises(TypeError):
        RunsightTeamRunner()
