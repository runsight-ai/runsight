from pathlib import Path

import yaml

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.domain.value_objects import SoulEntity
from runsight_api.logic.services.soul_service import SoulService


def test_soul_entity_accepts_new_api_fields():
    soul = SoulEntity(
        id="researcher",
        role="Researcher",
        system_prompt="Research the topic",
        provider="openai",
        temperature=0.7,
        max_tokens=4096,
        avatar_color="lime",
    )

    assert soul.provider == "openai"
    assert soul.temperature == 0.7
    assert soul.max_tokens == 4096
    assert soul.avatar_color == "lime"


def test_soul_entity_preserves_unknown_fields():
    soul = SoulEntity(
        id="legacy",
        role="Legacy Soul",
        system_prompt="Keep unknown fields intact.",
        custom_notes="test value",
        legacy_name="Legacy Soul",
    )

    assert soul.custom_notes == "test value"
    assert soul.legacy_name == "Legacy Soul"


def test_update_soul_preserves_unknown_yaml_fields_on_disk(tmp_path: Path):
    repo = SoulRepository(base_path=str(tmp_path))
    service = SoulService(repo)
    soul_path = tmp_path / "custom" / "souls" / "preserve_me.yaml"
    soul_path.parent.mkdir(parents=True, exist_ok=True)
    soul_path.write_text(
        yaml.safe_dump(
            {
                "id": "preserve_me",
                "role": "Original",
                "system_prompt": "Original prompt",
                "custom_notes": "test value",
                "legacy_name": "Legacy Soul",
            },
            sort_keys=False,
        )
    )

    updated = service.update_soul(
        "preserve_me",
        {
            "role": "Updated",
            "provider": "anthropic",
        },
    )

    reloaded = yaml.safe_load(soul_path.read_text())

    assert updated.role == "Updated"
    assert updated.provider == "anthropic"
    assert reloaded["role"] == "Updated"
    assert reloaded["provider"] == "anthropic"
    assert reloaded["custom_notes"] == "test value"
    assert reloaded["legacy_name"] == "Legacy Soul"


def test_update_soul_normalizes_null_max_tool_iterations_to_default(tmp_path: Path):
    repo = SoulRepository(base_path=str(tmp_path))
    service = SoulService(repo)
    soul_path = tmp_path / "custom" / "souls" / "normalize_me.yaml"
    soul_path.parent.mkdir(parents=True, exist_ok=True)
    soul_path.write_text(
        yaml.safe_dump(
            {
                "id": "normalize_me",
                "role": "Original",
                "system_prompt": "Original prompt",
                "max_tool_iterations": 5,
            },
            sort_keys=False,
        )
    )

    updated = service.update_soul(
        "normalize_me",
        {
            "role": "Updated",
            "max_tool_iterations": None,
        },
    )

    reloaded = yaml.safe_load(soul_path.read_text())

    assert updated.max_tool_iterations == 5
    assert reloaded["max_tool_iterations"] == 5
