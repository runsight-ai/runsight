from pathlib import Path

import yaml
import pytest
from pydantic import ValidationError

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.domain.errors import SoulNotFound
from runsight_api.domain.value_objects import SoulEntity
from runsight_api.logic.services.soul_service import SoulService


def test_soul_entity_accepts_new_api_fields():
    soul = SoulEntity(
        id="researcher",
        kind="soul",
        name="Researcher",
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


def test_soul_entity_rejects_unknown_fields():
    with pytest.raises(ValidationError, match="custom_notes"):
        SoulEntity(
            id="legacy",
            kind="soul",
            name="Legacy Soul",
            role="Legacy Soul",
            system_prompt="Reject unknown fields.",
            custom_notes="test value",
            legacy_name="Legacy Soul",
        )


def test_update_soul_rejects_unknown_yaml_fields_without_rewriting(tmp_path: Path):
    repo = SoulRepository(base_path=str(tmp_path))
    service = SoulService(repo)
    soul_path = tmp_path / "custom" / "souls" / "preserve-me.yaml"
    soul_path.parent.mkdir(parents=True, exist_ok=True)
    soul_path.write_text(
        yaml.safe_dump(
            {
                "id": "preserve-me",
                "kind": "soul",
                "name": "Original",
                "role": "Original",
                "system_prompt": "Original prompt",
                "custom_notes": "test value",
                "legacy_name": "Legacy Soul",
            },
            sort_keys=False,
        )
    )
    before = soul_path.read_text()

    with pytest.raises(SoulNotFound, match="soul:preserve-me"):
        service.update_soul(
            "preserve-me",
            {
                "role": "Updated",
                "provider": "anthropic",
            },
        )

    assert soul_path.read_text() == before


def test_update_soul_normalizes_null_max_tool_iterations_to_default(tmp_path: Path):
    repo = SoulRepository(base_path=str(tmp_path))
    service = SoulService(repo)
    soul_path = tmp_path / "custom" / "souls" / "normalize-me.yaml"
    soul_path.parent.mkdir(parents=True, exist_ok=True)
    soul_path.write_text(
        yaml.safe_dump(
            {
                "id": "normalize-me",
                "kind": "soul",
                "name": "Original",
                "role": "Original",
                "system_prompt": "Original prompt",
                "max_tool_iterations": 5,
            },
            sort_keys=False,
        )
    )

    updated = service.update_soul(
        "normalize-me",
        {
            "role": "Updated",
            "max_tool_iterations": None,
        },
    )

    reloaded = yaml.safe_load(soul_path.read_text())

    assert updated.max_tool_iterations == 5
    assert reloaded["max_tool_iterations"] == 5
