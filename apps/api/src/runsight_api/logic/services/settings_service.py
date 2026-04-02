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
        active_providers = {provider.id: provider for provider in self._list_active_providers()}
        defaults = [
            entry for entry in self._list_model_defaults() if entry.provider_id in active_providers
        ]
        fallback_map = {
            entry.provider_id: entry
            for entry in self._list_fallback_map()
            if entry.provider_id in active_providers
        }

        return [
            self._model_default_out(
                provider=active_providers[entry.provider_id],
                default_entry=entry,
                fallback_target=self._readable_fallback_target(
                    fallback_target=fallback_map.get(entry.provider_id),
                    active_providers=active_providers,
                ),
            )
            for entry in defaults
        ]

    def update_model_default(
        self,
        provider_id: str,
        model_name: str | None,
        is_default: bool | None,
        fallback_provider_id: str | None,
        fallback_model_id: str | None,
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

        fallback_target = self._fallback_target_for_provider(provider_id)
        if fallback_provider_id == "" or fallback_model_id == "":
            if fallback_provider_id == "" and fallback_model_id == "":
                self.settings_repo.remove_fallback_target(provider_id)
                fallback_target = None
            else:
                raise InputValidationError(
                    "fallback_provider_id and fallback_model_id must both be provided or both omitted"
                )
        elif fallback_provider_id is not None or fallback_model_id is not None:
            fallback_target = self._validated_fallback_target(
                provider_id=provider_id,
                fallback_provider_id=fallback_provider_id,
                fallback_model_id=fallback_model_id,
            )
            self.settings_repo.set_fallback_target(fallback_target)

        return self._model_default_out(
            provider=provider,
            default_entry=default_entry,
            fallback_target=self._readable_fallback_target_for_update(fallback_target),
        )

    def _default_entry_for_provider(self, provider_id: str) -> ModelDefaultEntry | None:
        for entry in self._list_model_defaults():
            if entry.provider_id == provider_id:
                return entry
        return None

    def _model_default_out(
        self,
        *,
        provider,
        default_entry: ModelDefaultEntry | None,
        fallback_target: FallbackTargetEntry | None,
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
            "fallback_provider_id": (
                fallback_target.fallback_provider_id if fallback_target is not None else None
            ),
            "fallback_model_id": (
                fallback_target.fallback_model_id if fallback_target is not None else None
            ),
        }

    def _readable_fallback_target(
        self,
        *,
        fallback_target: FallbackTargetEntry | None,
        active_providers: dict[str, object],
    ) -> FallbackTargetEntry | None:
        if fallback_target is None:
            return None
        if fallback_target.fallback_provider_id not in active_providers:
            return None
        return fallback_target

    def _readable_fallback_target_for_update(
        self,
        fallback_target: FallbackTargetEntry | None,
    ) -> FallbackTargetEntry | None:
        if fallback_target is None:
            return None

        target_provider = self.provider_repo.get_by_id(fallback_target.fallback_provider_id)
        if target_provider is None or not getattr(target_provider, "is_active", True):
            return None
        return fallback_target

    def _validated_fallback_target(
        self,
        *,
        provider_id: str,
        fallback_provider_id: str | None,
        fallback_model_id: str | None,
    ) -> FallbackTargetEntry:
        if fallback_provider_id is None or fallback_model_id is None:
            raise InputValidationError(
                "fallback_provider_id and fallback_model_id must both be provided or both omitted"
            )
        if fallback_provider_id == provider_id:
            raise InputValidationError("fallback target cannot reference self")

        target_provider = self.provider_repo.get_by_id(fallback_provider_id)
        if target_provider is None:
            raise ProviderNotFound(f"Provider {fallback_provider_id} not found")
        if not getattr(target_provider, "is_active", True):
            raise InputValidationError(f"Provider {fallback_provider_id} is disabled")
        if fallback_model_id not in (target_provider.models or []):
            raise InputValidationError(
                f"Model {fallback_model_id} does not belong to provider {fallback_provider_id}"
            )

        return FallbackTargetEntry(
            provider_id=provider_id,
            fallback_provider_id=fallback_provider_id,
            fallback_model_id=fallback_model_id,
        )

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
