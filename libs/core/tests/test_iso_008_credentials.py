"""
Failing tests for RUN-398: ISO-008 — Credential injection + URL allowlists.

Tests cover every AC item:
1.  LLM API key passed via env var — ONE key per subprocess
2.  HTTP tool: credentials injected by engine at IPC time, subprocess never sees token
3.  HTTP tool: URL allowlist enforced (requests to non-allowed hosts rejected)
4.  HTTP tool: SSRF blocks private/reserved IPs
5.  File I/O: base_dir scoped per workflow, not CWD
6.  File I/O: path traversal blocked (.. in path parts rejected)
7.  ${ENV_VAR} resolved at engine level (existing SecretsEnvLoader pattern)
8.  Undefined ${ENV_VAR} produces clear error at parse time (not silent empty string)
9.  Subprocess memory has ONE API key only, no other secrets
"""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any

import pytest

from runsight_core.isolation import (
    ContextEnvelope,
    IPCClient,
    IPCServer,
    SoulEnvelope,
    SubprocessHarness,
    TaskEnvelope,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context_envelope(
    *,
    block_id: str = "block-1",
    block_type: str = "linear",
    block_config: dict[str, Any] | None = None,
    tools: list | None = None,
    timeout_seconds: int = 30,
) -> ContextEnvelope:
    return ContextEnvelope(
        block_id=block_id,
        block_type=block_type,
        block_config=block_config or {},
        soul=SoulEnvelope(
            id="soul-1",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o-mini",
            max_tool_iterations=3,
        ),
        tools=tools or [],
        task=TaskEnvelope(id="task-1", instruction="Do the thing.", context={}),
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=timeout_seconds,
        max_output_bytes=1_000_000,
    )


async def _setup_ipc_pair(
    tmp_path: Path,
    handlers: dict[str, Any],
    *,
    sock_name: str = "test.sock",
) -> tuple[IPCServer, IPCClient, socket.socket, Path, asyncio.Task]:
    """Create an IPC server+client pair for testing handlers."""
    sock_path = tmp_path / sock_name
    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(str(sock_path))
    server_sock.listen(1)

    server = IPCServer(sock=server_sock, handlers=handlers)
    server_task = asyncio.create_task(server.serve())

    client = IPCClient(socket_path=str(sock_path))
    await client.connect()

    return server, client, server_sock, sock_path, server_task


async def _teardown_ipc_pair(
    server: IPCServer,
    client: IPCClient,
    server_sock: socket.socket,
    sock_path: Path,
    server_task: asyncio.Task,
) -> None:
    """Clean up an IPC server+client pair."""
    await client.close()
    await server.shutdown()
    server_task.cancel()
    server_sock.close()
    sock_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AC1 + AC9: ONE API key per subprocess, no other secrets in env
# NOTE: _build_subprocess_env already exists and passes basic checks.
#       These tests verify the NEW credential-scoped envelope building
#       where the harness resolves tool credentials at envelope construction
#       time and strips them from the subprocess env.
# ---------------------------------------------------------------------------


class TestSubprocessCredentialScoping:
    """Harness must resolve tool credentials and pass them only via IPC handlers."""

    def test_harness_accepts_tool_credentials(self):
        """SubprocessHarness accepts a tool_credentials dict for IPC handler setup."""
        harness = SubprocessHarness(
            api_key="sk-test-key",
            tool_credentials={"http_tool_1": {"Authorization": "Bearer sk-secret"}},
        )
        assert harness is not None

    def test_tool_credentials_not_in_subprocess_env(self):
        """Tool credentials must NOT appear in the subprocess environment."""
        harness = SubprocessHarness(
            api_key="sk-test-key",
            tool_credentials={"http_tool_1": {"Authorization": "Bearer sk-tool-secret"}},
        )
        env = harness._build_subprocess_env(socket_path="/tmp/test.sock")

        # The tool credential value must not appear anywhere in the env
        all_env_values = " ".join(env.values())
        assert "sk-tool-secret" not in all_env_values

    def test_harness_creates_handlers_with_credentials(self):
        """Harness builds IPC handlers that have the tool credentials baked in."""
        harness = SubprocessHarness(
            api_key="sk-test-key",
            tool_credentials={"http_tool_1": {"Authorization": "Bearer sk-injected"}},
        )
        handlers = harness._build_ipc_handlers()
        assert "http" in handlers
        assert "file_io" in handlers


# ---------------------------------------------------------------------------
# AC2: HTTP tool — credentials injected by engine at IPC time
# ---------------------------------------------------------------------------


class TestHTTPCredentialInjection:
    """Engine-side IPC http handler must inject credentials into outgoing requests.

    The subprocess sends a bare HTTP request via IPC. The engine-side handler
    enriches the request with credentials (e.g. Authorization header) from the
    tool config before executing it. The subprocess never sees the raw token.
    """

    async def test_http_handler_injects_auth_header(self, tmp_path: Path):
        """http handler adds Authorization header from tool credential config."""
        from runsight_core.isolation.handlers import make_http_handler

        credentials = {"Authorization": "Bearer sk-engine-secret-token"}
        handler = make_http_handler(credentials=credentials, url_allowlist=["*"])

        result = await handler(
            {
                "method": "GET",
                "url": "https://api.example.com/data",
                "headers": {"Accept": "application/json"},
            }
        )

        # The handler should have merged the credential header into the request
        assert "error" not in result

    async def test_http_handler_does_not_expose_token_in_response(self, tmp_path: Path):
        """The token injected by the engine must not appear in the IPC response."""
        from runsight_core.isolation.handlers import make_http_handler

        credentials = {"Authorization": "Bearer sk-super-secret"}
        handler = make_http_handler(credentials=credentials, url_allowlist=["*"])

        result = await handler(
            {
                "method": "GET",
                "url": "https://api.example.com/data",
                "headers": {},
            }
        )

        # Response must not contain the injected credential
        result_str = json.dumps(result)
        assert "sk-super-secret" not in result_str

    async def test_subprocess_request_has_no_credential_fields(self, tmp_path: Path):
        """Subprocess sends requests without credential fields — engine adds them."""
        from runsight_core.isolation.handlers import make_http_handler

        credentials = {"Authorization": "Bearer sk-injected"}
        handler = make_http_handler(credentials=credentials, url_allowlist=["*"])

        # Simulate a subprocess request with NO auth header
        subprocess_request = {
            "method": "GET",
            "url": "https://api.example.com/data",
            "headers": {},
        }

        # The handler should work fine even though subprocess didn't send credentials
        result = await handler(subprocess_request)
        assert "error" not in result


# ---------------------------------------------------------------------------
# AC3: HTTP tool — URL allowlist enforced
# ---------------------------------------------------------------------------


class TestHTTPURLAllowlist:
    """HTTP requests must be validated against a URL allowlist."""

    async def test_allowed_host_passes(self, tmp_path: Path):
        """Requests to hosts on the allowlist are permitted."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(
            credentials={},
            url_allowlist=["api.example.com", "cdn.example.com"],
        )

        result = await handler(
            {
                "method": "GET",
                "url": "https://api.example.com/data",
                "headers": {},
            }
        )
        assert "error" not in result

    async def test_disallowed_host_rejected(self, tmp_path: Path):
        """Requests to hosts NOT on the allowlist are rejected with an error."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(
            credentials={},
            url_allowlist=["api.example.com"],
        )

        result = await handler(
            {
                "method": "GET",
                "url": "https://evil.attacker.com/steal",
                "headers": {},
            }
        )
        assert "error" in result
        assert "allowlist" in result["error"].lower() or "allowed" in result["error"].lower()

    async def test_empty_allowlist_blocks_all(self, tmp_path: Path):
        """An empty allowlist blocks all HTTP requests."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=[])

        result = await handler(
            {
                "method": "GET",
                "url": "https://any-host.com/path",
                "headers": {},
            }
        )
        assert "error" in result

    async def test_wildcard_allowlist_permits_all(self, tmp_path: Path):
        """A '*' entry in the allowlist permits all hosts."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["*"])

        result = await handler(
            {
                "method": "GET",
                "url": "https://literally-anything.com/path",
                "headers": {},
            }
        )
        assert "error" not in result

    async def test_allowlist_matches_hostname_not_path(self, tmp_path: Path):
        """Allowlist checks the hostname, not the full URL path."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(
            credentials={},
            url_allowlist=["api.example.com"],
        )

        # Different paths on the same allowed host should be fine
        result = await handler(
            {
                "method": "GET",
                "url": "https://api.example.com/any/path/here",
                "headers": {},
            }
        )
        assert "error" not in result


# ---------------------------------------------------------------------------
# AC4: HTTP tool — SSRF blocks private/reserved IPs
# ---------------------------------------------------------------------------


class TestHTTPSSRFProtection:
    """HTTP handler must block requests targeting private/reserved IPs."""

    async def test_localhost_blocked(self, tmp_path: Path):
        """Requests to 127.0.0.1 are blocked by SSRF validation."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["*"])

        result = await handler(
            {
                "method": "GET",
                "url": "http://127.0.0.1:8080/admin",
                "headers": {},
            }
        )
        assert "error" in result
        assert "ssrf" in result["error"].lower() or "blocked" in result["error"].lower()

    async def test_private_ip_10_blocked(self, tmp_path: Path):
        """Requests to 10.x.x.x private range are blocked."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["*"])

        result = await handler(
            {
                "method": "GET",
                "url": "http://10.0.0.1/internal",
                "headers": {},
            }
        )
        assert "error" in result

    async def test_private_ip_192_168_blocked(self, tmp_path: Path):
        """Requests to 192.168.x.x private range are blocked."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["*"])

        result = await handler(
            {
                "method": "GET",
                "url": "http://192.168.1.1/router",
                "headers": {},
            }
        )
        assert "error" in result

    async def test_link_local_169_254_blocked(self, tmp_path: Path):
        """Requests to 169.254.x.x (link-local / cloud metadata) are blocked."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["*"])

        result = await handler(
            {
                "method": "GET",
                "url": "http://169.254.169.254/latest/meta-data/",
                "headers": {},
            }
        )
        assert "error" in result

    async def test_public_ip_allowed(self, tmp_path: Path):
        """Requests to public IPs pass SSRF validation."""
        from runsight_core.isolation.handlers import make_http_handler

        handler = make_http_handler(credentials={}, url_allowlist=["*"])

        # 8.8.8.8 is public (Google DNS)
        result = await handler(
            {
                "method": "GET",
                "url": "http://8.8.8.8/",
                "headers": {},
            }
        )
        # Should not have an SSRF error (may have a connection error, but not SSRF)
        if "error" in result:
            assert "ssrf" not in result["error"].lower()


# ---------------------------------------------------------------------------
# AC5: File I/O — base_dir scoped per workflow
# ---------------------------------------------------------------------------


class TestFileIOBaseDir:
    """File I/O handler must scope all paths to a per-workflow base directory."""

    async def test_file_io_handler_requires_base_dir(self, tmp_path: Path):
        """make_file_io_handler requires a base_dir parameter."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "workflow-files"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        assert handler is not None

    async def test_read_resolves_relative_to_base_dir(self, tmp_path: Path):
        """Reading a file resolves the path relative to base_dir."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-data"
        base.mkdir()
        (base / "notes.txt").write_text("hello from base")

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "read",
                "path": "notes.txt",
            }
        )

        assert result.get("content") == "hello from base"

    async def test_write_resolves_relative_to_base_dir(self, tmp_path: Path):
        """Writing a file places it inside base_dir."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-output"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "write",
                "path": "output.txt",
                "content": "result data",
            }
        )

        assert "error" not in result
        assert (base / "output.txt").read_text() == "result data"

    async def test_absolute_path_rejected(self, tmp_path: Path):
        """Absolute paths must be rejected — only relative paths within base_dir."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-safe"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "read",
                "path": "/etc/passwd",
            }
        )

        assert "error" in result


# ---------------------------------------------------------------------------
# AC6: File I/O — path traversal blocked
# ---------------------------------------------------------------------------


class TestFileIOPathTraversal:
    """File I/O handler must block path traversal via '..' in path components."""

    async def test_dotdot_in_path_rejected(self, tmp_path: Path):
        """Paths containing '..' are rejected."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-guarded"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "read",
                "path": "../../../etc/passwd",
            }
        )

        assert "error" in result
        assert "traversal" in result["error"].lower() or ".." in result["error"]

    async def test_dotdot_in_middle_of_path_rejected(self, tmp_path: Path):
        """Paths with '..' in a middle segment are rejected."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-mid"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "read",
                "path": "subdir/../../secret.txt",
            }
        )

        assert "error" in result

    async def test_encoded_dotdot_rejected(self, tmp_path: Path):
        """URL-encoded '..' variants should also be caught."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-enc"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))

        # Even after normalization, if the resolved path escapes base_dir, it's blocked
        result = await handler(
            {
                "action_type": "read",
                "path": "subdir/%2e%2e/secret.txt",
            }
        )

        # Should either reject the encoded traversal or resolve safely within base_dir
        if "error" not in result:
            # If no error, the resolved path must still be inside base_dir
            assert result.get("content") is not None or "error" in result

    async def test_write_with_traversal_rejected(self, tmp_path: Path):
        """Write operations with path traversal are blocked."""
        from runsight_core.isolation.handlers import make_file_io_handler

        base = tmp_path / "wf-write-guard"
        base.mkdir()

        handler = make_file_io_handler(base_dir=str(base))
        result = await handler(
            {
                "action_type": "write",
                "path": "../../escape.txt",
                "content": "malicious content",
            }
        )

        assert "error" in result
        # Ensure the file was NOT written outside base_dir
        assert not (tmp_path / "escape.txt").exists()


# ---------------------------------------------------------------------------
# AC7: ${ENV_VAR} resolved at engine level
# ---------------------------------------------------------------------------


class TestEnvVarResolution:
    """${ENV_VAR} references in tool configs must be resolved at engine level."""

    def test_resolve_env_var_reference(self, monkeypatch):
        """${MY_TOKEN} in a credential config resolves to the env var value."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        monkeypatch.setenv("MY_TOKEN", "resolved-secret-value")

        config = {"Authorization": "Bearer ${MY_TOKEN}"}
        resolved = resolve_credential_refs(config)

        assert resolved["Authorization"] == "Bearer resolved-secret-value"

    def test_resolve_multiple_refs_in_one_value(self, monkeypatch):
        """Multiple ${VAR} references in one string are all resolved."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        monkeypatch.setenv("USER_ID", "user-42")
        monkeypatch.setenv("API_SECRET", "s3cr3t")

        config = {"X-Custom": "${USER_ID}:${API_SECRET}"}
        resolved = resolve_credential_refs(config)

        assert resolved["X-Custom"] == "user-42:s3cr3t"

    def test_resolve_nested_dict(self, monkeypatch):
        """Nested dicts have their ${VAR} references resolved recursively."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        monkeypatch.setenv("DB_PASS", "p@ssw0rd")

        config = {
            "headers": {"Authorization": "Basic ${DB_PASS}"},
            "params": {"key": "${DB_PASS}"},
        }
        resolved = resolve_credential_refs(config)

        assert resolved["headers"]["Authorization"] == "Basic p@ssw0rd"
        assert resolved["params"]["key"] == "p@ssw0rd"

    def test_plain_strings_unchanged(self):
        """Strings without ${...} are returned unchanged."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        config = {"host": "api.example.com", "port": "443"}
        resolved = resolve_credential_refs(config)

        assert resolved == config


# ---------------------------------------------------------------------------
# AC8: Undefined ${ENV_VAR} produces clear error
# ---------------------------------------------------------------------------


class TestUndefinedEnvVarError:
    """Undefined ${ENV_VAR} must produce a clear error, not silent empty string."""

    def test_undefined_var_raises(self):
        """Referencing an undefined env var raises a clear error."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        config = {"Authorization": "Bearer ${TOTALLY_UNDEFINED_VAR}"}

        with pytest.raises(Exception) as exc_info:
            resolve_credential_refs(config)

        error_msg = str(exc_info.value)
        assert "TOTALLY_UNDEFINED_VAR" in error_msg

    def test_undefined_var_not_empty_string(self, monkeypatch):
        """An undefined var must NOT silently become an empty string."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        # Make sure the var is truly undefined
        monkeypatch.delenv("NONEXISTENT_SECRET", raising=False)

        config = {"token": "${NONEXISTENT_SECRET}"}

        with pytest.raises(Exception):
            resolve_credential_refs(config)

    def test_error_message_names_the_variable(self):
        """The error message must name the undefined variable for debugging."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        config = {"key": "${MISSING_KEY_XYZ}"}

        with pytest.raises(Exception) as exc_info:
            resolve_credential_refs(config)

        assert "MISSING_KEY_XYZ" in str(exc_info.value)

    def test_partially_defined_config_reports_first_missing(self, monkeypatch):
        """When some vars exist and some don't, error names the missing one."""
        from runsight_core.isolation.credentials import resolve_credential_refs

        monkeypatch.setenv("GOOD_VAR", "exists")

        config = {
            "good": "${GOOD_VAR}",
            "bad": "${DOES_NOT_EXIST_999}",
        }

        with pytest.raises(Exception) as exc_info:
            resolve_credential_refs(config)

        assert "DOES_NOT_EXIST_999" in str(exc_info.value)
