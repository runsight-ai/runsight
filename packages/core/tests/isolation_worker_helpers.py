"""Package-local helpers for isolation worker subprocess tests."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from runsight_core.isolation.envelope import (
    ContextEnvelope,
    PromptEnvelope,
    ResultEnvelope,
    SoulEnvelope,
)
from runsight_core.isolation.workspace import IPCClientConfig, IPCTransport

SAFE_SUBPROCESS_ENV_KEYS = (
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "PYTHONIOENCODING",
    "TMP",
    "TMPDIR",
    "TEMP",
    "VIRTUAL_ENV",
)
WORKER_SUBPROCESS_TIMEOUT_SECONDS = 30.0


def worker_socket_path(label: str = "fixture", *, tmp_path: Path | None = None) -> str:
    """Return a unique nonexistent socket path for worker subprocess tests."""
    safe_label = "".join(ch if ch.isalnum() else "-" for ch in label)[:12] or "fixture"
    base_path = tmp_path if tmp_path is not None else Path(tempfile.gettempdir())
    return str(base_path / f"rsw-{safe_label}-{uuid.uuid4().hex[:12]}.sock")


def worker_ipc_config_env(
    *,
    ipc_socket_path: str | None = None,
    grant_token: str = "grant-token-fixture",
) -> dict[str, str]:
    """Build the encoded worker IPC config environment contract."""
    socket_path = ipc_socket_path or worker_socket_path()
    config = IPCClientConfig(
        version=1,
        transport=IPCTransport.UNIX_SOCKET,
        grant_token=grant_token,
        unix_socket={"path": socket_path},
    )
    return config.to_env()


def minimal_worker_env(
    env_extra: dict[str, str] | None = None,
    *,
    omit: tuple[str, ...] = (),
    ipc_socket_path: str | None = None,
) -> dict[str, str]:
    """Build a subprocess env without leaking host credentials into worker tests."""
    env = {key: os.environ[key] for key in SAFE_SUBPROCESS_ENV_KEYS if key in os.environ}
    core_src = Path(__file__).resolve().parents[1] / "src"
    pythonpath = [str(core_src)]
    if os.environ.get("PYTHONPATH"):
        pythonpath.append(os.environ["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    env.update(worker_ipc_config_env(ipc_socket_path=ipc_socket_path))
    if env_extra:
        env.update(env_extra)
    for key in omit:
        env.pop(key, None)
    return env


def make_context_envelope(**overrides) -> ContextEnvelope:
    """Build a minimal valid ContextEnvelope for test purposes."""
    defaults = dict(
        block_id="worker_block",
        block_type="linear",
        block_config={},
        soul=SoulEnvelope(
            id="worker_soul",
            name="Tester",
            role="Tester",
            system_prompt="You test things.",
            model_name="gpt-4o",
            max_tool_iterations=5,
        ),
        tools=[],
        prompt=PromptEnvelope(
            id="worker_prompt",
            instruction="Say hello",
            context={},
        ),
        scoped_results={},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=30,
        max_output_bytes=1_000_000,
    )
    defaults.update(overrides)
    return ContextEnvelope(**defaults)


def run_worker_subprocess(
    envelope: ContextEnvelope | None = None,
    env_extra: dict[str, str] | None = None,
    *,
    omit: tuple[str, ...] = (),
    input_text: str | None = None,
    timeout: float = WORKER_SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Invoke the isolation worker subprocess with a test-owned environment."""
    stdin_payload = input_text if input_text is not None else envelope.model_dump_json()
    env = minimal_worker_env(env_extra, omit=omit)

    return subprocess.run(
        [sys.executable, "-m", "runsight_core.isolation.worker"],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def parse_result_envelope(stdout: str) -> ResultEnvelope:
    """Parse a worker stdout payload as a ResultEnvelope."""
    return ResultEnvelope.model_validate_json(stdout.strip())
