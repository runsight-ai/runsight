from __future__ import annotations

from ...data.filesystem.provider_repo import FileSystemProviderRepo
from ...data.filesystem.settings_repo import FileSystemSettingsRepo
from ...domain.entities.settings import FallbackChainEntry, ModelDefaultEntry
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
            self._list_fallback_chain()
            return []

        provider_ids = {provider.id for provider in providers}
        defaults_by_provider = {
            entry.provider_id: entry
            for entry in self._list_model_defaults()
            if entry.provider_id in provider_ids
        }
        fallback_chain = self._fallback_chain_for_provider_ids(provider_ids)

        items: list[dict] = []
        for provider in providers:
            items.append(
                self._model_default_out(
                    provider=provider,
                    default_entry=defaults_by_provider.get(provider.id),
                    fallback_chain=fallback_chain,
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

        if fallback_chain is not None:
            self.settings_repo.update_fallback_chain(self._resolve_fallback_entries(fallback_chain))

        provider_ids = {item.id for item in self._list_active_providers()}
        return self._model_default_out(
            provider=provider,
            default_entry=default_entry,
            fallback_chain=(
                fallback_chain
                if fallback_chain is not None
                else self._fallback_chain_for_provider_ids(provider_ids)
            ),
        )

    def _default_entry_for_provider(self, provider_id: str) -> ModelDefaultEntry | None:
        for entry in self._list_model_defaults():
            if entry.provider_id == provider_id:
                return entry
        return None

    def _fallback_chain_for_provider_ids(self, provider_ids: set[str]) -> list[str]:
        return [
            entry.model_id
            for entry in self._list_fallback_chain()
            if entry.provider_id in provider_ids
        ]

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

    def _resolve_fallback_entries(self, fallback_chain: list[str]) -> list[FallbackChainEntry]:
        providers = self._list_active_providers()
        resolved: list[FallbackChainEntry] = []
        for model_name in fallback_chain:
            for provider in providers:
                if model_name in (provider.models or []):
                    resolved.append(
                        FallbackChainEntry(provider_id=provider.id, model_id=model_name)
                    )
                    break
        return resolved

    def _list_model_defaults(self) -> list[ModelDefaultEntry]:
        defaults = self.settings_repo.list_model_defaults()
        return defaults if isinstance(defaults, list) else []

    def _list_fallback_chain(self) -> list[FallbackChainEntry]:
        chain = self.settings_repo.get_fallback_chain()
        return chain if isinstance(chain, list) else []
