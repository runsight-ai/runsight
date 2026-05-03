"""GET /api/models returns and filters available model catalog entries."""

from fastapi.testclient import TestClient
from unittest.mock import Mock

from runsight_api.main import app
from runsight_api.transport.deps import get_model_service
from tests.transport.model_catalog_helpers import (
    _make_model_response,
    _override_model_service,
)

client = TestClient(app)


class TestGetModelsEndpoint:
    """Tests for GET /api/models route existence and response shape."""

    def test_endpoint_exists(self):
        """GET /api/models must return 200, not 404/405."""
        _override_model_service(models=[])
        try:
            response = client.get("/api/models")
            assert response.status_code != 404, "Route /api/models not registered"
            assert response.status_code != 405, "Method GET not allowed on /api/models"
        finally:
            app.dependency_overrides.clear()

    def test_returns_list(self):
        """Response body must be a JSON list (or wrapper with 'items' list)."""
        _override_model_service(models=[])
        try:
            response = client.get("/api/models")
            data = response.json()
            # Accept either bare list or {"items": [...], "total": N}
            items = data if isinstance(data, list) else data.get("items", data)
            assert isinstance(items, list)
        finally:
            app.dependency_overrides.clear()

    def test_model_response_shape(self):
        """Each item must include required ModelResponse fields."""
        mock_service = Mock()
        mock_service.get_available_models.return_value = [_make_model_response()]
        app.dependency_overrides[get_model_service] = lambda: mock_service
        try:
            response = client.get("/api/models")
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            assert len(items) == 1
            first = items[0]
            required_fields = {
                "provider",
                "provider_name",
                "model_id",
                "mode",
                "max_tokens",
                "input_cost_per_token",
                "output_cost_per_token",
                "supports_vision",
                "supports_function_calling",
            }
            missing = required_fields - set(first.keys())
            assert not missing, f"ModelResponse missing fields: {missing}"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# GET /api/models — query-param filtering
# ===========================================================================


class TestGetModelsFiltering:
    """Tests for query-param filtering on GET /api/models."""

    def test_filter_by_provider(self):
        """?provider=openai must return only openai models."""
        mock_service = _override_model_service(models=[_make_model_response(provider="openai")])
        try:
            response = client.get("/api/models", params={"provider": "openai"})
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            for item in items:
                assert item["provider"] == "openai"
            mock_service.get_available_models.assert_called_once()
            assert mock_service.get_available_models.call_args.kwargs["provider"] == "openai"
        finally:
            app.dependency_overrides.clear()

    def test_filter_by_mode(self):
        """?mode=chat must return only chat-mode models."""
        mock_service = _override_model_service(models=[_make_model_response(mode="chat")])
        try:
            response = client.get("/api/models", params={"mode": "chat"})
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            for item in items:
                assert item["mode"] == "chat"
            mock_service.get_available_models.assert_called_once()
            assert mock_service.get_available_models.call_args.kwargs["mode"] == "chat"
        finally:
            app.dependency_overrides.clear()

    def test_filter_by_supports_vision(self):
        """?supports_vision=true must return only vision-capable models."""
        mock_service = _override_model_service(models=[_make_model_response(supports_vision=True)])
        try:
            response = client.get("/api/models", params={"supports_vision": "true"})
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            for item in items:
                assert item["supports_vision"] is True
            assert mock_service.get_available_models.call_args.kwargs["supports_vision"] is True
        finally:
            app.dependency_overrides.clear()

    def test_filter_by_supports_function_calling(self):
        """?supports_function_calling=true must return only function-calling models."""
        mock_service = _override_model_service(
            models=[_make_model_response(supports_function_calling=True)]
        )
        try:
            response = client.get("/api/models", params={"supports_function_calling": "true"})
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            for item in items:
                assert item["supports_function_calling"] is True
            assert (
                mock_service.get_available_models.call_args.kwargs["supports_function_calling"]
                is True
            )
        finally:
            app.dependency_overrides.clear()

    def test_unknown_provider_returns_empty(self):
        """?provider=nonexistent must return empty list, not error."""
        mock_service = _override_model_service(models=[])
        try:
            response = client.get("/api/models", params={"provider": "definitely_not_a_provider"})
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            assert items == []
            assert (
                mock_service.get_available_models.call_args.kwargs["provider"]
                == "definitely_not_a_provider"
            )
        finally:
            app.dependency_overrides.clear()

    def test_combined_filters(self):
        """Multiple filters applied simultaneously must all be honoured."""
        mock_service = _override_model_service(
            models=[_make_model_response(provider="openai", mode="chat", supports_vision=True)]
        )
        try:
            response = client.get(
                "/api/models",
                params={"provider": "openai", "mode": "chat", "supports_vision": "true"},
            )
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            for item in items:
                assert item["provider"] == "openai"
                assert item["mode"] == "chat"
                assert item["supports_vision"] is True
            kwargs = mock_service.get_available_models.call_args.kwargs
            assert kwargs["provider"] == "openai"
            assert kwargs["mode"] == "chat"
            assert kwargs["supports_vision"] is True
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# GET /api/models — ?all=true flag
# ===========================================================================


class TestGetModelsAllFlag:
    """Tests for the ?all=true bypass of configured-provider filtering."""

    def test_all_true_returns_all_catalog_models(self):
        """?all=true must return models even for unconfigured providers."""
        mock_service = _override_model_service(models=[_make_model_response(provider="openai")])
        try:
            response = client.get("/api/models", params={"all": "true"})
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            assert isinstance(items, list)
            assert mock_service.get_available_models.call_args.kwargs["all_providers"] is True
        finally:
            app.dependency_overrides.clear()

    def test_default_excludes_unconfigured_providers(self):
        """Without ?all=true, only models from configured providers should appear."""
        mock_service = _override_model_service(models=[])
        try:
            resp_default = client.get("/api/models")
            resp_all = client.get("/api/models", params={"all": "true"})
            assert resp_default.status_code == 200
            assert resp_all.status_code == 200
            calls = mock_service.get_available_models.call_args_list
            assert calls[0].kwargs["all_providers"] is False
            assert calls[1].kwargs["all_providers"] is True
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# GET /api/models/providers — basic wiring
# ===========================================================================
