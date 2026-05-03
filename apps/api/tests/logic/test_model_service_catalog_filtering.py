"""ModelService filters catalog models against configured providers."""

from unittest.mock import Mock


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
