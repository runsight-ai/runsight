"""Red tests for RUN-141: ExecutionService builds api_keys dict from provider table.

The API layer should query ALL configured providers, build a Dict[str, str] mapping
provider_type -> decrypted key, and pass it as api_keys to parse_workflow_yaml.

All tests should FAIL until the implementation exists.
"""

from unittest.mock import Mock, patch

import pytest

from runsight_api.logic.services.execution_service import ExecutionService


class TestResolveApiKeys:
    def test_resolve_api_keys_method_exists(self):
        """ExecutionService should have a _resolve_api_keys method (plural) returning dict."""
        svc = ExecutionService(run_repo=Mock(), workflow_repo=Mock(), provider_repo=Mock())
        assert hasattr(svc, "_resolve_api_keys"), (
            "ExecutionService must have _resolve_api_keys (plural) method"
        )

    def test_resolve_api_keys_returns_dict(self):
        """_resolve_api_keys returns Dict[str, str] (provider_type -> decrypted key)."""
        provider_repo = Mock()

        # Two active providers
        openai_provider = Mock()
        openai_provider.type = "openai"
        openai_provider.api_key_encrypted = "enc-openai"

        anthropic_provider = Mock()
        anthropic_provider.type = "anthropic"
        anthropic_provider.api_key_encrypted = "enc-anthropic"

        provider_repo.list_all.return_value = [openai_provider, anthropic_provider]

        svc = ExecutionService(run_repo=Mock(), workflow_repo=Mock(), provider_repo=provider_repo)

        with patch(
            "runsight_api.logic.services.execution_service.decrypt",
            side_effect=lambda x: f"decrypted-{x}",
        ):
            result = svc._resolve_api_keys()

        assert isinstance(result, dict)
        assert result == {
            "openai": "decrypted-enc-openai",
            "anthropic": "decrypted-enc-anthropic",
        }

    def test_resolve_api_keys_skips_providers_without_key(self):
        """Providers with no api_key_encrypted are skipped."""
        provider_repo = Mock()

        openai_provider = Mock()
        openai_provider.type = "openai"
        openai_provider.api_key_encrypted = "enc-openai"

        empty_provider = Mock()
        empty_provider.type = "anthropic"
        empty_provider.api_key_encrypted = None  # no key configured

        provider_repo.list_all.return_value = [openai_provider, empty_provider]

        svc = ExecutionService(run_repo=Mock(), workflow_repo=Mock(), provider_repo=provider_repo)

        with patch(
            "runsight_api.logic.services.execution_service.decrypt",
            side_effect=lambda x: f"decrypted-{x}",
        ):
            result = svc._resolve_api_keys()

        assert "openai" in result
        assert "anthropic" not in result

    def test_resolve_api_keys_includes_env_var_fallback(self):
        """If no DB provider exists for a type, env vars are checked as fallback."""
        import os

        provider_repo = Mock()
        provider_repo.list_all.return_value = []  # no DB providers

        svc = ExecutionService(run_repo=Mock(), workflow_repo=Mock(), provider_repo=provider_repo)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-openai"}, clear=False):
            result = svc._resolve_api_keys()

        assert result.get("openai") == "sk-env-openai"


class TestLaunchExecutionPassesApiKeys:
    @pytest.mark.asyncio
    async def test_launch_execution_passes_api_keys_to_parser(self):
        """launch_execution calls parse_workflow_yaml with api_keys= (dict), not api_key= (str)."""
        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()

        mock_entity = Mock()
        mock_entity.yaml = """
workflow:
  name: test
  entry: b1
  transitions:
    - from: b1
      to: null
blocks:
  b1:
    type: placeholder
    description: test
souls: {}
config: {}
"""
        workflow_repo.get_by_id.return_value = mock_entity

        openai_provider = Mock()
        openai_provider.type = "openai"
        openai_provider.api_key_encrypted = "enc-openai"
        provider_repo.list_all.return_value = [openai_provider]
        provider_repo.get_by_type.return_value = openai_provider

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
        )

        with (
            patch(
                "runsight_api.logic.services.execution_service.parse_workflow_yaml"
            ) as mock_parse,
            patch(
                "runsight_api.logic.services.execution_service.decrypt",
                return_value="sk-decrypted-openai",
            ),
        ):
            from unittest.mock import AsyncMock

            mock_wf = AsyncMock()
            mock_wf.run = AsyncMock()
            mock_parse.return_value = mock_wf

            await svc.launch_execution("run_1", "wf_1", {"instruction": "test"})

            mock_parse.assert_called_once()
            call_kwargs = mock_parse.call_args.kwargs
            # Must use api_keys (dict), not api_key (string)
            assert "api_keys" in call_kwargs, (
                f"Expected parse_workflow_yaml called with api_keys=, got kwargs: {call_kwargs}"
            )
            assert isinstance(call_kwargs["api_keys"], dict)
