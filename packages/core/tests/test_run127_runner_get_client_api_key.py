"""Red tests for RUN-127: RunsightTeamRunner._get_client forwards api_key to soul-override clients.

When a soul has a model_name override, _get_client creates a new LiteLLMClient.
That client must also receive the api_key that was passed to the runner.
"""

from runsight_core.primitives import Soul


class TestGetClientForwardsApiKey:
    def test_get_client_default_model_has_api_key(self):
        """_get_client returns the default llm_client which should have api_key set."""
        from runsight_core.runner import RunsightTeamRunner

        runner = RunsightTeamRunner(model_name="gpt-4o", api_key="sk-test-key")
        soul = Soul(id="s1", role="test", system_prompt="test")
        # soul has no model_name override, so default client is returned
        client = runner._get_client(soul)
        assert client.api_key == "sk-test-key"

    def test_get_client_soul_override_model_has_api_key(self):
        """When soul has a model_name override, the new LiteLLMClient gets api_key."""
        from runsight_core.runner import RunsightTeamRunner

        runner = RunsightTeamRunner(model_name="gpt-4o", api_key="sk-override-test")
        soul = Soul(
            id="s1",
            role="test",
            system_prompt="test",
            model_name="claude-3-opus-20240229",
        )
        # soul has a different model, so a new client is created
        client = runner._get_client(soul)
        assert client.api_key == "sk-override-test"

    def test_get_client_cached_override_has_api_key(self):
        """Cached soul-override clients also retain the api_key."""
        from runsight_core.runner import RunsightTeamRunner

        runner = RunsightTeamRunner(model_name="gpt-4o", api_key="sk-cached")
        soul = Soul(
            id="s1",
            role="test",
            system_prompt="test",
            model_name="gpt-3.5-turbo",
        )
        # Call twice to trigger caching
        client1 = runner._get_client(soul)
        client2 = runner._get_client(soul)
        assert client1 is client2
        assert client2.api_key == "sk-cached"
