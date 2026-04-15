import pytest
from pydantic import ValidationError
from runsight_core.primitives import Soul


def test_soul_validation():
    soul = Soul(id="test1", kind="soul", name="Coder", role="Coder", system_prompt="Write code.")
    assert soul.id == "test1"
    assert soul.kind == "soul"
    assert soul.name == "Coder"
    assert soul.role == "Coder"
    assert soul.system_prompt == "Write code."
    assert soul.tools is None

    with pytest.raises(ValidationError):
        Soul(role="Coder", system_prompt="Missing id")
