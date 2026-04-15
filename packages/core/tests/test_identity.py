from __future__ import annotations

import pytest


def test_identity_module_exports_foundation_symbols() -> None:
    from runsight_core.identity import (
        ENTITY_ID_PATTERN,
        RESERVED_IDS,
        EntityKind,
        EntityRef,
        validate_entity_id,
    )

    assert ENTITY_ID_PATTERN is not None
    assert RESERVED_IDS is not None
    assert EntityKind is not None
    assert EntityRef is not None
    assert callable(validate_entity_id)


def test_entitykind_has_exactly_five_members_without_step() -> None:
    from runsight_core.identity import EntityKind

    assert [member.value for member in EntityKind] == [
        "soul",
        "workflow",
        "tool",
        "provider",
        "assertion",
    ]
    assert "STEP" not in EntityKind.__members__
    assert "step" not in EntityKind.__members__


def test_entityref_stringifies_as_kind_and_id() -> None:
    from runsight_core.identity import EntityKind, EntityRef

    entity_ref = EntityRef(EntityKind.SOUL, "researcher")

    assert str(entity_ref) == "soul:researcher"
    assert entity_ref.kind is EntityKind.SOUL
    assert entity_ref.entity_id == "researcher"


@pytest.mark.parametrize(
    ("entity_id", "entity_kind", "should_raise"),
    [
        ("ab", "soul", True),
        ("Researcher", "soul", True),
        ("researcher", "soul", False),
        ("my-tool-99", "tool", False),
        ("abc", "soul", False),
        ("a" * 100, "workflow", False),
        ("a" * 101, "workflow", True),
        ("1researcher", "workflow", True),
        ("researcher-", "workflow", True),
        ("my--tool", "tool", False),
        ("", "workflow", True),
    ],
)
def test_validate_entity_id_enforces_contract(
    entity_id: str, entity_kind: str, should_raise: bool
) -> None:
    from runsight_core.identity import EntityKind, validate_entity_id

    kind = EntityKind(entity_kind)

    if should_raise:
        with pytest.raises(ValueError):
            validate_entity_id(entity_id, kind)
    else:
        validate_entity_id(entity_id, kind)


def test_validate_entity_id_rejects_every_reserved_id() -> None:
    from runsight_core.identity import RESERVED_IDS, EntityKind, validate_entity_id

    reserved_ids = sorted(RESERVED_IDS)

    assert reserved_ids

    for reserved_id in reserved_ids:
        with pytest.raises(ValueError):
            validate_entity_id(reserved_id, EntityKind.TOOL)


def test_runsight_core_top_level_exports_identity_symbols() -> None:
    from runsight_core import EntityKind, EntityRef, validate_entity_id

    assert EntityKind.SOUL.value == "soul"
    assert str(EntityRef(EntityKind.SOUL, "researcher")) == "soul:researcher"
    validate_entity_id("researcher", EntityKind.SOUL)
