from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestSoulEntityIdentity:
    def test_soul_entity_requires_embedded_kind_and_name(self) -> None:
        from runsight_api.domain.value_objects import SoulEntity

        soul = SoulEntity(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research the topic.",
        )

        assert soul.id == "researcher"
        assert soul.kind == "soul"
        assert soul.name == "Researcher"
        assert soul.role == "Researcher"
        assert soul.system_prompt == "Research the topic."

    @pytest.mark.parametrize(
        ("kwargs", "expected_field"),
        [
            (
                {"id": "researcher", "role": "Researcher", "system_prompt": "Research the topic."},
                "kind",
            ),
            (
                {
                    "id": "researcher",
                    "kind": "soul",
                    "role": "Researcher",
                    "system_prompt": "Research the topic.",
                },
                "name",
            ),
        ],
    )
    def test_soul_entity_direct_constructor_rejects_missing_identity_fields(
        self, kwargs: dict, expected_field: str
    ) -> None:
        from runsight_api.domain.value_objects import SoulEntity

        with pytest.raises(ValidationError):
            SoulEntity(**kwargs)

    @pytest.mark.parametrize(
        ("payload", "expected_field"),
        [
            ({"id": "researcher", "kind": "soul", "role": "Researcher"}, "name"),
            ({"id": "researcher", "name": "Researcher", "role": "Researcher"}, "kind"),
        ],
    )
    def test_missing_identity_fields_are_rejected(self, payload: dict, expected_field: str) -> None:
        from runsight_api.domain.value_objects import SoulEntity

        with pytest.raises(ValidationError):
            SoulEntity.model_validate(payload)

    @pytest.mark.parametrize("kind", ["tool", "workflow", "provider"])
    def test_wrong_kind_is_rejected(self, kind: str) -> None:
        from runsight_api.domain.value_objects import SoulEntity

        with pytest.raises(ValidationError):
            SoulEntity.model_validate(
                {
                    "id": "researcher",
                    "kind": kind,
                    "name": "Researcher",
                    "role": "Researcher",
                    "system_prompt": "Research the topic.",
                }
            )

    @pytest.mark.parametrize("soul_id", ["AI-review", "99-review", "ab", "tool/evil"])
    def test_soul_entity_rejects_invalid_embedded_id(self, soul_id: str) -> None:
        from runsight_api.domain.value_objects import SoulEntity

        with pytest.raises(ValidationError):
            SoulEntity.model_validate(
                {
                    "id": soul_id,
                    "kind": "soul",
                    "name": "Researcher",
                    "role": "Researcher",
                    "system_prompt": "Research the topic.",
                }
            )


class TestSoulResponseIdentity:
    def test_soul_response_exposes_embedded_kind_and_name(self) -> None:
        from runsight_api.transport.schemas.souls import SoulResponse

        soul = SoulResponse(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research the topic.",
        )

        assert soul.id == "researcher"
        assert soul.kind == "soul"
        assert soul.name == "Researcher"
        assert soul.role == "Researcher"
        assert soul.system_prompt == "Research the topic."

    @pytest.mark.parametrize(
        ("kwargs", "expected_field"),
        [
            (
                {"id": "researcher", "role": "Researcher", "system_prompt": "Research the topic."},
                "kind",
            ),
            (
                {
                    "id": "researcher",
                    "kind": "soul",
                    "role": "Researcher",
                    "system_prompt": "Research the topic.",
                },
                "name",
            ),
        ],
    )
    def test_soul_response_direct_constructor_rejects_missing_identity_fields(
        self, kwargs: dict, expected_field: str
    ) -> None:
        from runsight_api.transport.schemas.souls import SoulResponse

        with pytest.raises(ValidationError):
            SoulResponse(**kwargs)
