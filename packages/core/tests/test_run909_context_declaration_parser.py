"""
RED tests for RUN-909: attach context declarations through parser and wrappers.

These tests pin the parser/runtime metadata path for Epic C context governance:
- public YAML access is rejected by normal schema/config validation
- context namespace roots are reserved block ids
- parsed runtime blocks and Steps carry context_access plus declared_inputs
- isolation wrapping preserves those declarations
- Step construction preserves context metadata without dropping hooks/assertions
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.block_io import BlockOutput, build_block_context
from runsight_core.isolation import IsolatedBlockWrapper
from runsight_core.primitives import Step
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml


def _linear_workflow(block_body: str, *, block_id: str = "analyze") -> str:
    return f"""\
version: "1.0"
id: run909
kind: workflow
souls:
  analyst:
    id: analyst
    kind: soul
    name: Analyst
    role: Analyst
    system_prompt: Analyze carefully.
blocks:
  {block_id}:
{_indent(block_body, 4)}
workflow:
  name: run909
  entry: {block_id}
  transitions:
    - from: {block_id}
      to: null
"""


def _two_block_workflow(source_body: str, target_body: str) -> str:
    return f"""\
version: "1.0"
id: run909
kind: workflow
souls:
  analyst:
    id: analyst
    kind: soul
    name: Analyst
    role: Analyst
    system_prompt: Analyze carefully.
blocks:
  source:
{_indent(source_body, 4)}
  analyze:
{_indent(target_body, 4)}
workflow:
  name: run909
  entry: source
  transitions:
    - from: source
      to: analyze
    - from: analyze
      to: null
"""


def _code_workflow(block_body: str) -> str:
    return f"""\
version: "1.0"
id: run909
kind: workflow
blocks:
  transform:
{_indent(block_body, 4)}
workflow:
  name: run909
  entry: transform
  transitions:
    - from: transform
      to: null
"""


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _unwrap_step(block: Any) -> Step:
    assert isinstance(block, Step)
    return block


def test_parser_rejects_public_access_field_on_linear_block() -> None:
    """Linear blocks must reject public access configuration in YAML."""
    yaml_text = _linear_workflow(
        """\
type: linear
soul_ref: analyst
access: all
""",
        block_id="analyze",
    )

    with pytest.raises(
        ValueError, match=r"analyze.*access.*all.*CodeBlock|analyze.*CodeBlock.*access.*all"
    ):
        parse_workflow_yaml(yaml_text)


@pytest.mark.parametrize("access_value", ["declared", "all", "xyz"])
def test_parser_rejects_public_access_field_on_codeblock(access_value: str) -> None:
    """CodeBlock must reject public access values as unsupported YAML configuration."""
    yaml_text = _code_workflow(
        f"""\
type: code
access: {access_value}
code: |
  def main(data):
      return {{"ok": True}}
"""
    )

    with pytest.raises(
        ValueError,
        match=rf"access {access_value} is unsupported|CodeBlock all-access is no longer supported",
    ):
        parse_workflow_yaml(yaml_text)


@pytest.mark.parametrize(
    "reserved_input_name", ["workflow", "results", "shared_memory", "metadata"]
)
def test_parser_rejects_reserved_local_input_names(reserved_input_name: str) -> None:
    """Reserved context names must not be reusable as local block input names."""
    yaml_text = _two_block_workflow(
        """\
type: code
code: |
  def main(data):
      return {"summary": "ready"}
""",
        f"""\
type: code
inputs:
  {reserved_input_name}:
    from: source.summary
code: |
  def main(data):
      return data
""",
    )

    with pytest.raises(ValueError, match=rf"{reserved_input_name}.*reserved"):
        parse_workflow_yaml(yaml_text)


@pytest.mark.parametrize("reserved_id", ["results", "shared_memory", "metadata"])
def test_parser_rejects_context_namespace_roots_as_block_ids(reserved_id: str) -> None:
    """Context namespace roots must be reserved and unavailable as block ids."""
    yaml_text = _linear_workflow(
        """\
type: linear
soul_ref: analyst
""",
        block_id=reserved_id,
    )

    with pytest.raises(ValueError, match=rf"{reserved_id}.*reserved.*namespace"):
        parse_workflow_yaml(yaml_text)


def test_parsed_no_input_block_carries_empty_declarations_and_declared_access() -> None:
    """Blocks with no inputs still carry explicit empty declaration metadata."""
    yaml_text = _linear_workflow(
        """\
type: linear
soul_ref: analyst
""",
        block_id="analyze",
    )

    workflow = parse_workflow_yaml(yaml_text)
    block = workflow._blocks["analyze"]
    state = WorkflowState(shared_memory={"_resolved_inputs": {"reason": "legacy broad fallback"}})

    assert getattr(block, "context_access") == "declared"
    assert getattr(block, "declared_inputs") == {}
    inner = getattr(block, "inner_block", None)
    assert inner is not None
    assert getattr(inner, "context_access") == "declared"
    assert getattr(inner, "declared_inputs") == {}

    ctx = build_block_context(block, state, step=None)
    assert ctx.inputs == {}


def test_parsed_isolated_llm_step_preserves_context_declarations_through_wrapping() -> None:
    """YAML inputs survive parser isolation wrapping and Step wrapping."""
    yaml_text = _two_block_workflow(
        """\
type: code
code: |
  def main(data):
      return {"summary": "ready"}
""",
        """\
type: linear
soul_ref: analyst
inputs:
  summary:
    from: source.summary
""",
    )

    workflow = parse_workflow_yaml(yaml_text)
    step = _unwrap_step(workflow._blocks["analyze"])
    wrapper = step.block
    inner = wrapper.inner_block
    state = WorkflowState(results={"source": BlockResult(output=json.dumps({"summary": "ready"}))})

    assert isinstance(wrapper, IsolatedBlockWrapper)
    assert step.context_access == "declared"
    assert step.declared_inputs == {"summary": "source.summary"}
    assert getattr(wrapper, "context_access") == "declared"
    assert getattr(wrapper, "declared_inputs") == {"summary": "source.summary"}
    assert getattr(inner, "context_access") == "declared"
    assert getattr(inner, "declared_inputs") == {"summary": "source.summary"}

    ctx = build_block_context(step.block, state, step=step)
    assert ctx.inputs == {"summary": "ready"}


def test_step_construction_preserves_context_metadata_hooks_and_assertions() -> None:
    """Step carries context metadata while preserving hooks and assertion delegation."""
    calls: list[str] = []

    def pre_hook(state: WorkflowState) -> WorkflowState:
        calls.append("pre")
        return state

    def post_hook(state: WorkflowState) -> WorkflowState:
        calls.append("post")
        return state

    class CapturingBlock:
        block_id = "capture"
        assertions = [{"type": "contains", "value": "done"}]
        context_access = "declared"
        declared_inputs = {"reason": "workflow.reason"}

        async def execute(self, ctx: Any) -> BlockOutput:
            calls.append("execute")
            return BlockOutput(output="done")

    block = CapturingBlock()
    step = Step(
        block=block,
        pre_hook=pre_hook,
        post_hook=post_hook,
        declared_inputs={"reason": "workflow.reason"},
        context_access="declared",
    )

    assert step.context_access == "declared"
    assert step.declared_inputs == {"reason": "workflow.reason"}
    assert step.pre_hook is pre_hook
    assert step.post_hook is post_hook
    assert step.assertions == [{"type": "contains", "value": "done"}]
    assert block.context_access == "declared"
    assert block.declared_inputs == {"reason": "workflow.reason"}
