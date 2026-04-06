"""Red tests for RUN-127: RunsightTeamRunner._get_client resolves provider keys for override clients.

When a soul has a model_name override, _get_client creates a new LiteLLMClient
using the provider-key map supplied to the runner.
"""

from runsight_core.primitives import Soul


class TestGetClientResolvesApiKeys:
    def test_get_client_default_model_has_provider_key(self):
        """_get_client returns the default llm_client resolved from api_keys."""
        from runsight_core.runner import RunsightTeamRunner

        runner = RunsightTeamRunner(model_name="gpt-4o", api_keys={"openai": "sk-test-key"})
        soul = Soul(
            id="s1", role="test", system_prompt="test", provider="openai", model_name="gpt-4o"
        )
        client = runner._get_client(soul)
        assert client.api_key == "sk-test-key"

    def test_get_client_soul_override_model_has_provider_key(self):
        """When soul has a model_name override, the new LiteLLMClient gets the matching provider key."""
        from runsight_core.runner import RunsightTeamRunner

        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai", "anthropic": "sk-override-test"},
        )
        soul = Soul(
            id="s1",
            role="test",
            system_prompt="test",
            provider="anthropic",
            model_name="claude-3-opus-20240229",
        )
        client = runner._get_client(soul)
        assert client.api_key == "sk-override-test"

    def test_get_client_cached_override_has_provider_key(self):
        """Cached soul-override clients also retain the resolved provider key."""
        from runsight_core.runner import RunsightTeamRunner

        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai", "openai/text": "sk-cached"},
        )
        soul = Soul(
            id="s1",
            role="test",
            system_prompt="test",
            provider="openai",
            model_name="gpt-3.5-turbo",
        )
        client1 = runner._get_client(soul)
        client2 = runner._get_client(soul)
        assert client1 is client2
        assert client2.api_key == "sk-openai"
