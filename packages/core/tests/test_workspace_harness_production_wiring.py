"""Workspace harness production wiring expectations for isolated LLM blocks."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.linear import LinearBlock
from runsight_core.isolation.envelope import DelegateArtifact, ResultEnvelope
from runsight_core.tools._catalog import ToolInstance

pytestmark = pytest.mark.real_subprocess_isolation


def _result_envelope(
    *,
    block_id: str = "isolated_linear_block",
    output: str = "workspace output",
    exit_handle: str = "done",
    delegate_artifacts: dict[str, DelegateArtifact] | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
) -> ResultEnvelope:
    return ResultEnvelope(
        block_id=block_id,
        output=output,
        exit_handle=exit_handle,
        cost_usd=0.25,
        total_tokens=123,
        tool_calls_made=0,
        delegate_artifacts=delegate_artifacts or {},
        conversation_history=conversation_history or [],
        error=None,
        error_type=None,
    )


def _tool(name: str) -> ToolInstance:
    async def _execute(args: dict[str, Any]) -> dict[str, Any]:
        return {"tool": name, "args": args}

    return ToolInstance(
        name=name,
        description=f"{name} fixture tool",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        execute=_execute,
    )


class _CapturingWorkspaceHarness:
    def __init__(self, result: ResultEnvelope | None = None) -> None:
        self.requests: list[Any] = []
        self.result = result or _result_envelope()

    async def run(self, request: Any) -> ResultEnvelope:
        self.requests.append(request)
        return self.result


class _PrivateToolRegistryGuardHarness(_CapturingWorkspaceHarness):
    def __init__(self) -> None:
        object.__setattr__(self, "requests", [])
        object.__setattr__(self, "result", _result_envelope())
        object.__setattr__(self, "_resolved_tools", {"preexisting": object()})

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_resolved_tools":
            raise AssertionError("wrapper must not mutate harness private tool registries")
        object.__setattr__(self, name, value)


def _linear_wrapper(*, soul=None, harness=None, stateful: bool = False):
    from runsight_core.isolation import IsolatedBlockWrapper

    soul = soul or _make_soul()
    inner = LinearBlock("isolated_linear_block", soul, MagicMock())
    inner.stateful = stateful
    return IsolatedBlockWrapper(
        block_id="isolated_linear_block",
        inner_block=inner,
        harness=harness or _CapturingWorkspaceHarness(),
    )


class TestParserWorkspaceHarnessProductionWiring:
    def test_yaml_linear_llm_block_is_wrapped_with_unix_local_harness(self) -> None:
        from runsight_core.isolation import IsolatedBlockWrapper, UnixLocalHarness
        from runsight_core.yaml.parser import parse_workflow_yaml

        workflow = parse_workflow_yaml(
            """\
version: "1.0"
id: workspace_harness_parser_wiring
kind: workflow
souls:
  writer:
    id: writer
    kind: soul
    name: Writer
    role: Writer
    system_prompt: Write clearly.
    model_name: fixture-isolation-model
blocks:
  draft:
    type: linear
    soul_ref: writer
workflow:
  name: workspace_harness_parser_wiring
  entry: draft
  transitions:
    - from: draft
      to: null
""",
            runner=MagicMock(),
            api_keys={"openai": "dummy-openai-key"},
        )

        block = workflow.blocks["draft"]

        assert isinstance(block, IsolatedBlockWrapper)
        assert isinstance(block.harness, UnixLocalHarness)


class TestWrapperWorkspaceRunRequest:
    @pytest.mark.asyncio
    async def test_execute_passes_workspace_run_request_with_default_manifest_and_policy(self):
        from runsight_core.isolation import (
            WorkspaceManifest,
            WorkspacePolicy,
            WorkspaceRunRequest,
        )

        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(harness=harness)

        output = await wrapper.execute(_make_ctx(wrapper, _make_state()))

        assert len(harness.requests) == 1
        request = harness.requests[0]
        assert isinstance(request, WorkspaceRunRequest)
        assert isinstance(request.manifest, WorkspaceManifest)
        assert request.manifest.working_dir == "."
        assert request.manifest.materializations == []
        assert isinstance(request.policy, WorkspacePolicy)
        assert request.envelope.block_id == "isolated_linear_block"
        assert request.envelope.block_type == "linear"
        assert output.output == "workspace output"

    @pytest.mark.asyncio
    async def test_soul_without_tools_produces_empty_host_and_worker_registries(self):
        from runsight_core.isolation import WorkspaceRunRequest

        soul = _make_soul()
        soul.resolved_tools = None
        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert isinstance(request, WorkspaceRunRequest)
        assert request.host_bindings is not None
        assert request.host_bindings.host_tools.tools == []
        assert request.worker_tools == []

    @pytest.mark.asyncio
    async def test_resolved_tools_are_split_into_host_refs_and_worker_schemas_only(self):
        from runsight_core.isolation import HostToolExecutionRegistry, WorkerToolSchema
        from runsight_core.isolation.workspace import WorkspaceRunRequest

        search_tool = _tool("search")
        soul = _make_soul()
        soul.resolved_tools = [search_tool]
        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert isinstance(request, WorkspaceRunRequest)
        assert request.host_bindings is not None
        assert isinstance(request.host_bindings.host_tools, HostToolExecutionRegistry)
        assert len(request.host_bindings.host_tools.tools) == 1
        host_ref = request.host_bindings.host_tools.tools[0]
        assert host_ref.name == "search"
        assert host_ref.tool is search_tool
        assert callable(host_ref.tool.execute)

        assert len(request.worker_tools) == 1
        worker_tool = request.worker_tools[0]
        assert isinstance(worker_tool, WorkerToolSchema)
        assert worker_tool.name == "search"
        assert worker_tool.description == "search fixture tool"
        assert worker_tool.parameters == search_tool.parameters
        worker_payload = worker_tool.model_dump(mode="json")
        assert "execute" not in worker_payload
        assert "tool" not in worker_payload
        assert "headers" not in worker_payload
        assert "credential_refs" not in worker_payload

    @pytest.mark.asyncio
    async def test_duplicate_tool_names_fail_before_workspace_launch(self):
        soul = _make_soul()
        soul.resolved_tools = [_tool("lookup"), _tool("lookup")]

        class _LaunchForbiddenHarness(_CapturingWorkspaceHarness):
            async def run(self, request: Any) -> ResultEnvelope:
                raise AssertionError("workspace harness must not launch with duplicate tools")

        wrapper = _linear_wrapper(soul=soul, harness=_LaunchForbiddenHarness())

        with pytest.raises(ValueError, match="duplicate"):
            await wrapper.execute(_make_ctx(wrapper, _make_state()))

    @pytest.mark.asyncio
    async def test_wrapper_does_not_mutate_harness_private_tool_registries(self):
        soul = _make_soul()
        soul.resolved_tools = [_tool("search")]
        harness = _PrivateToolRegistryGuardHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        assert len(harness.requests) == 1
        assert harness._resolved_tools == {"preexisting": harness._resolved_tools["preexisting"]}

    @pytest.mark.asyncio
    async def test_host_binding_inputs_flow_on_request_not_harness_constructor(self):
        from runsight_core.isolation import IsolatedBlockWrapper, WorkspaceRunRequest

        harness = _CapturingWorkspaceHarness()
        soul = _make_soul()
        tool = _tool("http_lookup")
        soul.resolved_tools = [tool]
        inner = LinearBlock("isolated_linear_block", soul, MagicMock())
        wrapper = IsolatedBlockWrapper(
            block_id="isolated_linear_block",
            inner_block=inner,
            harness=harness,
            api_keys={"openai": "dummy-openai-key"},
            http_credentials={"api.fixture.test": {"Authorization": "Bearer dummy"}},
            url_allowlist=["api.fixture.test"],
        )

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert isinstance(request, WorkspaceRunRequest)
        assert request.host_bindings is not None
        assert request.host_bindings.api_keys == {"openai": "dummy-openai-key"}
        assert request.host_bindings.http_credentials == {
            "api.fixture.test": {"Authorization": "Bearer dummy"}
        }
        assert request.host_bindings.url_allowlist == ["api.fixture.test"]
        assert request.host_bindings.host_tools.tools[0].tool is tool

    @pytest.mark.asyncio
    async def test_workspace_result_mapping_preserves_artifacts_exit_and_history_replacement(self):
        from runsight_core.isolation import WorkspaceRunRequest

        soul = _make_soul()
        updated_history = [
            {"role": "user", "content": "round 1"},
            {"role": "assistant", "content": "answer 1"},
        ]
        harness = _CapturingWorkspaceHarness(
            _result_envelope(
                output="branch complete",
                exit_handle="review",
                delegate_artifacts={
                    "analysis": DelegateArtifact(prompt="analyze the report"),
                    "summary": DelegateArtifact(prompt="summarize the report"),
                },
                conversation_history=updated_history,
            )
        )
        wrapper = _linear_wrapper(soul=soul, harness=harness, stateful=True)

        block_output = await wrapper.execute(_make_ctx(wrapper, _make_state()))

        assert isinstance(harness.requests[0], WorkspaceRunRequest)
        assert block_output.output == "branch complete"
        assert block_output.exit_handle == "review"
        assert block_output.extra_results is not None
        assert block_output.extra_results["isolated_linear_block.analysis"].output == (
            "analyze the report"
        )
        assert block_output.extra_results["isolated_linear_block.summary"].exit_handle == "summary"

        history_key = f"isolated_linear_block_{soul.id}"
        assert block_output.conversation_replacements == {history_key: updated_history}
