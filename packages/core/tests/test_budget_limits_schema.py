"""
Failing tests for RUN-709: WorkflowLimitsDef + BlockLimitsDef — YAML schema models.

Tests cover:
- WorkflowLimitsDef and BlockLimitsDef exist and are importable from runsight_core.yaml.schema
- Both models enforce extra="forbid"
- RunsightWorkflowFile has limits: Optional[WorkflowLimitsDef] = None
- BaseBlockDef has limits: Optional[BlockLimitsDef] = None
- Field naming: max_duration_seconds (NOT timeout_seconds)
- on_exceed accepts only "warn" | "fail" (not "cancel")
- Validation: negative cost_cap_usd, invalid on_exceed, warn_at_pct out of range
- Unknown fields under limits raise ValidationError (extra="forbid")
- Absent limits key -> field is None, no error
- YAML round-trip: valid limits block produces correct model instances
"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError
from runsight_core.yaml.schema import (
    BlockLimitsDef,
    RunsightWorkflowFile,
    WorkflowLimitsDef,
)

# ===========================================================================
# 1. Model existence and importability
# ===========================================================================


class TestModelImportability:
    """WorkflowLimitsDef and BlockLimitsDef must exist in runsight_core.yaml.schema."""

    def test_workflow_limits_def_exists(self):
        """WorkflowLimitsDef should be a class importable from schema."""
        assert WorkflowLimitsDef is not None

    def test_block_limits_def_exists(self):
        """BlockLimitsDef should be a class importable from schema."""
        assert BlockLimitsDef is not None


# ===========================================================================
# 2. WorkflowLimitsDef field tests
# ===========================================================================


class TestWorkflowLimitsDefFields:
    """WorkflowLimitsDef field presence, types, and defaults."""

    def test_all_fields_optional_defaults(self):
        """Constructing with no args should succeed — all fields have defaults."""
        wl = WorkflowLimitsDef()
        assert wl.max_duration_seconds is None
        assert wl.cost_cap_usd is None
        assert wl.token_cap is None
        assert wl.on_exceed == "fail"
        assert wl.warn_at_pct == 0.8

    def test_max_duration_seconds_field_name(self):
        """Field is named max_duration_seconds, NOT timeout_seconds."""
        wl = WorkflowLimitsDef(max_duration_seconds=60)
        assert wl.max_duration_seconds == 60

    def test_max_duration_seconds_does_not_use_timeout_seconds(self):
        """timeout_seconds is NOT a valid field on WorkflowLimitsDef."""
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(timeout_seconds=60)  # type: ignore

    def test_cost_cap_usd_accepts_float(self):
        wl = WorkflowLimitsDef(cost_cap_usd=2.50)
        assert wl.cost_cap_usd == 2.50

    def test_cost_cap_usd_accepts_zero(self):
        wl = WorkflowLimitsDef(cost_cap_usd=0.0)
        assert wl.cost_cap_usd == 0.0

    def test_token_cap_accepts_int(self):
        wl = WorkflowLimitsDef(token_cap=10000)
        assert wl.token_cap == 10000

    def test_on_exceed_default_is_fail(self):
        wl = WorkflowLimitsDef()
        assert wl.on_exceed == "fail"

    def test_on_exceed_accepts_warn(self):
        wl = WorkflowLimitsDef(on_exceed="warn")
        assert wl.on_exceed == "warn"

    def test_on_exceed_accepts_fail(self):
        wl = WorkflowLimitsDef(on_exceed="fail")
        assert wl.on_exceed == "fail"

    def test_warn_at_pct_default_is_0_8(self):
        wl = WorkflowLimitsDef()
        assert wl.warn_at_pct == 0.8

    def test_warn_at_pct_accepts_boundary_0(self):
        wl = WorkflowLimitsDef(warn_at_pct=0.0)
        assert wl.warn_at_pct == 0.0

    def test_warn_at_pct_accepts_boundary_1(self):
        wl = WorkflowLimitsDef(warn_at_pct=1.0)
        assert wl.warn_at_pct == 1.0

    def test_all_fields_set(self):
        wl = WorkflowLimitsDef(
            max_duration_seconds=3600,
            cost_cap_usd=10.0,
            token_cap=50000,
            on_exceed="warn",
            warn_at_pct=0.9,
        )
        assert wl.max_duration_seconds == 3600
        assert wl.cost_cap_usd == 10.0
        assert wl.token_cap == 50000
        assert wl.on_exceed == "warn"
        assert wl.warn_at_pct == 0.9


# ===========================================================================
# 3. BlockLimitsDef field tests
# ===========================================================================


class TestBlockLimitsDefFields:
    """BlockLimitsDef field presence, types, and defaults."""

    def test_all_fields_optional_defaults(self):
        """Constructing with no args should succeed — all fields have defaults."""
        bl = BlockLimitsDef()
        assert bl.max_duration_seconds is None
        assert bl.cost_cap_usd is None
        assert bl.token_cap is None
        assert bl.on_exceed == "fail"

    def test_block_limits_has_no_warn_at_pct(self):
        """BlockLimitsDef does NOT have warn_at_pct (only WorkflowLimitsDef does)."""
        with pytest.raises(ValidationError):
            BlockLimitsDef(warn_at_pct=0.8)  # type: ignore

    def test_max_duration_seconds_field_name(self):
        """Field is named max_duration_seconds, NOT timeout_seconds."""
        bl = BlockLimitsDef(max_duration_seconds=120)
        assert bl.max_duration_seconds == 120

    def test_max_duration_seconds_does_not_use_timeout_seconds(self):
        """timeout_seconds is NOT a valid field on BlockLimitsDef."""
        with pytest.raises(ValidationError):
            BlockLimitsDef(timeout_seconds=60)  # type: ignore

    def test_cost_cap_usd_accepts_float(self):
        bl = BlockLimitsDef(cost_cap_usd=1.25)
        assert bl.cost_cap_usd == 1.25

    def test_on_exceed_default_is_fail(self):
        bl = BlockLimitsDef()
        assert bl.on_exceed == "fail"

    def test_on_exceed_accepts_warn(self):
        bl = BlockLimitsDef(on_exceed="warn")
        assert bl.on_exceed == "warn"

    def test_all_fields_set(self):
        bl = BlockLimitsDef(
            max_duration_seconds=600,
            cost_cap_usd=5.0,
            token_cap=10000,
            on_exceed="warn",
        )
        assert bl.max_duration_seconds == 600
        assert bl.cost_cap_usd == 5.0
        assert bl.token_cap == 10000
        assert bl.on_exceed == "warn"


# ===========================================================================
# 4. Validation — on_exceed
# ===========================================================================


class TestOnExceedValidation:
    """on_exceed must be strictly 'warn' or 'fail' — no other values."""

    def test_workflow_limits_cancel_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(on_exceed="cancel")  # type: ignore

    def test_block_limits_cancel_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(on_exceed="cancel")  # type: ignore

    def test_workflow_limits_arbitrary_string_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(on_exceed="stop")  # type: ignore

    def test_block_limits_arbitrary_string_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(on_exceed="abort")  # type: ignore

    def test_workflow_limits_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(on_exceed="")  # type: ignore

    def test_block_limits_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(on_exceed="")  # type: ignore


# ===========================================================================
# 5. Validation — cost_cap_usd
# ===========================================================================


class TestCostCapValidation:
    """cost_cap_usd must be >= 0.0."""

    def test_workflow_limits_negative_cost_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(cost_cap_usd=-1.0)

    def test_block_limits_negative_cost_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(cost_cap_usd=-0.01)

    def test_workflow_limits_zero_cost_accepted(self):
        wl = WorkflowLimitsDef(cost_cap_usd=0.0)
        assert wl.cost_cap_usd == 0.0

    def test_block_limits_zero_cost_accepted(self):
        bl = BlockLimitsDef(cost_cap_usd=0.0)
        assert bl.cost_cap_usd == 0.0


# ===========================================================================
# 6. Validation — warn_at_pct (WorkflowLimitsDef only)
# ===========================================================================


class TestWarnAtPctValidation:
    """warn_at_pct must be in [0.0, 1.0]."""

    def test_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(warn_at_pct=-0.1)

    def test_above_one_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(warn_at_pct=1.1)

    def test_boundary_zero_accepted(self):
        wl = WorkflowLimitsDef(warn_at_pct=0.0)
        assert wl.warn_at_pct == 0.0

    def test_boundary_one_accepted(self):
        wl = WorkflowLimitsDef(warn_at_pct=1.0)
        assert wl.warn_at_pct == 1.0

    def test_mid_range_accepted(self):
        wl = WorkflowLimitsDef(warn_at_pct=0.5)
        assert wl.warn_at_pct == 0.5


# ===========================================================================
# 7. Validation — max_duration_seconds
# ===========================================================================


class TestMaxDurationValidation:
    """max_duration_seconds must be >= 1 and <= 86400."""

    def test_workflow_limits_zero_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(max_duration_seconds=0)

    def test_block_limits_zero_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(max_duration_seconds=0)

    def test_workflow_limits_negative_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(max_duration_seconds=-10)

    def test_block_limits_negative_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(max_duration_seconds=-5)

    def test_workflow_limits_exceeds_86400_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(max_duration_seconds=86401)

    def test_block_limits_exceeds_86400_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(max_duration_seconds=86401)

    def test_workflow_limits_boundary_1_accepted(self):
        wl = WorkflowLimitsDef(max_duration_seconds=1)
        assert wl.max_duration_seconds == 1

    def test_workflow_limits_boundary_86400_accepted(self):
        wl = WorkflowLimitsDef(max_duration_seconds=86400)
        assert wl.max_duration_seconds == 86400

    def test_block_limits_boundary_1_accepted(self):
        bl = BlockLimitsDef(max_duration_seconds=1)
        assert bl.max_duration_seconds == 1

    def test_block_limits_boundary_86400_accepted(self):
        bl = BlockLimitsDef(max_duration_seconds=86400)
        assert bl.max_duration_seconds == 86400


# ===========================================================================
# 8. Validation — token_cap
# ===========================================================================


class TestTokenCapValidation:
    """token_cap must be >= 1."""

    def test_workflow_limits_zero_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(token_cap=0)

    def test_block_limits_zero_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(token_cap=0)

    def test_workflow_limits_negative_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(token_cap=-100)

    def test_block_limits_negative_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(token_cap=-1)

    def test_workflow_limits_one_accepted(self):
        wl = WorkflowLimitsDef(token_cap=1)
        assert wl.token_cap == 1

    def test_block_limits_one_accepted(self):
        bl = BlockLimitsDef(token_cap=1)
        assert bl.token_cap == 1


# ===========================================================================
# 9. extra="forbid" enforcement
# ===========================================================================


class TestExtraForbid:
    """Both models must reject unknown fields (extra='forbid')."""

    def test_workflow_limits_unknown_field_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(unknown_field="value")  # type: ignore

    def test_block_limits_unknown_field_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(unknown_field="value")  # type: ignore

    def test_workflow_limits_extra_nested_field_rejected(self):
        with pytest.raises(ValidationError):
            WorkflowLimitsDef(max_retries=3)  # type: ignore

    def test_block_limits_extra_nested_field_rejected(self):
        with pytest.raises(ValidationError):
            BlockLimitsDef(max_retries=3)  # type: ignore


# ===========================================================================
# 10. Integration: RunsightWorkflowFile.limits
# ===========================================================================


class TestRunsightWorkflowFileLimits:
    """RunsightWorkflowFile must have limits: Optional[WorkflowLimitsDef] = None."""

    def _make_minimal_workflow_file(self, **extra_fields):
        """Build a minimal valid RunsightWorkflowFile dict, with extra top-level fields."""
        base = {
            "id": "test",
            "kind": "workflow",
            "workflow": {"name": "test", "entry": "block1"},
        }
        base.update(extra_fields)
        return RunsightWorkflowFile.model_validate(base)

    def test_absent_limits_is_none(self):
        """When limits key is absent, field defaults to None."""
        wf = self._make_minimal_workflow_file()
        assert wf.limits is None

    def test_explicit_none_limits(self):
        """When limits is explicitly None, field is None."""
        wf = self._make_minimal_workflow_file(limits=None)
        assert wf.limits is None

    def test_valid_limits_parsed(self):
        """When limits is a valid dict, it produces a WorkflowLimitsDef."""
        wf = self._make_minimal_workflow_file(limits={"cost_cap_usd": 2.00, "on_exceed": "fail"})
        assert wf.limits is not None
        assert isinstance(wf.limits, WorkflowLimitsDef)
        assert wf.limits.cost_cap_usd == 2.00
        assert wf.limits.on_exceed == "fail"

    def test_limits_with_all_fields(self):
        """All WorkflowLimitsDef fields round-trip through RunsightWorkflowFile."""
        wf = self._make_minimal_workflow_file(
            limits={
                "max_duration_seconds": 7200,
                "cost_cap_usd": 5.0,
                "token_cap": 100000,
                "on_exceed": "warn",
                "warn_at_pct": 0.9,
            }
        )
        assert wf.limits.max_duration_seconds == 7200
        assert wf.limits.cost_cap_usd == 5.0
        assert wf.limits.token_cap == 100000
        assert wf.limits.on_exceed == "warn"
        assert wf.limits.warn_at_pct == 0.9

    def test_limits_invalid_on_exceed_cancel(self):
        """on_exceed='cancel' in limits raises ValidationError on the workflow file."""
        with pytest.raises(ValidationError):
            self._make_minimal_workflow_file(limits={"on_exceed": "cancel"})

    def test_limits_unknown_field_raises(self):
        """Unknown field in limits raises ValidationError (extra=forbid)."""
        with pytest.raises(ValidationError):
            self._make_minimal_workflow_file(limits={"cost_cap_usd": 1.0, "bogus_field": True})


# ===========================================================================
# 11. Integration: BaseBlockDef.limits
# ===========================================================================


class TestBaseBlockDefLimits:
    """BaseBlockDef must have limits: Optional[BlockLimitsDef] = None."""

    def _make_minimal_block(self, **extra_fields):
        """Build a minimal valid BaseBlockDef-compatible dict with extra fields.

        We use type='linear' and soul_ref to satisfy LinearBlockDef requirements,
        but test via BaseBlockDef field presence.
        """
        from runsight_core.blocks.linear import LinearBlockDef

        base = {"type": "linear", "soul_ref": "s1"}
        base.update(extra_fields)
        return LinearBlockDef.model_validate(base)

    def test_absent_limits_is_none(self):
        """When limits key is absent on a block, field defaults to None."""
        block = self._make_minimal_block()
        assert block.limits is None

    def test_explicit_none_limits(self):
        block = self._make_minimal_block(limits=None)
        assert block.limits is None

    def test_valid_limits_parsed(self):
        """When limits is a valid dict, it produces a BlockLimitsDef."""
        block = self._make_minimal_block(limits={"cost_cap_usd": 0.50, "on_exceed": "warn"})
        assert block.limits is not None
        assert isinstance(block.limits, BlockLimitsDef)
        assert block.limits.cost_cap_usd == 0.50
        assert block.limits.on_exceed == "warn"

    def test_limits_with_all_block_fields(self):
        """All BlockLimitsDef fields round-trip through a block."""
        block = self._make_minimal_block(
            limits={
                "max_duration_seconds": 300,
                "cost_cap_usd": 1.0,
                "token_cap": 5000,
                "on_exceed": "fail",
            }
        )
        assert block.limits.max_duration_seconds == 300
        assert block.limits.cost_cap_usd == 1.0
        assert block.limits.token_cap == 5000
        assert block.limits.on_exceed == "fail"

    def test_limits_invalid_on_exceed_raises(self):
        with pytest.raises(ValidationError):
            self._make_minimal_block(limits={"on_exceed": "cancel"})

    def test_limits_unknown_field_raises(self):
        with pytest.raises(ValidationError):
            self._make_minimal_block(limits={"mystery": 42})

    def test_block_limits_does_not_accept_warn_at_pct(self):
        """warn_at_pct is a WorkflowLimitsDef-only field, not on BlockLimitsDef."""
        with pytest.raises(ValidationError):
            self._make_minimal_block(limits={"warn_at_pct": 0.5})


# ===========================================================================
# 12. Acceptance scenarios: YAML round-trip
# ===========================================================================


class TestYamlRoundTrip:
    """End-to-end acceptance scenarios parsing YAML strings into RunsightWorkflowFile."""

    _MINIMAL_YAML_TEMPLATE = """\
id: test
kind: workflow
workflow:
  name: test
  entry: block1
{limits_section}
"""

    def _parse_yaml_to_workflow_file(self, yaml_str: str) -> RunsightWorkflowFile:
        """Parse a YAML string through safe_load then model_validate."""
        raw = yaml.safe_load(yaml_str)
        return RunsightWorkflowFile.model_validate(raw)

    def test_scenario_valid_limits(self):
        """
        Given a YAML with limits: {cost_cap_usd: 2.00, on_exceed: fail}
        When parsed
        Then workflow_file.limits.cost_cap_usd == 2.00 and on_exceed == "fail"
        """
        yaml_str = self._MINIMAL_YAML_TEMPLATE.format(
            limits_section="limits:\n  cost_cap_usd: 2.00\n  on_exceed: fail"
        )
        wf = self._parse_yaml_to_workflow_file(yaml_str)
        assert wf.limits is not None
        assert wf.limits.cost_cap_usd == 2.00
        assert wf.limits.on_exceed == "fail"

    def test_scenario_invalid_on_exceed_cancel(self):
        """
        Given a YAML with limits: {on_exceed: cancel}
        When parsed
        Then ValidationError raised (cancel is not a valid value)
        """
        yaml_str = self._MINIMAL_YAML_TEMPLATE.format(limits_section="limits:\n  on_exceed: cancel")
        with pytest.raises(ValidationError):
            self._parse_yaml_to_workflow_file(yaml_str)

    def test_scenario_no_limits_key(self):
        """
        Given a YAML with no limits key
        When parsed
        Then workflow_file.limits is None
        """
        yaml_str = self._MINIMAL_YAML_TEMPLATE.format(limits_section="")
        wf = self._parse_yaml_to_workflow_file(yaml_str)
        assert wf.limits is None

    def test_scenario_negative_cost_cap(self):
        """Negative cost_cap_usd in YAML raises ValidationError."""
        yaml_str = self._MINIMAL_YAML_TEMPLATE.format(
            limits_section="limits:\n  cost_cap_usd: -5.0"
        )
        with pytest.raises(ValidationError):
            self._parse_yaml_to_workflow_file(yaml_str)

    def test_scenario_warn_at_pct_out_of_range(self):
        """warn_at_pct > 1.0 in YAML raises ValidationError."""
        yaml_str = self._MINIMAL_YAML_TEMPLATE.format(limits_section="limits:\n  warn_at_pct: 1.5")
        with pytest.raises(ValidationError):
            self._parse_yaml_to_workflow_file(yaml_str)

    def test_scenario_unknown_limits_field_in_yaml(self):
        """Unknown field under limits in YAML raises ValidationError."""
        yaml_str = self._MINIMAL_YAML_TEMPLATE.format(
            limits_section="limits:\n  cost_cap_usd: 1.0\n  unknown_key: true"
        )
        with pytest.raises(ValidationError):
            self._parse_yaml_to_workflow_file(yaml_str)

    def test_scenario_full_limits_block(self):
        """All WorkflowLimitsDef fields parse correctly from YAML."""
        yaml_str = self._MINIMAL_YAML_TEMPLATE.format(
            limits_section=(
                "limits:\n"
                "  max_duration_seconds: 1800\n"
                "  cost_cap_usd: 10.0\n"
                "  token_cap: 200000\n"
                "  on_exceed: warn\n"
                "  warn_at_pct: 0.75"
            )
        )
        wf = self._parse_yaml_to_workflow_file(yaml_str)
        assert wf.limits.max_duration_seconds == 1800
        assert wf.limits.cost_cap_usd == 10.0
        assert wf.limits.token_cap == 200000
        assert wf.limits.on_exceed == "warn"
        assert wf.limits.warn_at_pct == 0.75
