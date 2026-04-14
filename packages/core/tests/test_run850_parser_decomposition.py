"""
RUN-850: Failing tests for parse_workflow_yaml decomposition.

AC:
1. Function decomposed into focused sub-functions (each ≤50 lines)
2. Block-bridging consolidated into a single iteration pass
3. All existing tests still pass
4. Each sub-function is independently testable

These tests are written BEFORE the refactor — they will fail (ImportError or
assertion failures) against the current 388-line god function and pass only
once the Green team completes the decomposition.
"""

from __future__ import annotations

import inspect
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

# ---------------------------------------------------------------------------
# Test Group 1: Sub-function existence
# Each test imports a named sub-function that does not yet exist.
# Expected failure mode: ImportError.
# ---------------------------------------------------------------------------


class TestSubFunctionExistence:
    """Sub-functions must exist as module-level callables after decomposition."""

    def test_normalize_input_exists(self):
        """A dedicated input-normalization sub-function must be importable."""
        from runsight_core.yaml.parser import _normalize_workflow_input  # noqa: F401

        assert callable(_normalize_workflow_input)

    def test_bridge_block_attributes_exists(self):
        """A consolidated block-bridging function must exist and be callable."""
        from runsight_core.yaml.parser import _bridge_block_attributes  # noqa: F401

        assert callable(_bridge_block_attributes)

    def test_resolve_tools_for_souls_exists(self):
        """A dedicated tool-resolution sub-function must be importable."""
        from runsight_core.yaml.parser import _resolve_tools_for_souls  # noqa: F401

        assert callable(_resolve_tools_for_souls)

    def test_validate_inputs_and_detect_cycles_exists(self):
        """A dedicated input-validation / cycle-detection sub-function must exist."""
        from runsight_core.yaml.parser import _validate_inputs_and_detect_cycles  # noqa: F401

        assert callable(_validate_inputs_and_detect_cycles)

    def test_assemble_workflow_exists(self):
        """A dedicated workflow-assembly sub-function must exist."""
        from runsight_core.yaml.parser import _assemble_workflow  # noqa: F401

        assert callable(_assemble_workflow)


# ---------------------------------------------------------------------------
# Test Group 2: Sub-function line counts
# Uses inspect.getsource() to count non-empty, non-comment lines.
# Expected failure mode: assertion error — current function is 388 lines.
# ---------------------------------------------------------------------------


def _count_non_blank_non_comment_lines(source: str) -> int:
    """Count lines that are neither blank nor pure comments."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


class TestSubFunctionLineCounts:
    """Every extracted sub-function must be ≤50 non-blank, non-comment lines."""

    def test_parse_workflow_yaml_orchestrator_is_short(self):
        """After decomposition parse_workflow_yaml should be ≤60 lines (orchestrator only)."""
        from runsight_core.yaml import parser

        source = inspect.getsource(parser.parse_workflow_yaml)
        line_count = _count_non_blank_non_comment_lines(source)
        assert line_count <= 60, (
            f"parse_workflow_yaml is {line_count} non-blank/non-comment lines; "
            f"expected ≤60 after extraction of sub-functions"
        )

    def test_normalize_input_under_50_lines(self):
        """_normalize_workflow_input must be ≤50 non-blank, non-comment lines."""
        from runsight_core.yaml.parser import _normalize_workflow_input

        source = inspect.getsource(_normalize_workflow_input)
        line_count = _count_non_blank_non_comment_lines(source)
        assert line_count <= 50, f"_normalize_workflow_input is {line_count} lines; expected ≤50"

    def test_bridge_block_attributes_under_50_lines(self):
        """_bridge_block_attributes must be ≤50 non-blank, non-comment lines."""
        from runsight_core.yaml.parser import _bridge_block_attributes

        source = inspect.getsource(_bridge_block_attributes)
        line_count = _count_non_blank_non_comment_lines(source)
        assert line_count <= 50, f"_bridge_block_attributes is {line_count} lines; expected ≤50"

    def test_resolve_tools_for_souls_under_50_lines(self):
        """_resolve_tools_for_souls must be ≤50 non-blank, non-comment lines."""
        from runsight_core.yaml.parser import _resolve_tools_for_souls

        source = inspect.getsource(_resolve_tools_for_souls)
        line_count = _count_non_blank_non_comment_lines(source)
        assert line_count <= 50, f"_resolve_tools_for_souls is {line_count} lines; expected ≤50"

    def test_validate_inputs_and_detect_cycles_under_50_lines(self):
        """_validate_inputs_and_detect_cycles must be ≤50 non-blank, non-comment lines."""
        from runsight_core.yaml.parser import _validate_inputs_and_detect_cycles

        source = inspect.getsource(_validate_inputs_and_detect_cycles)
        line_count = _count_non_blank_non_comment_lines(source)
        assert line_count <= 50, (
            f"_validate_inputs_and_detect_cycles is {line_count} lines; expected ≤50"
        )

    def test_assemble_workflow_under_50_lines(self):
        """_assemble_workflow must be ≤50 non-blank, non-comment lines."""
        from runsight_core.yaml.parser import _assemble_workflow

        source = inspect.getsource(_assemble_workflow)
        line_count = _count_non_blank_non_comment_lines(source)
        assert line_count <= 50, f"_assemble_workflow is {line_count} lines; expected ≤50"


# ---------------------------------------------------------------------------
# Test Group 3: Block-bridging consolidation
# Verifies that _bridge_block_attributes handles all attributes in one call.
# Expected failure mode: ImportError until the function is extracted.
# ---------------------------------------------------------------------------


class TestBridgeBlockAttributesConsolidation:
    """_bridge_block_attributes must handle every previously-separate bridging loop."""

    def _make_mock_block(self) -> Mock:
        """Return a mock runtime block with relevant bridging attributes."""
        blk = Mock()
        blk._declared_exits = None
        blk.retry_config = None
        blk.stateful = False
        blk.assertions = None
        blk.exit_conditions = None
        blk.limits = None
        blk.max_duration_seconds = None
        blk.inner_block = None
        return blk

    def _make_mock_block_def(self, **kwargs) -> SimpleNamespace:
        """Return a minimal schema block_def stub."""
        defaults = {
            "exits": None,
            "retry_config": None,
            "stateful": False,
            "assertions": None,
            "exit_conditions": None,
            "limits": None,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_bridge_block_attributes_bridges_exits(self):
        """_bridge_block_attributes must bridge _declared_exits from block_def to block."""
        from runsight_core.yaml.parser import _bridge_block_attributes

        fake_exits = [SimpleNamespace(name="done")]
        block = self._make_mock_block()
        block_def = self._make_mock_block_def(exits=fake_exits)

        _bridge_block_attributes("b1", block_def, block)

        assert block._declared_exits == fake_exits

    def test_bridge_block_attributes_bridges_retry(self):
        """_bridge_block_attributes must bridge retry_config from block_def to block."""
        from runsight_core.yaml.parser import _bridge_block_attributes

        retry = SimpleNamespace(max_attempts=3, backoff_seconds=1.0)
        block = self._make_mock_block()
        block_def = self._make_mock_block_def(retry_config=retry)

        _bridge_block_attributes("b1", block_def, block)

        assert block.retry_config == retry

    def test_bridge_block_attributes_bridges_stateful(self):
        """_bridge_block_attributes must bridge stateful flag from block_def to block."""
        from runsight_core.yaml.parser import _bridge_block_attributes

        block = self._make_mock_block()
        block_def = self._make_mock_block_def(stateful=True)

        _bridge_block_attributes("b1", block_def, block)

        assert block.stateful is True

    def test_bridge_block_attributes_bridges_assertions(self):
        """_bridge_block_attributes must bridge assertions from block_def to block."""
        from runsight_core.yaml.parser import _bridge_block_attributes

        raw_assertions = [{"type": "contains", "value": "ok"}]
        block = self._make_mock_block()
        block_def = self._make_mock_block_def(
            assertions=[SimpleNamespace(**a) for a in raw_assertions]
        )
        # block_def assertions need to support dict() conversion
        block_def.assertions = [
            type("Assertion", (), {"__iter__": lambda s: iter(a.items()), **a})()
            for a in raw_assertions
        ]
        # Simpler: just use dicts directly since the bridging function calls dict(assertion)
        block_def.assertions = raw_assertions

        _bridge_block_attributes("b1", block_def, block)

        assert block.assertions is not None

    def test_bridge_block_attributes_bridges_exit_conditions(self):
        """_bridge_block_attributes must bridge exit_conditions from block_def to block."""
        from runsight_core.yaml.parser import _bridge_block_attributes

        conds = [SimpleNamespace(exit_handle="done", condition=SimpleNamespace())]
        block = self._make_mock_block()
        block_def = self._make_mock_block_def(exit_conditions=conds)

        _bridge_block_attributes("b1", block_def, block)

        assert block.exit_conditions == conds

    def test_bridge_block_attributes_bridges_limits(self):
        """_bridge_block_attributes must bridge limits from block_def to block."""
        from runsight_core.yaml.parser import _bridge_block_attributes

        limits = SimpleNamespace(max_duration_seconds=30, max_tokens=None)
        block = self._make_mock_block()
        block_def = self._make_mock_block_def(limits=limits)

        _bridge_block_attributes("b1", block_def, block)

        assert block.limits == limits

    def test_bridge_block_attributes_bridges_all_in_one_pass(self):
        """A single call to _bridge_block_attributes sets all bridged attributes."""
        from runsight_core.yaml.parser import _bridge_block_attributes

        fake_exits = [SimpleNamespace(name="done")]
        retry = SimpleNamespace(max_attempts=2, backoff_seconds=0.5)
        limits = SimpleNamespace(max_duration_seconds=10, max_tokens=None)

        block = self._make_mock_block()
        block_def = self._make_mock_block_def(
            exits=fake_exits,
            retry_config=retry,
            stateful=True,
            assertions=None,
            exit_conditions=None,
            limits=limits,
        )

        # Single call — must cover exits, retry, stateful, and limits
        _bridge_block_attributes("b1", block_def, block)

        assert block._declared_exits == fake_exits
        assert block.retry_config == retry
        assert block.stateful is True
        assert block.limits == limits


# ---------------------------------------------------------------------------
# Test Group 4: Behavioral preservation (regression guard)
# Verifies parse_workflow_yaml produces correct output after decomposition.
# Expected failure: should PASS currently (regression guard).
# These will catch regressions if the refactor breaks behaviour.
# ---------------------------------------------------------------------------

_MINIMAL_WORKFLOW_YAML = dedent(
    """\
    version: "1.0"
    souls:
      writer:
        id: writer
        role: Writer
        system_prompt: Write clearly.
    blocks:
      draft:
        type: linear
        soul_ref: writer
    workflow:
      name: minimal_e2e
      entry: draft
    """
)

_TWO_BLOCK_YAML = dedent(
    """\
    version: "1.0"
    souls:
      agent:
        id: agent
        role: Agent
        system_prompt: Do stuff.
    blocks:
      step_a:
        type: linear
        soul_ref: agent
      step_b:
        type: linear
        soul_ref: agent
    workflow:
      name: two_block
      entry: step_a
      transitions:
        - from: step_a
          to: step_b
    """
)

_DISPATCH_YAML = dedent(
    """\
    version: "1.0"
    souls:
      coordinator:
        id: coordinator
        role: Coordinator
        system_prompt: Coordinate.
      worker:
        id: worker
        role: Worker
        system_prompt: Work.
    blocks:
      dispatch_block:
        type: dispatch
        soul_ref: coordinator
        exits:
          - name: done
            soul_ref: worker
    workflow:
      name: dispatch_e2e
      entry: dispatch_block
    """
)


class TestBehavioralPreservation:
    """parse_workflow_yaml must produce correct results after refactoring."""

    def test_parse_workflow_yaml_returns_workflow_instance(self):
        """Refactored parser must still return a Workflow instance."""
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner:
            mock_runner.return_value = Mock()
            result = parse_workflow_yaml(_MINIMAL_WORKFLOW_YAML)

        assert isinstance(result, Workflow)

    def test_parse_workflow_yaml_sets_workflow_name(self):
        """Workflow name must be correctly set after decomposition."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner:
            mock_runner.return_value = Mock()
            result = parse_workflow_yaml(_MINIMAL_WORKFLOW_YAML)

        assert result.name == "minimal_e2e"

    def test_parse_workflow_yaml_registers_all_blocks(self):
        """All blocks defined in YAML must appear in the assembled Workflow."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner:
            mock_runner.return_value = Mock()
            result = parse_workflow_yaml(_TWO_BLOCK_YAML)

        block_ids = set(result.blocks.keys())
        assert "step_a" in block_ids
        assert "step_b" in block_ids

    def test_parse_workflow_yaml_entry_block_preserved(self):
        """Entry block must be correctly wired after decomposition."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner:
            mock_runner.return_value = Mock()
            result = parse_workflow_yaml(_TWO_BLOCK_YAML)

        # Workflow stores entry as _entry_block_id
        assert result._entry_block_id == "step_a"

    def test_parse_workflow_yaml_transitions_preserved(self):
        """Transitions must be correctly registered after decomposition."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner:
            mock_runner.return_value = Mock()
            result = parse_workflow_yaml(_TWO_BLOCK_YAML)

        # Workflow stores transitions as _transitions dict: {from: to}
        assert result._transitions.get("step_a") == "step_b"

    def test_parse_workflow_yaml_unknown_block_type_still_raises(self):
        """ValueError for unknown block type must survive the decomposition."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        bad_yaml = dedent(
            """\
            version: "1.0"
            blocks:
              bad_block:
                type: unknown_type_xyz
            workflow:
              name: bad
              entry: bad_block
            """
        )
        with (
            patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner,
            pytest.raises(ValueError, match="unknown_type_xyz|Unknown block type"),
        ):
            mock_runner.return_value = Mock()
            parse_workflow_yaml(bad_yaml)

    def test_parse_workflow_yaml_missing_soul_ref_still_raises(self):
        """ValueError for missing soul_ref must survive the decomposition."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        bad_yaml = dedent(
            """\
            version: "1.0"
            blocks:
              linear_block:
                type: linear
            workflow:
              name: bad
              entry: linear_block
            """
        )
        with (
            patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner,
            pytest.raises(ValueError, match="soul_ref"),
        ):
            mock_runner.return_value = Mock()
            parse_workflow_yaml(bad_yaml)

    def test_parse_workflow_yaml_dict_input_still_works(self):
        """Passing a pre-parsed dict must still produce a valid Workflow."""
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        raw_dict = {
            "version": "1.0",
            "souls": {
                "writer": {
                    "id": "writer",
                    "role": "Writer",
                    "system_prompt": "Write.",
                }
            },
            "blocks": {
                "draft": {
                    "type": "linear",
                    "soul_ref": "writer",
                }
            },
            "workflow": {
                "name": "dict_input_test",
                "entry": "draft",
            },
        }

        with patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner:
            mock_runner.return_value = Mock()
            result = parse_workflow_yaml(raw_dict)

        assert isinstance(result, Workflow)
        assert result.name == "dict_input_test"

    def test_parse_workflow_yaml_circular_input_still_raises(self):
        """Circular input dependency detection must survive the decomposition."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        # InputRef schema requires dict with 'from' key, not bare strings
        circular_yaml = dedent(
            """\
            version: "1.0"
            souls:
              agent:
                id: agent
                role: Agent
                system_prompt: Do stuff.
            blocks:
              step_a:
                type: linear
                soul_ref: agent
                inputs:
                  ctx:
                    from: step_b.output
              step_b:
                type: linear
                soul_ref: agent
                inputs:
                  ctx:
                    from: step_a.output
            workflow:
              name: circular
              entry: step_a
            """
        )
        with (
            patch("runsight_core.yaml.parser.RunsightTeamRunner") as mock_runner,
            pytest.raises(ValueError, match="[Cc]ircular|cycle"),
        ):
            mock_runner.return_value = Mock()
            parse_workflow_yaml(circular_yaml)
