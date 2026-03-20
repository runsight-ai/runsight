"""
Shared test infrastructure for runsight_core tests.
"""

import pytest
from runsight_core.primitives import Soul


def make_test_yaml(steps_yaml: str) -> str:
    """Wrap step YAML with a standard souls section containing a 'test' soul.

    Args:
        steps_yaml: Block definitions YAML (indented with 2 spaces per block).

    Returns:
        Full workflow YAML string that includes a 'test' soul definition,
        so that ``parse_workflow_yaml`` can resolve ``soul_ref: test``.
    """
    # Extract block names from the steps_yaml for transitions
    import re

    block_names = re.findall(r"^  (\w+):", steps_yaml, re.MULTILINE)
    entry = block_names[0] if block_names else "my_block"

    # Build transitions: chain blocks linearly, last one is terminal
    transitions = ""
    for i, name in enumerate(block_names):
        if i < len(block_names) - 1:
            transitions += f"    - from: {name}\n      to: {block_names[i + 1]}\n"
        else:
            transitions += f"    - from: {name}\n      to: null\n"

    return f"""\
version: "1.0"
souls:
  test:
    id: test_1
    role: Tester
    system_prompt: You test things.
blocks:
{steps_yaml}
workflow:
  name: test_workflow
  entry: {entry}
  transitions:
{transitions}"""


@pytest.fixture
def test_souls_map():
    """Provide a souls map with a 'test' Soul for tests that construct blocks directly."""
    return {
        "test": Soul(
            id="test_1",
            role="Tester",
            system_prompt="You test things.",
        )
    }
