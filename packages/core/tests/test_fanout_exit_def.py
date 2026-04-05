"""
Failing tests for RUN-285: Add DispatchExitDef to schema.

DispatchExitDef extends ExitDef with per-exit soul_ref and task fields.
It should inherit id and label from ExitDef, require soul_ref and task,
and reject extra fields (extra="forbid").
"""

import pytest
from pydantic import ValidationError


class TestDispatchExitDefImportAndSubclass:
    """DispatchExitDef is importable and inherits from ExitDef."""

    def test_importable_from_schema(self):
        """DispatchExitDef is importable from runsight_core.yaml.schema."""
        from runsight_core.yaml.schema import DispatchExitDef

        assert DispatchExitDef is not None

    def test_is_subclass_of_exitdef(self):
        """DispatchExitDef is a subclass of ExitDef."""
        from runsight_core.yaml.schema import DispatchExitDef, ExitDef

        assert issubclass(DispatchExitDef, ExitDef)


class TestDispatchExitDefValidConstruction:
    """DispatchExitDef validates with all 4 fields: id, label, soul_ref, task."""

    def test_valid_with_all_fields(self):
        """Constructing with id, label, soul_ref, and task succeeds."""
        from runsight_core.yaml.schema import DispatchExitDef

        obj = DispatchExitDef(
            id="exit_a",
            label="Exit A",
            soul_ref="analyst",
            task="Summarize the data",
        )
        assert obj.id == "exit_a"
        assert obj.label == "Exit A"
        assert obj.soul_ref == "analyst"
        assert obj.task == "Summarize the data"

    def test_model_dump_contains_all_four_fields(self):
        """model_dump() returns dict with all 4 fields."""
        from runsight_core.yaml.schema import DispatchExitDef

        obj = DispatchExitDef(
            id="exit_b",
            label="Exit B",
            soul_ref="reviewer",
            task="Review the output",
        )
        dumped = obj.model_dump()
        assert dumped == {
            "id": "exit_b",
            "label": "Exit B",
            "soul_ref": "reviewer",
            "task": "Review the output",
        }


class TestDispatchExitDefInheritsIdAndLabel:
    """DispatchExitDef inherits id and label from ExitDef."""

    def test_id_accessible_on_instance(self):
        """id field inherited from ExitDef is accessible."""
        from runsight_core.yaml.schema import DispatchExitDef

        obj = DispatchExitDef(id="port_1", label="Port 1", soul_ref="s1", task="t1")
        assert obj.id == "port_1"

    def test_label_accessible_on_instance(self):
        """label field inherited from ExitDef is accessible."""
        from runsight_core.yaml.schema import DispatchExitDef

        obj = DispatchExitDef(id="port_2", label="Port 2", soul_ref="s2", task="t2")
        assert obj.label == "Port 2"


class TestDispatchExitDefRequiredFields:
    """soul_ref and task are required; missing either raises ValidationError."""

    def test_missing_soul_ref_raises(self):
        """Omitting soul_ref raises ValidationError."""
        from runsight_core.yaml.schema import DispatchExitDef

        with pytest.raises(ValidationError):
            DispatchExitDef(id="x", label="X", task="do stuff")  # type: ignore

    def test_missing_task_raises(self):
        """Omitting task raises ValidationError."""
        from runsight_core.yaml.schema import DispatchExitDef

        with pytest.raises(ValidationError):
            DispatchExitDef(id="x", label="X", soul_ref="agent")  # type: ignore

    def test_missing_both_soul_ref_and_task_raises(self):
        """Omitting both soul_ref and task raises ValidationError."""
        from runsight_core.yaml.schema import DispatchExitDef

        with pytest.raises(ValidationError):
            DispatchExitDef(id="x", label="X")  # type: ignore


class TestDispatchExitDefExtraForbid:
    """extra='forbid' rejects unknown fields."""

    def test_extra_field_rejected(self):
        """Passing an unknown field raises ValidationError."""
        from runsight_core.yaml.schema import DispatchExitDef

        with pytest.raises(ValidationError):
            DispatchExitDef(
                id="x",
                label="X",
                soul_ref="agent",
                task="do stuff",
                bogus="nope",
            )
