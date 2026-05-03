"""ProviderService stores API keys through SecretsEnvLoader references."""

from runsight_api.core.secrets import SecretsEnvLoader
from runsight_api.logic.services.provider_service import ProviderService

pytest_plugins = ("tests.unit.logic.provider_service_fixtures",)


class TestProviderServiceAcceptsSecrets:
    """ProviderService.__init__ must accept (repo, secrets) — not just (repo)."""

    def test_constructor_accepts_secrets_parameter(self, provider_repo, secrets):
        """ProviderService(repo, secrets) must not raise."""
        svc = ProviderService(provider_repo, secrets)
        assert svc is not None

    def test_service_has_secrets_attribute(self, service):
        """ProviderService must store the SecretsEnvLoader as an attribute."""
        assert hasattr(service, "secrets"), (
            "ProviderService must have a 'secrets' attribute for SecretsEnvLoader"
        )
        assert isinstance(service.secrets, SecretsEnvLoader)


# ===========================================================================
# 2. create_provider stores ${ENV_VAR} ref, not encrypted blob
# ===========================================================================


class TestCreateProviderUsesSecrets:
    """create_provider must use secrets.store_key for API key persistence."""

    def test_create_provider_stores_env_var_reference(self, service, secrets):
        """After create, the provider's api_key field must be a ${...} reference."""
        provider = service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test-key-123",
            provider_type="openai",
        )
        # The provider entity must store ${ENV_VAR}, not a Fernet blob
        assert provider.api_key is not None
        assert provider.api_key.startswith("${"), (
            f"Expected ${{ENV_VAR}} reference, got: {provider.api_key!r}"
        )
        assert provider.api_key.endswith("}")

    def test_create_provider_writes_raw_key_to_secrets_env(self, service, secrets):
        """The raw API key must end up in secrets.env, not in the YAML file."""
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test-key-123",
            provider_type="openai",
        )
        # SecretsEnvLoader must be able to resolve the stored key
        resolved = secrets.resolve("${OPENAI_API_KEY}")
        assert resolved == "dummy-test-key-123"

    def test_create_provider_no_key_stores_none(self, service):
        """Creating a provider without an API key must store None, not encrypt None."""
        provider = service.create_provider(
            id="ollama",
            kind="provider",
            name="Ollama",
            provider_type="ollama",
        )
        assert provider.api_key is None

    def test_create_provider_yaml_does_not_contain_raw_key(self, service, provider_repo, tmp_base):
        """The YAML file on disk must contain ${ENV_VAR}, never the raw key."""
        from pathlib import Path

        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test-key-123",
            provider_type="openai",
        )

        yaml_path = Path(tmp_base) / "custom" / "providers" / "openai.yaml"
        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "dummy-test-key-123" not in content, "Raw API key must not appear in YAML file"
        assert "${" in content, "YAML must contain ${ENV_VAR} reference"


# ===========================================================================
# 3. update_provider uses secrets.store_key for new keys
# ===========================================================================


class TestUpdateProviderUsesSecrets:
    """update_provider must use secrets.store_key for API key persistence."""

    def test_update_provider_stores_new_key_via_secrets(self, service, secrets):
        """Updating api_key must write new key to secrets.env."""
        # Create first
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-old-key",
            provider_type="openai",
        )
        # Update with new key
        provider = service.update_provider(
            "openai", id="openai", kind="provider", api_key="dummy-new-key"
        )

        assert provider is not None
        resolved = secrets.resolve("${OPENAI_API_KEY}")
        assert resolved == "dummy-new-key"

    def test_update_provider_preserves_env_ref_in_entity(self, service):
        """After update, the provider entity must still hold ${ENV_VAR} reference."""
        service.create_provider(
            id="openai", kind="provider", name="OpenAI", api_key="dummy-old", provider_type="openai"
        )
        provider = service.update_provider(
            "openai", id="openai", kind="provider", api_key="dummy-updated"
        )

        assert provider is not None
        assert provider.api_key is not None
        assert provider.api_key.startswith("${")


# ===========================================================================
# 4. test_connection resolves keys through SecretsEnvLoader
# ===========================================================================
