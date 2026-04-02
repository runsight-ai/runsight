"""RUN-548 red tests for the backend settings service foundation."""

from __future__ import annotations

import importlib
import inspect
from unittest.mock import Mock

from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
from runsight_api.data.filesystem.settings_repo import FileSystemSettingsRepo
from runsight_api.transport import deps as deps_module


def _load_settings_service_module():
    return importlib.import_module("runsight_api.logic.services.settings_service")


def _load_settings_service():
    return _load_settings_service_module().SettingsService


class TestSettingsServiceConstructor:
    def test_constructor_accepts_settings_repo_and_provider_repo(self):
        SettingsService = _load_settings_service()
        signature = inspect.signature(SettingsService.__init__)

        assert list(signature.parameters) == [
            "self",
            "settings_repo",
            "provider_repo",
        ]

    def test_get_settings_service_returns_settings_service(self):
        assert hasattr(deps_module, "get_settings_service"), (
            "deps.get_settings_service must exist to build SettingsService"
        )

        SettingsService = _load_settings_service()
        settings_repo = Mock(spec=FileSystemSettingsRepo)
        provider_repo = Mock(spec=FileSystemProviderRepo)

        service = deps_module.get_settings_service(
            settings_repo=settings_repo,
            provider_repo=provider_repo,
        )

        assert isinstance(service, SettingsService)


class TestFallbackFoundation:
    def test_settings_service_imports_fallback_target_entry_not_fallback_chain_entry(self):
        module = _load_settings_service_module()
        source = inspect.getsource(module)

        assert "FallbackTargetEntry" in source
        assert "FallbackChainEntry" not in source

    def test_settings_service_uses_fallback_map_repo_methods(self):
        module = _load_settings_service_module()
        source = inspect.getsource(module)

        assert "get_fallback_map" in source
        assert "get_fallback_chain" not in source
        assert "update_fallback_chain" not in source
