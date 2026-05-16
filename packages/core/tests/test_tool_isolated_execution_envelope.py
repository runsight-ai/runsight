"""Isolated execution tool envelope tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from runsight_core.block_io import build_block_context
from runsight_core.isolation.envelope import ResultEnvelope
from runsight_core.isolation.workspace import WorkspaceRunRequest
from runsight_core.state import WorkflowState
from runsight_core.yaml.parser import parse_workflow_yaml
from tool_integration_helpers import (
    _write_custom_tool_yaml,
    _write_workflow_file,
)

pytestmark = pytest.mark.real_subprocess_isolation


class TestIsolatedExecutionToolEnvelope:
    """Isolated worker envelopes should include resolved tool metadata."""

    @pytest.mark.asyncio
    async def test_isolated_linear_block_envelope_includes_tool_definitions_for_worker_loop(
        self,
        tmp_path: Path,
    ) -> None:
        """Isolated execution must ship resolved tool metadata to the worker."""
        _write_custom_tool_yaml(
            tmp_path,
            "adder",
            """\
version: "1.0"
id: adder
kind: tool
type: custom
executor: python
name: Adder
description: Add two integers together.
parameters:
  type: object
  properties:
    a:
      type: integer
    b:
      type: integer
  required:
    - a
    - b
code: |
  def main(args):
      return {"sum": args["a"] + args["b"]}
""",
        )
        _write_custom_tool_yaml(
            tmp_path,
            "fetch_answer",
            """\
version: "1.0"
id: fetch_answer
kind: tool
type: custom
executor: request
name: Fetch Answer
description: Fetch an answer from a remote API.
parameters:
  type: object
  properties:
    item_id:
      type: integer
  required:
    - item_id
request:
  method: GET
  url: https://fixture.test/items/{{ item_id }}
""",
        )
        workflow_path = _write_workflow_file(
            tmp_path,
            """\
version: "1.0"
id: isolated_tool_envelope
kind: workflow
config:
  model_name: gpt-4o
tools:
  - http
  - adder
  - fetch_answer
souls:
  agent:
    id: agent
    kind: soul
    name: Mixed Agent
    role: Mixed Agent
    provider: openai
    model_name: gpt-4o
    system_prompt: Use every tool.
    tools:
      - http
      - adder
      - fetch_answer
blocks:
  step:
    type: linear
    soul_ref: agent
workflow:
  name: isolated_tool_envelope
  entry: step
  transitions:
    - from: step
      to: null
""",
        )

        workflow = parse_workflow_yaml(str(workflow_path))
        block = workflow.blocks["step"]
        state = WorkflowState()
        captured: dict[str, Any] = {}

        async def _capture(request: WorkspaceRunRequest) -> ResultEnvelope:
            captured["request"] = request
            return ResultEnvelope(
                block_id="step",
                output="done",
                exit_handle="done",
                cost_usd=0.0,
                total_tokens=0,
                tool_calls_made=0,
                delegate_artifacts={},
                conversation_history=[],
                error=None,
                error_type=None,
            )

        with patch.object(block, "_run_in_subprocess", side_effect=_capture):
            await block.execute(build_block_context(block, state))

        request = captured["request"]
        assert isinstance(request, WorkspaceRunRequest)

        envelope = request.envelope
        assert [tool.name for tool in envelope.tools] == ["http_request", "adder", "fetch_answer"]
        assert {tool.tool_type for tool in envelope.tools} == {"builtin", "custom"}

        assert [tool.name for tool in request.worker_tools] == [
            "http_request",
            "adder",
            "fetch_answer",
        ]
        for worker_tool in request.worker_tools:
            worker_payload = worker_tool.model_dump(mode="json")
            assert "execute" not in worker_payload
            assert "tool" not in worker_payload

        assert request.host_bindings is not None
        host_refs = request.host_bindings.host_tools.tools
        assert [tool.name for tool in host_refs] == ["http_request", "adder", "fetch_answer"]
        for host_ref in host_refs:
            assert callable(host_ref.tool.execute)
