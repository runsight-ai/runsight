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
        self.engine = engine

    def fail_ghost_runs(self) -> None:
        """Mark active runs as failed after an API restart."""
        restart_error = "API process restarted during execution"

        if self.engine is not None:
            try:
                from sqlmodel import Session, select

                from ...domain.entities.run import Run

                with Session(self.engine) as session:
                    ghost_runs = session.exec(
                        select(Run).where(Run.status.in_([RunStatus.pending, RunStatus.running]))
                    ).all()
                    completed_at = time.time()
                    for run in ghost_runs:
                        run.status = RunStatus.failed
                        run.error = restart_error
                        run.completed_at = completed_at
                        run.updated_at = completed_at
                        session.add(run)
                    session.commit()
                return
            except Exception:
                logger.exception("Failed to mark ghost runs via engine session")

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
                self.run_repo.update_run(run)
        except Exception:
            logger.exception("Failed to mark ghost runs via run_repo")

    def fail_prepare(self, run_id: str, error: Exception) -> None:
        """Persist a prepare-time failure before any task starts."""
        if self.engine is not None:
            try:
                from sqlmodel import Session

                from ...domain.entities.run import Run

                with Session(self.engine) as session:
                    run = session.get(Run, run_id)
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
                        session.add(run)
                        session.commit()
                return
            except Exception:
                logger.exception("Failed to mark run %s as failed via engine session", run_id)

        try:
            run = self.run_repo.get_run(run_id)
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
                self.run_repo.update_run(run)
        except Exception:
            logger.exception("Failed to mark run %s as failed via run_repo", run_id)

    def set_status(
        self, run_id: str, status: RunStatus, *, error: Optional[Exception] = None
    ) -> bool:
        """Persist a non-terminal execution status transition."""
        if self.engine is not None:
            try:
                from sqlmodel import Session

                from ...domain.entities.run import Run

                with Session(self.engine) as session:
                    run = session.get(Run, run_id)
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
                    session.add(run)
                    session.commit()
                    return True
            except Exception:
                logger.exception("Failed to update run %s status to %s", run_id, status)
                return False

        get_run = getattr(self.run_repo, "get_run", None)
        update_run = getattr(self.run_repo, "update_run", None)
        if not callable(get_run) or not callable(update_run):
            return False
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
        if self.engine is None:
            return
        try:
            from sqlmodel import Session

            from ...domain.entities.run import Run

            with Session(self.engine) as session:
                run = session.get(Run, run_id)
                if run:
                    run.branch = branch
                    run.commit_sha = commit_sha
                    run.updated_at = time.time()
                    session.add(run)
                    session.commit()
        except Exception:
            logger.exception("Failed to store branch/commit_sha for run %s", run_id)

    def is_run_cancelled(self, run_id: str) -> bool:
        """Return True when the run has already been cancelled."""
        if self.engine is not None:
            try:
                from sqlmodel import Session

                from ...domain.entities.run import Run

                with Session(self.engine) as session:
                    run = session.get(Run, run_id)
                    return bool(run and run.status == RunStatus.cancelled)
            except Exception:
                logger.exception("Failed to read run %s cancellation state via engine", run_id)
                return False

        get_run = getattr(self.run_repo, "get_run", None)
        if callable(get_run):
            try:
                run = get_run(run_id)
            except Exception:
                logger.exception("Failed to read run %s cancellation state via run_repo", run_id)
                return False
            return bool(run and run.status == RunStatus.cancelled)

        return False
