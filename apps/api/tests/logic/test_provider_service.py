from unittest.mock import Mock, patch
from runsight_api.logic.services.provider_service import (
    ProviderService,
    _infer_provider_type,
)
from runsight_api.domain.entities.provider import Provider


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
    repo.list_all.return_value = []
    service = ProviderService(repo)
    result = service.list_providers()
    assert result == []
    repo.list_all.assert_called_once()


def test_list_providers_multiple():
    repo = Mock()
    providers = [
        Provider(id="p1", name="P1", type="openai"),
        Provider(id="p2", name="P2", type="anthropic"),
    ]
    repo.list_all.return_value = providers
    service = ProviderService(repo)
    result = service.list_providers()
    assert result == providers
    assert len(result) == 2


# --- get_provider ---


def test_get_provider_exists():
    repo = Mock()
    prov = Provider(id="p1", name="OpenAI", type="openai")
    repo.get_by_id.return_value = prov
    service = ProviderService(repo)
    result = service.get_provider("p1")
    assert result == prov
    assert result.id == "p1"


def test_get_provider_not_found_returns_none():
    repo = Mock()
    repo.get_by_id.return_value = None
    service = ProviderService(repo)
    result = service.get_provider("missing")
    assert result is None


# --- create_provider ---


@patch("runsight_api.logic.services.provider_service.encrypt")
def test_create_provider_happy_path(mock_encrypt):
    mock_encrypt.return_value = "encrypted_key"
    repo = Mock()
    created = None

    def capture_create(p):
        nonlocal created
        created = p
        return p

    repo.create.side_effect = capture_create
    service = ProviderService(repo)
    service.create_provider(
        name="OpenAI",
        api_key="sk-xxx",
        base_url="https://api.openai.com/v1",
        provider_type="openai",
    )
    assert created is not None
    assert created.name == "OpenAI"
    assert created.type == "openai"
    assert created.api_key_encrypted == "encrypted_key"
    assert created.base_url == "https://api.openai.com/v1"
    assert created.id.startswith("prov_")
    mock_encrypt.assert_called_once_with("sk-xxx")


@patch("runsight_api.logic.services.provider_service.encrypt")
def test_create_provider_type_inferred_from_name_openai(mock_encrypt):
    mock_encrypt.return_value = "enc"
    repo = Mock()

    def capture_create(p):
        return p

    repo.create.side_effect = capture_create
    service = ProviderService(repo)
    result = service.create_provider(name="OpenAI", api_key="sk-x")
    assert result.type == "openai"


@patch("runsight_api.logic.services.provider_service.encrypt")
def test_create_provider_type_inferred_from_name_claude(mock_encrypt):
    mock_encrypt.return_value = "enc"
    repo = Mock()
    repo.create.side_effect = lambda p: p
    service = ProviderService(repo)
    result = service.create_provider(name="Claude API", api_key="sk-x")
    assert result.type == "anthropic"


@patch("runsight_api.logic.services.provider_service.encrypt")
def test_create_provider_type_inferred_unknown_to_custom(mock_encrypt):
    mock_encrypt.return_value = "enc"
    repo = Mock()
    repo.create.side_effect = lambda p: p
    service = ProviderService(repo)
    result = service.create_provider(name="Unknown Provider", api_key="key")
    assert result.type == "custom"


# --- update_provider ---


@patch("runsight_api.logic.services.provider_service.encrypt")
def test_update_provider_happy_path(mock_encrypt):
    mock_encrypt.return_value = "enc_new"
    repo = Mock()
    prov = Provider(id="p1", name="Old", type="openai", base_url="https://old.com")
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo)
    result = service.update_provider(
        "p1",
        name="New Name",
        api_key="new_key",
        base_url="https://new.com",
    )
    assert result is prov
    assert prov.name == "New Name"
    assert prov.api_key_encrypted == "enc_new"
    assert prov.base_url == "https://new.com"
    mock_encrypt.assert_called_once_with("new_key")


def test_update_provider_not_found_returns_none():
    repo = Mock()
    repo.get_by_id.return_value = None
    service = ProviderService(repo)
    result = service.update_provider("missing", name="New")
    assert result is None
    repo.update.assert_not_called()


@patch("runsight_api.logic.services.provider_service.encrypt")
def test_update_provider_partial_update(mock_encrypt):
    repo = Mock()
    prov = Provider(id="p1", name="Original", type="openai", base_url="https://a.com")
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo)
    service.update_provider("p1", name="Updated")
    assert prov.name == "Updated"
    assert prov.base_url == "https://a.com"  # unchanged
    mock_encrypt.assert_not_called()


# --- delete_provider ---


def test_delete_provider_exists_returns_true():
    repo = Mock()
    repo.delete.return_value = True
    service = ProviderService(repo)
    result = service.delete_provider("p1")
    assert result is True
    repo.delete.assert_called_once_with("p1")


def test_delete_provider_not_found_returns_false():
    repo = Mock()
    repo.delete.return_value = False
    service = ProviderService(repo)
    result = service.delete_provider("missing")
    assert result is False


# --- test_connection ---


def test_test_connection_provider_not_found():
    repo = Mock()
    repo.get_by_id.return_value = None
    service = ProviderService(repo)
    result = service.test_connection("missing")
    assert result["success"] is False
    assert result["message"] == "Provider not found"
    assert "models" not in result or result.get("models") == []


def test_test_connection_no_api_key_non_ollama():
    repo = Mock()
    prov = Provider(
        id="p1",
        name="OpenAI",
        type="openai",
        api_key_encrypted=None,
    )
    repo.get_by_id.return_value = prov
    service = ProviderService(repo)
    result = service.test_connection("p1")
    assert result["success"] is False
    assert result["message"] == "No API key configured"


def test_test_connection_ollama_no_api_key_allowed():
    repo = Mock()
    prov = Provider(
        id="p1",
        name="Ollama",
        type="ollama",
        api_key_encrypted=None,
        base_url="http://localhost:11434",
    )
    repo.get_by_id.return_value = prov
    service = ProviderService(repo)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3"}]}
        mock_httpx.get.return_value = mock_resp

        result = service.test_connection("p1")

    assert result["success"] is True
    assert "llama3" in result.get("models", [])


@patch("runsight_api.logic.services.provider_service.decrypt")
def test_test_connection_successful_openai(mock_decrypt):
    mock_decrypt.return_value = "sk-xxx"
    repo = Mock()
    prov = Provider(
        id="p1",
        name="OpenAI",
        type="openai",
        api_key_encrypted="enc",
        base_url="https://api.openai.com/v1",
    )
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "gpt-4o"}, {"id": "gpt-3.5"}]}
        mock_httpx.get.return_value = mock_resp

        result = service.test_connection("p1")

    assert result["success"] is True
    assert "gpt-4o" in result.get("models", [])
    assert "gpt-3.5" in result.get("models", [])
    mock_httpx.get.assert_called_once()
    call_kwargs = mock_httpx.get.call_args[1]
    assert "Bearer sk-xxx" in call_kwargs["headers"]["Authorization"]


@patch("runsight_api.logic.services.provider_service.decrypt")
def test_test_connection_http_error(mock_decrypt):
    mock_decrypt.return_value = "sk-xxx"
    repo = Mock()
    prov = Provider(
        id="p1",
        name="OpenAI",
        type="openai",
        api_key_encrypted="enc",
    )
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 401
        mock_httpx.get.return_value = mock_resp

        result = service.test_connection("p1")

    assert result["success"] is False
    assert "401" in result["message"]


@patch("runsight_api.logic.services.provider_service.decrypt")
def test_test_connection_timeout_exception(mock_decrypt):
    mock_decrypt.return_value = "sk-xxx"
    repo = Mock()
    prov = Provider(
        id="p1",
        name="OpenAI",
        type="openai",
        api_key_encrypted="enc",
    )
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        import httpx

        mock_httpx.get.side_effect = httpx.TimeoutException("Connection timed out")

        result = service.test_connection("p1")

    assert result["success"] is False
    assert "Connection failed" in result["message"]
