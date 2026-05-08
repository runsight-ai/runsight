"""Workspace runtime contract model and registry behavior."""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_type_hints

import pytest
from pydantic import ValidationError
from runsight_core.isolation import (
    ContextEnvelope,
    PromptEnvelope,
    ResultEnvelope,
    SoulEnvelope,
)
from runsight_core.tools import ToolInstance


def _contract(name: str) -> type[Any]:
    isolation = importlib.import_module("runsight_core.isolation")
    exports = set(getattr(isolation, "__all__", ()))

    assert hasattr(isolation, name), f"runsight_core.isolation must expose {name}"
    assert name in exports, f"runsight_core.isolation.__all__ must include {name}"
    return getattr(isolation, name)


async def _noop_execute(args: dict[str, Any]) -> dict[str, Any]:
    return {"args": args}


def _tool_parameters() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }


def _tool(name: str, execute: Callable[[dict[str, Any]], Any] = _noop_execute) -> ToolInstance:
    return ToolInstance(
        name=name,
        description="Fixture tool.",
        parameters=_tool_parameters(),
        execute=execute,
    )


class _ProviderNeutralTool:
    name = "lookup"
    description = "Fixture tool."
    parameters = _tool_parameters()

    def to_openai_schema(self) -> dict[str, Any]:
        raise AssertionError("Worker registry derivation must not call provider adapters")


def _assert_validation_rejects(factory: Callable[[], object]) -> None:
    with pytest.raises((ValueError, ValidationError)):
        factory()


def _json_payload(model: object) -> str:
    if hasattr(model, "model_dump_json"):
        return model.model_dump_json()
    return json.dumps(model, default=lambda value: getattr(value, "__dict__", str(value)))


def _iter_mapping_keys(value: object) -> set[str]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for child in value.values():
            keys.update(_iter_mapping_keys(child))
    elif isinstance(value, list | tuple):
        for child in value:
            keys.update(_iter_mapping_keys(child))
    return keys


def _context_envelope() -> ContextEnvelope:
    return ContextEnvelope(
        block_id="block",
        block_type="llm",
        block_config={},
        soul=SoulEnvelope(
            id="tester",
            role="Tester",
            system_prompt="Check contracts.",
            model_name="gpt-4o-mini",
            provider="openai",
            max_tool_iterations=1,
        ),
        tools=[],
        prompt=PromptEnvelope(id="prompt", instruction="Run.", context={}),
        inputs={},
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=30,
        max_output_bytes=4096,
    )


class TestWorkspaceManifestValidation:
    def test_manifest_rejects_absolute_materialization_paths_before_launch(self) -> None:
        WorkspaceManifest = _contract("WorkspaceManifest")
        WorkspaceMaterialization = _contract("WorkspaceMaterialization")

        _assert_validation_rejects(
            lambda: WorkspaceManifest(
                materializations=[
                    WorkspaceMaterialization(
                        path="/tmp/x",
                        content="payload",
                        mode=0o600,
                        overwrite=False,
                    )
                ],
                working_dir=".",
            )
        )

    @pytest.mark.parametrize(
        "path",
        [
            "",
            "../x",
            "safe/../escape.txt",
            "nested/\x00name",
            "C:/Users/alice/file.txt",
            "\\\\host\\share",
        ],
    )
    def test_manifest_rejects_non_workspace_relative_paths_before_launch(self, path: str) -> None:
        WorkspaceManifest = _contract("WorkspaceManifest")
        WorkspaceMaterialization = _contract("WorkspaceMaterialization")

        _assert_validation_rejects(
            lambda: WorkspaceManifest(
                materializations=[
                    WorkspaceMaterialization(
                        path=path,
                        content="payload",
                        mode=0o600,
                        overwrite=False,
                    )
                ],
                working_dir=".",
            )
        )

    def test_manifest_accepts_dot_working_directory_before_launch(self) -> None:
        WorkspaceManifest = _contract("WorkspaceManifest")

        manifest = WorkspaceManifest(materializations=[], working_dir=".")

        assert manifest.working_dir == "."

    @pytest.mark.parametrize(
        "working_dir",
        [
            "",
            "/tmp",
            "../work",
            "safe/../escape",
            "C:/work",
            "\\\\host\\share",
            "work/\x00dir",
        ],
    )
    def test_manifest_rejects_invalid_working_directories_before_launch(
        self,
        working_dir: str,
    ) -> None:
        WorkspaceManifest = _contract("WorkspaceManifest")

        _assert_validation_rejects(
            lambda: WorkspaceManifest(materializations=[], working_dir=working_dir)
        )

    @pytest.mark.parametrize("mode", [0o1600, 0o2600, 0o4600, 0o7600])
    def test_manifest_rejects_special_permission_bits_before_launch(self, mode: int) -> None:
        WorkspaceManifest = _contract("WorkspaceManifest")
        WorkspaceMaterialization = _contract("WorkspaceMaterialization")

        _assert_validation_rejects(
            lambda: WorkspaceManifest(
                materializations=[
                    WorkspaceMaterialization(
                        path="safe/file.txt",
                        content="payload",
                        mode=mode,
                        overwrite=False,
                    )
                ],
                working_dir=".",
            )
        )


class TestWorkspaceSessionFactory:
    def test_session_factory_creates_canonical_roots_for_empty_manifest(
        self, tmp_path: Path
    ) -> None:
        WorkspaceManifest = _contract("WorkspaceManifest")
        WorkspacePolicy = _contract("WorkspacePolicy")
        WorkspaceSessionFactory = _contract("WorkspaceSessionFactory")

        factory = WorkspaceSessionFactory(host_root=tmp_path / "host")
        session = factory.create(
            WorkspaceManifest(materializations=[], working_dir="."), WorkspacePolicy()
        )

        assert session.id
        assert session.host_root == (tmp_path / "host").resolve()
        assert session.runtime_root == session.host_root.resolve()
        assert session.runtime_workdir == session.runtime_root
        assert session.host_root.is_dir()
        assert session.runtime_workdir.is_dir()


class TestWorkspaceHarnessContract:
    def test_workspace_harness_exposes_async_run_protocol(self) -> None:
        WorkspaceHarness = _contract("WorkspaceHarness")
        WorkspaceRunRequest = _contract("WorkspaceRunRequest")
        annotations = get_type_hints(WorkspaceHarness.run)

        assert hasattr(WorkspaceHarness, "run")
        assert annotations["request"] is WorkspaceRunRequest
        assert annotations["return"] is ResultEnvelope


class TestPolicyCapabilityReport:
    def test_unix_local_policy_reports_advisory_raw_sandboxing_and_enforceable_mediation(
        self,
    ) -> None:
        PolicyCapabilityReport = _contract("PolicyCapabilityReport")
        WorkspacePolicy = _contract("WorkspacePolicy")

        policy = WorkspacePolicy(
            network={"raw": "deny", "mediated": "allow"},
            filesystem={"raw": "deny", "mediated": "workspace"},
            credentials={"mode": "host-bound"},
            max_materialization_bytes=4096,
        )

        report = PolicyCapabilityReport.from_policy(policy, backend="unix-local")

        assert report.backend == "unix-local"
        assert {"raw_network_restriction", "raw_filesystem_restriction"} <= set(report.advisory)
        assert {
            "credential_host_binding",
            "mediated_file_constraints",
            "materialization_size_limits",
        } <= set(report.enforced)


class TestIPCContractSerialization:
    def test_ipc_client_config_round_trips_without_losing_binding_details(self) -> None:
        IPCBinding = _contract("IPCBinding")
        IPCClientConfig = _contract("IPCClientConfig")
        IPCTransport = _contract("IPCTransport")

        config = IPCClientConfig(
            transport=IPCTransport.UNIX_SOCKET,
            binding=IPCBinding(path="ipc/worker.sock"),
            request_timeout_seconds=3.5,
            max_frame_bytes=65536,
        )

        restored = IPCClientConfig.model_validate_json(config.model_dump_json())

        assert restored.transport == IPCTransport.UNIX_SOCKET
        assert restored.binding.path == "ipc/worker.sock"
        assert restored.request_timeout_seconds == 3.5
        assert restored.max_frame_bytes == 65536

    @pytest.mark.parametrize("request_timeout_seconds", [float("nan"), float("inf"), float("-inf")])
    def test_ipc_client_config_rejects_non_finite_request_timeouts(
        self,
        request_timeout_seconds: float,
    ) -> None:
        IPCBinding = _contract("IPCBinding")
        IPCClientConfig = _contract("IPCClientConfig")
        IPCTransport = _contract("IPCTransport")

        _assert_validation_rejects(
            lambda: IPCClientConfig(
                transport=IPCTransport.UNIX_SOCKET,
                binding=IPCBinding(path="ipc/worker.sock"),
                request_timeout_seconds=request_timeout_seconds,
                max_frame_bytes=65536,
            )
        )


class TestHostAndWorkerToolRegistries:
    def test_host_tool_registry_rejects_duplicate_names_before_worker_launch(self) -> None:
        HostToolExecutionRef = _contract("HostToolExecutionRef")
        HostToolExecutionRegistry = _contract("HostToolExecutionRegistry")

        _assert_validation_rejects(
            lambda: HostToolExecutionRegistry(
                tools=[
                    HostToolExecutionRef(name="lookup", tool=_tool("lookup")),
                    HostToolExecutionRef(name="lookup", tool=_tool("lookup")),
                ]
            )
        )

    def test_worker_registry_derived_from_host_registry_contains_only_public_tool_metadata(
        self,
        tmp_path: Path,
    ) -> None:
        HostToolExecutionRef = _contract("HostToolExecutionRef")
        HostToolExecutionRegistry = _contract("HostToolExecutionRegistry")
        WorkerToolRegistry = _contract("WorkerToolRegistry")

        host_path = tmp_path / "host-only-token.txt"
        host_path.write_text("do-not-serialize", encoding="utf-8")
        registry = HostToolExecutionRegistry(
            tools=[
                HostToolExecutionRef(
                    name="lookup",
                    tool=_tool("lookup"),
                    credential_refs=["openai_api_key"],
                    headers={"Authorization": "Bearer secret-header"},
                    secret_config={"api_key": "sk-secret-value"},
                    host_path=host_path,
                    policy_metadata={"network": "mediated"},
                )
            ]
        )

        worker_registry = WorkerToolRegistry.from_host_registry(registry)
        serialized = _json_payload(worker_registry)
        keys = _iter_mapping_keys(worker_registry)

        assert worker_registry.tools[0].name == "lookup"
        assert worker_registry.tools[0].policy_metadata == {"network": "mediated"}
        assert "secret-header" not in serialized
        assert "sk-secret-value" not in serialized
        assert "openai_api_key" not in serialized
        assert str(host_path) not in serialized
        assert "execute" not in keys
        assert "headers" not in keys
        assert "credential_refs" not in keys
        assert "secret_config" not in keys
        assert "host_path" not in keys

        assert keys.isdisjoint({"function", "type"})
        assert worker_registry.model_dump(mode="json")["tools"][0] == {
            "name": "lookup",
            "description": "Fixture tool.",
            "parameters": _tool_parameters(),
            "policy_metadata": {"network": "mediated"},
        }

    def test_worker_registry_derivation_uses_provider_neutral_tool_metadata_without_provider_adapter(
        self,
    ) -> None:
        HostToolExecutionRef = _contract("HostToolExecutionRef")
        HostToolExecutionRegistry = _contract("HostToolExecutionRegistry")
        WorkerToolRegistry = _contract("WorkerToolRegistry")

        registry = HostToolExecutionRegistry(
            tools=[
                HostToolExecutionRef(
                    name="lookup",
                    tool=_ProviderNeutralTool(),
                    policy_metadata={"network": "mediated"},
                )
            ]
        )

        worker_registry = WorkerToolRegistry.from_host_registry(registry)

        assert worker_registry.model_dump(mode="json")["tools"][0] == {
            "name": "lookup",
            "description": "Fixture tool.",
            "parameters": _tool_parameters(),
            "policy_metadata": {"network": "mediated"},
        }

    def test_worker_registry_serializes_provider_neutral_parameters_without_function_wrappers(
        self,
    ) -> None:
        HostToolExecutionRef = _contract("HostToolExecutionRef")
        HostToolExecutionRegistry = _contract("HostToolExecutionRegistry")
        WorkerToolRegistry = _contract("WorkerToolRegistry")

        registry = HostToolExecutionRegistry(
            tools=[
                HostToolExecutionRef(
                    name="lookup",
                    tool=_tool("lookup"),
                    policy_metadata={"network": "mediated"},
                )
            ]
        )

        worker_registry = WorkerToolRegistry.from_host_registry(registry)
        payload = worker_registry.model_dump(mode="json")
        keys = _iter_mapping_keys(payload)

        assert keys.isdisjoint({"function", "type"})
        assert payload["tools"][0]["parameters"] == _tool_parameters()

    @pytest.mark.parametrize(
        "metadata_key",
        [
            "hostPath",
            "host path",
            "host-path",
            "local_path",
            "executable_path",
            "tool_ref",
            "command",
            "execute",
            "tool_instance",
            "api key",
            "private key",
            "credential refs",
            "http credentials",
            "url allowlist",
        ],
    )
    @pytest.mark.parametrize("contract_name", ["HostToolExecutionRef", "WorkerToolSchema"])
    def test_tool_policy_metadata_rejects_host_only_secret_and_tool_aliases_before_serialization(
        self,
        contract_name: str,
        metadata_key: str,
    ) -> None:
        contract = _contract(contract_name)
        policy_metadata = {metadata_key: "worker-visible"}

        if contract_name == "HostToolExecutionRef":
            _assert_validation_rejects(
                lambda: contract(
                    name="lookup",
                    tool=_tool("lookup"),
                    policy_metadata=policy_metadata,
                )
            )
            return

        _assert_validation_rejects(
            lambda: contract(
                name="lookup",
                description="Fixture tool.",
                parameters=_tool_parameters(),
                policy_metadata=policy_metadata,
            )
        )

    @pytest.mark.parametrize(
        "policy_metadata",
        [
            pytest.param(
                {"network": {"command": "worker-visible"}},
                id="nested-command",
            ),
            pytest.param(
                {"constraints": [{"host path": "/tmp/public-cache"}]},
                id="list-host-path",
            ),
            pytest.param(
                {"scope": {"credential refs": ["openai"]}},
                id="nested-credential-refs",
            ),
            pytest.param(
                {"layers": [[{"url allowlist": ["https://internal.test"]}]]},
                id="nested-list-url-allowlist",
            ),
        ],
    )
    @pytest.mark.parametrize("contract_name", ["HostToolExecutionRef", "WorkerToolSchema"])
    def test_tool_policy_metadata_rejects_nested_host_only_secret_and_tool_aliases_before_serialization(
        self,
        contract_name: str,
        policy_metadata: dict[str, Any],
    ) -> None:
        contract = _contract(contract_name)

        if contract_name == "HostToolExecutionRef":
            _assert_validation_rejects(
                lambda: contract(
                    name="lookup",
                    tool=_tool("lookup"),
                    policy_metadata=policy_metadata,
                )
            )
            return

        _assert_validation_rejects(
            lambda: contract(
                name="lookup",
                description="Fixture tool.",
                parameters=_tool_parameters(),
                policy_metadata=policy_metadata,
            )
        )

    def test_host_tool_registry_rejects_unsafe_policy_metadata_before_worker_derivation(
        self,
    ) -> None:
        HostToolExecutionRegistry = _contract("HostToolExecutionRegistry")

        _assert_validation_rejects(
            lambda: HostToolExecutionRegistry(
                tools=[
                    {
                        "name": "lookup",
                        "tool": _tool("lookup"),
                        "policy_metadata": {"command": "worker-visible"},
                    }
                ]
            )
        )

    @pytest.mark.parametrize(
        "policy_metadata",
        [
            pytest.param(
                {"network": {"command": "worker-visible"}},
                id="nested-command",
            ),
            pytest.param(
                {"constraints": [{"host path": "/tmp/public-cache"}]},
                id="list-host-path",
            ),
            pytest.param(
                {"scope": {"credential refs": ["openai"]}},
                id="nested-credential-refs",
            ),
        ],
    )
    def test_host_tool_registry_rejects_nested_unsafe_policy_metadata_before_worker_derivation(
        self,
        policy_metadata: dict[str, Any],
    ) -> None:
        HostToolExecutionRegistry = _contract("HostToolExecutionRegistry")

        _assert_validation_rejects(
            lambda: HostToolExecutionRegistry(
                tools=[
                    {
                        "name": "lookup",
                        "tool": _tool("lookup"),
                        "policy_metadata": policy_metadata,
                    }
                ]
            )
        )

    def test_workspace_host_bindings_are_excluded_from_worker_request_serialization(self) -> None:
        HostToolExecutionRegistry = _contract("HostToolExecutionRegistry")
        WorkspaceHostBindings = _contract("WorkspaceHostBindings")
        WorkspaceManifest = _contract("WorkspaceManifest")
        WorkspacePolicy = _contract("WorkspacePolicy")
        WorkspaceRunRequest = _contract("WorkspaceRunRequest")

        host_bindings = WorkspaceHostBindings(
            api_keys={"openai": "sk-host-only"},
            http_credentials={"internal": {"Authorization": "Bearer host-only"}},
            url_allowlist=["https://fixture.internal.test"],
            host_tools=HostToolExecutionRegistry(tools=[]),
        )
        request = WorkspaceRunRequest(
            envelope=_context_envelope(),
            manifest=WorkspaceManifest(materializations=[], working_dir="."),
            policy=WorkspacePolicy(),
            worker_tools=[],
            host_bindings=host_bindings,
        )

        serialized = _json_payload(request)

        assert "host_bindings" not in serialized
        assert "sk-host-only" not in serialized
        assert "Bearer host-only" not in serialized
        assert "fixture.internal.test" not in serialized
