"""Red source-audit tests for RUN-952 startup ghost-run cleanup wiring."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MAIN_FILE = REPO_ROOT / "apps" / "api" / "src" / "runsight_api" / "main.py"


def _read_main() -> str:
    return MAIN_FILE.read_text(encoding="utf-8")


class TestStartupGhostRunCleanupOwnership:
    def test_lifespan_delegates_ghost_run_cleanup_to_execution_service(self):
        source = _read_main()
        assert ".fail_ghost_runs(" in source, (
            "RUN-952 requires ghost-run cleanup to be owned by the execution "
            "startup collaborator. The lifespan wiring should delegate to "
            "ExecutionService.fail_ghost_runs() or its extracted equivalent."
        )

    def test_main_no_longer_defines_standalone_recover_stale_runs_helper(self):
        source = _read_main()
        assert "def _recover_stale_runs(" not in source, (
            "Ghost-run cleanup should not remain as a standalone helper in "
            "main.py after the RUN-952 coordinator split."
        )
