"""Tests for RUN-328: Google API key must be sent via header, not URL query param.

These tests verify that:
1. The Google API key is NOT embedded in the request URL
2. The Google API key IS sent in the `x-goog-api-key` header
3. The URL does not contain a `?key=` query parameter
4. Response parsing still works correctly with the header-based approach
"""

from unittest.mock import Mock, patch

from runsight_api.domain.value_objects import ProviderEntity as Provider
from runsight_api.logic.services.provider_service import ProviderService


def _make_google_provider() -> Provider:
    """Create a Google provider fixture with an encrypted API key."""
    return Provider(
        id="prov_google1",
        name="Google Gemini",
        type="google",
        api_key_encrypted="encrypted_google_key",
    )


@patch("runsight_api.logic.services.provider_service.decrypt")
def test_google_api_key_not_in_url(mock_decrypt):
    """The API key must NOT appear anywhere in the request URL."""
    mock_decrypt.return_value = "AIzaSy_test_key_123"
    repo = Mock()
    prov = _make_google_provider()
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "models/gemini-pro"}]}
        mock_httpx.get.return_value = mock_resp

        service.test_connection("prov_google1")

    call_args = mock_httpx.get.call_args
    url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
    assert "AIzaSy_test_key_123" not in url, "API key must not appear in URL"


@patch("runsight_api.logic.services.provider_service.decrypt")
def test_google_api_key_sent_in_header(mock_decrypt):
    """The API key must be sent via the `x-goog-api-key` header."""
    mock_decrypt.return_value = "AIzaSy_test_key_456"
    repo = Mock()
    prov = _make_google_provider()
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "models/gemini-pro"}]}
        mock_httpx.get.return_value = mock_resp

        service.test_connection("prov_google1")

    call_kwargs = mock_httpx.get.call_args[1]
    assert "headers" in call_kwargs, "Request must include headers"
    assert "x-goog-api-key" in call_kwargs["headers"], "Headers must contain x-goog-api-key"
    assert call_kwargs["headers"]["x-goog-api-key"] == "AIzaSy_test_key_456"


@patch("runsight_api.logic.services.provider_service.decrypt")
def test_google_url_has_no_key_query_param(mock_decrypt):
    """The URL must not contain a `?key=` or `&key=` query parameter."""
    mock_decrypt.return_value = "AIzaSy_test_key_789"
    repo = Mock()
    prov = _make_google_provider()
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": []}
        mock_httpx.get.return_value = mock_resp

        service.test_connection("prov_google1")

    call_args = mock_httpx.get.call_args
    url = call_args[0][0] if call_args[0] else call_args[1].get("url", "")
    assert "?key=" not in url, "URL must not contain ?key= query parameter"
    assert "&key=" not in url, "URL must not contain &key= query parameter"


@patch("runsight_api.logic.services.provider_service.decrypt")
def test_google_model_listing_response_parsed_correctly(mock_decrypt):
    """Model listing with header-based auth must still parse response correctly."""
    mock_decrypt.return_value = "AIzaSy_test_key_abc"
    repo = Mock()
    prov = _make_google_provider()
    repo.get_by_id.return_value = prov
    repo.update.return_value = prov
    service = ProviderService(repo)

    with patch("runsight_api.logic.services.provider_service.httpx") as mock_httpx:
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "models/gemini-pro"},
                {"name": "models/gemini-1.5-flash"},
                {"name": "models/gemini-1.5-pro"},
            ]
        }
        mock_httpx.get.return_value = mock_resp

        result = service.test_connection("prov_google1")

    assert result["success"] is True
    assert "gemini-pro" in result["models"]
    assert "gemini-1.5-flash" in result["models"]
    assert "gemini-1.5-pro" in result["models"]
    assert len(result["models"]) == 3
    assert "3 models available" in result["message"]
