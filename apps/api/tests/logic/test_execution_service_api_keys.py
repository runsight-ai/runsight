"""ExecutionService builds api_keys dict from provider table.

The API layer should query ALL configured providers, build a Dict[str, str] mapping
provider_type -> decrypted key, and pass it as api_keys to parse_workflow_yaml.
"""

from unittest.mock import Mock, patch

import pytest

from runsight_api.logic.services.execution_service import ExecutionService, PreparedRunInputs
from runsight_core.redaction import RunRedactor


def _prepared_inputs(inputs):
    return PreparedRunInputs(
        normalized_inputs=inputs,
        input_redactor=RunRedactor(),
    )


class TestResolveApiKeys:
    def test_resolve_api_keys_returns_dict(self):
        """_resolve_api_keys returns Dict[str, str] (provider_type -> resolved key)."""
        provider_repo = Mock()
        secrets = Mock()

        # Two active providers
        primary_provider = Mock()
        primary_provider.type = "primary-provider"
        primary_provider.api_key = "${DUMMY_PRIMARY_PROVIDER_TOKEN}"

        backup_provider = Mock()
        backup_provider.type = "backup-provider"
        backup_provider.api_key = "${DUMMY_BACKUP_PROVIDER_TOKEN}"

        provider_repo.list_all.return_value = [primary_provider, backup_provider]
        secrets.resolve.side_effect = lambda x: f"decrypted-{x}"

        svc = ExecutionService(
            run_repo=Mock(), workflow_repo=Mock(), provider_repo=provider_repo, secrets=secrets
        )

        result = svc._resolve_api_keys()

        assert isinstance(result, dict)
        assert result == {
            "primary-provider": "decrypted-${DUMMY_PRIMARY_PROVIDER_TOKEN}",
            "backup-provider": "decrypted-${DUMMY_BACKUP_PROVIDER_TOKEN}",
        }

    def test_resolve_api_keys_skips_providers_without_key(self):
        """Providers with no api_key are skipped."""
        provider_repo = Mock()
        secrets = Mock()

        primary_provider = Mock()
        primary_provider.type = "primary-provider"
        primary_provider.api_key = "${DUMMY_PRIMARY_PROVIDER_TOKEN}"

        empty_provider = Mock()
        empty_provider.type = "backup-provider"
        empty_provider.api_key = None  # no key configured

        provider_repo.list_all.return_value = [primary_provider, empty_provider]
        secrets.resolve.side_effect = lambda x: f"decrypted-{x}"

        svc = ExecutionService(
            run_repo=Mock(), workflow_repo=Mock(), provider_repo=provider_repo, secrets=secrets
        )

        result = svc._resolve_api_keys()

        assert "primary-provider" in result
        assert "backup-provider" not in result

    def test_resolve_api_keys_includes_env_var_fallback(self):
        """If no DB provider exists for a type, env vars are checked as fallback."""
        import os

        provider_repo = Mock()
        provider_repo.list_all.return_value = []  # no DB providers

        svc = ExecutionService(run_repo=Mock(), workflow_repo=Mock(), provider_repo=provider_repo)

        # The fallback map is intentionally provider-specific in production code.
        with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy-env-openai-key"}, clear=True):
            result = svc._resolve_api_keys()

        assert result.get("openai") == "dummy-env-openai-key"


class TestLaunchExecutionPassesApiKeys:
    @pytest.mark.asyncio
    async def test_launch_execution_passes_api_keys_to_parser(self):
        """launch_execution calls parse_workflow_yaml with api_keys= (dict), not api_key= (str)."""
        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        secrets = Mock()

        mock_entity = Mock()
        mock_entity.yaml = """
version: "1.0"
id: api-key-resolution-workflow
kind: workflow
workflow:
  name: API Key Resolution Workflow
  entry: api-key-resolution-step
  transitions:
    - from: api-key-resolution-step
      to: null
blocks:
  api-key-resolution-step:
    type: linear
    soul_ref: api-key-resolution-soul
souls:
  api-key-resolution-soul:
    id: api-key-resolution-soul
    kind: soul
    name: API Key Resolution Soul
    role: API key resolution tester
    system_prompt: hello
    provider: openai
    model_name: openai/fixture-chat-model
config: {}
"""
        workflow_repo.get_by_id.return_value = mock_entity

        # The launch path instantiates RunsightTeamRunner before the parser mock,
        # so this fixture uses a provider-qualified model that LiteLLM can classify.
        fixture_provider = Mock()
        fixture_provider.id = "openai"
        fixture_provider.type = "openai"
        fixture_provider.is_active = True
        fixture_provider.models = ["openai/fixture-chat-model"]
        fixture_provider.api_key = "${DUMMY_FIXTURE_PROVIDER_TOKEN}"
        provider_repo.list_all.return_value = [fixture_provider]
        provider_repo.get_by_type.return_value = fixture_provider
        secrets.resolve.return_value = "dummy-decrypted-fixture-key"

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            secrets=secrets,
        )

        with patch(
            "runsight_api.logic.services.execution_service.parse_workflow_yaml"
        ) as mock_parse:
            from unittest.mock import AsyncMock

            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution(
                "api-key-resolution-run",
                "api-key-resolution-workflow",
                _prepared_inputs({"instruction": "test"}),
                branch=None,
            )

            mock_parse.assert_called_once()
            call_kwargs = mock_parse.call_args.kwargs
            # Must use api_keys (dict), not api_key (string)
            assert "api_keys" in call_kwargs, (
                f"Expected parse_workflow_yaml called with api_keys=, got kwargs: {call_kwargs}"
            )
            assert isinstance(call_kwargs["api_keys"], dict)
