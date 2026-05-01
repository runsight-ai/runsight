"""Environment variable resolution and LLM budget ownership behavior."""

from __future__ import annotations

import pytest


class TestLLMHandlerBudgetOwnership:
    """Engine-side LLM calls must leave budget enforcement to the IPC interceptor."""

    @staticmethod
    def _make_litellm_response(
        content: str = "done",
        prompt_tokens: int = 50,
        completion_tokens: int = 30,
        total_tokens: int = 80,
    ):
        from unittest.mock import MagicMock

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

    @pytest.mark.asyncio
    async def test_llm_handler_does_not_use_active_budget_context(self):
        """The IPC handler should return the paid response even when it exceeds cap."""
        from unittest.mock import AsyncMock, patch

        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation.handlers import make_llm_call_handler

        session = BudgetSession(scope_name="workflow:test", cost_cap_usd=0.001)
        token = _active_budget.set(session)
        try:
            handler = make_llm_call_handler({"fixture-provider": "dummy-provider-key"})
            with (
                patch(
                    "runsight_core.isolation.handlers._detect_provider",
                    return_value="fixture-provider",
                ),
                patch(
                    "runsight_core.llm.client.acompletion",
                    new_callable=AsyncMock,
                    return_value=self._make_litellm_response(total_tokens=100),
                ),
                patch("runsight_core.llm.client.completion_cost", return_value=0.002),
            ):
                chunks = [
                    chunk
                    async for chunk in handler(
                        {
                            "model": "fixture-model",
                            "messages": [{"role": "user", "content": "hi"}],
                        }
                    )
                ]
        finally:
            _active_budget.reset(token)

        assert len(chunks) == 1
        assert chunks[0]["cost_usd"] == pytest.approx(0.002)
        assert session.cost_usd == 0.0


# ---------------------------------------------------------------------------
# Behavior coverage
# ---------------------------------------------------------------------------


class TestEnvVarResolution:
    """${ENV_VAR} references in tool configs must be resolved at engine level."""

    def test_resolve_env_var_reference(self, monkeypatch):
        """${MY_VALUE} in a credential config resolves to the env var value."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        monkeypatch.setenv("MY_VALUE", "resolved-credential-value")

        config = {"Authorization": "Bearer ${MY_VALUE}"}
        resolved = resolve_credential_refs(config)

        assert resolved["Authorization"] == "Bearer resolved-credential-value"

    def test_resolve_multiple_refs_in_one_value(self, monkeypatch):
        """Multiple ${VAR} references in one string are all resolved."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        monkeypatch.setenv("USER_ID", "user-42")
        monkeypatch.setenv("API_VALUE", "s3cr3t")

        config = {"X-Custom": "${USER_ID}:${API_VALUE}"}
        resolved = resolve_credential_refs(config)

        assert resolved["X-Custom"] == "user-42:s3cr3t"

    def test_resolve_nested_dict(self, monkeypatch):
        """Nested dicts have their ${VAR} references resolved recursively."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        monkeypatch.setenv("DB_VALUE", "p@ssw0rd")

        config = {
            "headers": {"Authorization": "Basic ${DB_VALUE}"},
            "params": {"key": "${DB_VALUE}"},
        }
        resolved = resolve_credential_refs(config)

        assert resolved["headers"]["Authorization"] == "Basic p@ssw0rd"
        assert resolved["params"]["key"] == "p@ssw0rd"

    def test_plain_strings_unchanged(self):
        """Strings without ${...} are returned unchanged."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        config = {"host": "api.fixture.test", "port": "443"}
        resolved = resolve_credential_refs(config)

        assert resolved == config


# ---------------------------------------------------------------------------
# Behavior coverage
# ---------------------------------------------------------------------------


class TestUndefinedEnvVarError:
    """Undefined ${ENV_VAR} must produce a clear error, not silent empty string."""

    def test_undefined_var_raises(self):
        """Referencing an undefined env var raises a clear error."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        config = {"Authorization": "Bearer ${TOTALLY_UNDEFINED_VAR}"}

        with pytest.raises(Exception) as exc_info:
            resolve_credential_refs(config)

        error_msg = str(exc_info.value)
        assert "TOTALLY_UNDEFINED_VAR" in error_msg

    def test_undefined_var_not_empty_string(self, monkeypatch):
        """An undefined var must not silently become an empty string."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        # Make sure the var is truly undefined
        monkeypatch.delenv("NONEXISTENT_VALUE", raising=False)

        config = {"token": "${NONEXISTENT_VALUE}"}

        with pytest.raises(Exception):
            resolve_credential_refs(config)

    def test_error_message_names_the_variable(self):
        """The error message must name the undefined variable for debugging."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        config = {"key": "${MISSING_KEY_XYZ}"}

        with pytest.raises(Exception) as exc_info:
            resolve_credential_refs(config)

        assert "MISSING_KEY_XYZ" in str(exc_info.value)

    def test_partially_defined_config_reports_first_missing(self, monkeypatch):
        """When some vars exist and some don't, error names the missing one."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        monkeypatch.setenv("GOOD_VAR", "exists")

        config = {
            "good": "${GOOD_VAR}",
            "bad": "${MISSING_VALUE_999}",
        }

        with pytest.raises(Exception) as exc_info:
            resolve_credential_refs(config)

        assert "MISSING_VALUE_999" in str(exc_info.value)
