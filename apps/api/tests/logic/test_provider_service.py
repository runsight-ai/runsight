import inspect

import pytest
from pydantic import ValidationError

from unittest.mock import AsyncMock, Mock, patch

from runsight_api.domain.value_objects import ProviderEntity
from runsight_api.logic.services.provider_service import (
    ProviderService,
    _infer_provider_type,
)

# --- _infer_provider_type ---


def test_infer_provider_type_openai():
    assert _infer_provider_type("OpenAI") == "openai"
    assert _infer_provider_type("openai-api") == "openai"


def test_infer_provider_type_claude_to_anthropic():
    assert _infer_provider_type("Claude") == "anthropic"
    assert _infer_provider_type("claude-api") == "anthropic"


def test_infer_provider_type_anthropic_direct():
    assert _infer_provider_type("Anthropic") == "anthropic"


def test_infer_provider_type_google():
    assert _infer_provider_type("Google") == "google"
    assert _infer_provider_type("Gemini") == "google"


def test_infer_provider_type_unknown_custom():
    assert _infer_provider_type("Unknown Provider") == "custom"
    assert _infer_provider_type("MyCustomAPI") == "custom"


def test_infer_provider_type_case_insensitive():
    assert _infer_provider_type("OPENAI") == "openai"
    assert _infer_provider_type("openai") == "openai"


# --- list_providers ---


def test_list_providers_empty():
    repo = Mock()
    secrets = Mock()
    repo.list_all.return_value = []
    service = ProviderService(repo, secrets)
    result = service.list_providers()
    assert result == []
    repo.list_all.assert_called_once()


def test_list_providers_multiple():
    repo = Mock()
    secrets = Mock()
    providers = [
        ProviderEntity(id="provider-one", kind="provider", name="Provider One", type="openai"),
        ProviderEntity(id="provider-two", kind="provider", name="Provider Two", type="anthropic"),
    ]
    repo.list_all.return_value = providers
    service = ProviderService(repo, secrets)
    result = service.list_providers()
    assert result == providers
    assert len(result) == 2


# --- get_provider ---


def test_get_provider_exists():
    repo = Mock()
    secrets = Mock()
    prov = ProviderEntity(id="openai-provider", kind="provider", name="OpenAI", type="openai")
    repo.get_by_id.return_value = prov
    service = ProviderService(repo, secrets)
    result = service.get_provider("openai-provider")
    assert result == prov
    assert result.id == "openai-provider"


def test_get_provider_not_found_returns_none():
    repo = Mock()
    secrets = Mock()
    repo.get_by_id.return_value = None
    service = ProviderService(repo, secrets)
    result = service.get_provider("missing")
    assert result is None


# --- create_provider ---


def test_create_provider_happy_path():
    repo = Mock()
    secrets = Mock()
    secrets.store_key.return_value = "${OPENAI_API_KEY}"
    created = None

    def capture_create(data):
        nonlocal created
        created = data
        return ProviderEntity(
            id=data["id"],
            kind=data["kind"],
            name=data["name"],
            type=data["type"],
            api_key=data.get("api_key"),
            base_url=data.get("base_url"),
        )

    repo.create.side_effect = capture_create
    service = ProviderService(repo, secrets)
    service.create_provider(
        id="openai",
        kind="provider",
        name="OpenAI",
        api_key="sk-xxx",
        base_url="https://api.openai.com/v1",
        provider_type="openai",
    )
    assert created is not None
    assert created["id"] == "openai"
    assert created["kind"] == "provider"
    assert created["name"] == "OpenAI"
    assert created["type"] == "openai"
    assert created["api_key"] == "${OPENAI_API_KEY}"
    assert created["base_url"] == "https://api.openai.com/v1"
    secrets.store_key.assert_called_once_with("openai", "sk-xxx")


def test_create_provider_type_inferred_from_name_openai():
    repo = Mock()
    secrets = Mock()
    secrets.store_key.return_value = "${OPENAI_API_KEY}"

    def capture_create(data):
        return ProviderEntity(
            id=data["id"],
            kind=data["kind"],
            name=data["name"],
            type=data["type"],
        )

    repo.create.side_effect = capture_create
    service = ProviderService(repo, secrets)
    result = service.create_provider(id="openai", kind="provider", name="OpenAI", api_key="sk-x")
    assert result.type == "openai"
    assert result.id == "openai"


def test_create_provider_type_inferred_from_name_claude():
    repo = Mock()
    secrets = Mock()
    secrets.store_key.return_value = "${ANTHROPIC_API_KEY}"
    repo.create.side_effect = lambda data: ProviderEntity(
        id=data["id"], kind=data["kind"], name=data["name"], type=data["type"]
    )
    service = ProviderService(repo, secrets)
    result = service.create_provider(
        id="claude-api", kind="provider", name="Claude API", api_key="sk-x"
    )
    assert result.type == "anthropic"
    assert result.id == "claude-api"


def test_create_provider_type_inferred_unknown_to_custom():
    repo = Mock()
    secrets = Mock()
    secrets.store_key.return_value = "${CUSTOM_API_KEY}"
    repo.create.side_effect = lambda data: ProviderEntity(
        id=data["id"], kind=data["kind"], name=data["name"], type=data["type"]
    )
    service = ProviderService(repo, secrets)
    result = service.create_provider(
        id="unknown-provider", kind="provider", name="Unknown Provider", api_key="key"
    )
    assert result.type == "custom"
    assert result.id == "unknown-provider"


def test_create_provider_signature_requires_explicit_id_and_kind():
    params = list(inspect.signature(ProviderService.create_provider).parameters)
    assert params[:3] == ["self", "id", "kind"]


def test_create_provider_rejects_invalid_embedded_id():
    repo = Mock()
    secrets = Mock()
    service = ProviderService(repo, secrets)

    with pytest.raises(ValidationError):
        service.create_provider(
            id="http",
            kind="provider",
            name="HTTP",
            provider_type="custom",
        )

    repo.create.assert_not_called()


# --- update_provider ---


def test_update_provider_happy_path():
    repo = Mock()
    secrets = Mock()
    secrets.store_key.return_value = "${OPENAI_API_KEY}"
    prov = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="Old",
        type="openai",
        base_url="https://old.com",
    )
    repo.get_by_id.return_value = prov
    repo.update.return_value = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="New Name",
        type="openai",
        api_key="${OPENAI_API_KEY}",
        base_url="https://new.com",
    )
    service = ProviderService(repo, secrets)
    result = service.update_provider(
        "openai-provider",
        id="openai-provider",
        kind="provider",
        name="New Name",
        api_key="new_key",
        base_url="https://new.com",
    )
    assert result is not None
    assert result.name == "New Name"
    assert result.api_key == "${OPENAI_API_KEY}"
    assert result.base_url == "https://new.com"
    secrets.store_key.assert_called_once_with("openai", "new_key")


def test_update_provider_not_found_returns_none():
    repo = Mock()
    secrets = Mock()
    repo.get_by_id.return_value = None
    service = ProviderService(repo, secrets)
    result = service.update_provider("missing", id="missing", kind="provider", name="New")
    assert result is None
    repo.update.assert_not_called()


def test_update_provider_partial_update():
    repo = Mock()
    secrets = Mock()
    prov = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="Original",
        type="openai",
        base_url="https://a.com",
    )
    repo.get_by_id.return_value = prov
    repo.update.return_value = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="Updated",
        type="openai",
        base_url="https://a.com",
    )
    service = ProviderService(repo, secrets)
    result = service.update_provider(
        "openai-provider", id="openai-provider", kind="provider", name="Updated"
    )
    assert result.name == "Updated"
    assert result.base_url == "https://a.com"  # unchanged
    secrets.store_key.assert_not_called()


def test_update_provider_preserves_embedded_identity_in_repo_payload():
    repo = Mock()
    secrets = Mock()
    prov = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="Original",
        type="openai",
        base_url="https://a.com",
    )
    repo.get_by_id.return_value = prov
    repo.update.return_value = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="Updated",
        type="openai",
        base_url="https://a.com",
    )
    service = ProviderService(repo, secrets)

    result = service.update_provider(
        "openai-provider", id="openai-provider", kind="provider", name="Updated"
    )

    assert result.name == "Updated"
    update_data = repo.update.call_args.args[1]
    assert update_data["id"] == "openai-provider"
    assert update_data["kind"] == "provider"


# --- delete_provider ---


def test_delete_provider_exists_returns_true():
    repo = Mock()
    secrets = Mock()
    repo.delete.return_value = True
    service = ProviderService(repo, secrets)
    result = service.delete_provider("openai-provider")
    assert result is True
    repo.delete.assert_called_once_with("openai-provider")


def test_delete_provider_not_found_returns_false():
    repo = Mock()
    secrets = Mock()
    repo.delete.return_value = False
    service = ProviderService(repo, secrets)
    result = service.delete_provider("missing")
    assert result is False


def test_delete_provider_removes_managed_secret_before_delete():
    repo = Mock()
    secrets = Mock()
    repo.get_by_id.return_value = ProviderEntity(
        id="openai",
        kind="provider",
        name="OpenAI",
        type="openai",
        api_key="${OPENAI_API_KEY}",
    )
    repo.delete.return_value = True

    service = ProviderService(repo, secrets)
    result = service.delete_provider("openai")

    assert result is True
    repo.get_by_id.assert_called_once_with("openai")
    secrets.remove_key.assert_called_once_with("${OPENAI_API_KEY}")
    repo.delete.assert_called_once_with("openai")


def test_delete_provider_skips_secret_cleanup_without_api_key_reference():
    repo = Mock()
    secrets = Mock()
    repo.get_by_id.return_value = ProviderEntity(
        id="ollama",
        kind="provider",
        name="Ollama",
        type="ollama",
        api_key=None,
    )
    repo.delete.return_value = True

    service = ProviderService(repo, secrets)
    result = service.delete_provider("ollama")

    assert result is True
    secrets.remove_key.assert_not_called()
    repo.delete.assert_called_once_with("ollama")


# --- test_connection ---


@pytest.mark.asyncio
async def test_test_connection_provider_not_found():
    repo = Mock()
    secrets = Mock()
    repo.get_by_id.return_value = None
    service = ProviderService(repo, secrets)
    result = await service.test_connection("missing")
    assert result["success"] is False
    assert "provider:missing" in result["message"]
    assert result["model_count"] == 0
    assert result["latency_ms"] >= 0
    repo.get_by_id.assert_called_once_with("missing")
    repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_test_credentials_provider_not_found_uses_kind_qualified_ref():
    repo = Mock()
    secrets = Mock()
    repo.get_by_id.return_value = None
    service = ProviderService(repo, secrets)

    result = await service.test_credentials(provider_id="missing")

    assert result["success"] is False
    assert "provider:missing" in result["message"]
    assert result["model_count"] == 0
    assert result["latency_ms"] >= 0
    repo.get_by_id.assert_called_once_with("missing")
    repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_test_connection_no_api_key_non_ollama():
    repo = Mock()
    secrets = Mock()
    secrets.is_configured.return_value = False
    prov = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="OpenAI",
        type="openai",
        api_key=None,
    )
    repo.get_by_id.return_value = prov
    service = ProviderService(repo, secrets)
    result = await service.test_connection("openai-provider")
    assert result["success"] is False
    assert result["message"] == "No API key configured"
    assert result["model_count"] == 0
    assert result["latency_ms"] >= 0
    repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_test_connection_ollama_no_api_key_allowed():
    repo = Mock()
    secrets = Mock()
    prov = ProviderEntity(
        id="ollama-provider",
        kind="provider",
        name="Ollama",
        type="ollama",
        api_key=None,
        base_url="http://localhost:11434",
    )
    repo.get_by_id.return_value = prov
    service = ProviderService(repo, secrets)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.AsyncClient.return_value = mock_client

        result = await service.test_connection("ollama-provider")

    assert result["success"] is True
    assert "llama3" in result.get("models", [])
    assert result["model_count"] == 1
    assert result["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_test_connection_successful_openai():
    repo = Mock()
    secrets = Mock()
    secrets.is_configured.return_value = True
    secrets.resolve.return_value = "sk-xxx"
    prov = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="OpenAI",
        type="openai",
        api_key="${OPENAI_API_KEY}",
        base_url="https://api.openai.com/v1",
    )
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo, secrets)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "gpt-4o"}, {"id": "gpt-3.5"}]}
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.AsyncClient.return_value = mock_client

        result = await service.test_connection("openai-provider")

    assert result["success"] is True
    assert "gpt-4o" in result.get("models", [])
    assert "gpt-3.5" in result.get("models", [])
    assert result["model_count"] == 2
    assert result["latency_ms"] >= 0
    mock_client.get.assert_called_once()
    call_kwargs = mock_client.get.call_args[1]
    assert "Bearer sk-xxx" in call_kwargs["headers"]["Authorization"]
    repo.update.assert_called_once_with(
        "openai-provider",
        {
            "id": "openai-provider",
            "kind": "provider",
            "status": "connected",
            "models": ["gpt-3.5", "gpt-4o"],
            "last_status_check": repo.update.call_args.args[1]["last_status_check"],
            "updated_at": repo.update.call_args.args[1]["updated_at"],
        },
    )


@pytest.mark.asyncio
async def test_test_connection_http_error():
    repo = Mock()
    secrets = Mock()
    secrets.is_configured.return_value = True
    secrets.resolve.return_value = "sk-xxx"
    prov = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="OpenAI",
        type="openai",
        api_key="${OPENAI_API_KEY}",
    )
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo, secrets)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 401
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.AsyncClient.return_value = mock_client

        result = await service.test_connection("openai-provider")

    assert result["success"] is False
    assert "401" in result["message"]
    assert result["model_count"] == 0
    assert result["latency_ms"] >= 0
    repo.update.assert_called_once_with(
        "openai-provider",
        {
            "id": "openai-provider",
            "kind": "provider",
            "status": "error",
            "models": [],
            "last_status_check": repo.update.call_args.args[1]["last_status_check"],
            "updated_at": repo.update.call_args.args[1]["updated_at"],
        },
    )


@pytest.mark.asyncio
async def test_test_connection_timeout_exception():
    repo = Mock()
    secrets = Mock()
    secrets.is_configured.return_value = True
    secrets.resolve.return_value = "sk-xxx"
    prov = ProviderEntity(
        id="openai-provider",
        kind="provider",
        name="OpenAI",
        type="openai",
        api_key="${OPENAI_API_KEY}",
    )
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo, secrets)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        import httpx

        mock_httpx.get.side_effect = httpx.TimeoutException("Connection timed out")

        result = await service.test_connection("openai-provider")

    assert result["success"] is False
    assert "Connection failed" in result["message"]
