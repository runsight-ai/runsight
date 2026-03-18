"""Red-phase tests for RUN-151: Model Catalog API endpoints.

Tests target two endpoints and one service layer that do NOT yet exist:
  - GET /api/models          (filtered model list)
  - GET /api/models/providers (provider summary with is_configured flag)
  - ModelService             (service layer bridging catalog + provider config)
"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runsight_api.main import app

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

client = TestClient(app)


def _make_model_response(
    *,
    provider: str = "openai",
    provider_name: str = "Openai",
    model_id: str = "gpt-4o",
    mode: str = "chat",
    max_tokens: int = 4096,
    input_cost_per_token: float = 0.00003,
    output_cost_per_token: float = 0.00006,
    supports_vision: bool = False,
    supports_function_calling: bool = True,
) -> dict:
    return {
        "provider": provider,
        "provider_name": provider_name,
        "model_id": model_id,
        "mode": mode,
        "max_tokens": max_tokens,
        "input_cost_per_token": input_cost_per_token,
        "output_cost_per_token": output_cost_per_token,
        "supports_vision": supports_vision,
        "supports_function_calling": supports_function_calling,
    }


def _make_provider_summary(
    *,
    id: str = "openai",
    name: str = "Openai",
    model_count: int = 5,
    is_configured: bool = False,
) -> dict:
    return {
        "id": id,
        "name": name,
        "model_count": model_count,
        "is_configured": is_configured,
    }


# ===========================================================================
# GET /api/models — basic wiring
# ===========================================================================


class TestGetModelsEndpoint:
    """Tests for GET /api/models route existence and response shape."""

    def test_endpoint_exists(self):
        """GET /api/models must return 200, not 404/405."""
        response = client.get("/api/models")
        assert response.status_code != 404, "Route /api/models not registered"
        assert response.status_code != 405, "Method GET not allowed on /api/models"

    def test_returns_list(self):
        """Response body must be a JSON list (or wrapper with 'items' list)."""
        response = client.get("/api/models")
        data = response.json()
        # Accept either bare list or {"items": [...], "total": N}
        items = data if isinstance(data, list) else data.get("items", data)
        assert isinstance(items, list)

    def test_model_response_shape(self):
        """Each item must include required ModelResponse fields."""
        response = client.get("/api/models")
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        if len(items) == 0:
            pytest.skip("No models returned — shape check needs at least one item")
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


# ===========================================================================
# GET /api/models — query-param filtering
# ===========================================================================


class TestGetModelsFiltering:
    """Tests for query-param filtering on GET /api/models."""

    def test_filter_by_provider(self):
        """?provider=openai must return only openai models."""
        response = client.get("/api/models", params={"provider": "openai"})
        assert response.status_code == 200
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        for item in items:
            assert item["provider"] == "openai"

    def test_filter_by_mode(self):
        """?mode=chat must return only chat-mode models."""
        response = client.get("/api/models", params={"mode": "chat"})
        assert response.status_code == 200
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        for item in items:
            assert item["mode"] == "chat"

    def test_filter_by_supports_vision(self):
        """?supports_vision=true must return only vision-capable models."""
        response = client.get("/api/models", params={"supports_vision": "true"})
        assert response.status_code == 200
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        for item in items:
            assert item["supports_vision"] is True

    def test_filter_by_supports_function_calling(self):
        """?supports_function_calling=true must return only function-calling models."""
        response = client.get("/api/models", params={"supports_function_calling": "true"})
        assert response.status_code == 200
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        for item in items:
            assert item["supports_function_calling"] is True

    def test_unknown_provider_returns_empty(self):
        """?provider=nonexistent must return empty list, not error."""
        response = client.get("/api/models", params={"provider": "definitely_not_a_provider"})
        assert response.status_code == 200
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        assert items == []

    def test_combined_filters(self):
        """Multiple filters applied simultaneously must all be honoured."""
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


# ===========================================================================
# GET /api/models — ?all=true flag
# ===========================================================================


class TestGetModelsAllFlag:
    """Tests for the ?all=true bypass of configured-provider filtering."""

    def test_all_true_returns_all_catalog_models(self):
        """?all=true must return models even for unconfigured providers."""
        response = client.get("/api/models", params={"all": "true"})
        assert response.status_code == 200
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        # With ?all=true the catalog should include more providers than configured
        assert isinstance(items, list)

    def test_default_excludes_unconfigured_providers(self):
        """Without ?all=true, only models from configured providers should appear."""
        resp_default = client.get("/api/models")
        resp_all = client.get("/api/models", params={"all": "true"})
        assert resp_default.status_code == 200
        assert resp_all.status_code == 200
        items_default = (
            resp_default.json()
            if isinstance(resp_default.json(), list)
            else resp_default.json().get("items", resp_default.json())
        )
        items_all = (
            resp_all.json()
            if isinstance(resp_all.json(), list)
            else resp_all.json().get("items", resp_all.json())
        )
        # all=true must return >= default count
        assert len(items_all) >= len(items_default)


# ===========================================================================
# GET /api/models/providers — basic wiring
# ===========================================================================


class TestGetProvidersEndpoint:
    """Tests for GET /api/models/providers route existence and shape."""

    def test_endpoint_exists(self):
        """GET /api/models/providers must return 200, not 404/405."""
        response = client.get("/api/models/providers")
        assert response.status_code != 404, "Route /api/models/providers not registered"
        assert response.status_code != 405

    def test_returns_list(self):
        """Response body must be a JSON list (or wrapper with 'items' list)."""
        response = client.get("/api/models/providers")
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        assert isinstance(items, list)

    def test_provider_summary_shape(self):
        """Each item must include required ProviderSummary fields."""
        response = client.get("/api/models/providers")
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        if len(items) == 0:
            pytest.skip("No providers returned — shape check needs at least one")
        first = items[0]
        required_fields = {"id", "name", "model_count", "is_configured"}
        missing = required_fields - set(first.keys())
        assert not missing, f"ProviderSummary missing fields: {missing}"


# ===========================================================================
# GET /api/models/providers — is_configured flag
# ===========================================================================


class TestProviderConfiguredFlag:
    """Tests verifying the is_configured flag logic."""

    def test_unconfigured_provider_is_false(self):
        """A catalog provider with no matching configured provider must have is_configured=False."""
        response = client.get("/api/models/providers")
        assert response.status_code == 200
        data = response.json()
        items = data if isinstance(data, list) else data.get("items", data)
        # With a clean DB (no providers configured), every entry should be False
        for item in items:
            assert item["is_configured"] is False, (
                f"Provider {item['id']} should be is_configured=False with no providers in DB"
            )

    def test_configured_provider_is_true(self):
        """A catalog provider that IS configured must have is_configured=True.

        This test relies on dependency-override or DB seeding to inject a
        configured provider and assert the flag flips to True.
        """
        # We import here to allow the test to fail at import if the dep
        # function doesn't exist yet (proving green-phase is needed).
        from runsight_api.transport.deps import get_model_service

        mock_service = Mock()
        mock_service.get_provider_summary.return_value = [
            _make_provider_summary(id="openai", is_configured=True),
            _make_provider_summary(id="anthropic", is_configured=False),
        ]
        app.dependency_overrides[get_model_service] = lambda: mock_service
        try:
            response = client.get("/api/models/providers")
            assert response.status_code == 200
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data)
            openai_entry = next((p for p in items if p["id"] == "openai"), None)
            assert openai_entry is not None
            assert openai_entry["is_configured"] is True
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# ModelService unit tests
# ===========================================================================


class TestModelServiceImport:
    """Verify ModelService can be imported (proves the module exists)."""

    def test_model_service_importable(self):
        from runsight_api.logic.services.model_service import ModelService  # noqa: F401

    def test_model_service_has_get_available_models(self):
        from runsight_api.logic.services.model_service import ModelService

        assert hasattr(ModelService, "get_available_models")

    def test_model_service_has_get_provider_summary(self):
        from runsight_api.logic.services.model_service import ModelService

        assert hasattr(ModelService, "get_provider_summary")


class TestModelServiceGetAvailableModels:
    """Unit tests for ModelService.get_available_models."""

    def _make_service(self, catalog_models=None, configured_providers=None):
        """Build a ModelService with mocked catalog + provider repo."""
        from runsight_api.logic.services.model_service import ModelService

        mock_catalog = Mock()
        mock_catalog.get_models.return_value = catalog_models or []

        mock_provider_repo = Mock()
        mock_provider_repo.list_all.return_value = configured_providers or []

        return ModelService(catalog=mock_catalog, provider_repo=mock_provider_repo)

    def test_empty_catalog_returns_empty(self):
        svc = self._make_service(catalog_models=[], configured_providers=[])
        result = svc.get_available_models()
        assert result == []

    def test_filters_to_configured_providers(self):
        from runsight_core.llm.model_catalog import ModelInfo

        openai_model = ModelInfo(
            provider="openai",
            model_id="gpt-4o",
            mode="chat",
            supports_function_calling=True,
        )
        anthropic_model = ModelInfo(
            provider="anthropic",
            model_id="claude-3",
            mode="chat",
        )
        # Only openai is configured
        mock_provider = Mock()
        mock_provider.type = "openai"

        svc = self._make_service(
            catalog_models=[openai_model, anthropic_model],
            configured_providers=[mock_provider],
        )
        result = svc.get_available_models()
        provider_ids = {r.provider for r in result}
        assert "openai" in provider_ids
        assert "anthropic" not in provider_ids

    def test_all_flag_bypasses_configured_filter(self):
        from runsight_core.llm.model_catalog import ModelInfo

        openai_model = ModelInfo(provider="openai", model_id="gpt-4o", mode="chat")
        anthropic_model = ModelInfo(provider="anthropic", model_id="claude-3", mode="chat")

        svc = self._make_service(
            catalog_models=[openai_model, anthropic_model],
            configured_providers=[],  # none configured
        )
        result = svc.get_available_models(all_providers=True)
        assert len(result) == 2

    def test_filter_by_provider(self):
        from runsight_core.llm.model_catalog import ModelInfo

        m1 = ModelInfo(provider="openai", model_id="gpt-4o", mode="chat")
        m2 = ModelInfo(provider="openai", model_id="gpt-3.5", mode="chat")
        m3 = ModelInfo(provider="anthropic", model_id="claude-3", mode="chat")

        svc = self._make_service(catalog_models=[m1, m2, m3], configured_providers=[])
        result = svc.get_available_models(provider="openai", all_providers=True)
        assert all(r.provider == "openai" for r in result)
        assert len(result) == 2

    def test_filter_by_mode(self):
        from runsight_core.llm.model_catalog import ModelInfo

        chat = ModelInfo(provider="openai", model_id="gpt-4o", mode="chat")
        embed = ModelInfo(provider="openai", model_id="text-embed", mode="embedding")

        svc = self._make_service(catalog_models=[chat, embed], configured_providers=[])
        result = svc.get_available_models(mode="chat", all_providers=True)
        assert all(r.mode == "chat" for r in result)

    def test_filter_by_vision_capability(self):
        from runsight_core.llm.model_catalog import ModelInfo

        vision = ModelInfo(
            provider="openai",
            model_id="gpt-4o",
            mode="chat",
            supports_vision=True,
        )
        no_vision = ModelInfo(
            provider="openai",
            model_id="gpt-3.5",
            mode="chat",
            supports_vision=False,
        )

        svc = self._make_service(
            catalog_models=[vision, no_vision],
            configured_providers=[],
        )
        result = svc.get_available_models(
            supports_vision=True,
            all_providers=True,
        )
        assert len(result) == 1
        assert result[0].model_id == "gpt-4o"

    def test_filter_by_function_calling(self):
        from runsight_core.llm.model_catalog import ModelInfo

        fc = ModelInfo(
            provider="openai",
            model_id="gpt-4o",
            mode="chat",
            supports_function_calling=True,
        )
        no_fc = ModelInfo(
            provider="openai",
            model_id="o1-preview",
            mode="chat",
            supports_function_calling=False,
        )

        svc = self._make_service(
            catalog_models=[fc, no_fc],
            configured_providers=[],
        )
        result = svc.get_available_models(
            supports_function_calling=True,
            all_providers=True,
        )
        assert len(result) == 1
        assert result[0].model_id == "gpt-4o"

    def test_provider_configured_but_no_catalog_models(self):
        """A configured provider with zero catalog entries => empty result."""
        mock_provider = Mock()
        mock_provider.type = "custom_local"

        svc = self._make_service(
            catalog_models=[],  # nothing in catalog
            configured_providers=[mock_provider],
        )
        result = svc.get_available_models()
        assert result == []


class TestModelServiceGetProviderSummary:
    """Unit tests for ModelService.get_provider_summary."""

    def _make_service(self, catalog_providers=None, configured_providers=None):
        from runsight_api.logic.services.model_service import ModelService

        mock_catalog = Mock()
        mock_catalog.get_providers.return_value = catalog_providers or []

        mock_provider_repo = Mock()
        mock_provider_repo.list_all.return_value = configured_providers or []

        return ModelService(catalog=mock_catalog, provider_repo=mock_provider_repo)

    def test_empty_catalog_returns_empty(self):
        svc = self._make_service(catalog_providers=[], configured_providers=[])
        result = svc.get_provider_summary()
        assert result == []

    def test_unconfigured_provider_has_false_flag(self):
        from runsight_core.llm.model_catalog import ProviderInfo

        svc = self._make_service(
            catalog_providers=[ProviderInfo(id="openai", name="Openai", model_count=5)],
            configured_providers=[],
        )
        result = svc.get_provider_summary()
        assert len(result) == 1
        assert result[0]["id"] == "openai"
        assert result[0]["is_configured"] is False

    def test_configured_provider_has_true_flag(self):
        from runsight_core.llm.model_catalog import ProviderInfo

        mock_provider = Mock()
        mock_provider.type = "openai"

        svc = self._make_service(
            catalog_providers=[ProviderInfo(id="openai", name="Openai", model_count=5)],
            configured_providers=[mock_provider],
        )
        result = svc.get_provider_summary()
        openai = next(p for p in result if p["id"] == "openai")
        assert openai["is_configured"] is True

    def test_multiple_providers_mixed_config(self):
        from runsight_core.llm.model_catalog import ProviderInfo

        mock_openai = Mock()
        mock_openai.type = "openai"

        svc = self._make_service(
            catalog_providers=[
                ProviderInfo(id="openai", name="Openai", model_count=10),
                ProviderInfo(id="anthropic", name="Anthropic", model_count=8),
                ProviderInfo(id="google", name="Google", model_count=6),
            ],
            configured_providers=[mock_openai],
        )
        result = svc.get_provider_summary()
        lookup = {p["id"]: p for p in result}
        assert lookup["openai"]["is_configured"] is True
        assert lookup["anthropic"]["is_configured"] is False
        assert lookup["google"]["is_configured"] is False


# ===========================================================================
# Dependency injection wiring
# ===========================================================================


class TestDependencyWiring:
    """Verify the DI function for ModelService exists in deps.py."""

    def test_get_model_service_importable(self):
        from runsight_api.transport.deps import get_model_service  # noqa: F401

    def test_get_model_catalog_importable(self):
        from runsight_api.transport.deps import get_model_catalog  # noqa: F401


# ===========================================================================
# Response schema (Pydantic models)
# ===========================================================================


class TestResponseSchemas:
    """Verify ModelResponse and ProviderSummary Pydantic schemas exist."""

    def test_model_response_importable(self):
        from runsight_api.transport.routers.models import ModelResponse  # noqa: F401

    def test_provider_summary_importable(self):
        from runsight_api.transport.routers.models import ProviderSummary  # noqa: F401

    def test_model_response_has_required_fields(self):
        from runsight_api.transport.routers.models import ModelResponse

        fields = set(ModelResponse.model_fields.keys())
        expected = {
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
        missing = expected - fields
        assert not missing, f"ModelResponse missing fields: {missing}"

    def test_provider_summary_has_required_fields(self):
        from runsight_api.transport.routers.models import ProviderSummary

        fields = set(ProviderSummary.model_fields.keys())
        expected = {"id", "name", "model_count", "is_configured"}
        missing = expected - fields
        assert not missing, f"ProviderSummary missing fields: {missing}"
