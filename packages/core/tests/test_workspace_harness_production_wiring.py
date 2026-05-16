"""Workspace harness production wiring expectations for isolated LLM blocks."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from isolation_wrapper_helpers import make_ctx as _make_ctx
from isolation_wrapper_helpers import make_soul as _make_soul
from isolation_wrapper_helpers import make_state as _make_state
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.gate import GateBlock
from runsight_core.blocks.linear import LinearBlock
from runsight_core.blocks.synthesize import SynthesizeBlock
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
    conversation_histories: dict[str, list[dict[str, Any]]] | None = None,
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
        conversation_histories=conversation_histories or {},
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


def _wrapper_for(inner_block, *, harness=None, stateful: bool = False):
    from runsight_core.isolation import IsolatedBlockWrapper

    inner_block.stateful = stateful
    return IsolatedBlockWrapper(
        block_id=inner_block.block_id,
        inner_block=inner_block,
        harness=harness or _CapturingWorkspaceHarness(),
    )


def _linear_wrapper(*, soul=None, harness=None, stateful: bool = False):
    soul = soul or _make_soul()
    inner = LinearBlock("isolated_linear_block", soul, MagicMock())
    return _wrapper_for(inner, harness=harness, stateful=stateful)


def _block_under_test(block_type: str):
    soul = _make_soul(f"{block_type}_soul")
    runner = MagicMock()

    if block_type == "linear":
        return LinearBlock("isolated_linear_block", soul, runner)

    if block_type == "gate":
        return GateBlock(
            "isolated_gate_block",
            soul,
            eval_key="draft_output",
            extract_field="score",
            runner=runner,
        )

    if block_type == "synthesize":
        return SynthesizeBlock(
            "isolated_synthesize_block",
            ["research", "review"],
            soul,
            runner,
        )

    if block_type == "dispatch":
        review_soul = _make_soul("dispatch_review_soul")
        return DispatchBlock(
            "isolated_dispatch_block",
            [
                DispatchBranch(
                    exit_id="research",
                    label="Research",
                    soul=soul,
                    task_instruction="Research the input.",
                ),
                DispatchBranch(
                    exit_id="review",
                    label="Review",
                    soul=review_soul,
                    task_instruction="Review the draft.",
                ),
            ],
            runner,
        )

    raise AssertionError(f"unsupported block type fixture: {block_type}")


def _assert_block_config(block_type: str, block_config: dict[str, Any]) -> None:
    if block_type == "linear":
        assert block_config == {}
    elif block_type == "gate":
        assert block_config["eval_key"] == "draft_output"
        assert block_config["extract_field"] == "score"
    elif block_type == "synthesize":
        assert block_config["input_block_ids"] == ["research", "review"]
        assert block_config["synthesizer_soul"]["id"] == "synthesize_soul"
        assert block_config["synthesizer_soul"]["model_name"] == "fixture-isolation-model"
    elif block_type == "dispatch":
        assert block_config["branches"] == [
            {
                "exit_id": "research",
                "label": "Research",
                "task_instruction": "Research the input.",
                "soul": {
                    "id": "dispatch_soul",
                    "role": "Isolation Fixture Soul",
                    "system_prompt": "Exercise the isolation wrapper contract.",
                    "model_name": "fixture-isolation-model",
                    "provider": "",
                    "temperature": None,
                    "max_tokens": None,
                    "required_tool_calls": [],
                    "max_tool_iterations": 5,
                    "resolved_tool_binding_ids": [],
                },
            },
            {
                "exit_id": "review",
                "label": "Review",
                "task_instruction": "Review the draft.",
                "soul": {
                    "id": "dispatch_review_soul",
                    "role": "Isolation Fixture Soul",
                    "system_prompt": "Exercise the isolation wrapper contract.",
                    "model_name": "fixture-isolation-model",
                    "provider": "",
                    "temperature": None,
                    "max_tokens": None,
                    "required_tool_calls": [],
                    "max_tool_iterations": 5,
                    "resolved_tool_binding_ids": [],
                },
            },
        ]
    else:
        raise AssertionError(f"unsupported block type assertion: {block_type}")


def _state_for_block(block_type: str):
    from runsight_core.state import BlockResult

    state = _make_state()
    if block_type == "gate":
        return state.model_copy(
            update={"results": {"draft_output": BlockResult(output='{"score": "PASS"}')}}
        )
    if block_type == "synthesize":
        return state.model_copy(
            update={
                "results": {
                    "research": BlockResult(output="research notes"),
                    "review": BlockResult(output="review notes"),
                }
            }
        )
    return state


def _workspace_context_envelope(*, timeout_seconds: int = 30):
    from runsight_core.isolation import ContextEnvelope, PromptEnvelope, SoulEnvelope

    return ContextEnvelope(
        block_id="workspace-cleanup-block",
        block_type="linear",
        block_config={},
        soul=SoulEnvelope(
            id="workspace-cleanup-soul",
            role="Tester",
            system_prompt="Verify workspace cleanup.",
            model_name="fixture-isolation-model",
        ),
        tools=[],
        prompt=PromptEnvelope(
            id="workspace-cleanup-prompt",
            instruction="Return cleanly.",
            context={},
        ),
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=timeout_seconds,
        max_output_bytes=1_000_000,
    )


def _workspace_run_request(*, timeout_seconds: int = 30):
    from runsight_core.isolation import WorkspaceManifest, WorkspacePolicy, WorkspaceRunRequest

    return WorkspaceRunRequest(
        envelope=_workspace_context_envelope(timeout_seconds=timeout_seconds),
        manifest=WorkspaceManifest(materializations=[], working_dir="."),
        policy=WorkspacePolicy(
            network={"raw": "deny", "mediated": "allow"},
            filesystem={"raw": "deny", "mediated": "workspace"},
            credentials={"mode": "host-bound"},
        ),
        worker_tools=[],
        host_bindings=None,
    )


def _ipc_binding(socket_path: Path):
    from runsight_core.isolation import IPCBinding, IPCClientConfig, IPCTransport
    from runsight_core.isolation.workspace import UnixSocketEndpoint

    config = IPCClientConfig(
        transport=IPCTransport.UNIX_SOCKET,
        grant_token="dummy-grant-token",
        unix_socket=UnixSocketEndpoint(path=str(socket_path)),
    )
    return IPCBinding(
        client_config=config,
        server_endpoint=UnixSocketEndpoint(path=str(socket_path)),
        env=config.to_env(),
        cleanup_required=True,
    )


class _CleanupSessionFactory:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def create(self, manifest: Any, policy: Any):
        from runsight_core.isolation import WorkspaceSession

        del manifest, policy
        root = self.workspace_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return WorkspaceSession(
            id="cleanup-session",
            host_root=root,
            runtime_root=root,
            runtime_workdir=root,
            cleanup=True,
        )


class _CleanupIPCTransport:
    def __init__(self, socket_path: Path) -> None:
        self.binding = _ipc_binding(socket_path)
        self.closed = False

    def prepare(self, session: Any, policy: Any):
        del session, policy

        def _close() -> None:
            self.closed = True
            Path(self.binding.server_endpoint.path).unlink(missing_ok=True)

        self.binding._close_callback = _close
        return self.binding


class _RecordingStdin:
    def write(self, _payload: bytes) -> None:
        return None

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None


class _ImmediateStdout:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self._sent = False

    async def read(self, n: int = -1) -> bytes:
        if self._sent:
            return b""
        self._sent = True
        if n is None or n < 0:
            return self.payload
        return self.payload[:n]


class _TimeoutStdout:
    async def read(self, n: int = -1) -> bytes:
        del n
        raise TimeoutError("worker timed out")


class _ClosedStderr:
    async def readline(self) -> bytes:
        return b""


class _FakeWorkerProcess:
    def __init__(self, *, stdout: Any, returncode: int | None = 0) -> None:
        self.pid = 4242
        self.returncode = returncode
        self.stdin = _RecordingStdin()
        self.stdout = stdout
        self.stderr = _ClosedStderr()
        self.terminate_calls = 0

    async def wait(self) -> int:
        assert self.returncode is not None
        return self.returncode

    async def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = -15


class _CleanupWorkerLauncher:
    def __init__(self, process: _FakeWorkerProcess) -> None:
        self.process = process

    async def launch(self, spec: Any) -> _FakeWorkerProcess:
        self.spec = spec
        return self.process


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

    def test_yaml_linear_llm_block_accepts_workspace_harness_factory_override(self) -> None:
        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.yaml.parser import parse_workflow_yaml

        captured_kwargs: list[dict[str, Any]] = []

        class _DockerSwapHarness:
            async def run(self, request: Any) -> ResultEnvelope:
                del request
                return _result_envelope()

        def _factory(**kwargs: Any) -> _DockerSwapHarness:
            captured_kwargs.append(dict(kwargs))
            return _DockerSwapHarness()

        workflow = parse_workflow_yaml(
            """\
version: "1.0"
id: workspace_harness_factory_wiring
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
  name: workspace_harness_factory_wiring
  entry: draft
  transitions:
    - from: draft
      to: null
""",
            runner=MagicMock(),
            api_keys={"openai": "dummy-openai-key"},
            workspace_harness_factory=_factory,
        )

        block = workflow.blocks["draft"]

        assert isinstance(block, IsolatedBlockWrapper)
        assert isinstance(block.harness, _DockerSwapHarness)
        assert captured_kwargs == [{"timeout_seconds": 300, "stall_thresholds": {}}]


class TestWrapperWorkspaceRunRequest:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("block_type", ["linear", "gate", "synthesize", "dispatch"])
    async def test_execute_passes_workspace_run_request_for_supported_llm_blocks(
        self,
        block_type: str,
    ):
        from runsight_core.isolation import (
            WorkspaceManifest,
            WorkspacePolicy,
            WorkspaceRunRequest,
        )

        inner_block = _block_under_test(block_type)
        harness = _CapturingWorkspaceHarness(
            _result_envelope(
                block_id=inner_block.block_id,
                output=f"{block_type} workspace output",
                exit_handle=f"{block_type}_done",
                delegate_artifacts={
                    "handoff": DelegateArtifact(prompt=f"{block_type} delegate prompt")
                },
            )
        )
        wrapper = _wrapper_for(inner_block, harness=harness)

        output = await wrapper.execute(_make_ctx(wrapper, _state_for_block(block_type)))

        assert len(harness.requests) == 1
        request = harness.requests[0]
        assert isinstance(request, WorkspaceRunRequest)
        assert isinstance(request.manifest, WorkspaceManifest)
        assert request.manifest.working_dir == "."
        assert request.manifest.materializations == []
        assert isinstance(request.policy, WorkspacePolicy)
        assert request.envelope.block_id == inner_block.block_id
        assert request.envelope.block_type == block_type
        _assert_block_config(block_type, request.envelope.block_config)
        assert output.output == f"{block_type} workspace output"
        assert output.exit_handle == f"{block_type}_done"
        assert output.extra_results is not None
        assert output.extra_results[f"{inner_block.block_id}.handoff"].output == (
            f"{block_type} delegate prompt"
        )
        assert output.extra_results[f"{inner_block.block_id}.handoff"].exit_handle == "handoff"

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
        search_tool.binding_id = "host-binding:search"
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
        assert host_ref.binding_id == "host-binding:search"
        assert host_ref.tool is search_tool
        assert callable(host_ref.tool.execute)

        assert len(request.worker_tools) == 1
        worker_tool = request.worker_tools[0]
        assert isinstance(worker_tool, WorkerToolSchema)
        assert worker_tool.name == "search"
        assert worker_tool.binding_id == "host-binding:search"
        assert worker_tool.description == "search fixture tool"
        assert worker_tool.parameters == search_tool.parameters
        assert request.envelope.tools[0].binding_id == "host-binding:search"
        worker_payload = worker_tool.model_dump(mode="json")
        assert "execute" not in worker_payload
        assert "tool" not in worker_payload
        assert "headers" not in worker_payload
        assert "credential_refs" not in worker_payload

    @pytest.mark.asyncio
    async def test_request_tool_hosts_seed_workspace_http_allowlist(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("RUNSIGHT_HTTP_URL_ALLOWLIST", raising=False)
        request_tool = _tool("lookup_profile")
        request_tool.request_config = {
            "method": "GET",
            "url": "https://api.fixture.test/profiles/{{ profile_id }}",
            "headers": {},
            "body_template": None,
            "response_path": "data.profile",
        }
        soul = _make_soul()
        soul.resolved_tools = [request_tool]
        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert request.host_bindings is not None
        assert request.host_bindings.url_allowlist == ["api.fixture.test"]
        worker_payload = request.worker_tools[0].model_dump(mode="json")
        assert "api.fixture.test" not in str(worker_payload)
        assert "url_allowlist" not in str(worker_payload)

    @pytest.mark.asyncio
    async def test_request_tool_malformed_static_url_is_dropped_without_crash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("RUNSIGHT_HTTP_URL_ALLOWLIST", raising=False)
        request_tool = _tool("lookup_profile")
        request_tool.request_config = {
            "method": "GET",
            "url": "https://[2001:db8::1",
            "headers": {},
            "body_template": None,
            "response_path": "data.profile",
        }
        soul = _make_soul()
        soul.resolved_tools = [request_tool]
        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert request.host_bindings is not None
        assert request.host_bindings.url_allowlist == []

    @pytest.mark.asyncio
    async def test_request_tool_static_url_with_invalid_port_is_not_allowlisted(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("RUNSIGHT_HTTP_URL_ALLOWLIST", raising=False)
        request_tool = _tool("lookup_profile")
        request_tool.request_config = {
            "method": "GET",
            "url": "http://[::1]:bad/path",
            "headers": {},
            "body_template": None,
            "response_path": "data.profile",
        }
        soul = _make_soul()
        soul.resolved_tools = [request_tool]
        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert request.host_bindings is not None
        assert request.host_bindings.url_allowlist == []

    @pytest.mark.asyncio
    async def test_dynamic_http_tool_uses_host_allowlist_environment_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv(
            "RUNSIGHT_HTTP_URL_ALLOWLIST",
            "public.fixture.test, https://cdn.fixture.test/assets",
        )
        http_tool = _tool("http_request")
        soul = _make_soul()
        soul.resolved_tools = [http_tool]
        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert request.host_bindings is not None
        assert request.host_bindings.url_allowlist == [
            "cdn.fixture.test",
            "public.fixture.test",
        ]

    @pytest.mark.asyncio
    async def test_dynamic_http_allowlist_host_port_entry_normalizes_without_crash(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv(
            "RUNSIGHT_HTTP_URL_ALLOWLIST",
            "api.fixture.test:8443, https://cdn.fixture.test/assets",
        )
        http_tool = _tool("http_request")
        soul = _make_soul()
        soul.resolved_tools = [http_tool]
        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert request.host_bindings is not None
        assert request.host_bindings.url_allowlist == [
            "api.fixture.test",
            "cdn.fixture.test",
        ]

    @pytest.mark.asyncio
    async def test_dynamic_http_allowlist_drops_malformed_url_like_at_entries(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv(
            "RUNSIGHT_HTTP_URL_ALLOWLIST",
            "mailto:user@example.com, https://api.fixture.test/path",
        )
        http_tool = _tool("http_request")
        soul = _make_soul()
        soul.resolved_tools = [http_tool]
        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert request.host_bindings is not None
        assert request.host_bindings.url_allowlist == ["api.fixture.test"]

    @pytest.mark.asyncio
    async def test_dynamic_http_allowlist_drops_url_like_invalid_port_entries(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv(
            "RUNSIGHT_HTTP_URL_ALLOWLIST",
            "https://api.fixture.test:bad/path, https://cdn.fixture.test/assets",
        )
        http_tool = _tool("http_request")
        soul = _make_soul()
        soul.resolved_tools = [http_tool]
        harness = _CapturingWorkspaceHarness()
        wrapper = _linear_wrapper(soul=soul, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert request.host_bindings is not None
        assert request.host_bindings.url_allowlist == ["cdn.fixture.test"]

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
    async def test_dispatch_branch_tool_scopes_survive_worker_reconstruction(self):
        from runsight_core.isolation import WorkspaceRunRequest
        from runsight_core.isolation.worker_proxies import create_tool_stubs
        from runsight_core.isolation.worker_support import _resolve_block_soul

        research_soul = _make_soul("dispatch_research_soul")
        research_soul.resolved_tools = [_tool("research_lookup")]
        review_soul = _make_soul("dispatch_review_soul")
        review_soul.resolved_tools = [_tool("review_lookup")]
        dispatch = DispatchBlock(
            "isolated_dispatch_block",
            [
                DispatchBranch(
                    exit_id="research",
                    label="Research",
                    soul=research_soul,
                    task_instruction="Research the input.",
                ),
                DispatchBranch(
                    exit_id="review",
                    label="Review",
                    soul=review_soul,
                    task_instruction="Review the draft.",
                ),
            ],
            MagicMock(),
        )
        harness = _CapturingWorkspaceHarness(
            _result_envelope(block_id="isolated_dispatch_block", exit_handle="research")
        )
        wrapper = _wrapper_for(dispatch, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert isinstance(request, WorkspaceRunRequest)
        branches = request.envelope.block_config["branches"]
        assert branches[0]["soul"]["resolved_tool_binding_ids"] == [
            "dispatch:research:research_lookup:0"
        ]
        assert branches[1]["soul"]["resolved_tool_binding_ids"] == [
            "dispatch:review:review_lookup:0"
        ]

        class _NoopIPCClient:
            async def request(self, _action: str, _payload: dict[str, Any]) -> dict[str, Any]:
                return {"output": "unused"}

        fallback_soul = _make_soul("dispatch_fallback_soul")
        fallback_soul.resolved_tools = create_tool_stubs(
            request.envelope.tools,
            ipc_client=_NoopIPCClient(),
        )
        reconstructed = [_resolve_block_soul(branch["soul"], fallback_soul) for branch in branches]

        assert [[tool.name for tool in soul.resolved_tools or []] for soul in reconstructed] == [
            ["research_lookup"],
            ["review_lookup"],
        ]

    @pytest.mark.asyncio
    async def test_dispatch_branch_same_name_tool_scopes_survive_worker_reconstruction(self):
        from runsight_core.isolation import WorkspaceRunRequest
        from runsight_core.isolation.worker_proxies import create_tool_stubs
        from runsight_core.isolation.worker_support import _resolve_block_soul

        left_tool = _tool("shared")
        left_tool.description = "left-config"
        right_tool = _tool("shared")
        right_tool.description = "right-config"
        left_soul = _make_soul("dispatch_left_soul")
        left_soul.resolved_tools = [left_tool]
        right_soul = _make_soul("dispatch_right_soul")
        right_soul.resolved_tools = [right_tool]
        dispatch = DispatchBlock(
            "isolated_dispatch_block",
            [
                DispatchBranch(
                    exit_id="left",
                    label="Left",
                    soul=left_soul,
                    task_instruction="Use the left config.",
                ),
                DispatchBranch(
                    exit_id="right",
                    label="Right",
                    soul=right_soul,
                    task_instruction="Use the right config.",
                ),
            ],
            MagicMock(),
        )
        harness = _CapturingWorkspaceHarness(
            _result_envelope(block_id="isolated_dispatch_block", exit_handle="left")
        )
        wrapper = _wrapper_for(dispatch, harness=harness)

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert isinstance(request, WorkspaceRunRequest)
        assert request.host_bindings is not None
        host_refs = request.host_bindings.host_tools.tools
        assert [ref.name for ref in host_refs] == ["shared", "shared"]
        assert [ref.tool.description for ref in host_refs] == ["left-config", "right-config"]
        assert len({ref.binding_id for ref in host_refs}) == 2

        branches = request.envelope.block_config["branches"]
        assert branches[0]["soul"]["resolved_tool_binding_ids"] == [host_refs[0].binding_id]
        assert branches[1]["soul"]["resolved_tool_binding_ids"] == [host_refs[1].binding_id]

        class _NoopIPCClient:
            async def request(self, _action: str, _payload: dict[str, Any]) -> dict[str, Any]:
                return {"output": "unused"}

        fallback_soul = _make_soul("dispatch_fallback_soul")
        fallback_soul.resolved_tools = create_tool_stubs(
            request.envelope.tools,
            ipc_client=_NoopIPCClient(),
        )
        reconstructed = [_resolve_block_soul(branch["soul"], fallback_soul) for branch in branches]

        assert [
            [tool.description for tool in soul.resolved_tools or []] for soul in reconstructed
        ] == [["left-config"], ["right-config"]]

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
        from runsight_core.yaml.parser import parse_workflow_yaml

        workflow = parse_workflow_yaml(
            """\
version: "1.0"
id: workspace_harness_host_binding_wiring
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
  name: workspace_harness_host_binding_wiring
  entry: draft
  transitions:
    - from: draft
      to: null
""",
            runner=MagicMock(),
            api_keys={"openai": "dummy-openai-key"},
        )

        wrapper = workflow.blocks["draft"]
        assert isinstance(wrapper, IsolatedBlockWrapper)
        harness = _CapturingWorkspaceHarness()
        wrapper.harness = harness

        await wrapper.execute(_make_ctx(wrapper, _make_state()))

        request = harness.requests[0]
        assert isinstance(request, WorkspaceRunRequest)
        assert request.host_bindings is not None
        assert request.host_bindings.api_keys == {"openai": "dummy-openai-key"}

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

    @pytest.mark.asyncio
    async def test_workspace_result_mapping_preserves_all_stateful_history_replacements(self):
        branch_histories = {
            "isolated_dispatch_block_research": [
                {"role": "user", "content": "research branch"},
                {"role": "assistant", "content": "research answer"},
            ],
            "isolated_dispatch_block_review": [
                {"role": "user", "content": "review branch"},
                {"role": "assistant", "content": "review answer"},
            ],
        }
        dispatch = _block_under_test("dispatch")
        harness = _CapturingWorkspaceHarness(
            _result_envelope(
                block_id="isolated_dispatch_block",
                output="research output",
                exit_handle="research",
                conversation_histories=branch_histories,
            )
        )
        wrapper = _wrapper_for(dispatch, harness=harness, stateful=True)

        block_output = await wrapper.execute(_make_ctx(wrapper, _make_state()))

        assert block_output.conversation_replacements == branch_histories


class TestUnixLocalHarnessDefaults:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("stdout", "returncode", "expected_exception"),
        [
            pytest.param(
                _ImmediateStdout(
                    _result_envelope(block_id="workspace-cleanup-block").model_dump_json().encode()
                ),
                0,
                None,
                id="success",
            ),
            pytest.param(_ImmediateStdout(b"not json"), 2, None, id="failure"),
            pytest.param(_TimeoutStdout(), None, TimeoutError, id="timeout"),
        ],
    )
    async def test_default_cleanup_removes_workspace_and_ipc_resources_after_run(
        self,
        tmp_path: Path,
        stdout: Any,
        returncode: int | None,
        expected_exception: type[BaseException] | None,
    ) -> None:
        from runsight_core.isolation import UnixLocalHarness

        session_factory = _CleanupSessionFactory(tmp_path / "workspace")
        ipc_transport = _CleanupIPCTransport(tmp_path / "ipc" / "run.sock")
        launcher = _CleanupWorkerLauncher(_FakeWorkerProcess(stdout=stdout, returncode=returncode))
        harness = UnixLocalHarness(
            session_factory=session_factory,
            ipc_transport=ipc_transport,
            worker_launcher=launcher,
            timeout_seconds=1,
            heartbeat_timeout=1,
        )

        if expected_exception is None:
            await harness.run(_workspace_run_request(timeout_seconds=1))
        else:
            with pytest.raises(expected_exception):
                await harness.run(_workspace_run_request(timeout_seconds=1))

        assert not session_factory.workspace_root.exists()
        assert ipc_transport.closed is True
        assert not Path(ipc_transport.binding.server_endpoint.path).exists()
