from __future__ import annotations

import pytest
from pydantic import ValidationError

from runsight_api.domain.value_objects import WorkflowEntity
from runsight_api.transport.routers.settings import SettingsProviderResponse
from runsight_api.transport.schemas.workflows import WorkflowResponse


def test_workflow_entity_exposes_embedded_kind() -> None:
    entity = WorkflowEntity(kind="workflow", id="research-review", name="Research Review")

    assert entity.kind == "workflow"
    assert entity.model_dump()["kind"] == "workflow"

    with pytest.raises(ValidationError):
        WorkflowEntity.model_validate(
            {
                "id": "research-review",
                "name": "Research Review",
            }
        )


def test_workflow_response_exposes_embedded_kind() -> None:
    response = WorkflowResponse(kind="workflow", id="research-review", name="Research Review")

    assert response.kind == "workflow"
    assert response.model_dump()["kind"] == "workflow"

    with pytest.raises(ValidationError):
        WorkflowResponse.model_validate(
            {
                "id": "research-review",
                "name": "Research Review",
            }
        )


def test_settings_provider_response_requires_embedded_kind() -> None:
    response = SettingsProviderResponse(
        id="openai",
        kind="provider",
        name="OpenAI",
        status="connected",
    )

    assert response.kind == "provider"

    with pytest.raises(ValidationError):
        SettingsProviderResponse.model_validate(
            {
                "id": "openai",
                "name": "OpenAI",
                "status": "connected",
            }
        )
