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
        role="Researcher",
        system_prompt="Study the issue.",
        provider="openai",
        temperature=0.7,
        max_tokens=4096,
        avatar_color="#44aa88",
    )

    assert soul.id is None
    assert soul.provider == "openai"
    assert soul.temperature == 0.7
    assert soul.max_tokens == 4096
    assert soul.avatar_color == "#44aa88"


def test_soul_create_rejects_assertions_field():
    try:
        SoulCreate(
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
