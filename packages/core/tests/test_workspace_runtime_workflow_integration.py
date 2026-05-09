"""Workflow-level coverage for the Unix-local workspace runtime."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from isolation_harness_helpers import _make_context_envelope
from pydantic import ValidationError
from runsight_core.isolation import (
    HostToolExecutionRegistry,
    IsolatedBlockWrapper,
    UnixLocalHarness,
    UnixSocketIPCTransport,
    UnixWorkerLauncher,
    WorkerLaunchSpec,
    WorkspaceHostBindings,
    WorkspaceManifest,
    WorkspaceMaterialization,
    WorkspacePolicy,
    WorkspaceRunRequest,
    WorkspaceSessionFactory,
)
from runsight_core.isolation.errors import BlockExecutionError
from runsight_core.isolation.workspace import UnixLocalHarness as HarnessClass
from runsight_core.isolation.wrapper import IsolatedBlockWrapper as WrapperClass
from runsight_core.paths import is_path_within_base
from runsight_core.state import WorkflowState
from runsight_core.tools import ToolInstance
from runsight_core.yaml.parser import parse_workflow_yaml

pytestmark = pytest.mark.real_workspace_runtime


class _RecordingUnixWorkerLauncher:
    def __init__(self) -> None:
        self.specs: list[WorkerLaunchSpec] = []
        self._launcher = UnixWorkerLauncher()

    async def launch(self, spec: WorkerLaunchSpec):
        self.specs.append(spec)
        return await self._launcher.launch(spec)


class _LaunchForbidden:
    def __init__(self) -> None:
        self.specs: list[WorkerLaunchSpec] = []

    async def launch(self, spec: WorkerLaunchSpec):
        self.specs.append(spec)
        raise AssertionError("worker must not launch for an invalid manifest")


class _EnvelopeTimeoutHarness(UnixLocalHarness):
    async def run(self, request: WorkspaceRunRequest):
        request = request.model_copy(
            update={
                "envelope": request.envelope.model_copy(update={"timeout_seconds": 1}),
            }
        )
        return await super().run(request)


class _HostToolDeniedHarness(UnixLocalHarness):
    async def run(self, request: WorkspaceRunRequest):
        host_bindings = request.host_bindings or WorkspaceHostBindings()
        request = request.model_copy(
            update={
                "host_bindings": host_bindings.model_copy(
                    update={"host_tools": HostToolExecutionRegistry(tools=[])}
                )
            }
        )
        return await super().run(request)


def _assert_real_workspace_runtime_fixture_active() -> None:
    assert inspect.getfile(WrapperClass._run_in_subprocess).endswith("wrapper.py")
    assert "worker_launcher" in inspect.getsource(HarnessClass.run)


def _workflow_yaml(
    *,
    block_id: str = "draft",
    soul_id: str = "writer",
    stateful: bool = False,
    soul_tools: list[str] | None = None,
    workflow_tools: list[str] | None = None,
) -> str:
    tools_section = ""
    if workflow_tools is not None:
        tools_section = "tools:\n" + "\n".join(f"  - {tool}" for tool in workflow_tools)
    soul_tool_section = ""
    if soul_tools is not None:
        soul_tool_section = "    tools:\n" + "\n".join(f"      - {tool}" for tool in soul_tools)
    stateful_line = "    stateful: true\n" if stateful else ""
    return f"""\
version: "1.0"
id: workspace-runtime-integration
kind: workflow
{tools_section}
souls:
  {soul_id}:
    id: {soul_id}
    kind: soul
    name: Writer
    role: Writer
    system_prompt: Write deterministic test output.
    provider: openai
    model_name: gpt-4o-mini
{soul_tool_section}
blocks:
  {block_id}:
    type: linear
{stateful_line}    soul_ref: {soul_id}
workflow:
  name: workspace_runtime_integration
  entry: {block_id}
  transitions:
    - from: {block_id}
      to: null
"""


def _patch_llm_stream(
    monkeypatch: pytest.MonkeyPatch,
    responder: Callable[[dict[str, Any], int], dict[str, Any]],
) -> dict[str, Any]:
    import runsight_core.isolation.handlers as handlers_module

    captured: dict[str, Any] = {"api_keys": None, "payloads": []}

    def fake_make_llm_call_handler(api_keys: dict[str, str]):
        captured["api_keys"] = dict(api_keys)

        def _handler(payload: dict[str, Any]):
            captured["payloads"].append(payload)
            call_number = len(captured["payloads"])
            response = responder(payload, call_number)

            async def _stream():
                yield response

            return _stream()

        return _handler

    monkeypatch.setattr(handlers_module, "make_llm_call_handler", fake_make_llm_call_handler)
    return captured


def _patch_tool_call_recorder(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    import runsight_core.isolation.handlers as handlers_module

    original_factory = handlers_module.make_tool_call_handler
    results: list[dict[str, Any]] = []

    def recording_make_tool_call_handler(*args: Any, **kwargs: Any):
        handler = original_factory(*args, **kwargs)

        async def _handler(payload: dict[str, Any]) -> dict[str, Any]:
            result = await handler(payload)
            results.append(result)
            return result

        return _handler

    monkeypatch.setattr(handlers_module, "make_tool_call_handler", recording_make_tool_call_handler)
    return results


def _harness(
    tmp_path: Path,
    *,
    host_root: Path | None = None,
    cleanup: str = "always",
    harness_cls: type[UnixLocalHarness] = UnixLocalHarness,
    timeout_seconds: int = 5,
) -> tuple[UnixLocalHarness, _RecordingUnixWorkerLauncher, Path]:
    workspace_root = (host_root or tmp_path / "workspace").resolve()
    launcher = _RecordingUnixWorkerLauncher()
    harness = harness_cls(
        session_factory=WorkspaceSessionFactory(host_root=workspace_root),
        ipc_transport=UnixSocketIPCTransport(socket_dir=Path("/tmp")),
        worker_launcher=launcher,
        cleanup=cleanup,
        timeout_seconds=timeout_seconds,
        heartbeat_timeout=2.0,
        phase_timeout=2.0,
    )
    return harness, launcher, workspace_root


def _parse_with_harness(
    yaml_text: str,
    *,
    base_dir: Path,
    harness: UnixLocalHarness,
    block_id: str = "draft",
):
    workflow = parse_workflow_yaml(
        yaml_text,
        _base_dir=str(base_dir),
        api_keys={"openai": "sk-host-only-runtime-test"},
        runner=MagicMock(model_name="gpt-4o-mini"),
    )
    wrapper = workflow.blocks[block_id]
    assert isinstance(wrapper, IsolatedBlockWrapper)
    wrapper.harness = harness
    return workflow, wrapper


def _assert_worker_env_is_ipc_only(launcher: _RecordingUnixWorkerLauncher) -> None:
    assert launcher.specs, "real worker launcher was not called"
    worker_env = launcher.specs[0].env
    serialized = json.dumps(worker_env, sort_keys=True)
    assert set(worker_env) == {"RUNSIGHT_IPC_CONFIG_B64"}
    assert "RUNSIGHT_GRANT_TOKEN" not in worker_env
    assert "RUNSIGHT_IPC_SOCKET" not in worker_env
    assert "sk-host-only-runtime-test" not in serialized


@pytest.mark.asyncio
async def test_parsed_linear_workflow_runs_through_workspace_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_workspace_runtime_fixture_active()
    captured = _patch_llm_stream(
        monkeypatch,
        lambda _payload, _call: {
            "content": "workspace linear output",
            "cost_usd": 0.07,
            "prompt_tokens": 3,
            "completion_tokens": 4,
            "total_tokens": 7,
            "tool_calls": [],
            "finish_reason": "stop",
        },
    )
    harness, launcher, workspace_root = _harness(tmp_path)
    workflow, _wrapper = _parse_with_harness(
        _workflow_yaml(),
        base_dir=tmp_path,
        harness=harness,
    )

    state = await workflow.run(WorkflowState())

    assert state.results["draft"].output == "workspace linear output"
    assert state.results["draft"].exit_handle == "done"
    assert state.total_cost_usd == pytest.approx(0.07)
    assert state.total_tokens == 7
    assert captured["api_keys"] == {"openai": "sk-host-only-runtime-test"}
    assert captured["payloads"][0]["model"] == "gpt-4o-mini"
    _assert_worker_env_is_ipc_only(launcher)
    assert not workspace_root.exists()


@pytest.mark.asyncio
async def test_stateful_workflow_replaces_history_returned_from_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_workspace_runtime_fixture_active()
    payload_messages: list[list[dict[str, Any]]] = []

    def responder(payload: dict[str, Any], call_number: int) -> dict[str, Any]:
        payload_messages.append(list(payload["messages"]))
        return {
            "content": f"stateful answer {call_number}",
            "cost_usd": 0.01,
            "prompt_tokens": 2,
            "completion_tokens": 3,
            "total_tokens": 5,
            "tool_calls": [],
            "finish_reason": "stop",
        }

    _patch_llm_stream(monkeypatch, responder)
    harness, launcher, workspace_root = _harness(tmp_path)
    workflow, _wrapper = _parse_with_harness(
        _workflow_yaml(stateful=True),
        base_dir=tmp_path,
        harness=harness,
    )

    first_state = await workflow.run(WorkflowState())
    second_state = await workflow.run(first_state)

    history_key = "draft_writer"
    assert [message["content"] for message in second_state.conversation_histories[history_key]] == [
        "",
        "stateful answer 1",
        "",
        "stateful answer 2",
    ]
    assert payload_messages[1][:2] == [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "stateful answer 1"},
    ]
    assert second_state.total_cost_usd == pytest.approx(0.02)
    assert second_state.total_tokens == 10
    assert len(launcher.specs) == 2
    assert not workspace_root.exists()


@pytest.mark.asyncio
async def test_tool_workflow_requires_worker_and_host_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_workspace_runtime_fixture_active()
    tool_calls: list[dict[str, Any]] = []

    async def execute_lookup(args: dict[str, Any]) -> dict[str, Any]:
        tool_calls.append(args)
        return {"profile": f"known:{args['name']}"}

    def responder(payload: dict[str, Any], call_number: int) -> dict[str, Any]:
        if call_number == 1:
            return {
                "content": "",
                "cost_usd": 0.02,
                "prompt_tokens": 6,
                "completion_tokens": 1,
                "total_tokens": 7,
                "tool_calls": [
                    {
                        "id": "call_lookup",
                        "type": "function",
                        "function": {
                            "name": "lookup_profile",
                            "arguments": json.dumps({"name": "Ada"}),
                        },
                    }
                ],
                "finish_reason": "tool_calls",
            }
        assert payload["messages"][-1]["role"] == "tool"
        assert "known:Ada" in payload["messages"][-1]["content"]
        return {
            "content": "lookup complete",
            "cost_usd": 0.03,
            "prompt_tokens": 8,
            "completion_tokens": 2,
            "total_tokens": 10,
            "tool_calls": [],
            "finish_reason": "stop",
        }

    _patch_llm_stream(monkeypatch, responder)
    harness, launcher, workspace_root = _harness(tmp_path)
    workflow, wrapper = _parse_with_harness(
        _workflow_yaml(),
        base_dir=tmp_path,
        harness=harness,
    )
    wrapper.soul.resolved_tools = [
        ToolInstance(
            name="lookup_profile",
            description="Lookup a test profile.",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            execute=execute_lookup,
        )
    ]

    state = await workflow.run(WorkflowState())

    assert state.results["draft"].output == "lookup complete"
    assert state.total_cost_usd == pytest.approx(0.05)
    assert state.total_tokens == 17
    assert tool_calls == [{"name": "Ada"}]
    _assert_worker_env_is_ipc_only(launcher)
    assert not workspace_root.exists()


@pytest.mark.asyncio
async def test_file_tool_writes_under_canonical_workspace_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_workspace_runtime_fixture_active()
    workspace_root = (tmp_path / "canonical-workspace").resolve()

    def responder(payload: dict[str, Any], call_number: int) -> dict[str, Any]:
        if call_number == 1:
            return {
                "content": "",
                "cost_usd": 0.01,
                "prompt_tokens": 5,
                "completion_tokens": 1,
                "total_tokens": 6,
                "tool_calls": [
                    {
                        "id": "call_file",
                        "type": "function",
                        "function": {
                            "name": "file_io",
                            "arguments": json.dumps(
                                {
                                    "action": "write",
                                    "path": "reports/result.txt",
                                    "content": "file output",
                                }
                            ),
                        },
                    }
                ],
                "finish_reason": "tool_calls",
            }
        assert "Written 11 bytes" in payload["messages"][-1]["content"]
        return {
            "content": "file write complete",
            "cost_usd": 0.01,
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "total_tokens": 7,
            "tool_calls": [],
            "finish_reason": "stop",
        }

    _patch_llm_stream(monkeypatch, responder)
    harness, launcher, _workspace_root = _harness(
        tmp_path,
        host_root=workspace_root,
        cleanup="never",
    )
    workflow, _wrapper = _parse_with_harness(
        _workflow_yaml(soul_tools=["file_io"], workflow_tools=["file_io"]),
        base_dir=workspace_root,
        harness=harness,
    )

    state = await workflow.run(WorkflowState())

    written = (workspace_root / "reports" / "result.txt").resolve()
    assert state.results["draft"].output == "file write complete"
    assert written.read_text(encoding="utf-8") == "file output"
    assert is_path_within_base(workspace_root, written)
    assert not (tmp_path / "reports" / "result.txt").exists()
    _assert_worker_env_is_ipc_only(launcher)


@pytest.mark.asyncio
async def test_unknown_host_tool_returns_structured_error_to_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_workspace_runtime_fixture_active()
    tool_results = _patch_tool_call_recorder(monkeypatch)

    def responder(payload: dict[str, Any], call_number: int) -> dict[str, Any]:
        if call_number == 1:
            return {
                "content": "",
                "cost_usd": 0.01,
                "prompt_tokens": 5,
                "completion_tokens": 1,
                "total_tokens": 6,
                "tool_calls": [
                    {
                        "id": "call_lookup",
                        "type": "function",
                        "function": {
                            "name": "lookup_profile",
                            "arguments": json.dumps({"name": "Ada"}),
                        },
                    }
                ],
                "finish_reason": "tool_calls",
            }
        assert "tool_not_found" in payload["messages"][-1]["content"]
        return {
            "content": "handled missing tool",
            "cost_usd": 0.01,
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "total_tokens": 7,
            "tool_calls": [],
            "finish_reason": "stop",
        }

    _patch_llm_stream(monkeypatch, responder)
    harness, launcher, workspace_root = _harness(
        tmp_path,
        harness_cls=_HostToolDeniedHarness,
    )
    workflow, wrapper = _parse_with_harness(
        _workflow_yaml(),
        base_dir=tmp_path,
        harness=harness,
    )
    wrapper.soul.resolved_tools = [
        ToolInstance(
            name="lookup_profile",
            description="Lookup a test profile.",
            parameters={"type": "object", "properties": {"name": {"type": "string"}}},
            execute=lambda _args: {"profile": "should not run"},
        )
    ]

    state = await workflow.run(WorkflowState())

    assert state.results["draft"].output == "handled missing tool"
    assert tool_results == [
        {"error": {"code": "tool_not_found", "tool": "lookup_profile"}},
    ]
    _assert_worker_env_is_ipc_only(launcher)
    assert not workspace_root.exists()


@pytest.mark.asyncio
async def test_worker_failure_cleans_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_workspace_runtime_fixture_active()
    _patch_llm_stream(
        monkeypatch,
        lambda _payload, _call: {
            "error": "host-side model failure",
        },
    )
    harness, launcher, workspace_root = _harness(tmp_path)
    workflow, _wrapper = _parse_with_harness(
        _workflow_yaml(),
        base_dir=tmp_path,
        harness=harness,
    )

    with pytest.raises(BlockExecutionError, match="llm_call failed"):
        await workflow.run(WorkflowState())

    _assert_worker_env_is_ipc_only(launcher)
    assert not workspace_root.exists()


@pytest.mark.asyncio
async def test_worker_timeout_cleans_workspace_and_terminates_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_real_workspace_runtime_fixture_active()

    def fake_make_llm_call_handler(api_keys: dict[str, str]):
        del api_keys

        def _handler(_payload: dict[str, Any]):
            async def _stream():
                await asyncio.sleep(30)
                yield {"content": "too late"}

            return _stream()

        return _handler

    import runsight_core.isolation.handlers as handlers_module

    monkeypatch.setattr(handlers_module, "make_llm_call_handler", fake_make_llm_call_handler)
    harness, launcher, workspace_root = _harness(
        tmp_path,
        harness_cls=_EnvelopeTimeoutHarness,
        timeout_seconds=1,
    )
    workflow, _wrapper = _parse_with_harness(
        _workflow_yaml(),
        base_dir=tmp_path,
        harness=harness,
    )

    with pytest.raises(TimeoutError, match="Subprocess timed out"):
        await workflow.run(WorkflowState())

    _assert_worker_env_is_ipc_only(launcher)
    assert not workspace_root.exists()


@pytest.mark.asyncio
async def test_invalid_manifest_path_fails_before_worker_launch_and_cleans_workspace(
    tmp_path: Path,
) -> None:
    _assert_real_workspace_runtime_fixture_active()
    workspace_root = (tmp_path / "workspace").resolve()
    with pytest.raises(ValidationError, match=r"workspace path cannot contain '\.\.'"):
        WorkspaceMaterialization(path="../escape.txt", content="nope")

    workspace_root.mkdir(parents=True)
    (workspace_root / "not-a-directory").write_text("conflict", encoding="utf-8")
    launcher = _LaunchForbidden()
    harness = UnixLocalHarness(
        session_factory=WorkspaceSessionFactory(host_root=workspace_root),
        ipc_transport=UnixSocketIPCTransport(socket_dir=Path("/tmp")),
        worker_launcher=launcher,
        cleanup="always",
    )
    request = WorkspaceRunRequest(
        envelope=_make_context_envelope(timeout_seconds=1),
        manifest=WorkspaceManifest(
            materializations=[],
            working_dir="not-a-directory",
        ),
        policy=WorkspacePolicy(
            network={"raw": "deny", "mediated": "allow"},
            filesystem={"raw": "deny", "mediated": "workspace"},
            credentials={"mode": "host-bound"},
        ),
        worker_tools=[],
        host_bindings=WorkspaceHostBindings(),
    )

    with pytest.raises(ValueError, match="working directory is not a directory"):
        await harness.run(request)

    assert launcher.specs == []
    assert not workspace_root.exists()
