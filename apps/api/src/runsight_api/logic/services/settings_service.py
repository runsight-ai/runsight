from __future__ import annotations

from runsight_core.identity import EntityKind, EntityRef

from ...data.filesystem.provider_repo import FileSystemProviderRepo
from ...data.filesystem.settings_repo import FileSystemSettingsRepo
from ...domain.entities.settings import FallbackTargetEntry
from ...domain.errors import InputValidationError, ProviderNotFound


def _provider_ref(provider_id: str) -> str:
    return str(EntityRef(EntityKind.PROVIDER, provider_id))


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

    def get_fallback_targets(self) -> list[dict]:
        active_providers = {provider.id: provider for provider in self._list_active_providers()}
        fallback_map = {
            entry.provider_id: entry
            for entry in self._list_fallback_map()
            if entry.provider_id in active_providers
        }

        return [
            self._fallback_target_out(
                provider=provider,
                fallback_target=self._readable_fallback_target(
                    fallback_target=fallback_map.get(provider.id),
                    active_providers=active_providers,
                ),
            )
            for provider in active_providers.values()
        ]

    def update_fallback_target(
        self,
        provider_id: str,
        fallback_provider_id: str | None,
        fallback_model_id: str | None,
    ) -> dict:
        provider = self.provider_repo.get_by_id(provider_id)
        if provider is None:
            raise ProviderNotFound(f"Provider {_provider_ref(provider_id)} not found")
        if not getattr(provider, "is_active", True):
            raise InputValidationError(f"Provider {_provider_ref(provider_id)} is disabled")

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

        return self._fallback_target_out(
            provider=provider,
            fallback_target=self._readable_fallback_target_for_update(fallback_target),
        )

    def _fallback_target_out(
        self,
        *,
        provider,
        fallback_target: FallbackTargetEntry | None,
    ) -> dict:
        return {
            "id": provider.id,
            "provider_id": provider.id,
            "provider_name": provider.name or provider.id,
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
        target_provider = active_providers.get(fallback_target.fallback_provider_id)
        if target_provider is None:
            return None
        if fallback_target.fallback_model_id not in (
            getattr(target_provider, "models", None) or []
        ):
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
        if fallback_target.fallback_model_id not in (target_provider.models or []):
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
            raise ProviderNotFound(f"Provider {_provider_ref(fallback_provider_id)} not found")
        if not getattr(target_provider, "is_active", True):
            raise InputValidationError(
                f"Provider {_provider_ref(fallback_provider_id)} is disabled"
            )
        if fallback_model_id not in (target_provider.models or []):
            raise InputValidationError(
                f"Model {fallback_model_id} does not belong to provider {_provider_ref(fallback_provider_id)}"
            )

        return FallbackTargetEntry(
            provider_id=provider_id,
            fallback_provider_id=fallback_provider_id,
            fallback_model_id=fallback_model_id,
        )

    def _fallback_target_for_provider(self, provider_id: str) -> FallbackTargetEntry | None:
        for entry in self._list_fallback_map():
            if entry.provider_id == provider_id:
                return entry
        return None

    def _list_fallback_map(self) -> list[FallbackTargetEntry]:
        fallback_map = self.settings_repo.get_fallback_map()
        return fallback_map if isinstance(fallback_map, list) else []
