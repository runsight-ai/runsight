"""Worker grant-token environment behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from isolation_worker_helpers import (
    make_context_envelope,
    parse_result_envelope,
    run_worker_subprocess,
    worker_socket_path,
)

pytestmark = pytest.mark.real_subprocess_isolation


class TestWorkerGrantTokenContract:
    """Worker authenticates via grant token, not raw API key env injection."""

    def test_worker_source_does_not_reference_block_api_key_env_var(self):
        """Security contract: worker must not read RUNSIGHT_BLOCK_API_KEY at all."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "RUNSIGHT_BLOCK_API_KEY" not in source

    def test_worker_does_not_fail_for_missing_block_api_key_when_grant_token_present(self):
        envelope = make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = run_worker_subprocess(
            envelope,
            {
                "RUNSIGHT_GRANT_TOKEN": "grant-token-fixture",
                "RUNSIGHT_IPC_SOCKET": worker_socket_path("grant-contract"),
            },
            omit=("RUNSIGHT_BLOCK_API_KEY",),
        )

        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        result_env = parse_result_envelope(stdout)
        assert result_env.error is not None
        assert "RUNSIGHT_BLOCK_API_KEY" not in result_env.error
