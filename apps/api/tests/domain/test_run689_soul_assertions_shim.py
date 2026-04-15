"""
RUN-689/RUN-823: SoulEntity should not accept legacy assertions payloads.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from runsight_api.domain.value_objects import SoulEntity


class TestSoulEntityAssertionsFieldRejected:
    def test_assertions_not_in_explicit_model_fields(self) -> None:
        assert "assertions" not in SoulEntity.model_fields

    def test_assertions_data_is_rejected_as_unknown(self) -> None:
        with pytest.raises(ValidationError):
            SoulEntity(
                id="soul-tester",
                kind="soul",
                name="Tester",
                role="Tester",
                assertions=[{"type": "contains", "value": "hello"}],
            )
