"""
Failing tests for RUN-266: exit_handle on BlockResult + ExitDef / exits on BaseBlockDef.

Foundation ticket: add data-model fields that enable named ports.
Zero behavior change — purely additive schema additions.

Tests cover:
- AC1: BlockResult(output="x") still works (exit_handle defaults to None)
- AC2: BlockResult(output="x", exit_handle="pass") stores the handle
- AC3: BlockResult.from_string("x") still works (exit_handle is None)
- AC4: ExitDef validates id and label are required
- AC5: BaseBlockDef with exits parses correctly
- AC6: BaseBlockDef without exits parses (backward compat)
- AC7: Existing tests pass unchanged (covered implicitly — no existing tests modified)
"""

import pytest
from pydantic import ValidationError

# ==============================================================================
# AC1 + AC2 + AC3: BlockResult.exit_handle
# ==============================================================================


class TestBlockResultExitHandle:
    """Tests for the new exit_handle field on BlockResult."""

    def test_exit_handle_defaults_to_none(self):
        """AC1: BlockResult(output='x') works — exit_handle defaults to None."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="hello")
        assert result.output == "hello"
        assert result.exit_handle is None

    def test_exit_handle_explicit_none(self):
        """AC1 variant: exit_handle=None can be passed explicitly."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="hello", exit_handle=None)
        assert result.exit_handle is None

    def test_exit_handle_set_to_string(self):
        """AC2: BlockResult(output='x', exit_handle='pass') stores the handle."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="decided", exit_handle="pass")
        assert result.output == "decided"
        assert result.exit_handle == "pass"

    def test_exit_handle_various_values(self):
        """AC2 variant: exit_handle accepts arbitrary string identifiers."""
        from runsight_core.state import BlockResult

        for handle in ("pass", "fail", "case_a", "retry", "error", "default"):
            result = BlockResult(output="x", exit_handle=handle)
            assert result.exit_handle == handle

    def test_exit_handle_preserved_in_model_dump(self):
        """exit_handle appears in model_dump() when set."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="x", exit_handle="fail")
        dumped = result.model_dump()
        assert dumped["exit_handle"] == "fail"

    def test_exit_handle_none_in_model_dump(self):
        """exit_handle appears as None in model_dump() when not set."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="x")
        dumped = result.model_dump()
        assert "exit_handle" in dumped
        assert dumped["exit_handle"] is None

    def test_exit_handle_excluded_when_none_with_exclude_none(self):
        """exit_handle excluded from model_dump(exclude_none=True) when None."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="x")
        dumped = result.model_dump(exclude_none=True)
        assert "exit_handle" not in dumped

    def test_from_string_exit_handle_is_none(self):
        """AC3: BlockResult.from_string('x') still works; exit_handle is None."""
        from runsight_core.state import BlockResult

        result = BlockResult.from_string("hello")
        assert isinstance(result, BlockResult)
        assert result.output == "hello"
        assert result.exit_handle is None

    def test_exit_handle_with_all_other_fields(self):
        """exit_handle coexists with all existing BlockResult fields."""
        from runsight_core.state import BlockResult

        result = BlockResult(
            output="generated text",
            artifact_ref="s3://bucket/artifact.json",
            artifact_type="json",
            metadata={"model": "gpt-4", "tokens": 150},
            exit_handle="pass",
        )
        assert result.output == "generated text"
        assert result.artifact_ref == "s3://bucket/artifact.json"
        assert result.artifact_type == "json"
        assert result.metadata == {"model": "gpt-4", "tokens": 150}
        assert result.exit_handle == "pass"

    def test_exit_handle_str_representation_unchanged(self):
        """__str__ still returns output regardless of exit_handle."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="hello", exit_handle="pass")
        assert str(result) == "hello"

    def test_exit_handle_not_iterable(self):
        """BlockResult with exit_handle is still not iterable."""
        from runsight_core.state import BlockResult

        result = BlockResult(output="x", exit_handle="pass")
        with pytest.raises(TypeError, match="not iterable"):
            iter(result)


# ==============================================================================
# AC4: ExitDef model
# ==============================================================================


class TestExitDef:
    """Tests for the new ExitDef model in yaml/schema.py."""

    def test_exitdef_valid(self):
        """ExitDef with id and label is valid."""
        from runsight_core.yaml.schema import ExitDef

        ed = ExitDef(id="pass", label="Pass")
        assert ed.id == "pass"
        assert ed.label == "Pass"

    def test_exitdef_missing_id_raises(self):
        """AC4: ExitDef without id raises ValidationError."""
        from runsight_core.yaml.schema import ExitDef

        with pytest.raises(ValidationError):
            ExitDef(label="Pass")  # type: ignore

    def test_exitdef_missing_label_raises(self):
        """AC4: ExitDef without label raises ValidationError."""
        from runsight_core.yaml.schema import ExitDef

        with pytest.raises(ValidationError):
            ExitDef(id="pass")  # type: ignore

    def test_exitdef_missing_both_raises(self):
        """AC4: ExitDef with no fields raises ValidationError."""
        from runsight_core.yaml.schema import ExitDef

        with pytest.raises(ValidationError):
            ExitDef()  # type: ignore

    def test_exitdef_model_dump(self):
        """ExitDef serializes to dict with id and label."""
        from runsight_core.yaml.schema import ExitDef

        ed = ExitDef(id="fail", label="Fail")
        dumped = ed.model_dump()
        assert dumped == {"id": "fail", "label": "Fail"}

    def test_exitdef_from_dict(self):
        """ExitDef can be constructed from a dict."""
        from runsight_core.yaml.schema import ExitDef

        data = {"id": "case_a", "label": "Case A"}
        ed = ExitDef(**data)
        assert ed.id == "case_a"
        assert ed.label == "Case A"

    def test_exitdef_multiple_instances(self):
        """Multiple ExitDef instances can coexist in a list."""
        from runsight_core.yaml.schema import ExitDef

        exits = [
            ExitDef(id="pass", label="Pass"),
            ExitDef(id="fail", label="Fail"),
            ExitDef(id="error", label="Error"),
        ]
        assert len(exits) == 3
        assert exits[0].id == "pass"
        assert exits[1].id == "fail"
        assert exits[2].id == "error"


# ==============================================================================
# AC5 + AC6: BaseBlockDef.exits
# ==============================================================================


class TestBaseBlockDefExits:
    """Tests for the new exits field on BaseBlockDef."""

    def test_exits_defaults_to_none(self):
        """AC6: BaseBlockDef without exits is backward-compatible (defaults to None)."""
        from runsight_core.yaml.schema import BaseBlockDef

        block = BaseBlockDef(type="linear")
        assert block.exits is None

    def test_exits_explicit_none(self):
        """AC6 variant: exits=None can be passed explicitly."""
        from runsight_core.yaml.schema import BaseBlockDef

        block = BaseBlockDef(type="linear", exits=None)
        assert block.exits is None

    def test_exits_with_exit_defs(self):
        """AC5: BaseBlockDef with exits list parses correctly."""
        from runsight_core.yaml.schema import BaseBlockDef, ExitDef

        exits = [
            ExitDef(id="pass", label="Pass"),
            ExitDef(id="fail", label="Fail"),
        ]
        block = BaseBlockDef(type="linear", exits=exits)
        assert block.exits is not None
        assert len(block.exits) == 2
        assert block.exits[0].id == "pass"
        assert block.exits[0].label == "Pass"
        assert block.exits[1].id == "fail"
        assert block.exits[1].label == "Fail"

    def test_exits_empty_list(self):
        """BaseBlockDef with exits=[] is valid (explicit no exits)."""
        from runsight_core.yaml.schema import BaseBlockDef

        block = BaseBlockDef(type="linear", exits=[])
        assert block.exits == []

    def test_exits_single_exit(self):
        """BaseBlockDef with a single exit is valid."""
        from runsight_core.yaml.schema import BaseBlockDef, ExitDef

        block = BaseBlockDef(
            type="linear",
            exits=[ExitDef(id="default", label="Default")],
        )
        assert len(block.exits) == 1
        assert block.exits[0].id == "default"

    def test_exits_model_dump(self):
        """exits serializes correctly in model_dump()."""
        from runsight_core.yaml.schema import BaseBlockDef, ExitDef

        block = BaseBlockDef(
            type="linear",
            exits=[ExitDef(id="pass", label="Pass")],
        )
        dumped = block.model_dump()
        assert "exits" in dumped
        assert dumped["exits"] == [{"id": "pass", "label": "Pass"}]

    def test_exits_none_in_model_dump(self):
        """exits is None in model_dump() when not provided."""
        from runsight_core.yaml.schema import BaseBlockDef

        block = BaseBlockDef(type="linear")
        dumped = block.model_dump()
        assert "exits" in dumped
        assert dumped["exits"] is None

    def test_exits_excluded_with_exclude_none(self):
        """exits excluded from model_dump(exclude_none=True) when None."""
        from runsight_core.yaml.schema import BaseBlockDef

        block = BaseBlockDef(type="linear")
        dumped = block.model_dump(exclude_none=True)
        assert "exits" not in dumped

    def test_exits_from_raw_dicts(self):
        """AC5: BaseBlockDef with exits as raw dicts parses (Pydantic coercion)."""
        from runsight_core.yaml.schema import BaseBlockDef

        block = BaseBlockDef(
            type="linear",
            exits=[
                {"id": "pass", "label": "Pass"},
                {"id": "fail", "label": "Fail"},
            ],
        )
        assert block.exits is not None
        assert len(block.exits) == 2
        assert block.exits[0].id == "pass"
        assert block.exits[1].label == "Fail"

    def test_existing_fields_still_work_with_exits(self):
        """Existing BaseBlockDef fields work alongside exits."""
        from runsight_core.yaml.schema import BaseBlockDef, CaseDef, ExitDef

        block = BaseBlockDef(
            type="linear",
            stateful=True,
            output_conditions=[CaseDef(case_id="c1", default=True)],
            exits=[ExitDef(id="pass", label="Pass")],
        )
        assert block.type == "linear"
        assert block.stateful is True
        assert len(block.output_conditions) == 1
        assert len(block.exits) == 1


# ==============================================================================
# AC5 (YAML round-trip): BaseBlockDef parses from dict as YAML would
# ==============================================================================


class TestExitsYAMLParsing:
    """Simulate YAML parsing by constructing from dicts (as yaml.safe_load would produce)."""

    def test_parse_block_with_exits_from_yaml_dict(self):
        """BaseBlockDef parses from a YAML-like dict with exits."""
        from runsight_core.yaml.schema import BaseBlockDef

        yaml_data = {
            "type": "linear",
            "exits": [
                {"id": "pass", "label": "Pass"},
                {"id": "fail", "label": "Fail"},
            ],
        }
        block = BaseBlockDef(**yaml_data)
        assert block.exits is not None
        assert len(block.exits) == 2

    def test_parse_block_without_exits_from_yaml_dict(self):
        """AC6: BaseBlockDef parses from a YAML-like dict without exits (backward compat)."""
        from runsight_core.yaml.schema import BaseBlockDef

        yaml_data = {"type": "linear"}
        block = BaseBlockDef(**yaml_data)
        assert block.exits is None

    def test_parse_block_with_exits_null_from_yaml_dict(self):
        """BaseBlockDef parses from YAML dict where exits is explicitly null."""
        from runsight_core.yaml.schema import BaseBlockDef

        yaml_data = {"type": "linear", "exits": None}
        block = BaseBlockDef(**yaml_data)
        assert block.exits is None


# ==============================================================================
# AC7: Backward compatibility — existing BlockResult usage unchanged
# ==============================================================================


class TestBackwardCompatibility:
    """Ensure adding exit_handle / exits does not break existing usage patterns."""

    def test_block_result_in_workflow_state(self):
        """BlockResult with exit_handle works in WorkflowState.results."""
        from runsight_core.state import BlockResult, WorkflowState

        br = BlockResult(output="done", exit_handle="pass")
        state = WorkflowState(results={"block1": br})
        assert state.results["block1"].output == "done"
        assert state.results["block1"].exit_handle == "pass"

    def test_block_result_without_exit_handle_in_workflow_state(self):
        """BlockResult without exit_handle still works in WorkflowState.results."""
        from runsight_core.state import BlockResult, WorkflowState

        br = BlockResult(output="done")
        state = WorkflowState(results={"block1": br})
        assert state.results["block1"].output == "done"
        assert state.results["block1"].exit_handle is None

    def test_model_copy_preserves_exit_handle(self):
        """model_copy preserves exit_handle on BlockResult."""
        from runsight_core.state import BlockResult, WorkflowState

        br = BlockResult(output="done", exit_handle="fail")
        state1 = WorkflowState(results={"a": br})
        state2 = state1.model_copy(update={"results": {"a": br, "b": BlockResult(output="new")}})
        assert state2.results["a"].exit_handle == "fail"
        assert state2.results["b"].exit_handle is None

    def test_exitdef_importable_from_schema(self):
        """ExitDef is importable from runsight_core.yaml.schema."""
        from runsight_core.yaml.schema import ExitDef

        assert ExitDef is not None
