"""Persistence collaborator for execution lifecycle state."""

import logging
import time
from typing import Optional

from ...domain.entities.run import InvalidStateTransition, RunStatus, validate_transition

logger = logging.getLogger(__name__)


def _coerce_run_status(value: object) -> RunStatus | None:
    if isinstance(value, RunStatus):
        return value
    if isinstance(value, str):
        try:
            return RunStatus(value)
        except ValueError:
            return None
    raw_value = getattr(value, "value", None)
    if isinstance(raw_value, str):
        try:
            return RunStatus(raw_value)
        except ValueError:
            return None
    return None


class ExecutionRunStore:
    """Owns persistence for launch/cleanup state transitions."""

    def __init__(self, run_repo, engine=None):
        self.run_repo = run_repo

    def fail_ghost_runs(self) -> None:
        """Mark active runs as failed after an API restart."""
        restart_error = "API server restarted during execution"

        try:
            stale_runs = [
                run
                for run in self.run_repo.list_runs()
                if run.status in {RunStatus.pending, RunStatus.running}
            ]
            completed_at = time.time()
            for run in stale_runs:
                run.status = RunStatus.failed
                run.error = restart_error
                run.completed_at = completed_at
                run.updated_at = completed_at
                self.run_repo.update_run(run)
        except Exception:
            logger.exception("Failed to mark ghost runs via run_repo")

    def fail_prepare(self, run_id: str, error: Exception) -> None:
        """Persist a prepare-time failure before any task starts."""
        get_run = self.run_repo.get_run
        update_run = self.run_repo.update_run
        try:
            run = get_run(run_id)
            if run:
                current_status = _coerce_run_status(run.status)
                if current_status is not None:
                    try:
                        validate_transition(current_status, RunStatus.failed)
                    except InvalidStateTransition:
                        logger.warning(
                            "Skipping invalid prepare failure transition: %s -> %s for run %s",
                            current_status.value,
                            RunStatus.failed.value,
                            run_id,
                        )
                        return
                run.status = RunStatus.failed
                run.error = str(error)
                run.completed_at = time.time()
                update_run(run)
        except Exception:
            logger.exception("Failed to mark run %s as failed via run_repo", run_id)

    def set_status(
        self, run_id: str, status: RunStatus, *, error: Optional[Exception] = None
    ) -> bool:
        """Persist a non-terminal execution status transition."""
        get_run = self.run_repo.get_run
        update_run = self.run_repo.update_run
        try:
            run = get_run(run_id)
            if run is None:
                return False
            current_status = _coerce_run_status(run.status)
            if current_status is not None:
                try:
                    validate_transition(current_status, status)
                except InvalidStateTransition:
                    logger.warning(
                        "Skipping invalid state transition: %s -> %s for run %s",
                        current_status.value,
                        status.value,
                        run_id,
                    )
                    return False
            run.status = status
            run.updated_at = time.time()
            if error is not None:
                run.error = str(error)
            update_run(run)
            return True
        except Exception:
            logger.exception("Failed to update run %s status to %s", run_id, status)
            return False

    def store_branch_and_sha(self, run_id: str, branch: str, commit_sha: Optional[str]) -> None:
        """Persist the branch and canonical commit SHA used for execution."""
        get_run = self.run_repo.get_run
        update_run = self.run_repo.update_run
        try:
            run = get_run(run_id)
            if run is None:
                return
            run.branch = branch
            run.commit_sha = commit_sha
            run.updated_at = time.time()
            update_run(run)
        except Exception:
            logger.exception("Failed to store branch/commit_sha for run %s via run_repo", run_id)

    def is_run_cancelled(self, run_id: str) -> bool:
        """Return True when the run has already been cancelled."""
        get_run = self.run_repo.get_run
        try:
            run = get_run(run_id)
        except Exception:
            logger.exception("Failed to read run %s cancellation state via run_repo", run_id)
            return False
        return bool(run and run.status == RunStatus.cancelled)
