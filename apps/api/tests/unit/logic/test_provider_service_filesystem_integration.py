"""ProviderService CRUD works with FileSystemProviderRepo and SecretsEnvLoader."""

pytest_plugins = ("tests.unit.logic.provider_service_fixtures",)


class TestProviderCrudFilesystemIntegration:
    """Full CRUD cycle using real FileSystemProviderRepo + SecretsEnvLoader."""

    def test_create_then_get_returns_provider(self, service):
        """Create a provider then get by id — should return the same entity."""
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test",
            provider_type="openai",
        )
        provider = service.get_provider("openai")

        assert provider is not None
        assert provider.name == "OpenAI"
        assert provider.type == "openai"

    def test_create_then_list_includes_provider(self, service):
        """Created provider should appear in list_providers."""
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test",
            provider_type="openai",
        )
        providers = service.list_providers()

        assert len(providers) >= 1
        names = [p.name for p in providers]
        assert "OpenAI" in names

    def test_create_update_get_reflects_changes(self, service, secrets):
        """Update should modify the provider and update the secret."""
        service.create_provider(
            id="openai", kind="provider", name="OpenAI", api_key="dummy-v1", provider_type="openai"
        )
        service.update_provider("openai", id="openai", kind="provider", api_key="dummy-v2")

        provider = service.get_provider("openai")
        assert provider is not None

        resolved = secrets.resolve("${OPENAI_API_KEY}")
        assert resolved == "dummy-v2"

    def test_delete_removes_provider(self, service):
        """Delete should remove the provider YAML file."""
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-test",
            provider_type="openai",
        )
        result = service.delete_provider("openai")
        assert result is True

        provider = service.get_provider("openai")
        assert provider is None

    def test_multiple_providers_coexist(self, service, secrets):
        """Multiple providers should coexist with separate secrets."""
        service.create_provider(
            id="openai",
            kind="provider",
            name="OpenAI",
            api_key="dummy-openai",
            provider_type="openai",
        )
        service.create_provider(
            id="anthropic",
            kind="provider",
            name="Anthropic",
            api_key="dummy-anthropic",
            provider_type="anthropic",
        )

        assert secrets.resolve("${OPENAI_API_KEY}") == "dummy-openai"
        assert secrets.resolve("${ANTHROPIC_API_KEY}") == "dummy-anthropic"

        providers = service.list_providers()
        assert len(providers) == 2
