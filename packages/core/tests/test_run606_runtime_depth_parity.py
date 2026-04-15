"""
RUN-606 runtime/parse-time depth parity tests.

These tests verify that the parse-time validation
(``validate_workflow_call_contracts``) and the runtime depth check
(``WorkflowBlock.execute``) agree on the same depth semantic:

  max_depth: N  =>  allow N nesting levels below the declaring block
  max_depth: 1  =>  child only
  max_depth: 2  =>  grandchild allowed
  max_depth: 3  =>  great-grandchild allowed

The runtime check (``len(call_stack) >= self.max_depth``) is already
correct: the call_stack grows by 1 per level.

The parse-time check (``current_call_stack_depth >= max_depth``) is
WRONG: it starts at 1 and increments by +2, causing it to reject
nesting that the runtime would allow.

These parity tests directly assert that both sides agree on the same
boundary.  They FAIL because parse-time incorrectly rejects at
max_depth=3 with a parent->child->grandchild chain.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock

import pytest
import yaml as yaml_mod
from runsight_core import WorkflowBlock
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import validate_workflow_call_contracts
from runsight_core.yaml.schema import RunsightWorkflowFile


def _make_workflow_file(yaml_text: str) -> RunsightWorkflowFile:
    data = yaml_mod.safe_load(dedent(yaml_text).strip())
    if "id" not in data:
        data["id"] = "test-workflow"
    if "kind" not in data:
        data["kind"] = "workflow"
    return RunsightWorkflowFile.model_validate(data)


def _write_yaml_file(base: Path, rel_path: str, yaml_text: str) -> Path:
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    content = dedent(yaml_text).strip() + "\n"
    if "id: " not in content:
        content = "id: test-workflow\nkind: workflow\n" + content
    target.write_text(content, encoding="utf-8")
    return target


class TestDepthParityMaxDepth3:
    """max_depth=3 must allow parent->child->grandchild in BOTH parse-time
    and runtime.  Currently the runtime allows it but parse-time rejects it.
    """

    @pytest.mark.asyncio
    async def test_runtime_allows_grandchild_at_max_depth_3(self) -> None:
        """Runtime: call_stack=["parent", "child"] (len=2), max_depth=3.
        2 < 3 -> ALLOWED.
        """
        child = AsyncMock()
        child.name = "grandchild"
        child.run = AsyncMock(return_value=WorkflowState())
        block = WorkflowBlock(
            block_id="call_grandchild",
            child_workflow=child,
            inputs={},
            outputs={},
            max_depth=3,
        )

        result = await block.execute(WorkflowState(), call_stack=["parent", "child"])
        assert isinstance(result, WorkflowState)

    def test_parse_time_allows_grandchild_at_max_depth_3(self, tmp_path) -> None:
        """Parse-time: the same parent->child->grandchild chain with
        max_depth=3 must also be ALLOWED.

        This FAILS because validate_workflow_call_contracts starts at
        depth=1 and increments by +2, so the child level sees depth=3
        and 3 >= 3 triggers rejection.
        """
        grandchild_file = _make_workflow_file("""
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            workflow:
              name: grandchild
              entry: finish
              transitions: []
        """)
        child_file = _make_workflow_file("""
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            blocks:
              call_grandchild:
                type: workflow
                workflow_ref: grandchild
            workflow:
              name: child
              entry: call_grandchild
              transitions:
                - from: call_grandchild
                  to: null
            config:
              max_workflow_depth: 3
        """)
        parent_file = _make_workflow_file("""
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            blocks:
              call_child:
                type: workflow
                workflow_ref: child
                max_depth: 3
            workflow:
              name: parent
              entry: call_child
              transitions:
                - from: call_child
                  to: null
        """)

        # Write files so filesystem-based resolution works
        _write_yaml_file(
            tmp_path,
            "custom/workflows/grandchild.yaml",
            """
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            workflow:
              name: grandchild
              entry: finish
              transitions: []
        """,
        )
        _write_yaml_file(
            tmp_path,
            "custom/workflows/child.yaml",
            """
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            blocks:
              call_grandchild:
                type: workflow
                workflow_ref: grandchild
            workflow:
              name: child
              entry: call_grandchild
              transitions:
                - from: call_grandchild
                  to: null
            config:
              max_workflow_depth: 3
        """,
        )

        grandchild_path = (tmp_path / "custom/workflows/grandchild.yaml").resolve()
        child_path = (tmp_path / "custom/workflows/child.yaml").resolve()

        validation_index = {
            str(grandchild_path): (grandchild_path, grandchild_file),
            "grandchild": (grandchild_path, grandchild_file),
            "custom/workflows/grandchild.yaml": (grandchild_path, grandchild_file),
            str(child_path): (child_path, child_file),
            "child": (child_path, child_file),
            "custom/workflows/child.yaml": (child_path, child_file),
        }

        # This should NOT raise — max_depth=3 allows 2 nesting levels
        # (parent->child->grandchild).  But current code raises ValueError.
        try:
            validate_workflow_call_contracts(
                parent_file,
                base_dir=str(tmp_path),
                validation_index=validation_index,
            )
        except ValueError as exc:
            pytest.fail(
                f"parse-time rejected grandchild at max_depth=3, "
                f"but runtime allows it. Parity broken. Error: {exc}"
            )


class TestDepthParityMaxDepth2:
    """max_depth=2 must allow parent->child->grandchild in BOTH layers.
    Currently parse-time rejects it because depth increments by +2.
    """

    @pytest.mark.asyncio
    async def test_runtime_allows_grandchild_at_max_depth_2(self) -> None:
        """Runtime: call_stack=["parent"] (len=1), max_depth=2.
        1 < 2 -> ALLOWED.
        """
        child = AsyncMock()
        child.name = "grandchild"
        child.run = AsyncMock(return_value=WorkflowState())
        block = WorkflowBlock(
            block_id="call_grandchild",
            child_workflow=child,
            inputs={},
            outputs={},
            max_depth=2,
        )

        result = await block.execute(WorkflowState(), call_stack=["parent"])
        assert isinstance(result, WorkflowState)

    def test_parse_time_allows_grandchild_at_max_depth_2(self, tmp_path) -> None:
        """Parse-time: max_depth=2 with parent->child->grandchild must also
        be ALLOWED.

        FAILS because depth starts at 1 and jumps to 3 at child level,
        and 3 >= 2 rejects.
        """
        grandchild_file = _make_workflow_file("""
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            workflow:
              name: grandchild
              entry: finish
              transitions: []
        """)
        child_file = _make_workflow_file("""
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            blocks:
              call_grandchild:
                type: workflow
                workflow_ref: grandchild
            workflow:
              name: child
              entry: call_grandchild
              transitions:
                - from: call_grandchild
                  to: null
            config:
              max_workflow_depth: 2
        """)
        parent_file = _make_workflow_file("""
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            blocks:
              call_child:
                type: workflow
                workflow_ref: child
                max_depth: 2
            workflow:
              name: parent
              entry: call_child
              transitions:
                - from: call_child
                  to: null
        """)

        _write_yaml_file(
            tmp_path,
            "custom/workflows/grandchild.yaml",
            """
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            workflow:
              name: grandchild
              entry: finish
              transitions: []
        """,
        )
        _write_yaml_file(
            tmp_path,
            "custom/workflows/child.yaml",
            """
            version: "1.0"
            interface:
              inputs: []
              outputs: []
            blocks:
              call_grandchild:
                type: workflow
                workflow_ref: grandchild
            workflow:
              name: child
              entry: call_grandchild
              transitions:
                - from: call_grandchild
                  to: null
            config:
              max_workflow_depth: 2
        """,
        )

        grandchild_path = (tmp_path / "custom/workflows/grandchild.yaml").resolve()
        child_path = (tmp_path / "custom/workflows/child.yaml").resolve()

        validation_index = {
            str(grandchild_path): (grandchild_path, grandchild_file),
            "grandchild": (grandchild_path, grandchild_file),
            "custom/workflows/grandchild.yaml": (grandchild_path, grandchild_file),
            str(child_path): (child_path, child_file),
            "child": (child_path, child_file),
            "custom/workflows/child.yaml": (child_path, child_file),
        }

        try:
            validate_workflow_call_contracts(
                parent_file,
                base_dir=str(tmp_path),
                validation_index=validation_index,
            )
        except ValueError as exc:
            pytest.fail(
                f"parse-time rejected grandchild at max_depth=2, "
                f"but runtime allows it. Parity broken. Error: {exc}"
            )
