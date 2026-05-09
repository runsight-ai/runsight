"""Unix-local workspace harness behavior and host-binding contracts."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_type_hints

import pytest
from isolation_harness_helpers import _make_context_envelope, _make_result_envelope
from runsight_core.isolation import (
    HostToolExecutionRef,
    HostToolExecutionRegistry,
    IPCBinding,
    IPCClientConfig,
    IPCTransport,
    ResultEnvelope,
    UnixSocketIPCTransport,
    WorkerLaunchSpec,
    WorkerToolSchema,
    WorkspaceHostBindings,
    WorkspaceManifest,
    WorkspaceMaterialization,
    WorkspacePolicy,
    WorkspaceRunRequest,
    WorkspaceSession,
)
from runsight_core.isolation.workspace import UnixSocketEndpoint

pytestmark = pytest.mark.real_subprocess_isolation


def _isolation_contract(name: str) -> type[Any]:
    return getattr(importlib.import_module("runsight_core.isolation"), name)


def _workspace_policy() -> WorkspacePolicy:
    return WorkspacePolicy(
        network={"raw": "deny", "mediated": "allow"},
        filesystem={"raw": "deny", "mediated": "workspace"},
        credentials={"mode": "host-bound"},
    )


def _workspace_manifest(
    *,
    materializations: list[WorkspaceMaterialization] | None = None,
    working_dir: str = ".",
) -> WorkspaceManifest:
    return WorkspaceManifest(
        materializations=materializations or [],
        working_dir=working_dir,
    )


def _workspace_request(
    *,
    manifest: WorkspaceManifest | None = None,
    policy: WorkspacePolicy | None = None,
    host_bindings: WorkspaceHostBindings | None = None,
    worker_tools: list[WorkerToolSchema] | None = None,
    timeout_seconds: int = 30,
) -> WorkspaceRunRequest:
    return WorkspaceRunRequest(
        envelope=_make_context_envelope(timeout_seconds=timeout_seconds),
        manifest=manifest or _workspace_manifest(),
        policy=policy or _workspace_policy(),
        host_bindings=host_bindings,
        worker_tools=worker_tools or [],
    )


def _ipc_binding(socket_path: Path) -> IPCBinding:
    config = IPCClientConfig(
        transport=IPCTransport.UNIX_SOCKET,
        grant_token="dummy-grant-token",
        unix_socket=UnixSocketEndpoint(path=str(socket_path)),
    )
    binding = IPCBinding(
        client_config=config,
        server_endpoint=UnixSocketEndpoint(path=str(socket_path)),
        env=config.to_env(),
        cleanup_required=True,
    )
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    socket_path.write_text("", encoding="utf-8")
    return binding


class _RecordingSessionFactory:
    def __init__(self, host_root: Path) -> None:
        self.host_root = host_root
        self.created_with: list[tuple[WorkspaceManifest, WorkspacePolicy]] = []

    def create(self, manifest: WorkspaceManifest, policy: WorkspacePolicy) -> WorkspaceSession:
        self.created_with.append((manifest, policy))
        root = self.host_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return WorkspaceSession(
            id="workspace-session",
            host_root=root,
            runtime_root=root,
            runtime_workdir=root,
            cleanup=True,
        )


class _RecordingIPCTransport:
    def __init__(self, binding: IPCBinding) -> None:
        self.binding = binding
        self.closed = False

    def prepare(self, session: WorkspaceSession, policy: WorkspacePolicy) -> IPCBinding:
        self.session = session
        self.policy = policy

        def _close() -> None:
            self.closed = True
            Path(self.binding.server_endpoint.path).unlink(missing_ok=True)

        self.binding._close_callback = _close
        return self.binding


class _RecordingStdin:
    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, payload: bytes) -> None:
        self.writes.append(payload)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class _ImmediateStdout:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    async def read(self) -> bytes:
        return self.payload


class _TimeoutStdout:
    async def read(self) -> bytes:
        raise TimeoutError("worker timed out")


class _UntilTerminatedStdout:
    def __init__(self, process: "_FakeWorkerProcess") -> None:
        self.process = process

    async def read(self) -> bytes:
        await self.process.terminated.wait()
        return b""


class _QuietStderr:
    async def readline(self) -> bytes:
        await asyncio.sleep(3600)
        return b""


class _FakeWorkerProcess:
    def __init__(
        self,
        *,
        stdout: Any,
        returncode: int | None = 0,
        stderr: Any | None = None,
    ) -> None:
        self.pid = 4242
        self.returncode = returncode
        self.stdin = _RecordingStdin()
        self.stdout = stdout
        self.stderr = stderr or _QuietStderr()
        self.terminated = asyncio.Event()
        self.terminate_calls = 0

    async def wait(self) -> int:
        if self.returncode is None:
            await self.terminated.wait()
        assert self.returncode is not None
        return self.returncode

    async def terminate(self) -> None:
        self.terminate_calls += 1
        self.returncode = -15
        self.terminated.set()


class _RecordingWorkerLauncher:
    def __init__(
        self,
        process: _FakeWorkerProcess,
        *,
        on_launch: Callable[[WorkerLaunchSpec], None] | None = None,
    ) -> None:
        self.process = process
        self.on_launch = on_launch
        self.specs: list[WorkerLaunchSpec] = []

    async def launch(self, spec: WorkerLaunchSpec) -> _FakeWorkerProcess:
        self.specs.append(spec)
        if self.on_launch is not None:
            self.on_launch(spec)
        return self.process


class _RecordingTool:
    description = "Recording tool."
    parameters = {"type": "object", "properties": {"value": {"type": "string"}}}

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(args)
        return {"echo": args}


class _DirectExecutionTrapTool:
    def __init__(self, *, name: str, parameters: dict[str, Any]) -> None:
        self.name = name
        self.description = "Must be mediated by the workspace handler."
        self.parameters = parameters
        self.calls: list[dict[str, Any]] = []

    async def execute(self, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(args)
        return {"direct_tool_instance_executed": self.name}


def _worker_tool(name: str) -> WorkerToolSchema:
    return WorkerToolSchema(
        name=name,
        description="Worker-visible test tool.",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}},
    )


def _host_tool_registry(name: str, tool: Any) -> HostToolExecutionRegistry:
    return HostToolExecutionRegistry(
        tools=[
            HostToolExecutionRef(
                name=name,
                tool=tool,
                credential_refs=["dummy-credential-ref"],
                headers={"Authorization": "Bearer host-only"},
            )
        ]
    )


def _harness(
    *,
    tmp_path: Path,
    process: _FakeWorkerProcess,
    cleanup: str = "always",
    ipc_transport: Any | None = None,
    on_launch: Callable[[WorkerLaunchSpec], None] | None = None,
    heartbeat_timeout: float = 1.0,
) -> tuple[Any, _RecordingSessionFactory, Any, _RecordingWorkerLauncher]:
    UnixLocalHarness = _isolation_contract("UnixLocalHarness")
    session_factory = _RecordingSessionFactory(tmp_path / "workspace")
    transport = ipc_transport or _RecordingIPCTransport(_ipc_binding(tmp_path / "ipc" / "rs.sock"))
    launcher = _RecordingWorkerLauncher(process, on_launch=on_launch)
    harness = UnixLocalHarness(
        session_factory=session_factory,
        ipc_transport=transport,
        worker_launcher=launcher,
        cleanup=cleanup,
        heartbeat_timeout=heartbeat_timeout,
    )
    return harness, session_factory, transport, launcher


def test_unix_local_harness_public_contract_uses_workspace_request() -> None:
    UnixLocalHarness = _isolation_contract("UnixLocalHarness")
    WorkspaceRunRequestContract = _isolation_contract("WorkspaceRunRequest")

    init_parameters = set(inspect.signature(UnixLocalHarness).parameters)
    constructor_side_channels = {
        "api_keys",
        "resolved_tools",
        "tool_credentials",
        "http_credentials",
        "url_allowlist",
        "working_dir",
        "grant_token",
    }
    assert init_parameters.isdisjoint(constructor_side_channels)

    run_signature = inspect.signature(UnixLocalHarness.run)
    run_hints = get_type_hints(UnixLocalHarness.run)
    assert "request" in run_signature.parameters
    assert run_hints["request"] is WorkspaceRunRequestContract
    assert run_hints["return"] is ResultEnvelope


@pytest.mark.asyncio
async def test_valid_workspace_run_launches_worker_module_and_returns_result(
    tmp_path: Path,
) -> None:
    expected = _make_result_envelope(output="workspace complete")
    process = _FakeWorkerProcess(stdout=_ImmediateStdout(expected.model_dump_json().encode()))
    harness, session_factory, _transport, launcher = _harness(tmp_path=tmp_path, process=process)
    request = _workspace_request()

    result = await harness.run(request)

    assert result == expected
    assert len(session_factory.created_with) == 1
    assert session_factory.created_with[0] == (request.manifest, request.policy)
    assert len(launcher.specs) == 1
    spec = launcher.specs[0]
    assert spec.argv[-2:] == ["-m", "runsight_core.isolation.worker"]
    assert spec.cwd == session_factory.host_root.resolve()
    assert spec.ipc is not None


@pytest.mark.asyncio
async def test_unix_worker_launcher_executes_worker_launch_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_module = importlib.import_module("runsight_core.isolation.workspace")
    UnixWorkerLauncher = _isolation_contract("UnixWorkerLauncher")
    launched: dict[str, Any] = {}
    fake_process = _FakeWorkerProcess(stdout=_ImmediateStdout(b""), returncode=0)
    spec = WorkerLaunchSpec(
        argv=["python", "-m", "runsight_core.isolation.worker"],
        cwd=tmp_path / "runtime-workspace",
        env={"RUNSIGHT_IPC_CONFIG_B64": "encoded-ipc-config"},
    )
    spec.cwd.mkdir()

    async def fake_create_subprocess_exec(*argv: str, **kwargs: Any) -> _FakeWorkerProcess:
        launched["argv"] = list(argv)
        launched["cwd"] = kwargs.get("cwd")
        launched["env"] = kwargs.get("env")
        return fake_process

    monkeypatch.setattr(
        workspace_module.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )

    handle = await UnixWorkerLauncher().launch(spec)

    assert launched["argv"] == spec.argv
    assert launched["cwd"] == spec.cwd
    assert launched["env"] == spec.env
    assert handle.pid == fake_process.pid
    assert await handle.wait() == 0
    await handle.terminate()
    assert fake_process.terminate_calls == 1


@pytest.mark.asyncio
async def test_materialized_files_and_worker_cwd_share_the_canonical_workspace_root(
    tmp_path: Path,
) -> None:
    materialized_at_launch: dict[str, Any] = {}
    manifest = _workspace_manifest(
        materializations=[
            WorkspaceMaterialization(path="data/input.txt", content="seed data"),
        ],
        working_dir="work",
    )
    expected = _make_result_envelope()
    process = _FakeWorkerProcess(stdout=_ImmediateStdout(expected.model_dump_json().encode()))

    def on_launch(spec: WorkerLaunchSpec) -> None:
        workspace_root = (tmp_path / "workspace").resolve()
        materialized_at_launch["file_content"] = (workspace_root / "data" / "input.txt").read_text(
            encoding="utf-8"
        )
        materialized_at_launch["workspace_root"] = workspace_root
        materialized_at_launch["cwd"] = spec.cwd

    harness, _session_factory, _transport, _launcher = _harness(
        tmp_path=tmp_path,
        process=process,
        on_launch=on_launch,
    )

    await harness.run(_workspace_request(manifest=manifest))

    assert materialized_at_launch["file_content"] == "seed data"
    assert materialized_at_launch["cwd"] == materialized_at_launch["workspace_root"] / "work"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stdout", "returncode", "expected_exception"),
    [
        pytest.param(
            _ImmediateStdout(_make_result_envelope().model_dump_json().encode()),
            0,
            None,
            id="success",
        ),
        pytest.param(_ImmediateStdout(b"not json"), 2, None, id="failure"),
        pytest.param(_TimeoutStdout(), None, TimeoutError, id="timeout"),
    ],
)
async def test_cleanup_always_removes_workspace_and_ipc_resources(
    tmp_path: Path,
    stdout: Any,
    returncode: int | None,
    expected_exception: type[BaseException] | None,
) -> None:
    process = _FakeWorkerProcess(stdout=stdout, returncode=returncode)
    binding = _ipc_binding(tmp_path / "ipc" / "run.sock")
    transport = _RecordingIPCTransport(binding)
    harness, session_factory, _transport, _launcher = _harness(
        tmp_path=tmp_path,
        process=process,
        ipc_transport=transport,
        cleanup="always",
    )

    if expected_exception is None:
        await harness.run(_workspace_request(timeout_seconds=1))
    else:
        with pytest.raises(expected_exception):
            await harness.run(_workspace_request(timeout_seconds=1))

    assert not session_factory.host_root.exists()
    assert transport.closed is True
    assert not Path(binding.server_endpoint.path).exists()


@pytest.mark.asyncio
async def test_heartbeat_stall_terminates_worker_and_returns_stall_error(
    tmp_path: Path,
) -> None:
    process = _FakeWorkerProcess(stdout=None, returncode=None)
    process.stdout = _UntilTerminatedStdout(process)
    harness, _session_factory, _transport, _launcher = _harness(
        tmp_path=tmp_path,
        process=process,
        heartbeat_timeout=0.01,
    )

    result = await harness.run(_workspace_request())

    assert process.terminate_calls == 1
    assert result.exit_handle == "error"
    assert result.error_type == "BlockStallError"
    assert "heartbeat" in (result.error or "").lower() or "stall" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_host_handlers_are_built_from_workspace_host_bindings_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from runsight_core.isolation import handlers as handlers_module

    captured: dict[str, Any] = {}

    def fake_make_llm_call_handler(*, api_keys: dict[str, str]):
        captured["api_keys"] = dict(api_keys)

        async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"content": "ok"}

        return _handler

    def fake_make_http_handler(*, credentials: dict[str, dict[str, str]], url_allowlist: list[str]):
        captured["http_credentials"] = dict(credentials)
        captured["url_allowlist"] = list(url_allowlist)

        async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"status_code": 200}

        return _handler

    def fake_make_file_io_handler(*, base_dir: str):
        captured["file_io_base_dir"] = Path(base_dir).resolve()

        async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True}

        return _handler

    def fake_make_tool_call_handler(*_args: Any, **_kwargs: Any):
        async def _handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"output": "ok"}

        return _handler

    monkeypatch.setattr(handlers_module, "make_llm_call_handler", fake_make_llm_call_handler)
    monkeypatch.setattr(handlers_module, "make_http_handler", fake_make_http_handler)
    monkeypatch.setattr(handlers_module, "make_file_io_handler", fake_make_file_io_handler)
    monkeypatch.setattr(handlers_module, "make_tool_call_handler", fake_make_tool_call_handler)

    host_bindings = WorkspaceHostBindings(
        api_keys={"openai": "sk-host-only"},
        http_credentials={"api.fixture.test": {"Authorization": "Bearer http-host-only"}},
        url_allowlist=["api.fixture.test"],
        host_tools=HostToolExecutionRegistry(tools=[]),
    )
    expected = _make_result_envelope()
    process = _FakeWorkerProcess(stdout=_ImmediateStdout(expected.model_dump_json().encode()))
    real_ipc_transport = UnixSocketIPCTransport(socket_dir=tmp_path / "ipc")
    harness, session_factory, _transport, launcher = _harness(
        tmp_path=tmp_path,
        process=process,
        ipc_transport=real_ipc_transport,
    )

    await harness.run(_workspace_request(host_bindings=host_bindings))

    assert captured["api_keys"] == {"openai": "sk-host-only"}
    assert captured["http_credentials"] == {
        "api.fixture.test": {"Authorization": "Bearer http-host-only"}
    }
    assert captured["url_allowlist"] == ["api.fixture.test"]
    assert captured["file_io_base_dir"] == session_factory.host_root.resolve()

    worker_env = launcher.specs[0].env
    serialized_env = json.dumps(worker_env, sort_keys=True)
    assert set(worker_env) == {"RUNSIGHT_IPC_CONFIG_B64"}
    assert "RUNSIGHT_GRANT_TOKEN" not in worker_env
    assert "RUNSIGHT_IPC_SOCKET" not in worker_env
    assert "sk-host-only" not in serialized_env
    assert "Bearer http-host-only" not in serialized_env


@pytest.mark.asyncio
async def test_invalid_manifest_materialization_fails_before_worker_launch(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    conflict = workspace_root / "data" / "input.txt"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("already exists", encoding="utf-8")
    manifest = _workspace_manifest(
        materializations=[
            WorkspaceMaterialization(path="data/input.txt", content="replacement"),
        ]
    )
    process = _FakeWorkerProcess(
        stdout=_ImmediateStdout(_make_result_envelope().model_dump_json().encode())
    )
    harness, _session_factory, _transport, launcher = _harness(tmp_path=tmp_path, process=process)

    with pytest.raises(FileExistsError):
        await harness.run(_workspace_request(manifest=manifest))

    assert launcher.specs == []


@pytest.mark.asyncio
async def test_nonzero_exit_with_valid_result_returns_worker_envelope(
    tmp_path: Path,
) -> None:
    expected = _make_result_envelope(output="worker reported handled failure")
    process = _FakeWorkerProcess(
        stdout=_ImmediateStdout(expected.model_dump_json().encode()),
        returncode=7,
    )
    harness, _session_factory, _transport, _launcher = _harness(tmp_path=tmp_path, process=process)

    result = await harness.run(_workspace_request())

    assert result == expected


@pytest.mark.asyncio
async def test_nonzero_exit_without_valid_result_maps_to_subprocess_error(
    tmp_path: Path,
) -> None:
    process = _FakeWorkerProcess(stdout=_ImmediateStdout(b"not a result"), returncode=7)
    harness, _session_factory, _transport, _launcher = _harness(tmp_path=tmp_path, process=process)

    result = await harness.run(_workspace_request())

    assert result.block_id == "harness-block"
    assert result.exit_handle == "error"
    assert result.error_type == "SubprocessError"
    assert result.error == "Process exit error (code 7)"


def test_unix_local_capability_report_marks_raw_restrictions_advisory() -> None:
    UnixLocalHarness = _isolation_contract("UnixLocalHarness")

    report = UnixLocalHarness.capability_report(
        WorkspacePolicy(
            network={"raw": "deny"},
            filesystem={"raw": "deny", "mediated": "workspace"},
            credentials={"mode": "host-bound"},
        )
    )

    assert report.backend == "unix-local"
    assert "raw_network_restriction" in report.advisory
    assert "raw_filesystem_restriction" in report.advisory
    assert "credential_host_binding" in report.enforced
    assert "docker" not in report.backend.lower()


def test_tool_call_handler_public_contract_requires_workspace_registries_only() -> None:
    from runsight_core.isolation.handlers import make_tool_call_handler

    signature = inspect.signature(make_tool_call_handler)

    assert "resolved_tools" not in signature.parameters
    assert list(signature.parameters) == ["host_tools", "worker_tools"]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in signature.parameters.values()
    )


def test_tool_call_handler_rejects_positional_tool_registry_contract() -> None:
    from runsight_core.isolation.handlers import make_tool_call_handler

    with pytest.raises(TypeError):
        make_tool_call_handler({"lookup": _RecordingTool()})

    with pytest.raises(TypeError):
        make_tool_call_handler()


@pytest.mark.asyncio
async def test_tool_call_executes_only_when_host_and_worker_registries_match() -> None:
    from runsight_core.isolation.handlers import make_tool_call_handler

    tool = _RecordingTool()
    handler = make_tool_call_handler(
        host_tools=_host_tool_registry("lookup", tool),
        worker_tools=[_worker_tool("lookup")],
    )

    result = await handler({"name": "lookup", "arguments": {"value": "hi"}})

    assert result == {"output": {"echo": {"value": "hi"}}}
    assert tool.calls == [{"value": "hi"}]


@pytest.mark.asyncio
async def test_tool_call_mediates_worker_file_io_through_workspace_file_handler(
    tmp_path: Path,
) -> None:
    file_parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "write"]},
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["action", "path"],
    }
    direct_file_tool = _DirectExecutionTrapTool(name="file_io", parameters=file_parameters)
    host_bindings = WorkspaceHostBindings(
        host_tools=HostToolExecutionRegistry(
            tools=[HostToolExecutionRef(name="file_io", tool=direct_file_tool)]
        )
    )
    request = _workspace_request(
        host_bindings=host_bindings,
        worker_tools=[
            WorkerToolSchema(
                name="file_io",
                description="Read or write files in the workspace.",
                parameters=file_parameters,
            )
        ],
    )
    process = _FakeWorkerProcess(
        stdout=_ImmediateStdout(_make_result_envelope().model_dump_json().encode())
    )
    harness, session_factory, _transport, _launcher = _harness(
        tmp_path=tmp_path,
        process=process,
    )
    session = session_factory.create(request.manifest, request.policy)
    tool_call_handler = harness._build_ipc_handlers(request=request, session=session)["tool_call"]

    result = await tool_call_handler(
        {
            "name": "file_io",
            "arguments": {
                "action": "write",
                "path": "reports/result.txt",
                "content": "workspace-owned",
            },
        }
    )

    assert direct_file_tool.calls == []
    assert "error" not in result
    assert (session.host_root / "reports" / "result.txt").read_text(
        encoding="utf-8"
    ) == "workspace-owned"


@pytest.mark.asyncio
async def test_tool_call_mediates_worker_http_request_through_workspace_http_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from runsight_core.isolation import handlers as handlers_module

    http_parameters = {
        "type": "object",
        "properties": {
            "method": {"type": "string"},
            "url": {"type": "string"},
            "headers": {"type": "object"},
        },
        "required": ["method", "url"],
    }
    direct_http_tool = _DirectExecutionTrapTool(
        name="http_request",
        parameters=http_parameters,
    )
    captured_http: list[dict[str, Any]] = []
    ssrf_checks: list[str] = []

    async def fake_validate_ssrf(url: str) -> None:
        ssrf_checks.append(url)

    async def fake_perform_http_request(**kwargs: Any) -> dict[str, Any]:
        captured_http.append(kwargs)
        return {"status_code": 200, "body": "ok", "headers": {}}

    monkeypatch.setattr(handlers_module, "validate_ssrf", fake_validate_ssrf)
    monkeypatch.setattr(handlers_module, "_perform_http_request", fake_perform_http_request)

    host_bindings = WorkspaceHostBindings(
        http_credentials={"api.fixture.test": {"Authorization": "Bearer host-http-token"}},
        url_allowlist=["api.fixture.test"],
        host_tools=HostToolExecutionRegistry(
            tools=[HostToolExecutionRef(name="http_request", tool=direct_http_tool)]
        ),
    )
    request = _workspace_request(
        host_bindings=host_bindings,
        worker_tools=[
            WorkerToolSchema(
                name="http_request",
                description="Perform an HTTP request through the workspace host.",
                parameters=http_parameters,
            )
        ],
    )
    process = _FakeWorkerProcess(
        stdout=_ImmediateStdout(_make_result_envelope().model_dump_json().encode())
    )
    harness, session_factory, _transport, _launcher = _harness(
        tmp_path=tmp_path,
        process=process,
    )
    session = session_factory.create(request.manifest, request.policy)
    tool_call_handler = harness._build_ipc_handlers(request=request, session=session)["tool_call"]

    allowed = await tool_call_handler(
        {
            "name": "http_request",
            "arguments": {
                "method": "GET",
                "url": "https://api.fixture.test/data",
                "headers": {"Accept": "application/json"},
            },
        }
    )

    assert direct_http_tool.calls == []
    assert "error" not in allowed
    assert ssrf_checks == ["https://api.fixture.test/data"]
    assert captured_http[0]["headers"]["Authorization"] == "Bearer host-http-token"
    assert captured_http[0]["headers"]["Accept"] == "application/json"

    blocked = await tool_call_handler(
        {
            "name": "http_request",
            "arguments": {
                "method": "GET",
                "url": "https://blocked.fixture.test/data",
                "headers": {},
            },
        }
    )

    assert "Host not on allowed list" in json.dumps(blocked)
    assert len(captured_http) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("host_tools", "worker_tools", "requested_name"),
    [
        pytest.param(HostToolExecutionRegistry(tools=[]), [], "missing", id="unknown"),
        pytest.param(
            _host_tool_registry("host_only", _RecordingTool()),
            [],
            "host_only",
            id="host-only",
        ),
        pytest.param(
            HostToolExecutionRegistry(tools=[]),
            [_worker_tool("worker_only")],
            "worker_only",
            id="worker-only",
        ),
    ],
)
async def test_tool_call_mismatches_return_structured_tool_not_found(
    host_tools: HostToolExecutionRegistry,
    worker_tools: list[WorkerToolSchema],
    requested_name: str,
) -> None:
    from runsight_core.isolation.handlers import make_tool_call_handler

    handler = make_tool_call_handler(host_tools=host_tools, worker_tools=worker_tools)

    result = await handler({"name": requested_name, "arguments": {"value": "hi"}})

    assert result == {"error": {"code": "tool_not_found", "tool": requested_name}}
    assert "Bearer host-only" not in json.dumps(result)
