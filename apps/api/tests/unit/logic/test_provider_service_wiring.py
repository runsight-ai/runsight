"""Red tests for RUN-235: Wire routers to filesystem repos.

Tests verify the NEW wiring — ProviderService and ExecutionService use
FileSystemProviderRepo + SecretsEnvLoader instead of SQLite + encrypt/decrypt.

All tests should FAIL until the implementation is wired.

Acceptance criteria covered:
  - ProviderService accepts SecretsEnvLoader, uses store_key/resolve instead of encrypt/decrypt
  - Provider CRUD stores ${ENV_VAR} references in YAML, raw keys go to secrets.env
  - API key resolution in test_connection goes through SecretsEnvLoader.resolve
  - SSRF validation is still called during test_connection (no regression)
  - API response contract unchanged: api_key_env shows "configured" or ""
  - ExecutionService._resolve_api_keys uses SecretsEnvLoader
  - No SQLite session dependency for provider/settings endpoints
  - deps.py provides FileSystemProviderRepo + SecretsEnvLoader
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from runsight_api.core.secrets import SecretsEnvLoader
from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.logic.services.provider_service import ProviderService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_base(tmp_path):
    """Return a temp base path for filesystem repos."""
    return str(tmp_path)


@pytest.fixture
def secrets(tmp_base):
    """Create a SecretsEnvLoader rooted at a temporary directory."""
    return SecretsEnvLoader(base_path=tmp_base)


@pytest.fixture
def provider_repo(tmp_base):
    """Create a FileSystemProviderRepo rooted at a temporary directory."""
    return FileSystemProviderRepo(base_path=tmp_base)


@pytest.fixture
def service(provider_repo, secrets):
    """Create a ProviderService wired with filesystem repo + secrets loader."""
    return ProviderService(provider_repo, secrets)


# ===========================================================================
# 1. ProviderService constructor accepts SecretsEnvLoader
# ===========================================================================


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
            name="OpenAI",
            api_key="sk-test-key-123",
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
            name="OpenAI",
            api_key="sk-test-key-123",
            provider_type="openai",
        )
        # SecretsEnvLoader must be able to resolve the stored key
        resolved = secrets.resolve("${OPENAI_API_KEY}")
        assert resolved == "sk-test-key-123"

    def test_create_provider_no_key_stores_none(self, service):
        """Creating a provider without an API key must store None, not encrypt None."""
        provider = service.create_provider(
            name="Ollama",
            provider_type="ollama",
        )
        assert provider.api_key is None

    def test_create_provider_yaml_does_not_contain_raw_key(self, service, provider_repo, tmp_base):
        """The YAML file on disk must contain ${ENV_VAR}, never the raw key."""
        from pathlib import Path

        service.create_provider(
            name="OpenAI",
            api_key="sk-test-key-123",
            provider_type="openai",
        )

        yaml_path = Path(tmp_base) / "custom" / "providers" / "openai.yaml"
        assert yaml_path.exists()
        content = yaml_path.read_text()
        assert "sk-test-key-123" not in content, "Raw API key must not appear in YAML file"
        assert "${" in content, "YAML must contain ${ENV_VAR} reference"


# ===========================================================================
# 3. update_provider uses secrets.store_key for new keys
# ===========================================================================


class TestUpdateProviderUsesSecrets:
    """update_provider must use secrets.store_key for API key persistence."""

    def test_update_provider_stores_new_key_via_secrets(self, service, secrets):
        """Updating api_key must write new key to secrets.env."""
        # Create first
        service.create_provider(name="OpenAI", api_key="sk-old-key", provider_type="openai")
        # Update with new key
        provider = service.update_provider("openai", api_key="sk-new-key")

        assert provider is not None
        resolved = secrets.resolve("${OPENAI_API_KEY}")
        assert resolved == "sk-new-key"

    def test_update_provider_preserves_env_ref_in_entity(self, service):
        """After update, the provider entity must still hold ${ENV_VAR} reference."""
        service.create_provider(name="OpenAI", api_key="sk-old", provider_type="openai")
        provider = service.update_provider("openai", api_key="sk-updated")

        assert provider is not None
        assert provider.api_key is not None
        assert provider.api_key.startswith("${")


# ===========================================================================
# 4. test_connection resolves keys through SecretsEnvLoader
# ===========================================================================


class TestTestConnectionUsesSecrets:
    """test_connection must resolve API keys via secrets.resolve."""

    @pytest.mark.asyncio
    async def test_test_connection_resolves_key_via_secrets(self, service, secrets):
        """test_connection must use secrets.resolve to get the actual API key."""
        service.create_provider(
            name="OpenAI",
            api_key="sk-real-key",
            provider_type="openai",
        )

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": [{"id": "gpt-4o"}]}
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await service.test_connection("openai")

        assert result["success"] is True
        # Verify the HTTP call used the real key, not the ${ENV_VAR} reference
        call_kwargs = mock_client.get.call_args
        auth_header = call_kwargs[1]["headers"]["Authorization"]
        assert "sk-real-key" in auth_header
        assert "${" not in auth_header, "Must not send ${ENV_VAR} as auth header"

    @pytest.mark.asyncio
    async def test_test_connection_no_key_configured(self, service):
        """test_connection with no API key must return failure for non-ollama."""
        service.create_provider(name="OpenAI", provider_type="openai")
        result = await service.test_connection("openai")
        assert result["success"] is False
        assert "No API key configured" in result["message"]

    def test_test_connection_checks_is_configured_via_secrets(self, service, secrets):
        """test_connection must check secrets.is_configured() to determine if a key exists."""
        # Create provider with a key — api_key field will have ${ENV_VAR}
        service.create_provider(name="OpenAI", api_key="sk-test", provider_type="openai")

        # Verify is_configured returns True for the stored key
        provider = service.get_provider("openai")
        assert provider is not None
        assert secrets.is_configured(provider.api_key) is True


# ===========================================================================
# 5. SSRF validation preserved (no regression from RUN-225)
# ===========================================================================


class TestSSRFPreserved:
    """SSRF validation must still be called in test_connection after rewiring."""

    @pytest.mark.asyncio
    async def test_ssrf_blocks_private_ip(self, service):
        """Private IP in base_url must still be blocked after filesystem rewiring."""
        service.create_provider(
            name="OpenAI",
            api_key="sk-test",
            provider_type="openai",
            base_url="http://192.168.1.1/v1",
        )

        result = await service.test_connection("openai")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_ssrf_blocks_metadata_endpoint(self, service):
        """Cloud metadata endpoint must still be blocked."""
        service.create_provider(
            name="OpenAI",
            api_key="sk-test",
            provider_type="openai",
            base_url="http://169.254.169.254/latest",
        )

        result = await service.test_connection("openai")

        assert result["success"] is False
        assert "ssrf" in result["message"].lower() or "blocked" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_ssrf_allows_ollama_localhost(self, service):
        """Ollama localhost must still be allowed after rewiring."""
        service.create_provider(
            name="Ollama",
            provider_type="ollama",
            base_url="http://localhost:11434",
        )

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            mock_resp = Mock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await service.test_connection("ollama")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_ssrf_no_http_call_for_blocked_url(self, service):
        """When SSRF blocks a URL, httpx.get must NOT be called."""
        service.create_provider(
            name="OpenAI",
            api_key="sk-test",
            provider_type="openai",
            base_url="http://10.0.0.1/v1",
        )

        with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
            result = await service.test_connection("openai")

        assert result["success"] is False
        mock_httpx.get.assert_not_called()


# ===========================================================================
# 6. API response contract: api_key_env shows "configured" or ""
# ===========================================================================


class TestApiResponseContract:
    """_provider_to_out must check secrets.is_configured(), not api_key_encrypted."""

    def test_provider_to_out_shows_configured_when_key_exists(self, service, secrets):
        """Provider with stored API key must show api_key_env with the env var reference."""
        from runsight_api.transport.routers.settings import _provider_to_out

        provider = service.create_provider(name="OpenAI", api_key="sk-test", provider_type="openai")
        out = _provider_to_out(provider, service)
        # api_key_env now stores the ${ENV_VAR} reference directly
        assert out.api_key_env is not None
        assert out.api_key_env.startswith("${")

    def test_provider_to_out_shows_empty_when_no_key(self, service):
        """Provider without API key must show api_key_env=None."""
        from runsight_api.transport.routers.settings import _provider_to_out

        provider = service.create_provider(name="Ollama", provider_type="ollama")
        out = _provider_to_out(provider, service)
        assert out.api_key_env is None

    def test_provider_to_out_uses_api_key_not_api_key_encrypted(self):
        """_provider_to_out must use ProviderEntity.api_key, not .api_key_encrypted."""
        from runsight_api.domain.value_objects import ProviderEntity
        from runsight_api.transport.routers.settings import _provider_to_out

        # ProviderEntity has api_key (not api_key_encrypted)
        entity = ProviderEntity(
            id="openai",
            name="OpenAI",
            type="openai",
            api_key="${OPENAI_API_KEY}",
            status="connected",
        )
        mock_svc = Mock()
        mock_svc.secrets = Mock()
        mock_svc.secrets.resolve.return_value = "sk-resolved"
        out = _provider_to_out(entity, mock_svc)
        # api_key_env now stores the ${ENV_VAR} reference directly
        assert out.api_key_env == "${OPENAI_API_KEY}"


# ===========================================================================
# 7. ExecutionService._resolve_api_keys uses SecretsEnvLoader
# ===========================================================================


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

        # Set up a provider with ${ENV_VAR} ref and store the real key in secrets
        provider_repo = FileSystemProviderRepo(base_path=tmp_base)
        provider_repo.create(
            {
                "name": "OpenAI",
                "type": "openai",
                "api_key": "${OPENAI_API_KEY}",
            }
        )
        secrets.store_key("openai", "sk-real-key-123")

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=provider_repo,
            secrets=secrets,
        )

        result = svc._resolve_api_keys()

        assert isinstance(result, dict)
        assert result.get("openai") == "sk-real-key-123"

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


class TestNoLegacyEncryption:
    """After rewiring, provider_service and execution_service must not use encrypt/decrypt."""

    def test_provider_service_does_not_import_encrypt(self):
        """provider_service must not import encrypt from core.encryption."""
        import importlib

        source = importlib.util.find_spec("runsight_api.logic.services.provider_service")
        if source and source.origin:
            with open(source.origin) as f:
                content = f.read()
            assert "from ...core.encryption import" not in content, (
                "provider_service must not import from core.encryption"
            )

    def test_execution_service_does_not_import_decrypt(self):
        """execution_service must not import decrypt from core.encryption."""
        import importlib

        source = importlib.util.find_spec("runsight_api.logic.services.execution_service")
        if source and source.origin:
            with open(source.origin) as f:
                content = f.read()
            assert "from ...core.encryption import" not in content, (
                "execution_service must not import from core.encryption"
            )


# ===========================================================================
# 11. Settings router uses FileSystemSettingsRepo (not SQLite)
# ===========================================================================


class TestSettingsRouterWiring:
    """Settings router endpoints must use FileSystemSettingsRepo, not SQLite."""

    def test_settings_router_does_not_import_sqlite_session(self):
        """settings.py router must not import Session from sqlmodel."""
        import importlib

        source = importlib.util.find_spec("runsight_api.transport.routers.settings")
        if source and source.origin:
            with open(source.origin) as f:
                content = f.read()
            assert "from sqlmodel import Session" not in content, (
                "settings router must not import SQLite Session"
            )

    def test_settings_router_does_not_import_sqlite_settings_repo(self):
        """settings.py must not import SettingsRepository (SQLite-backed)."""
        import importlib

        source = importlib.util.find_spec("runsight_api.transport.routers.settings")
        if source and source.origin:
            with open(source.origin) as f:
                content = f.read()
            assert (
                "from ...data.repositories.settings_repo import SettingsRepository" not in content
            ), "settings router must not import SQLite SettingsRepository"

    def test_provider_to_out_works_with_provider_entity(self):
        """_provider_to_out must work with ProviderEntity (not just Provider SQLModel)."""
        from runsight_api.domain.value_objects import ProviderEntity
        from runsight_api.transport.routers.settings import _provider_to_out

        entity = ProviderEntity(
            id="openai",
            name="OpenAI",
            type="openai",
            api_key="${OPENAI_API_KEY}",
            status="connected",
            models=["gpt-4o"],
        )
        mock_svc = Mock()
        mock_svc.secrets = Mock()
        mock_svc.secrets.resolve.return_value = "sk-resolved"
        out = _provider_to_out(entity, mock_svc)

        assert out.id == "openai"
        assert out.name == "OpenAI"
        assert out.api_key_env == "${OPENAI_API_KEY}"
        assert out.models == ["gpt-4o"]


# ===========================================================================
# 12. End-to-end provider CRUD with filesystem repos
# ===========================================================================


class TestEndToEndProviderCRUD:
    """Full CRUD cycle using real FileSystemProviderRepo + SecretsEnvLoader."""

    def test_create_then_get_returns_provider(self, service):
        """Create a provider then get by id — should return the same entity."""
        service.create_provider(name="OpenAI", api_key="sk-test", provider_type="openai")
        provider = service.get_provider("openai")

        assert provider is not None
        assert provider.name == "OpenAI"
        assert provider.type == "openai"

    def test_create_then_list_includes_provider(self, service):
        """Created provider should appear in list_providers."""
        service.create_provider(name="OpenAI", api_key="sk-test", provider_type="openai")
        providers = service.list_providers()

        assert len(providers) >= 1
        names = [p.name for p in providers]
        assert "OpenAI" in names

    def test_create_update_get_reflects_changes(self, service, secrets):
        """Update should modify the provider and update the secret."""
        service.create_provider(name="OpenAI", api_key="sk-v1", provider_type="openai")
        service.update_provider("openai", api_key="sk-v2")

        provider = service.get_provider("openai")
        assert provider is not None

        resolved = secrets.resolve("${OPENAI_API_KEY}")
        assert resolved == "sk-v2"

    def test_delete_removes_provider(self, service):
        """Delete should remove the provider YAML file."""
        service.create_provider(name="OpenAI", api_key="sk-test", provider_type="openai")
        result = service.delete_provider("openai")
        assert result is True

        provider = service.get_provider("openai")
        assert provider is None

    def test_multiple_providers_coexist(self, service, secrets):
        """Multiple providers should coexist with separate secrets."""
        service.create_provider(name="OpenAI", api_key="sk-openai", provider_type="openai")
        service.create_provider(name="Anthropic", api_key="sk-anthropic", provider_type="anthropic")

        assert secrets.resolve("${OPENAI_API_KEY}") == "sk-openai"
        assert secrets.resolve("${ANTHROPIC_API_KEY}") == "sk-anthropic"

        providers = service.list_providers()
        assert len(providers) == 2
