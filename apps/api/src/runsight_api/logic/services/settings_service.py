from __future__ import annotations

from ...data.filesystem.provider_repo import FileSystemProviderRepo
from ...data.filesystem.settings_repo import FileSystemSettingsRepo
from ...domain.entities.settings import FallbackTargetEntry, ModelDefaultEntry
from ...domain.errors import InputValidationError, ProviderNotFound


class SettingsService:
    def __init__(
        self,
        settings_repo: FileSystemSettingsRepo,
        provider_repo: FileSystemProviderRepo,
    ) -> None:
        self.settings_repo = settings_repo
        self.provider_repo = provider_repo

    def _list_active_providers(self) -> list:
        return [
            provider
            for provider in self.provider_repo.list_all()
            if getattr(provider, "is_active", True)
        ]

    def get_model_defaults(self) -> list[dict]:
        providers = self._list_active_providers()
        if not providers:
            self._list_model_defaults()
            self._list_fallback_map()
            return []

        provider_ids = {provider.id for provider in providers}
        defaults_by_provider = {
            entry.provider_id: entry
            for entry in self._list_model_defaults()
            if entry.provider_id in provider_ids
        }
        fallback_map = self._fallback_map_for_provider_ids(provider_ids)

        items: list[dict] = []
        for provider in providers:
            items.append(
                self._model_default_out(
                    provider=provider,
                    default_entry=defaults_by_provider.get(provider.id),
                    fallback_chain=self._fallback_chain_for_provider(
                        default_entry=defaults_by_provider.get(provider.id),
                        fallback_target=fallback_map.get(provider.id),
                    ),
                )
            )

        return items

    def update_model_default(
        self,
        provider_id: str,
        model_name: str | None,
        is_default: bool | None,
        fallback_chain: list[str] | None,
    ) -> dict:
        provider = self.provider_repo.get_by_id(provider_id)
        if provider is None:
            raise ProviderNotFound(f"Provider {provider_id} not found")
        if not getattr(provider, "is_active", True):
            raise InputValidationError(f"Provider {provider_id} is disabled")

        default_entry = self._default_entry_for_provider(provider_id)

        if model_name is not None:
            default_entry = ModelDefaultEntry(
                provider_id=provider_id,
                model_id=model_name,
                is_default=is_default if is_default is not None else False,
            )
            self.settings_repo.set_model_default(default_entry)
        elif is_default is not None and default_entry is not None:
            default_entry = ModelDefaultEntry(
                provider_id=provider_id,
                model_id=default_entry.model_id,
                is_default=is_default,
            )
            self.settings_repo.set_model_default(default_entry)

        persisted_fallback_chain = self._fallback_chain_from_target(
            self._fallback_target_for_provider(provider_id)
        )

        if fallback_chain is not None:
            self._persist_fallback_target(provider_id, fallback_chain)
            response_fallback_chain = fallback_chain
        else:
            response_fallback_chain = persisted_fallback_chain

        return self._model_default_out(
            provider=provider,
            default_entry=default_entry,
            fallback_chain=response_fallback_chain,
        )

    def _default_entry_for_provider(self, provider_id: str) -> ModelDefaultEntry | None:
        for entry in self._list_model_defaults():
            if entry.provider_id == provider_id:
                return entry
        return None

    def _fallback_map_for_provider_ids(
        self, provider_ids: set[str]
    ) -> dict[str, FallbackTargetEntry]:
        return {
            entry.provider_id: entry
            for entry in self._list_fallback_map()
            if entry.provider_id in provider_ids and entry.fallback_provider_id in provider_ids
        }

    def _model_default_out(
        self,
        *,
        provider,
        default_entry: ModelDefaultEntry | None,
        fallback_chain: list[str],
    ) -> dict:
        provider_models = provider.models or []
        return {
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

    def _fallback_chain_for_provider(
        self,
        *,
        default_entry: ModelDefaultEntry | None,
        fallback_target: FallbackTargetEntry | None,
    ) -> list[str]:
        if fallback_target is not None:
            return [fallback_target.fallback_model_id]
        if default_entry is not None:
            return [default_entry.model_id]
        return []

    def _fallback_chain_from_target(self, fallback_target: FallbackTargetEntry | None) -> list[str]:
        if fallback_target is None:
            return []
        return [fallback_target.fallback_model_id]

    def _persist_fallback_target(self, provider_id: str, fallback_chain: list[str]) -> None:
        if not fallback_chain:
            self.settings_repo.remove_fallback_target(provider_id)
            return

        fallback_target = self._resolve_fallback_target(provider_id, fallback_chain)
        if fallback_target is None:
            self.settings_repo.remove_fallback_target(provider_id)
            return

        self.settings_repo.set_fallback_target(fallback_target)

    def _resolve_fallback_target(
        self,
        provider_id: str,
        fallback_chain: list[str],
    ) -> FallbackTargetEntry | None:
        providers = self._list_active_providers()
        for model_name in fallback_chain:
            for provider in providers:
                if model_name in (provider.models or []):
                    return FallbackTargetEntry(
                        provider_id=provider_id,
                        fallback_provider_id=provider.id,
                        fallback_model_id=model_name,
                    )
        return None

    def _list_model_defaults(self) -> list[ModelDefaultEntry]:
        defaults = self.settings_repo.list_model_defaults()
        return defaults if isinstance(defaults, list) else []

    def _fallback_target_for_provider(self, provider_id: str) -> FallbackTargetEntry | None:
        for entry in self._list_fallback_map():
            if entry.provider_id == provider_id:
                return entry
        return None

    def _list_fallback_map(self) -> list[FallbackTargetEntry]:
        fallback_map = self.settings_repo.get_fallback_map()
        return fallback_map if isinstance(fallback_map, list) else []
