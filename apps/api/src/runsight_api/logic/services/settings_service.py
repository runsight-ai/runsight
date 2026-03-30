from __future__ import annotations

from ...data.filesystem.provider_repo import FileSystemProviderRepo
from ...data.filesystem.settings_repo import FileSystemSettingsRepo


class SettingsService:
    def __init__(
        self,
        settings_repo: FileSystemSettingsRepo,
        provider_repo: FileSystemProviderRepo,
    ) -> None:
        self.settings_repo = settings_repo
        self.provider_repo = provider_repo

    def get_model_defaults(self) -> list[dict]:
        providers = self.provider_repo.list_all()
        if not providers:
            self.settings_repo.list_model_defaults()
            self.settings_repo.get_fallback_chain()
            return []

        provider_ids = {provider.id for provider in providers}
        defaults_by_provider = {
            entry.provider_id: entry
            for entry in self.settings_repo.list_model_defaults()
            if entry.provider_id in provider_ids
        }
        fallback_chain = [
            entry.model_id
            for entry in self.settings_repo.get_fallback_chain()
            if entry.provider_id in provider_ids
        ]

        items: list[dict] = []
        for provider in providers:
            default_entry = defaults_by_provider.get(provider.id)
            provider_models = provider.models or []
            items.append(
                {
                    "id": provider.id,
                    "provider_id": provider.id,
                    "provider_name": provider.name or provider.id,
                    "model_name": (
                        default_entry.model_id
                        if default_entry is not None
                        else (provider_models[0] if provider_models else "")
                    ),
                    "is_default": default_entry.is_default if default_entry is not None else False,
                    "fallback_chain": fallback_chain,
                }
            )

        return items
