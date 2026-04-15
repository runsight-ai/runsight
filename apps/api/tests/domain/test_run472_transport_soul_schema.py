import pytest
from pydantic import ValidationError

from runsight_api.transport.schemas.souls import (
    SoulCreate,
    SoulResponse,
    SoulUpdate,
    SoulUsageEntry,
    SoulUsageResponse,
)


def test_soul_create_accepts_new_transport_fields():
    soul = SoulCreate(
        id="soul_1",
        kind="soul",
        name="Researcher",
        role="Researcher",
        system_prompt="Study the issue.",
        provider="openai",
        temperature=0.7,
        max_tokens=4096,
        avatar_color="#44aa88",
    )

    assert soul.id == "soul_1"
    assert soul.provider == "openai"
    assert soul.temperature == 0.7
    assert soul.max_tokens == 4096
    assert soul.avatar_color == "#44aa88"


def test_soul_create_rejects_missing_id():
    with pytest.raises(ValidationError):
        SoulCreate.model_validate(
            {
                "kind": "soul",
                "name": "Researcher",
                "role": "Researcher",
                "system_prompt": "Study the issue.",
            }
        )


def test_soul_create_rejects_missing_kind():
    with pytest.raises(ValidationError):
        SoulCreate.model_validate(
            {
                "id": "soul_1",
                "name": "Researcher",
                "role": "Researcher",
                "system_prompt": "Study the issue.",
            }
        )


def test_soul_create_rejects_missing_name():
    with pytest.raises(ValidationError):
        SoulCreate.model_validate(
            {
                "id": "soul_1",
                "kind": "soul",
                "role": "Researcher",
                "system_prompt": "Study the issue.",
            }
        )


@pytest.mark.parametrize("soul_id", ["AI-review", "99-review", "ab", "tool/evil"])
def test_soul_create_rejects_invalid_id(soul_id):
    with pytest.raises(ValidationError):
        SoulCreate.model_validate(
            {
                "id": soul_id,
                "kind": "soul",
                "name": "Researcher",
                "role": "Researcher",
                "system_prompt": "Study the issue.",
            }
        )


def test_soul_create_rejects_assertions_field():
    try:
        SoulCreate(
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Study the issue.",
            assertions=[{"type": "contains", "value": "result"}],
        )
    except ValidationError:
        return

    raise AssertionError("SoulCreate should reject assertions")


def test_soul_update_accepts_new_transport_fields():
    soul = SoulUpdate(
        provider="anthropic",
        temperature=0.0,
        max_tokens=2048,
        avatar_color="hsl(210 60% 50%)",
    )

    assert soul.provider == "anthropic"
    assert soul.temperature == 0.0
    assert soul.max_tokens == 2048
    assert soul.avatar_color == "hsl(210 60% 50%)"


def test_soul_response_exposes_new_transport_fields():
    soul = SoulResponse(
        id="soul_1",
        kind="soul",
        name="Reviewer",
        role="Reviewer",
        system_prompt="Review carefully.",
        provider="openai",
        temperature=2.0,
        max_tokens=8192,
        avatar_color="lime",
    )

    assert soul.provider == "openai"
    assert soul.temperature == 2.0
    assert soul.max_tokens == 8192
    assert soul.avatar_color == "lime"


def test_soul_usage_response_keeps_usages_and_total_shape():
    usage = SoulUsageResponse(
        soul_id="soul_1",
        usages=[SoulUsageEntry(workflow_id="wf_1", workflow_name="Workflow 1")],
        total=1,
    )

    assert usage.soul_id == "soul_1"
    assert usage.usages[0].workflow_id == "wf_1"
    assert usage.total == 1
