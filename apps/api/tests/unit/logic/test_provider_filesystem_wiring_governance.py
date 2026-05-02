"""Governance: provider/settings wiring stays on filesystem repos and secrets.

Boundary: provider and settings runtime paths must not reintroduce SQLite or legacy encryption.
Owner: API provider/settings owners.
Exit criteria: replace source checks with architectural lint rules.
"""

from unittest.mock import Mock


pytest_plugins = ("tests.unit.logic.provider_service_fixtures",)


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
            kind="provider",
            name="OpenAI",
            type="openai",
            api_key="${OPENAI_API_KEY}",
            status="connected",
            models=["gpt-4o"],
        )
        mock_svc = Mock()
        mock_svc.secrets = Mock()
        mock_svc.secrets.resolve.return_value = "dummy-resolved"
        out = _provider_to_out(entity, mock_svc)

        assert out.id == "openai"
        assert out.name == "OpenAI"
        assert out.api_key_env == "${OPENAI_API_KEY}"
        assert out.models == ["gpt-4o"]


# ===========================================================================
# 12. Provider CRUD integration with filesystem repos
# ===========================================================================
