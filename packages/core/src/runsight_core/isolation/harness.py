"""SubprocessHarness — manages the full subprocess lifecycle (ISO-003).

Responsibilities:
1. Build ContextEnvelope (scoped context from YAML declarations)
2. Create Unix socket (random path, mode 0600)
3. Spawn subprocess with minimal env
4. Write envelope to stdin, read result from stdout, heartbeats from stderr
5. Enforce timeout, handle heartbeat stalls, handle phase stalls
6. SIGTERM -> SIGKILL escalation
7. Validate ResultEnvelope
8. Clean up socket + temp dir
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from runsight_core.budget_enforcement import BudgetSession, _active_budget
from runsight_core.context_governance import ContextDeclaration, ContextResolver
from runsight_core.isolation.envelope import (
    ContextEnvelope,
    HeartbeatMessage,
    PromptEnvelope,
    ResultEnvelope,
    SoulEnvelope,
)
from runsight_core.isolation.interceptors import (
    BudgetInterceptor,
    InterceptorRegistry,
    ObserverInterceptor,
)
from runsight_core.isolation.ipc import IPCServer
from runsight_core.isolation.ipc_models import GrantToken
from runsight_core.state import BlockResult
from runsight_core.yaml.schema import BlockLimitsDef

# ---------------------------------------------------------------------------
# HeartbeatTracker — tracks phase changes and detects stalls
# ---------------------------------------------------------------------------


class HeartbeatTracker:
    """Tracks heartbeat phase changes and detects phase stalls."""

    def __init__(
        self,
        phase_timeout: float = 60.0,
        stall_thresholds: dict[str, int | float] | None = None,
    ) -> None:
        self._phase_timeout = phase_timeout
        self.stall_thresholds: dict[str, int | float] = stall_thresholds or {}
        self.current_phase: str = ""
        self._phase_started_at: float = time.monotonic()

    def update(self, heartbeat: HeartbeatMessage) -> None:
        """Update the tracker with a new heartbeat."""
        if heartbeat.phase != self.current_phase:
            self.current_phase = heartbeat.phase
            self._phase_started_at = time.monotonic()

    @property
    def is_stalled(self) -> bool:
        """Return True if the current phase has exceeded its timeout threshold."""
        threshold = self.stall_thresholds.get(self.current_phase, self._phase_timeout)
        return (time.monotonic() - self._phase_started_at) > threshold


# ---------------------------------------------------------------------------
# SubprocessHarness
# ---------------------------------------------------------------------------

_SIGTERM_GRACE_SECONDS = 5


def _declared_inputs_from_block_config(block_config: dict[str, Any]) -> dict[str, str]:
    raw_inputs = block_config.get("declared_inputs") or block_config.get("inputs") or {}
    declared_inputs: dict[str, str] = {}
    for input_name, raw_ref in raw_inputs.items():
        from_ref = raw_ref
        if isinstance(raw_ref, dict):
            from_ref = raw_ref.get("from") or raw_ref.get("from_ref")
        if from_ref is not None:
            declared_inputs[str(input_name)] = str(from_ref)
    return declared_inputs


def _internal_inputs_from_block_config(
    block_type: str,
    block_config: dict[str, Any],
) -> dict[str, str]:
    if block_type == "gate" and block_config.get("eval_key") is not None:
        return {"content": str(block_config["eval_key"])}
    if block_type == "synthesize":
        return {
            str(block_id): str(block_id) for block_id in block_config.get("input_block_ids", [])
        }
    return {}


def _serialize_scoped_results(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    serialized: dict[str, dict[str, Any]] = {}
    for key, value in results.items():
        if isinstance(value, BlockResult):
            serialized[key] = value.model_dump()
        else:
            serialized[key] = {"output": value}
    return serialized


class SubprocessHarness:
    """Manages the full lifecycle of a process-isolated block execution."""

    def __init__(
        self,
        *,
        api_keys: dict[str, str],
        timeout_seconds: int = 300,
        heartbeat_timeout: float = 30.0,
        phase_timeout: float = 60.0,
        stall_thresholds: dict[str, int | float] | None = None,
        tool_credentials: dict[str, dict[str, str]] | None = None,
        url_allowlist: list[str] | None = None,
        resolved_tools: dict[str, Any] | None = None,
    ) -> None:
        self._api_keys = dict(api_keys)
        self._timeout_seconds = timeout_seconds
        self._heartbeat_timeout = heartbeat_timeout
        self._phase_timeout = phase_timeout
        self._stall_thresholds = stall_thresholds or {}
        self._tool_credentials = tool_credentials or {}
        self._url_allowlist = list(url_allowlist or [])
        self._resolved_tools = dict(resolved_tools or {})
        self._grant_token: GrantToken | None = None
        self._file_io_temp_dir: str | None = None

    # -- ISO-008: IPC handlers with baked-in credentials --------------------

    def _build_ipc_handlers(self) -> dict[str, Any]:
        """Build IPC handlers with tool credentials injected engine-side."""
        from runsight_core.isolation.handlers import (
            make_file_io_handler,
            make_http_handler,
            make_llm_call_handler,
            make_tool_call_handler,
        )

        file_io_base_dir = tempfile.mkdtemp(prefix="rs-fio-")
        self._file_io_temp_dir = file_io_base_dir

        return {
            "llm_call": make_llm_call_handler(api_keys=dict(self._api_keys)),
            "http": make_http_handler(
                credentials=dict(self._tool_credentials),
                url_allowlist=list(self._url_allowlist),
            ),
            "file_io": make_file_io_handler(base_dir=file_io_base_dir),
            "tool_call": make_tool_call_handler(self._resolved_tools),
        }

    # -- AC1: Minimal subprocess environment --------------------------------

    def _build_subprocess_env(
        self,
        *,
        socket_path: str | None = None,
        block_id: str = "unknown",
    ) -> dict[str, str]:
        """Return a minimal environment dict for the subprocess."""
        self._grant_token = GrantToken(block_id=block_id)
        env: dict[str, str] = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "RUNSIGHT_GRANT_TOKEN": self._grant_token.token,
        }
        if socket_path is not None:
            env["RUNSIGHT_IPC_SOCKET"] = socket_path

        # macOS dynamic linker paths
        if sys.platform == "darwin":
            env["DYLD_FALLBACK_LIBRARY_PATH"] = "/usr/lib"

        return env

    # -- AC2: Fresh temp working dir ----------------------------------------

    def _create_working_dir(self) -> str:
        """Create a fresh temp directory for the subprocess cwd."""
        return tempfile.mkdtemp(prefix="rs-work-")

    # -- AC3: Socket creation -----------------------------------------------

    def _create_socket(self) -> tuple[socket.socket, str]:
        """Create and bind a Unix socket with mode 0600 at a random path."""
        sock_path = f"/tmp/rs-{uuid.uuid4().hex[:12]}.sock"

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(sock_path)
        os.chmod(sock_path, 0o600)
        sock.listen(1)

        return sock, sock_path

    # -- AC4: Context scoping -----------------------------------------------

    def _build_context_envelope(
        self,
        *,
        state: Any,
        block_config: dict[str, Any],
    ) -> ContextEnvelope:
        """Build a ContextEnvelope with data scoped by context declarations."""
        if "access" in block_config:
            raise ValueError(
                f"Block '{block_config.get('block_id', '<unknown>')}': access block configuration "
                "is unsupported; declare context with the 'inputs' field"
            )

        block_id = block_config.get("block_id", "")
        block_type = block_config.get("block_type", "linear")

        declaration = ContextDeclaration(
            block_id=str(block_id),
            block_type=str(block_type),
            access=str(block_config.get("context_access", "declared")),
            declared_inputs=_declared_inputs_from_block_config(block_config),
            internal_inputs=_internal_inputs_from_block_config(block_type, block_config),
        )
        resolver = ContextResolver(
            run_id=str(getattr(state, "metadata", {}).get("run_id", "")),
            workflow_name=str(getattr(state, "metadata", {}).get("workflow_name", "")),
        )
        scoped = resolver.resolve(declaration=declaration, state=state)

        return ContextEnvelope(
            block_id=block_id,
            block_type=block_type,
            block_config=block_config,
            soul=SoulEnvelope(
                id="default",
                role="worker",
                name="worker",
                system_prompt="",
                model_name="gpt-4o-mini",
                max_tool_iterations=3,
            ),
            tools=[],
            prompt=PromptEnvelope(id="task-0", instruction="", context={}),
            inputs=dict(scoped.inputs),
            scoped_results=_serialize_scoped_results(scoped.scoped_results),
            scoped_shared_memory=dict(scoped.scoped_shared_memory),
            scoped_metadata=dict(scoped.scoped_metadata),
            access=str(scoped.audit_event.access),
            context_audit=[scoped.audit_event],
            conversation_history=[],
            timeout_seconds=self._timeout_seconds,
            max_output_bytes=1_000_000,
        )

    # -- AC5/AC6/AC7: Heartbeat monitoring -----------------------------------

    def _create_heartbeat_tracker(self) -> HeartbeatTracker:
        """Create a HeartbeatTracker with the configured phase timeout and stall thresholds."""
        return HeartbeatTracker(
            phase_timeout=self._phase_timeout,
            stall_thresholds=self._stall_thresholds,
        )

    async def _monitor_heartbeats(
        self,
        proc: Any,
        *,
        timeout: float | None = None,
    ) -> bool:
        """Monitor stderr for heartbeats. Returns True if the subprocess was killed or exited."""
        hb_timeout = timeout if timeout is not None else self._heartbeat_timeout
        tracker = self._create_heartbeat_tracker()

        while proc.returncode is None:
            try:
                line = await asyncio.wait_for(
                    proc.stderr.readline(),
                    timeout=hb_timeout,
                )
                if not line:
                    # EOF on stderr — subprocess exited or closed stderr
                    return True

                # Parse heartbeat and update tracker
                try:
                    hb = HeartbeatMessage.model_validate_json(line.strip())
                    tracker.update(hb)
                except Exception:
                    pass

                # Check for phase stall after updating
                if tracker.is_stalled:
                    try:
                        proc.terminate()
                    except ProcessLookupError:
                        pass
                    return True

            except asyncio.TimeoutError:
                # No heartbeat within timeout — kill
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
                return True

        return False

    # -- AC8: Result validation ----------------------------------------------

    def _validate_result(self, raw_json: str, *, max_bytes: int) -> ResultEnvelope:
        """Validate a raw JSON string as a ResultEnvelope with a size cap."""
        raw_bytes = raw_json.encode("utf-8") if isinstance(raw_json, str) else raw_json
        if len(raw_bytes) > max_bytes:
            raise ValueError(
                f"Result size {len(raw_bytes)} bytes exceeds maximum of {max_bytes} bytes"
            )
        return ResultEnvelope.model_validate_json(raw_json)

    # -- AC9: SIGTERM -> SIGKILL escalation ----------------------------------

    async def _kill_subprocess(self, proc: Any) -> None:
        """Send SIGTERM, wait for grace period, then SIGKILL if needed."""
        proc.terminate()

        if proc.returncode is not None:
            return

        try:
            await asyncio.wait_for(proc.wait(), timeout=_SIGTERM_GRACE_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()

    # -- AC10: Return code mapping -------------------------------------------

    def _map_return_code(self, code: int) -> str | None:
        """Map a process return code to a human-readable error message."""
        if code == 0:
            return None

        signal_names: dict[int, str] = {
            -9: "Process killed by SIGKILL (signal 9) — possible OOM",
            -11: "Process killed by SIGSEGV (signal 11) — segfault",
            -15: "Process terminated by SIGTERM (signal 15)",
            -6: "Process aborted by SIGABRT (signal 6)",
            -2: "Process interrupted by SIGINT (signal 2)",
        }
        if code in signal_names:
            return signal_names[code]

        if code < 0:
            return f"Process killed by signal {-code}"

        return f"Process exit error (code {code})"

    # -- AC11: Cleanup -------------------------------------------------------

    def _cleanup(
        self,
        *,
        socket_path: str | None,
        working_dir: str | None,
    ) -> None:
        """Remove socket file and temp dir. Safe to call multiple times."""
        if socket_path:
            try:
                Path(socket_path).unlink()
            except (FileNotFoundError, OSError):
                pass

        if working_dir:
            try:
                shutil.rmtree(working_dir)
            except (FileNotFoundError, OSError):
                pass

        if self._file_io_temp_dir:
            try:
                shutil.rmtree(self._file_io_temp_dir)
            except (FileNotFoundError, OSError):
                pass
            self._file_io_temp_dir = None

    # -- AC12: Full lifecycle (run) ------------------------------------------

    async def run(self, envelope: ContextEnvelope) -> ResultEnvelope:
        """Execute the full subprocess lifecycle: spawn, communicate, validate, cleanup."""
        sock = None
        sock_path: str | None = None
        work_dir: str | None = None

        try:
            # Create socket and working dir
            sock, sock_path = self._create_socket()
            work_dir = self._create_working_dir()

            # Build environment
            env = self._build_subprocess_env(socket_path=sock_path, block_id=envelope.block_id)

            # Serialize envelope for stdin
            envelope_json = envelope.model_dump_json()

            # Determine the worker module entry point
            worker_cmd = [sys.executable, "-m", "runsight_core.isolation.worker"]

            timeout = envelope.timeout_seconds or self._timeout_seconds

            # Start IPC server task
            ipc_handlers = self._build_ipc_handlers()
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
                sock=sock,
                handlers=ipc_handlers,
                registry=registry,
                grant_token=self._grant_token,
            )
            ipc_task = asyncio.create_task(ipc_server.serve())

            try:
                # Spawn subprocess
                proc = await asyncio.create_subprocess_exec(
                    *worker_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=work_dir,
                )

                # Write envelope to stdin
                assert proc.stdin is not None
                proc.stdin.write(envelope_json.encode())
                proc.stdin.write(b"\n")
                await proc.stdin.drain()
                proc.stdin.close()

                # Monitor heartbeats in parallel with waiting for result
                monitor_task = asyncio.create_task(
                    self._monitor_heartbeats(proc, timeout=self._heartbeat_timeout)
                )

                try:
                    # Wait for the subprocess with timeout
                    assert proc.stdout is not None
                    stdout_data = await asyncio.wait_for(
                        proc.stdout.read(),
                        timeout=timeout,
                    )
                except (asyncio.TimeoutError, TimeoutError):
                    await self._kill_subprocess(proc)
                    raise TimeoutError(f"Subprocess timed out after {timeout} seconds")
                finally:
                    monitor_task.cancel()
                    try:
                        await monitor_task
                    except asyncio.CancelledError:
                        pass

                # Wait for process to finish
                await proc.wait()

                # Check return code
                if proc.returncode != 0:
                    raw_output = stdout_data.decode("utf-8").strip()
                    if raw_output:
                        try:
                            return self._validate_result(
                                raw_output,
                                max_bytes=envelope.max_output_bytes,
                            )
                        except Exception:
                            pass
                    error_msg = self._map_return_code(proc.returncode or 1)
                    return ResultEnvelope(
                        block_id=envelope.block_id,
                        output=None,
                        exit_handle="error",
                        cost_usd=0.0,
                        total_tokens=0,
                        tool_calls_made=0,
                        delegate_artifacts={},
                        conversation_history=[],
                        error=error_msg,
                        error_type="SubprocessError",
                    )

                # Validate and return result
                raw_output = stdout_data.decode("utf-8").strip()
                return self._validate_result(
                    raw_output,
                    max_bytes=envelope.max_output_bytes,
                )

            finally:
                await ipc_server.shutdown()
                ipc_task.cancel()
                try:
                    await ipc_task
                except asyncio.CancelledError:
                    pass

        finally:
            self._cleanup(socket_path=sock_path, working_dir=work_dir)
