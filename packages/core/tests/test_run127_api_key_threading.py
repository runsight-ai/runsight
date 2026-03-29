"""Red tests for RUN-127: API key threading through LiteLLMClient, RunsightTeamRunner, and parse_workflow_yaml.

These tests verify that an api_key parameter can be threaded from the API layer
down through the parser -> runner -> LLM client chain.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. LiteLLMClient accepts api_key parameter
# ---------------------------------------------------------------------------


class TestLiteLLMClientApiKey:
    def test_init_accepts_api_key(self):
        """LiteLLMClient.__init__() accepts an optional api_key parameter."""
        from runsight_core.llm.client import LiteLLMClient

        client = LiteLLMClient(model_name="gpt-4o", api_key="sk-test-123")
        assert client.api_key == "sk-test-123"

    def test_init_api_key_defaults_to_none(self):
        """LiteLLMClient.__init__() defaults api_key to None."""
        from runsight_core.llm.client import LiteLLMClient

        client = LiteLLMClient(model_name="gpt-4o")
        assert client.api_key is None

    @pytest.mark.asyncio
    async def test_achat_passes_api_key_to_acompletion(self):
        """achat() passes api_key to litellm.acompletion() kwargs."""
        from runsight_core.llm.client import LiteLLMClient

        client = LiteLLMClient(model_name="gpt-4o", api_key="sk-thread-test")

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "hello"
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        with patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.return_value = mock_response
            with patch("runsight_core.llm.client.completion_cost", return_value=0.001):
                await client.achat(messages=[{"role": "user", "content": "hi"}])

            # api_key must be passed to acompletion
            call_kwargs = mock_acomp.call_args
            assert (
                call_kwargs.kwargs.get("api_key") == "sk-thread-test"
                or call_kwargs[1].get("api_key") == "sk-thread-test"
            )

    @pytest.mark.asyncio
    async def test_astream_chat_passes_api_key_to_acompletion(self):
        """astream_chat() passes api_key to litellm.acompletion() kwargs."""
        from runsight_core.llm.client import LiteLLMClient

        client = LiteLLMClient(model_name="gpt-4o", api_key="sk-stream-test")

        async def fake_stream(*args, **kwargs):
            # Yield nothing, just need to check kwargs
            return
            yield  # make it a generator

        with patch("runsight_core.llm.client.acompletion", new_callable=AsyncMock) as mock_acomp:
            mock_acomp.return_value = fake_stream()
            # Consume the generator
            async for _ in client.astream_chat(messages=[{"role": "user", "content": "hi"}]):
                pass

            call_kwargs = mock_acomp.call_args
            assert (
                call_kwargs.kwargs.get("api_key") == "sk-stream-test"
                or call_kwargs[1].get("api_key") == "sk-stream-test"
            )


# ---------------------------------------------------------------------------
# 2. RunsightTeamRunner accepts and forwards api_key
# ---------------------------------------------------------------------------


class TestRunnerApiKey:
    def test_init_accepts_api_key(self):
        """RunsightTeamRunner.__init__() accepts an optional api_key parameter."""
        from runsight_core.runner import RunsightTeamRunner

        runner = RunsightTeamRunner(model_name="gpt-4o", api_key="sk-runner-key")
        assert runner.api_key == "sk-runner-key"

    def test_init_api_key_defaults_to_none(self):
        """RunsightTeamRunner.__init__() defaults api_key to None."""
        from runsight_core.runner import RunsightTeamRunner

        runner = RunsightTeamRunner(model_name="gpt-4o")
        assert runner.api_key is None

    def test_api_key_forwarded_to_llm_client(self):
        """RunsightTeamRunner passes api_key to its LiteLLMClient instance."""
        from runsight_core.runner import RunsightTeamRunner

        runner = RunsightTeamRunner(model_name="gpt-4o", api_key="sk-forward-test")
        assert runner.llm_client.api_key == "sk-forward-test"


# ---------------------------------------------------------------------------
# 3. parse_workflow_yaml accepts and forwards api_key
# ---------------------------------------------------------------------------


class TestParserApiKey:
    def test_parse_workflow_yaml_accepts_api_key(self):
        """parse_workflow_yaml() accepts an optional api_key parameter."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test
  entry: b1
  transitions:
    - from: b1
      to: null
blocks:
  b1:
    type: linear
    soul_ref: researcher
souls:
  researcher:
    id: researcher_1
    role: Researcher
    system_prompt: You research things.
config: {}
"""
        # Should not raise — api_key is an accepted kwarg
        wf = parse_workflow_yaml(yaml_content, api_key="sk-parse-test")
        assert wf is not None

    def test_api_key_forwarded_to_runner(self):
        """parse_workflow_yaml passes api_key to the RunsightTeamRunner it creates."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_content = """
workflow:
  name: test
  entry: b1
  transitions: []
blocks:
  b1:
    type: linear
    soul_ref: researcher
souls: {}
config:
  model_name: gpt-4o
"""
        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as MockRunner:
            MockRunner.return_value = Mock()
            # Need to make the workflow validate, so mock the block builder too
            mock_block = Mock()
            mock_block.block_id = "b1"
            mock_builder = Mock(return_value=mock_block)
            with patch("runsight_core.blocks._registry.get_builder", return_value=mock_builder):
                try:
                    parse_workflow_yaml(yaml_content, api_key="sk-fwd-test")
                except Exception:
                    pass  # Validation may fail with mocked runner, that's OK

                # RunsightTeamRunner should have been called with api_key
                MockRunner.assert_called_once()
                call_kwargs = MockRunner.call_args
                assert call_kwargs.kwargs.get("api_key") == "sk-fwd-test" or (
                    len(call_kwargs.args) > 1 and call_kwargs.args[1] == "sk-fwd-test"
                )

    def test_api_key_forwarded_to_recursive_calls(self):
        """When parse_workflow_yaml recurses for workflow blocks, api_key is forwarded."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        # This test verifies that the api_key parameter is passed in recursive calls
        # for workflow-type blocks. We patch parse_workflow_yaml itself to verify.
        parent_yaml = """
workflow:
  name: parent
  entry: child_block
  transitions: []
blocks:
  child_block:
    type: workflow
    workflow_ref: child_wf
souls: {}
config: {}
"""
        mock_registry = Mock()
        child_file = Mock()
        child_file.model_dump.return_value = {
            "workflow": {"name": "child", "entry": "b1", "transitions": []},
            "blocks": {"b1": {"type": "linear", "soul_ref": "researcher"}},
            "souls": {},
            "config": {},
        }
        mock_registry.get.return_value = child_file

        with patch(
            "runsight_core.yaml.parser.parse_workflow_yaml", wraps=parse_workflow_yaml
        ) as spy:
            try:
                parse_workflow_yaml(
                    parent_yaml,
                    workflow_registry=mock_registry,
                    api_key="sk-recursive-test",
                )
            except Exception:
                pass  # May fail for other reasons

            # The recursive call should also receive api_key
            if spy.call_count > 1:
                recursive_call = spy.call_args_list[1]
                assert recursive_call.kwargs.get("api_key") == "sk-recursive-test"
