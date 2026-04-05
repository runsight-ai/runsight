from pydantic import ValidationError


def test_soul_entity_accepts_core_fields_and_avatar_color():
    from runsight_api.domain.value_objects import SoulEntity

    soul = SoulEntity(
        id="researcher",
        role="Researcher",
        system_prompt="Research the topic",
        tools=["web_search", "summarize"],
        max_tool_iterations=6,
        model_name="gpt-4o",
        custom_notes="test value",
        avatar_color="lime",
    )

    assert soul.id == "researcher"
    assert soul.role == "Researcher"
    assert soul.system_prompt == "Research the topic"
    assert soul.tools == ["web_search", "summarize"]
    assert soul.max_tool_iterations == 6
    assert soul.model_name == "gpt-4o"
    assert soul.custom_notes == "test value"
    assert soul.avatar_color == "lime"


def test_soul_entity_preserves_legacy_name_and_models_fields_as_extras():
    from runsight_api.domain.value_objects import SoulEntity

    soul = SoulEntity(id="legacy", name="Legacy Soul", models=["gpt-4o"])

    assert soul.id == "legacy"
    assert soul.role is None
    assert soul.name == "Legacy Soul"
    assert soul.models == ["gpt-4o"]


def test_soul_create_requires_role_and_system_prompt():
    from runsight_api.transport.schemas.souls import SoulCreate

    created = SoulCreate(role="Reviewer", system_prompt="Review carefully")
    assert created.role == "Reviewer"
    assert created.system_prompt == "Review carefully"

    try:
        SoulCreate()
    except ValidationError as exc:
        missing_fields = {err["loc"][-1] for err in exc.errors()}
        assert {"role", "system_prompt"}.issubset(missing_fields)
    else:
        raise AssertionError("SoulCreate() should reject missing role/system_prompt")


def test_soul_response_includes_workflow_count_default_zero():
    from runsight_api.transport.schemas.souls import SoulResponse

    soul = SoulResponse(
        id="reviewer",
        role="Reviewer",
        system_prompt="Review carefully",
        model_name="gpt-4o-mini",
    )

    assert soul.workflow_count == 0
    assert soul.model_name == "gpt-4o-mini"


def test_soul_usage_response_tracks_workflow_references():
    from runsight_api.transport.schemas.souls import SoulUsageResponse

    usage = SoulUsageResponse(
        soul_id="researcher",
        usages=[{"workflow_id": "wf-1", "workflow_name": "Research Flow"}],
        total=1,
    )

    assert usage.soul_id == "researcher"
    assert usage.total == 1
    assert usage.usages[0].workflow_id == "wf-1"
    assert usage.usages[0].workflow_name == "Research Flow"


def test_soul_errors_use_structured_409_metadata():
    from runsight_api.domain.errors import SoulAlreadyExists, SoulInUse

    in_use = SoulInUse("Soul is in use", details={"usages": [{"workflow_id": "wf-1"}]})
    duplicate = SoulAlreadyExists("Soul already exists")

    assert in_use.to_dict()["error_code"] == "SOUL_IN_USE"
    assert in_use.to_dict()["status_code"] == 409
    assert in_use.to_dict()["details"] == {"usages": [{"workflow_id": "wf-1"}]}
    assert duplicate.to_dict()["error_code"] == "SOUL_ALREADY_EXISTS"
    assert duplicate.to_dict()["status_code"] == 409
