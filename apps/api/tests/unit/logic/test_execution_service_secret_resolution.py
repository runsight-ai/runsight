"""ExecutionService resolves provider API keys through SecretsEnvLoader."""

from unittest.mock import Mock


from runsight_api.core.secrets import SecretsEnvLoader
from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo

pytest_plugins = ("tests.unit.logic.provider_service_fixtures",)


class TestExecutionServiceUsesSecrets:
    """ExecutionService must accept SecretsEnvLoader and resolve keys through it."""

    def test_execution_service_accepts_secrets_param(self, secrets):
        """ExecutionService constructor must accept a secrets parameter."""
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            secrets=secrets,
        )
        assert svc is not None

    def test_execution_service_has_secrets_attribute(self, secrets):
        """ExecutionService must store the SecretsEnvLoader."""
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            secrets=secrets,
        )
        assert hasattr(svc, "secrets")
        assert isinstance(svc.secrets, SecretsEnvLoader)

    def test_resolve_api_keys_uses_secrets_resolve(self, tmp_base, secrets):
        """_resolve_api_keys must call secrets.resolve()."""
        from runsight_api.logic.services.execution_service import ExecutionService

        # Set up a provider with ${ENV_VAR} ref and store the resolved value in secrets.
        provider_repo = FileSystemProviderRepo(base_path=tmp_base)
        provider_repo.create(
            {
                "id": "openai",
                "kind": "provider",
                "name": "OpenAI",
                "type": "openai",
                "api_key": "${OPENAI_API_KEY}",
            }
        )
        secrets.store_key("openai", "dummy-stored-key-123")

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=provider_repo,
            secrets=secrets,
        )

        result = svc._resolve_api_keys()

        assert isinstance(result, dict)
        assert result.get("openai") == "dummy-stored-key-123"

    def test_resolve_api_keys_skips_provider_without_api_key(self, secrets):
        """Providers with no api_key ref should be skipped."""
        from runsight_api.logic.services.execution_service import ExecutionService

        provider_repo = Mock()
        provider_no_key = Mock()
        provider_no_key.type = "anthropic"
        provider_no_key.api_key = None
        provider_repo.list_all.return_value = [provider_no_key]

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=provider_repo,
            secrets=secrets,
        )

        result = svc._resolve_api_keys()
        assert "anthropic" not in result


# ===========================================================================
# 8. deps.py provides filesystem repos and SecretsEnvLoader
# ===========================================================================


# ===========================================================================
# 8. No encrypt/decrypt imports in rewired modules
# ===========================================================================
