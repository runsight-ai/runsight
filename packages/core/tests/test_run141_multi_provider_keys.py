"""Red tests for RUN-141: Multi-provider API key resolution (per-soul model overrides).

RunsightTeamRunner should accept `api_keys: Dict[str, str]` mapping provider_type -> key,
and _get_client() should resolve the correct key per soul's model provider.

All tests should FAIL until the implementation exists.
"""

import pytest
from runsight_core.primitives import Soul
from runsight_core.runner import RunsightTeamRunner

# ---------------------------------------------------------------------------
# 1. Runner accepts api_keys dict
# ---------------------------------------------------------------------------


class TestRunnerAcceptsApiKeysDict:
    def test_runner_accepts_api_keys_kwarg(self):
        """RunsightTeamRunner.__init__ accepts api_keys: Dict[str, str]."""
        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai-123", "anthropic": "sk-ant-456"},
        )
        assert runner.api_keys == {"openai": "sk-openai-123", "anthropic": "sk-ant-456"}

    def test_runner_api_keys_defaults_to_none(self):
        """api_keys defaults to None when not provided."""
        runner = RunsightTeamRunner(model_name="gpt-4o")
        assert runner.api_keys is None

    def test_runner_stores_api_keys_not_api_key(self):
        """When api_keys is provided, it is stored as api_keys and no legacy api_key attr is exposed."""
        keys = {"openai": "sk-openai", "anthropic": "sk-ant"}
        runner = RunsightTeamRunner(model_name="gpt-4o", api_keys=keys)
        assert hasattr(runner, "api_keys")
        assert runner.api_keys is keys
        assert not hasattr(runner, "api_key")


# ---------------------------------------------------------------------------
# 2. _get_client picks correct key per model's provider
# ---------------------------------------------------------------------------


class TestGetClientResolvesProviderKey:
    def test_openai_model_gets_openai_key(self):
        """For an OpenAI model (gpt-4o), _get_client uses api_keys['openai']."""
        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai-key", "anthropic": "sk-ant-key"},
        )
        soul = Soul(
            id="s1", role="test", system_prompt="test", provider="openai", model_name="gpt-4o"
        )
        # Default model is gpt-4o (OpenAI), so default client should have openai key
        client = runner._get_client(soul)
        assert client.api_key == "sk-openai-key"

    def test_anthropic_model_gets_anthropic_key(self):
        """For an Anthropic model override, _get_client uses api_keys['anthropic']."""
        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai-key", "anthropic": "sk-ant-key"},
        )
        soul = Soul(
            id="s1",
            role="test",
            system_prompt="test",
            provider="anthropic",
            model_name="claude-3-opus-20240229",
        )
        client = runner._get_client(soul)
        assert client.api_key == "sk-ant-key"

    def test_different_souls_get_different_keys(self):
        """Two souls with different providers get clients with different API keys."""
        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai-key", "anthropic": "sk-ant-key"},
        )
        openai_soul = Soul(
            id="s1", role="test", system_prompt="test", provider="openai", model_name="gpt-4o"
        )
        anthropic_soul = Soul(
            id="s2",
            role="test",
            system_prompt="test",
            provider="anthropic",
            model_name="claude-3-opus-20240229",
        )
        openai_client = runner._get_client(openai_soul)
        anthropic_client = runner._get_client(anthropic_soul)

        assert openai_client.api_key == "sk-openai-key"
        assert anthropic_client.api_key == "sk-ant-key"
        assert openai_client is not anthropic_client


# ---------------------------------------------------------------------------
# 3. Missing provider key -> descriptive error (not crash)
# ---------------------------------------------------------------------------


class TestMissingProviderKey:
    def test_missing_key_raises_descriptive_error(self):
        """If api_keys has no entry for a soul's model provider, raise a clear error."""
        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai-key"},  # no anthropic key
        )
        soul = Soul(
            id="s1",
            role="test",
            system_prompt="test",
            provider="anthropic",
            model_name="claude-3-opus-20240229",
        )
        with pytest.raises((KeyError, ValueError)) as exc_info:
            runner._get_client(soul)
        # Error message should mention the missing provider
        assert "anthropic" in str(exc_info.value).lower()

    def test_missing_key_error_mentions_model_name(self):
        """The error for a missing key should mention the model that triggered it."""
        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai-key"},
        )
        soul = Soul(
            id="s1",
            role="test",
            system_prompt="test",
            provider="anthropic",
            model_name="claude-3-opus-20240229",
        )
        with pytest.raises((KeyError, ValueError)) as exc_info:
            runner._get_client(soul)
        assert "claude-3-opus" in str(exc_info.value).lower()

    def test_empty_api_keys_dict_raises_on_any_model(self):
        """If api_keys is an empty dict, any model lookup should fail descriptively."""
        runner = RunsightTeamRunner(model_name="gpt-4o", api_keys={})
        soul = Soul(
            id="s1", role="test", system_prompt="test", provider="openai", model_name="gpt-4o"
        )
        with pytest.raises((KeyError, ValueError)):
            runner._get_client(soul)


# ---------------------------------------------------------------------------
# 4. Legacy single-key runner path is retired
# ---------------------------------------------------------------------------


class TestNoLegacySingleApiKey:
    def test_single_api_key_kwarg_is_rejected(self):
        """The runner no longer accepts the legacy api_key kwarg."""
        with pytest.raises(TypeError):
            RunsightTeamRunner(model_name="gpt-4o", api_key="sk-legacy-key")


# ---------------------------------------------------------------------------
# 5. Unknown model provider -> graceful error
# ---------------------------------------------------------------------------


class TestUnknownModelProvider:
    def test_unknown_model_provider_raises_descriptive_error(self):
        """A model name that cannot be mapped to a provider raises a clear error."""
        runner = RunsightTeamRunner(
            model_name="gpt-4o",
            api_keys={"openai": "sk-openai-key", "anthropic": "sk-ant-key"},
        )
        soul = Soul(
            id="s1",
            role="test",
            system_prompt="test",
            provider="unknown_provider",
            model_name="totally-unknown-model-xyz",
        )
        with pytest.raises((KeyError, ValueError)) as exc_info:
            runner._get_client(soul)
        # Error should mention the unrecognized model
        assert "totally-unknown-model-xyz" in str(exc_info.value).lower()
