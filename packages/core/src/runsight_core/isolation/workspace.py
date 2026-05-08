"""Workspace runtime contract models and filesystem materialization."""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import stat
import uuid
from collections.abc import Callable, Mapping
from enum import Enum
from math import isfinite
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

from runsight_core.isolation.envelope import ContextEnvelope, ResultEnvelope

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
        host_root = self.host_root.resolve()
        host_root.mkdir(parents=True, exist_ok=True)
        runtime_root = host_root
        return WorkspaceSession(
            id=uuid.uuid4().hex,
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

    def materialize(self, manifest: WorkspaceManifest) -> WorkspaceSession:
        self._validate_or_create_working_dir(manifest.working_dir)
        for materialization in manifest.materializations:
            self._write_materialization(materialization)
        self._validate_or_create_working_dir(manifest.working_dir)
        return self.session

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
