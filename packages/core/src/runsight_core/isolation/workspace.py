"""Workspace runtime contract models and filesystem materialization."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
import re
import shutil
import socket
import stat
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Mapping
from enum import Enum
from math import isfinite
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

from runsight_core.isolation.envelope import (
    ContextEnvelope,
    HeartbeatMessage,
    ResultEnvelope,
    ToolDefEnvelope,
)

_SPECIAL_PERMISSION_BITS = stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX
_RAW_POLICY_MODES = frozenset({"allow", "deny"})
_NETWORK_MEDIATED_MODES = frozenset({"allow", "deny"})
_FILESYSTEM_MEDIATED_MODES = frozenset({"workspace", "deny"})
_CREDENTIAL_MODES = frozenset({"host-bound", "none", "deny"})
_RESERVED_WORKER_METADATA_KEYS = frozenset(
    {
        "api_keys",
        "authorization",
        "callable",
        "command",
        "credential_refs",
        "execute",
        "executable_path",
        "headers",
        "host_path",
        "host_tools",
        "http_credentials",
        "local_path",
        "secret_config",
        "tool",
        "tool_instance",
        "tool_ref",
        "url_allowlist",
    }
)
_SECRET_KEY_FRAGMENTS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "access_token",
    }
)
_SECRET_VALUE_MARKERS = (
    "bearer ",
    "basic ",
    "sk-",
    "secret",
    "api_key",
    "authorization",
    "password",
    "-----begin ",
)
_CAMEL_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_METADATA_KEY_SEPARATOR = re.compile(r"[^0-9A-Za-z]+")
_COMPACT_RESERVED_WORKER_METADATA_KEYS = frozenset(
    key.replace("_", "") for key in _RESERVED_WORKER_METADATA_KEYS
)
_IPC_CONFIG_ENV = "RUNSIGHT_IPC_CONFIG_B64"


def _validate_workspace_relative_path(value: str, *, allow_dot: bool) -> str:
    if not value:
        raise ValueError("workspace path cannot be empty")
    if "\x00" in value:
        raise ValueError("workspace path cannot contain NUL bytes")
    if "\\" in value:
        raise ValueError("workspace path must use POSIX separators")
    if value.startswith("//"):
        raise ValueError("workspace path cannot be a UNC path")
    if len(value) >= 3 and value[1] == ":" and value[0].isalpha() and value[2] == "/":
        raise ValueError("workspace path cannot include a Windows drive")

    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValueError("workspace path must be relative")
    if value == ".":
        if allow_dot:
            return value
        raise ValueError("workspace path cannot be '.'")
    if any(part == ".." for part in path.parts):
        raise ValueError("workspace path cannot contain '..' components")
    return value


def _validate_mode_mapping(
    value: dict[str, Any],
    *,
    owner: str,
    allowed_keys: set[str],
    allowed_modes: dict[str, frozenset[str]],
) -> dict[str, Any]:
    for key, mode in value.items():
        if key not in allowed_keys:
            raise ValueError(f"{owner} policy contains unknown key: {key}")
        if not isinstance(mode, str):
            raise ValueError(f"{owner}.{key} policy mode must be a string")
        if mode not in allowed_modes[key]:
            raise ValueError(f"{owner}.{key} policy mode is invalid: {mode}")
    return value


def _normalized_metadata_key(key: str) -> str:
    camel_split = _CAMEL_CASE_BOUNDARY.sub("_", key.strip())
    separated = _METADATA_KEY_SEPARATOR.sub("_", camel_split)
    return "_".join(part for part in separated.lower().split("_") if part)


def _validate_worker_policy_metadata_key(key: str) -> str:
    if not key:
        raise ValueError("worker policy metadata keys cannot be empty")
    normalized = _normalized_metadata_key(key)
    compact_normalized = normalized.replace("_", "")
    if (
        normalized in _RESERVED_WORKER_METADATA_KEYS
        or compact_normalized in _COMPACT_RESERVED_WORKER_METADATA_KEYS
    ):
        raise ValueError(f"worker policy metadata key is host-only: {key}")
    if any(
        fragment in normalized or fragment.replace("_", "") in compact_normalized
        for fragment in _SECRET_KEY_FRAGMENTS
    ):
        raise ValueError(f"worker policy metadata key is secret-like: {key}")
    return key


def _validate_worker_policy_metadata_string(value: str) -> str:
    lowered = value.strip().lower()
    if any(marker in lowered for marker in _SECRET_VALUE_MARKERS):
        raise ValueError("worker policy metadata value is secret-like")
    return value


def _sanitize_worker_policy_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("worker policy metadata keys must be strings")
            sanitized[_validate_worker_policy_metadata_key(key)] = _sanitize_worker_policy_metadata(
                child
            )
        return sanitized
    if isinstance(value, list | tuple):
        return [_sanitize_worker_policy_metadata(child) for child in value]
    if isinstance(value, str):
        return _validate_worker_policy_metadata_string(value)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("worker policy metadata numbers must be finite")
        return value
    raise ValueError("worker policy metadata must be JSON-serializable policy data")


def _sanitize_worker_policy_metadata_mapping(value: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_worker_policy_metadata(value)
    if not isinstance(sanitized, dict):
        raise ValueError("worker policy metadata must be a mapping")
    return sanitized


class WorkspaceMaterialization(BaseModel):
    """A file to create in a workspace before worker launch."""

    model_config = ConfigDict(extra="forbid")

    path: str
    content: str
    mode: int = 0o600
    overwrite: bool = False

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _validate_workspace_relative_path(value, allow_dot=False)

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, value: int) -> int:
        if value & _SPECIAL_PERMISSION_BITS:
            raise ValueError("workspace materialization mode cannot set special permission bits")
        return value


class WorkspaceManifest(BaseModel):
    """Pure data contract for workspace materialization requests."""

    model_config = ConfigDict(extra="forbid")

    materializations: list[WorkspaceMaterialization] = Field(default_factory=list)
    working_dir: str = "."

    @field_validator("working_dir")
    @classmethod
    def _validate_working_dir(cls, value: str) -> str:
        return _validate_workspace_relative_path(value, allow_dot=True)


class WorkspacePolicy(BaseModel):
    """Policy requested for workspace runtime execution."""

    model_config = ConfigDict(extra="forbid")

    network: dict[str, Any] = Field(default_factory=dict)
    filesystem: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)
    max_materialization_bytes: int | None = None

    @field_validator("network")
    @classmethod
    def _validate_network(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_mode_mapping(
            value,
            owner="network",
            allowed_keys={"raw", "mediated"},
            allowed_modes={
                "raw": _RAW_POLICY_MODES,
                "mediated": _NETWORK_MEDIATED_MODES,
            },
        )

    @field_validator("filesystem")
    @classmethod
    def _validate_filesystem(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_mode_mapping(
            value,
            owner="filesystem",
            allowed_keys={"raw", "mediated"},
            allowed_modes={
                "raw": _RAW_POLICY_MODES,
                "mediated": _FILESYSTEM_MEDIATED_MODES,
            },
        )

    @field_validator("credentials")
    @classmethod
    def _validate_credentials(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_mode_mapping(
            value,
            owner="credentials",
            allowed_keys={"mode"},
            allowed_modes={"mode": _CREDENTIAL_MODES},
        )

    @field_validator("max_materialization_bytes")
    @classmethod
    def _validate_max_materialization_bytes(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("max_materialization_bytes must be positive")
        return value

    def raw_network_mode(self) -> str | None:
        value = self.network.get("raw")
        return value if isinstance(value, str) else None

    def raw_filesystem_mode(self) -> str | None:
        value = self.filesystem.get("raw")
        return value if isinstance(value, str) else None

    def credential_mode(self) -> str | None:
        value = self.credentials.get("mode")
        return value if isinstance(value, str) else None


class PolicyCapabilityReport(BaseModel):
    """Backend capability report for advisory and enforced policy controls."""

    model_config = ConfigDict(extra="forbid")

    backend: str
    advisory: list[str] = Field(default_factory=list)
    enforced: list[str] = Field(default_factory=list)

    @classmethod
    def from_policy(
        cls,
        policy: WorkspacePolicy,
        *,
        backend: str,
    ) -> "PolicyCapabilityReport":
        advisory: list[str] = []
        enforced: list[str] = []

        if policy.raw_network_mode() == "deny":
            advisory.append("raw_network_restriction")
        if policy.raw_filesystem_mode() == "deny":
            advisory.append("raw_filesystem_restriction")
        if policy.credential_mode() in {"host-bound", "deny"}:
            enforced.append("credential_host_binding")
        if policy.filesystem.get("mediated") in {"workspace", "deny"}:
            enforced.append("mediated_file_constraints")
        if policy.max_materialization_bytes is not None:
            enforced.append("materialization_size_limits")

        return cls(backend=backend, advisory=advisory, enforced=enforced)


class WorkspaceSession(BaseModel):
    """Concrete host/runtime roots for one workspace run."""

    model_config = ConfigDict(extra="forbid")

    id: str
    host_root: Path
    runtime_root: Path
    runtime_workdir: Path
    cleanup: bool = True


class WorkspaceSessionFactory:
    """Creates canonical workspace sessions for a manifest and policy."""

    def __init__(self, *, host_root: Path) -> None:
        self.host_root = Path(host_root)

    def create(self, manifest: WorkspaceManifest, policy: WorkspacePolicy) -> WorkspaceSession:
        del manifest, policy
        base_root = self.host_root.resolve()
        base_root.mkdir(parents=True, exist_ok=True)
        session_id = uuid.uuid4().hex
        host_root = base_root / session_id
        host_root.mkdir(mode=0o700)
        runtime_root = host_root
        return WorkspaceSession(
            id=session_id,
            host_root=host_root,
            runtime_root=runtime_root,
            runtime_workdir=runtime_root,
            cleanup=True,
        )


def _relative_parts(path: str) -> tuple[str, ...]:
    return tuple(part for part in PurePosixPath(path).parts if part != ".")


def _reject_existing_symlink_components(root: Path, relative_path: str) -> None:
    current = root
    for part in _relative_parts(relative_path):
        current = current / part
        if current.is_symlink():
            raise PermissionError(f"workspace path component is a symlink: {current}")


def _resolve_under(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    _reject_existing_symlink_components(root, relative_path)
    target = root.joinpath(*_relative_parts(relative_path)).resolve(strict=False)
    if not target.is_relative_to(root):
        raise ValueError("workspace path resolves outside the workspace root")
    return target


def _ensure_parent_directory(root: Path, target: Path) -> None:
    parent = target.parent
    if parent == root:
        return

    current = root
    for part in target.relative_to(root).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise PermissionError(f"workspace path component is a symlink: {current}")
        if current.exists():
            if not current.is_dir():
                raise ValueError(f"workspace parent path is not a directory: {current}")
            continue
        current.mkdir()


class WorkspaceMaterializer:
    """Materializes workspace files under a session host root."""

    def __init__(self, session: WorkspaceSession) -> None:
        self.session = session

    def materialize(
        self,
        manifest: WorkspaceManifest,
        *,
        policy: WorkspacePolicy | None = None,
    ) -> WorkspaceSession:
        self._validate_materialization_size(manifest, policy)
        self._validate_or_create_working_dir(manifest.working_dir)
        for materialization in manifest.materializations:
            self._write_materialization(materialization)
        self._validate_or_create_working_dir(manifest.working_dir)
        return self.session

    def _validate_materialization_size(
        self,
        manifest: WorkspaceManifest,
        policy: WorkspacePolicy | None,
    ) -> None:
        if policy is None or policy.max_materialization_bytes is None:
            return
        total_bytes = sum(
            len(materialization.content.encode("utf-8"))
            for materialization in manifest.materializations
        )
        if total_bytes > policy.max_materialization_bytes:
            raise ValueError(
                "workspace materializations exceed max_materialization_bytes="
                f"{policy.max_materialization_bytes}"
            )

    def _validate_or_create_working_dir(self, working_dir: str) -> None:
        target = _resolve_under(self.session.runtime_root, working_dir)
        if target.is_symlink():
            raise PermissionError(f"workspace working directory is a symlink: {target}")
        if target.exists() and not target.is_dir():
            raise ValueError(f"workspace working directory is not a directory: {target}")
        target.mkdir(parents=True, exist_ok=True)
        self.session.runtime_workdir = target

    def _write_materialization(self, materialization: WorkspaceMaterialization) -> None:
        target = _resolve_under(self.session.host_root, materialization.path)
        _ensure_parent_directory(self.session.host_root.resolve(), target)

        if target.exists() or target.is_symlink():
            mode = target.lstat().st_mode
            if not materialization.overwrite:
                raise FileExistsError(f"workspace target already exists: {target}")
            if target.is_symlink() or not stat.S_ISREG(mode):
                raise PermissionError(f"workspace target is not a regular file: {target}")

        target.write_text(materialization.content, encoding="utf-8")
        target.chmod(materialization.mode)


class WorkspaceHostBindings(BaseModel):
    """Host-only bindings that must not be serialized into worker requests."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    api_keys: dict[str, str] = Field(default_factory=dict)
    http_credentials: dict[str, dict[str, str]] = Field(default_factory=dict)
    url_allowlist: list[str] = Field(default_factory=list)
    host_tools: "HostToolExecutionRegistry" = Field(
        default_factory=lambda: HostToolExecutionRegistry(tools=[])
    )


class WorkerToolSchema(BaseModel):
    """Serializable worker-visible tool metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    parameters: dict[str, Any]
    policy_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("policy_metadata")
    @classmethod
    def _validate_policy_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _sanitize_worker_policy_metadata_mapping(value)


class HostToolExecutionRef(BaseModel):
    """Host-owned executable tool reference."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    name: str
    tool: Any
    credential_refs: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    secret_config: dict[str, Any] = Field(default_factory=dict)
    host_path: Path | None = None
    policy_metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = Field(default=None, exclude=True)
    tool_type: str | None = Field(default=None, exclude=True)
    config: dict[str, Any] = Field(default_factory=dict, exclude=True)
    request_config: dict[str, Any] | None = Field(default=None, exclude=True)
    timeout_seconds: int | None = Field(default=None, exclude=True)
    max_output_bytes: int | None = Field(default=None, exclude=True)
    response_size_policy: Any | None = Field(default=None, exclude=True)
    mediation: str | None = Field(default=None, exclude=True)
    mediated_handler: Any | None = Field(default=None, exclude=True)

    @field_validator("policy_metadata")
    @classmethod
    def _validate_policy_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _sanitize_worker_policy_metadata_mapping(value)


class HostToolExecutionRegistry(BaseModel):
    """Registry of executable host tool references keyed by unique name."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    tools: list[HostToolExecutionRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_names(self) -> "HostToolExecutionRegistry":
        names = [tool.name for tool in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("host tool execution registry cannot contain duplicate names")
        return self


class WorkerToolRegistry(BaseModel):
    """Worker-visible registry derived from host executable tools."""

    model_config = ConfigDict(extra="forbid")

    tools: list[WorkerToolSchema] = Field(default_factory=list)

    @classmethod
    def from_host_registry(cls, registry: HostToolExecutionRegistry) -> "WorkerToolRegistry":
        return cls(
            tools=[
                WorkerToolSchema(
                    name=ref.name,
                    description=ref.tool.description,
                    parameters=dict(ref.tool.parameters),
                    policy_metadata=dict(ref.policy_metadata),
                )
                for ref in registry.tools
            ]
        )


class WorkspaceRunRequest(BaseModel):
    """Worker run request with host-only bindings excluded from serialization."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    envelope: ContextEnvelope
    manifest: WorkspaceManifest
    policy: WorkspacePolicy
    worker_tools: list[WorkerToolSchema] = Field(default_factory=list)
    host_bindings: WorkspaceHostBindings | None = Field(default=None, exclude=True)


class WorkspaceHarness(Protocol):
    """Protocol for workspace-aware execution harnesses."""

    async def run(self, request: WorkspaceRunRequest) -> ResultEnvelope:
        """Run one workspace request and return the isolated result."""


class IPCTransport(str, Enum):
    """Supported worker IPC transports."""

    UNIX_SOCKET = "unix_socket"
    TCP = "tcp"
    STDIO = "stdio"


class UnixSocketEndpoint(BaseModel):
    """Unix socket endpoint details."""

    model_config = ConfigDict(extra="forbid")

    path: str

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if not value:
            raise ValueError("IPC endpoint path cannot be empty")
        if not value.strip():
            raise ValueError("IPC endpoint path cannot be blank")
        return value


class TCPClientEndpoint(BaseModel):
    """TCP endpoint details for future IPC transports."""

    model_config = ConfigDict(extra="forbid")

    host: str
    port: int

    @field_validator("host")
    @classmethod
    def _validate_host(cls, value: str) -> str:
        if not value:
            raise ValueError("tcp host cannot be empty")
        if not value.strip():
            raise ValueError("tcp host cannot be blank")
        return value

    @field_validator("port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if value <= 0 or value > 65535:
            raise ValueError("tcp port must be between 1 and 65535")
        return value


class StdioClientEndpoint(BaseModel):
    """Stdio endpoint details for future IPC transports."""

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["jsonl"]


class IPCClientConfig(BaseModel):
    """Serializable IPC client configuration."""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    transport: IPCTransport
    grant_token: str
    heartbeat_interval_ms: int = 1000
    unix_socket: UnixSocketEndpoint | None = None
    tcp: TCPClientEndpoint | None = None
    stdio: StdioClientEndpoint | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_flat_endpoint_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)

        unix_socket_path = normalized.pop("unix_socket_path", None)
        if unix_socket_path is not None:
            if "unix_socket" in normalized and normalized["unix_socket"] != {
                "path": unix_socket_path
            }:
                raise ValueError("unix_socket and unix_socket_path must describe the same endpoint")
            normalized.setdefault("unix_socket", {"path": unix_socket_path})

        tcp_host = normalized.pop("tcp_host", None)
        tcp_port = normalized.pop("tcp_port", None)
        if tcp_host is not None or tcp_port is not None:
            tcp_endpoint = {
                key: value
                for key, value in {"host": tcp_host, "port": tcp_port}.items()
                if value is not None
            }
            if "tcp" in normalized and normalized["tcp"] != tcp_endpoint:
                raise ValueError("tcp and tcp_host/tcp_port must describe the same endpoint")
            normalized.setdefault("tcp", tcp_endpoint)

        stdio_protocol = normalized.pop("stdio_protocol", None)
        if stdio_protocol is not None:
            if "stdio" in normalized and normalized["stdio"] != {"protocol": stdio_protocol}:
                raise ValueError("stdio and stdio_protocol must describe the same endpoint")
            normalized.setdefault("stdio", {"protocol": stdio_protocol})

        return normalized

    @field_validator("grant_token")
    @classmethod
    def _validate_grant_token(cls, value: str) -> str:
        if not value:
            raise ValueError("grant_token cannot be empty")
        if not value.strip():
            raise ValueError("grant_token cannot be blank")
        return value

    @field_validator("heartbeat_interval_ms")
    @classmethod
    def _validate_heartbeat_interval_ms(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("heartbeat_interval_ms must be positive")
        return value

    @model_validator(mode="after")
    def _validate_transport_config(self) -> "IPCClientConfig":
        required_endpoint = {
            IPCTransport.UNIX_SOCKET: self.unix_socket,
            IPCTransport.TCP: self.tcp,
            IPCTransport.STDIO: self.stdio,
        }[self.transport]
        if required_endpoint is None:
            raise ValueError(f"{self.transport.value} transport requires endpoint config")

        configured = [
            self.unix_socket is not None,
            self.tcp is not None,
            self.stdio is not None,
        ]
        if sum(configured) != 1:
            raise ValueError("IPC client config must include exactly one transport endpoint")
        return self

    @property
    def unix_socket_path(self) -> str | None:
        return self.unix_socket.path if self.unix_socket is not None else None

    @property
    def tcp_host(self) -> str | None:
        return self.tcp.host if self.tcp is not None else None

    @property
    def tcp_port(self) -> int | None:
        return self.tcp.port if self.tcp is not None else None

    @property
    def stdio_protocol(self) -> Literal["jsonl"] | None:
        return self.stdio.protocol if self.stdio is not None else None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "IPCClientConfig":
        source = os.environ if env is None else env
        encoded = source.get(_IPC_CONFIG_ENV)
        if not encoded:
            raise ValueError(f"Missing required environment variable: {_IPC_CONFIG_ENV}")

        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"{_IPC_CONFIG_ENV} must be valid base64") from exc

        try:
            payload = json.loads(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ValueError(f"{_IPC_CONFIG_ENV} must decode to utf-8 json") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"{_IPC_CONFIG_ENV} must decode to json") from exc

        return cls.model_validate(payload)

    def to_env(self) -> dict[str, str]:
        raw = self.model_dump_json(exclude_none=True).encode("utf-8")
        return {_IPC_CONFIG_ENV: base64.b64encode(raw).decode("ascii")}


class IPCBinding(BaseModel):
    """Prepared IPC binding for launching a worker."""

    model_config = ConfigDict(extra="forbid")

    client_config: IPCClientConfig
    server_endpoint: UnixSocketEndpoint
    env: dict[str, str]
    cleanup_required: bool = True
    _close_callback: Callable[[], None] | None = PrivateAttr(default=None)

    def close(self) -> None:
        if self._close_callback is not None:
            self._close_callback()
            return
        if self.cleanup_required:
            Path(self.server_endpoint.path).unlink(missing_ok=True)


class UnixSocketIPCTransport:
    """Prepare Unix socket IPC bindings while exposing a transport-neutral worker config."""

    def __init__(self, *, socket_dir: Path | str | None = None) -> None:
        self._socket_dir = Path(socket_dir) if socket_dir is not None else None

    def prepare(self, session: WorkspaceSession, policy: WorkspacePolicy) -> IPCBinding:
        del policy
        socket_dir = self._socket_dir or (session.host_root / "ipc")
        socket_dir.mkdir(parents=True, exist_ok=True)
        socket_path = socket_dir / f"rs-{session.id}-{uuid.uuid4().hex[:12]}.sock"
        endpoint = UnixSocketEndpoint(path=str(socket_path))
        client_config = IPCClientConfig(
            version=1,
            transport=IPCTransport.UNIX_SOCKET,
            grant_token=uuid.uuid4().hex,
            heartbeat_interval_ms=1000,
            unix_socket=endpoint,
        )
        binding = IPCBinding(
            client_config=client_config,
            server_endpoint=endpoint,
            env=client_config.to_env(),
            cleanup_required=True,
        )

        def _close() -> None:
            socket_path.unlink(missing_ok=True)

        binding._close_callback = _close
        return binding


class WorkerLaunchSpec(BaseModel):
    """Serializable launch contract for a worker process."""

    model_config = ConfigDict(extra="forbid")

    argv: list[str]
    cwd: Path
    env: dict[str, str] = Field(default_factory=dict)
    ipc: IPCClientConfig | None = None


class WorkerProcessHandle(Protocol):
    """Protocol for launched worker process handles."""

    @property
    def pid(self) -> int:
        """Return the operating system process id."""

    async def wait(self) -> int:
        """Wait for process exit and return the status code."""

    async def terminate(self) -> None:
        """Request process termination."""


class WorkerLauncher(Protocol):
    """Protocol for worker process launchers."""

    async def launch(self, spec: WorkerLaunchSpec) -> WorkerProcessHandle:
        """Launch a worker process."""


_SIGTERM_GRACE_SECONDS = 5


class _WorkspaceHeartbeatTracker:
    def __init__(
        self,
        *,
        phase_timeout: float,
        stall_thresholds: dict[str, int | float] | None,
    ) -> None:
        self._phase_timeout = phase_timeout
        self._stall_thresholds = stall_thresholds or {}
        self._current_phase = ""
        self._phase_started_at = time.monotonic()

    def update(self, heartbeat: HeartbeatMessage) -> None:
        if heartbeat.phase != self._current_phase:
            self._current_phase = heartbeat.phase
            self._phase_started_at = time.monotonic()

    @property
    def is_stalled(self) -> bool:
        threshold = self._stall_thresholds.get(self._current_phase, self._phase_timeout)
        return (time.monotonic() - self._phase_started_at) > threshold


class _UnixWorkerProcessHandle:
    def __init__(self, process: Any) -> None:
        self._process = process

    @property
    def pid(self) -> int:
        return int(self._process.pid)

    @property
    def returncode(self) -> int | None:
        return self._process.returncode

    @property
    def stdin(self) -> Any:
        return self._process.stdin

    @property
    def stdout(self) -> Any:
        return self._process.stdout

    @property
    def stderr(self) -> Any:
        return self._process.stderr

    async def wait(self) -> int:
        return int(await self._process.wait())

    async def terminate(self) -> None:
        result = self._process.terminate()
        if hasattr(result, "__await__"):
            await result

    async def kill(self) -> None:
        kill = getattr(self._process, "kill", None)
        if kill is None:
            return
        result = kill()
        if hasattr(result, "__await__"):
            await result


class UnixWorkerLauncher:
    """Launches workspace workers from a transport-neutral launch spec."""

    async def launch(self, spec: WorkerLaunchSpec) -> WorkerProcessHandle:
        process = await asyncio.create_subprocess_exec(
            *spec.argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=spec.cwd,
            env=spec.env,
        )
        return _UnixWorkerProcessHandle(process)


class UnixLocalHarness:
    """Workspace-aware local Unix backend for process-isolated worker execution."""

    def __init__(
        self,
        *,
        session_factory: WorkspaceSessionFactory | None = None,
        ipc_transport: UnixSocketIPCTransport | None = None,
        worker_launcher: WorkerLauncher | None = None,
        cleanup: str = "always",
        timeout_seconds: int = 300,
        heartbeat_timeout: float = 30.0,
        phase_timeout: float = 60.0,
        stall_thresholds: dict[str, int | float] | None = None,
    ) -> None:
        self._owned_session_base_root: Path | None = None
        if session_factory is None:
            self._owned_session_base_root = Path(tempfile.mkdtemp(prefix="rs-workspace-")).resolve()
            self._session_factory = WorkspaceSessionFactory(host_root=self._owned_session_base_root)
        else:
            self._session_factory = session_factory
        self._ipc_transport = ipc_transport or UnixSocketIPCTransport()
        self._worker_launcher = worker_launcher or UnixWorkerLauncher()
        self._cleanup_mode = cleanup
        self._timeout_seconds = timeout_seconds
        self._heartbeat_timeout = heartbeat_timeout
        self._phase_timeout = phase_timeout
        self._stall_thresholds = stall_thresholds or {}

    @classmethod
    def capability_report(cls, policy: WorkspacePolicy) -> PolicyCapabilityReport:
        return PolicyCapabilityReport.from_policy(policy, backend="unix-local")

    def _build_ipc_handlers(
        self,
        *,
        request: WorkspaceRunRequest,
        session: WorkspaceSession,
    ) -> dict[str, Any]:
        from runsight_core.isolation import handlers as handlers_module

        host_bindings = request.host_bindings or WorkspaceHostBindings()
        http_handler = handlers_module.make_http_handler(
            credentials=dict(host_bindings.http_credentials),
            url_allowlist=list(host_bindings.url_allowlist),
        )
        file_io_handler = handlers_module.make_file_io_handler(base_dir=str(session.host_root))
        host_tools = self._bind_mediated_host_tools(
            host_bindings.host_tools,
            file_io_handler=file_io_handler,
            http_handler=http_handler,
        )
        return {
            "llm_call": handlers_module.make_llm_call_handler(
                api_keys=dict(host_bindings.api_keys)
            ),
            "http": http_handler,
            "file_io": file_io_handler,
            "tool_call": handlers_module.make_tool_call_handler(
                host_tools=host_tools,
                worker_tools=list(request.worker_tools),
            ),
        }

    def _bind_mediated_host_tools(
        self,
        registry: HostToolExecutionRegistry,
        *,
        file_io_handler: Any,
        http_handler: Any,
    ) -> HostToolExecutionRegistry:
        refs: list[HostToolExecutionRef] = []
        for ref in registry.tools:
            mediation = self._mediation_for_host_tool(ref)
            if mediation == "file_io":
                refs.append(
                    ref.model_copy(
                        update={"mediation": mediation, "mediated_handler": file_io_handler}
                    )
                )
                continue
            if mediation == "http":
                refs.append(
                    ref.model_copy(
                        update={"mediation": mediation, "mediated_handler": http_handler}
                    )
                )
                continue
            refs.append(ref)
        return HostToolExecutionRegistry(tools=refs)

    def _mediation_for_host_tool(self, ref: HostToolExecutionRef) -> str | None:
        if ref.name == "file_io":
            return "file_io"
        if ref.name == "http_request":
            return "http"
        if ref.request_config is not None:
            return "http"
        return None

    def _worker_envelope(self, request: WorkspaceRunRequest) -> ContextEnvelope:
        if not request.worker_tools:
            return request.envelope

        tools = [
            ToolDefEnvelope(
                source="host",
                config={"policy_metadata": dict(tool.policy_metadata)},
                exits=[],
                name=tool.name,
                description=tool.description,
                parameters=dict(tool.parameters),
                tool_type="host",
            )
            for tool in request.worker_tools
        ]
        return request.envelope.model_copy(update={"tools": tools})

    def _create_server_socket(self, endpoint: UnixSocketEndpoint) -> socket.socket:
        socket_path = Path(endpoint.path)
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.unlink(missing_ok=True)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        sock.listen(1)
        return sock

    async def _monitor_heartbeats(self, process: Any) -> str | None:
        tracker = _WorkspaceHeartbeatTracker(
            phase_timeout=self._phase_timeout,
            stall_thresholds=self._stall_thresholds,
        )

        while getattr(process, "returncode", None) is None:
            try:
                line = await asyncio.wait_for(
                    process.stderr.readline(),
                    timeout=self._heartbeat_timeout,
                )
            except asyncio.TimeoutError:
                await self._terminate_process(process)
                return "heartbeat stalled"

            if not line:
                return None

            try:
                tracker.update(HeartbeatMessage.model_validate_json(line.strip()))
            except Exception:
                continue

            if tracker.is_stalled:
                await self._terminate_process(process)
                return "worker phase stalled"

        return None

    async def _terminate_process(self, process: Any) -> None:
        terminate = getattr(process, "terminate", None)
        if terminate is None:
            return
        result = terminate()
        if hasattr(result, "__await__"):
            await result

    async def _kill_process(self, process: Any) -> None:
        await self._terminate_process(process)
        if getattr(process, "returncode", None) is not None:
            return

        try:
            await asyncio.wait_for(process.wait(), timeout=_SIGTERM_GRACE_SECONDS)
        except asyncio.TimeoutError:
            kill = getattr(process, "kill", None)
            if kill is None:
                return
            result = kill()
            if hasattr(result, "__await__"):
                await result

    def _validate_result(self, raw_json: str | bytes, *, max_bytes: int) -> ResultEnvelope:
        raw_bytes = raw_json.encode("utf-8") if isinstance(raw_json, str) else raw_json
        if len(raw_bytes) > max_bytes:
            raise ValueError(
                f"Result size {len(raw_bytes)} bytes exceeds maximum of {max_bytes} bytes"
            )
        return ResultEnvelope.model_validate_json(raw_bytes)

    def _map_return_code(self, code: int) -> str | None:
        if code == 0:
            return None

        signal_names: dict[int, str] = {
            -9: "Process killed by SIGKILL (signal 9) - possible OOM",
            -11: "Process killed by SIGSEGV (signal 11) - segfault",
            -15: "Process terminated by SIGTERM (signal 15)",
            -6: "Process aborted by SIGABRT (signal 6)",
            -2: "Process interrupted by SIGINT (signal 2)",
        }
        if code in signal_names:
            return signal_names[code]
        if code < 0:
            return f"Process killed by signal {-code}"
        return f"Process exit error (code {code})"

    def _error_result(
        self,
        *,
        envelope: ContextEnvelope,
        error: str,
        error_type: str,
    ) -> ResultEnvelope:
        return ResultEnvelope(
            block_id=envelope.block_id,
            output=None,
            exit_handle="error",
            cost_usd=0.0,
            total_tokens=0,
            tool_calls_made=0,
            delegate_artifacts={},
            conversation_history=[],
            error=error,
            error_type=error_type,
        )

    def _should_cleanup(self, *, succeeded: bool) -> bool:
        return self._cleanup_mode == "always" or (self._cleanup_mode == "on_success" and succeeded)

    def _cleanup_owned_session_base_root(self) -> None:
        if self._owned_session_base_root is None:
            return
        try:
            self._owned_session_base_root.rmdir()
        except FileNotFoundError:
            return
        except OSError:
            return

    async def run(self, request: WorkspaceRunRequest) -> ResultEnvelope:
        from runsight_core.budget_enforcement import BudgetSession, _active_budget
        from runsight_core.isolation.interceptors import (
            BudgetInterceptor,
            InterceptorRegistry,
            ObserverInterceptor,
        )
        from runsight_core.isolation.ipc import IPCServer
        from runsight_core.isolation.ipc_models import GrantToken
        from runsight_core.yaml.schema import BlockLimitsDef

        session = self._session_factory.create(request.manifest, request.policy)
        binding: IPCBinding | None = None
        server_socket: socket.socket | None = None
        ipc_server: Any | None = None
        ipc_task: asyncio.Task[None] | None = None
        succeeded = False

        try:
            session = WorkspaceMaterializer(session).materialize(
                request.manifest,
                policy=request.policy,
            )
            binding = self._ipc_transport.prepare(session, request.policy)
            server_socket = self._create_server_socket(binding.server_endpoint)

            envelope = self._worker_envelope(request)
            ipc_handlers = self._build_ipc_handlers(request=request, session=session)
            registry = InterceptorRegistry()
            registry.register(ObserverInterceptor(block_id=envelope.block_id))

            active_budget = _active_budget.get(None)
            if isinstance(active_budget, BudgetSession):
                raw_limits = envelope.block_config.get("limits")
                budget_session = active_budget
                if raw_limits is not None:
                    block_limits = (
                        raw_limits
                        if isinstance(raw_limits, BlockLimitsDef)
                        else BlockLimitsDef.model_validate(raw_limits)
                    )
                    budget_session = BudgetSession.from_block_limits(
                        block_limits,
                        envelope.block_id,
                        parent=active_budget,
                    )
                registry.register(
                    BudgetInterceptor(session=budget_session, block_id=envelope.block_id)
                )

            ipc_server = IPCServer(
                sock=server_socket,
                handlers=ipc_handlers,
                registry=registry,
                grant_token=GrantToken(
                    block_id=envelope.block_id,
                    token=binding.client_config.grant_token,
                ),
            )
            ipc_task = asyncio.create_task(ipc_server.serve())

            spec = WorkerLaunchSpec(
                argv=[sys.executable, "-m", "runsight_core.isolation.worker"],
                cwd=session.runtime_workdir,
                env=dict(binding.env),
                ipc=binding.client_config,
            )
            process = await self._worker_launcher.launch(spec)

            envelope_json = envelope.model_dump_json()
            if process.stdin is not None:
                process.stdin.write(envelope_json.encode())
                process.stdin.write(b"\n")
                await process.stdin.drain()
                process.stdin.close()

            monitor_task = asyncio.create_task(self._monitor_heartbeats(process))
            monitor_error: str | None = None
            timeout = envelope.timeout_seconds or self._timeout_seconds
            try:
                stdout_data = await asyncio.wait_for(process.stdout.read(), timeout=timeout)
            except (asyncio.TimeoutError, TimeoutError):
                await self._kill_process(process)
                raise TimeoutError(f"Subprocess timed out after {timeout} seconds")
            finally:
                if monitor_task.done():
                    monitor_error = monitor_task.result()
                else:
                    monitor_task.cancel()
                    try:
                        await monitor_task
                    except asyncio.CancelledError:
                        pass

            return_code = await process.wait()
            if monitor_error is not None:
                succeeded = True
                return self._error_result(
                    envelope=envelope,
                    error=monitor_error,
                    error_type="BlockStallError",
                )

            raw_output = stdout_data.decode("utf-8").strip()
            if return_code != 0:
                if raw_output:
                    try:
                        result = self._validate_result(
                            raw_output,
                            max_bytes=envelope.max_output_bytes,
                        )
                        succeeded = True
                        return result
                    except Exception:
                        pass
                error_msg = self._map_return_code(return_code)
                succeeded = True
                return self._error_result(
                    envelope=envelope,
                    error=error_msg or f"Process exit error (code {return_code})",
                    error_type="SubprocessError",
                )

            result = self._validate_result(raw_output, max_bytes=envelope.max_output_bytes)
            succeeded = True
            return result
        finally:
            if ipc_server is not None:
                await ipc_server.shutdown()
            if ipc_task is not None:
                ipc_task.cancel()
                try:
                    await ipc_task
                except asyncio.CancelledError:
                    pass
            if server_socket is not None:
                server_socket.close()
            if binding is not None:
                binding.close()
            if self._should_cleanup(succeeded=succeeded) and session.cleanup:
                shutil.rmtree(session.host_root, ignore_errors=True)
                self._cleanup_owned_session_base_root()
