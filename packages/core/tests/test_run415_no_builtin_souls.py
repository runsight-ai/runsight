"""
Tests for RUN-415: Remove BUILT_IN_SOULS from parser.

After implementation, the parser must no longer seed a souls_map with
built-in souls.  Every soul_ref used in YAML must be explicitly defined
in the ``souls:`` section of that YAML file.

Tests verify:
1. parse_workflow_yaml starts with an empty souls_map (soul_ref to a
   previously-built-in name without a souls: definition raises ValueError)
2. All 6 previously-built-in names are NOT special-cased
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from runsight_core.yaml.parser import parse_workflow_yaml

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Empty souls_map by default — implicit soul_ref raises ValueError
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmptySoulsMapByDefault:
    """parse_workflow_yaml must fail when no library soul can resolve a soul_ref."""

    def test_undefined_soul_ref_raises_value_error(self):
        """soul_ref: researcher without a souls: section must raise ValueError."""
        yaml_content = """\
id: test-workflow
kind: workflow
version: "1.0"
blocks:
  linear_block:
    type: linear
    soul_ref: researcher
workflow:
  name: test_empty_souls_map
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        with patch("runsight_core.yaml.parser.SoulScanner") as mock_scanner:
            mock_scanner.return_value.scan.return_value.ids.return_value = {}
            with pytest.raises(ValueError, match="researcher"):
                parse_workflow_yaml(yaml_content)

    def test_undefined_soul_ref_with_empty_souls_section(self):
        """soul_ref: reviewer with an empty souls: {} section must raise ValueError."""
        yaml_content = """\
id: test-workflow
kind: workflow
version: "1.0"
souls: {}
blocks:
  linear_block:
    type: linear
    soul_ref: reviewer
workflow:
  name: test_empty_souls_section
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        with patch("runsight_core.yaml.parser.SoulScanner") as mock_scanner:
            mock_scanner.return_value.scan.return_value.ids.return_value = {}
            with pytest.raises(ValueError, match="reviewer"):
                parse_workflow_yaml(yaml_content)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. All 6 previously-built-in names are NOT special
# ═══════════════════════════════════════════════════════════════════════════════

PREVIOUSLY_BUILTIN_NAMES = [
    "researcher",
    "reviewer",
    "coder",
    "architect",
    "synthesizer",
    "generalist",
]


class TestNoPreviouslyBuiltInNamesAreSpecial:
    """Formerly built-in names must not resolve unless library discovery finds them."""

    @pytest.mark.parametrize("soul_name", PREVIOUSLY_BUILTIN_NAMES)
    def test_previously_builtin_soul_raises_without_definition(self, soul_name: str):
        """soul_ref: {soul_name} without souls: definition must raise ValueError."""
        yaml_content = f"""\
id: test-workflow
kind: workflow
version: "1.0"
blocks:
  linear_block:
    type: linear
    soul_ref: {soul_name}
workflow:
  name: test_no_builtin_{soul_name}
  entry: linear_block
  transitions:
    - from: linear_block
      to: null
"""
        with patch("runsight_core.yaml.parser.SoulScanner") as mock_scanner:
            mock_scanner.return_value.scan.return_value.ids.return_value = {}
            with pytest.raises(ValueError, match=soul_name):
                parse_workflow_yaml(yaml_content)
