"""Required provider identity fields on ProviderEntity."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from runsight_api.domain.value_objects import ProviderEntity


def _provider_payload(**overrides):
    payload = {
        "id": "fixture-provider",
        "kind": "provider",
        "name": "Fixture Provider",
        "type": "fixture-provider",
        "api_key": "dummy-fixture-provider-key-ref",
        "base_url": "http://localhost/fixture-provider/v1",
        "is_active": True,
        "status": "connected",
        "models": ["fixture-provider-model"],
    }
    payload.update(overrides)
    return payload


def test_provider_entity_exposes_required_kind_field_in_schema():
    assert "kind" in ProviderEntity.model_fields
    assert ProviderEntity.model_fields["kind"].is_required()
    assert ProviderEntity.model_fields["id"].is_required()


def test_provider_entity_rejects_missing_kind():
    with pytest.raises(ValidationError) as exc_info:
        ProviderEntity.model_validate(
            {
                "id": "fixture-provider",
                "name": "Fixture Provider",
                "type": "fixture-provider",
            }
        )

    error_locs = {tuple(error["loc"]) for error in exc_info.value.errors()}
    assert ("kind",) in error_locs


def test_provider_entity_rejects_wrong_kind_value():
    with pytest.raises(ValidationError, match=r"provider"):
        ProviderEntity.model_validate(_provider_payload(kind="tool"))


@pytest.mark.parametrize(
    "provider_id",
    [
        "Fixture Provider",
        "ab",
        "http",
        "provider/evil",
    ],
)
def test_provider_entity_rejects_invalid_embedded_ids(provider_id):
    with pytest.raises(ValidationError) as exc_info:
        ProviderEntity.model_validate(_provider_payload(id=provider_id))

    assert "provider id" in str(exc_info.value).lower()
