from types import SimpleNamespace

from runsight_api.domain.entities.run import RunStatus
from runsight_api.logic.services.execution_persistence import ExecutionRunStore


def _make_run(run_id: str, status: RunStatus):
    return SimpleNamespace(
        id=run_id,
        status=status,
        error=None,
        completed_at=None,
        updated_at=None,
    )


def test_fail_ghost_runs_without_engine_uses_run_repo_list_runs() -> None:
    pending_run = _make_run("run_pending", RunStatus.pending)
    running_run = _make_run("run_running", RunStatus.running)
    completed_run = _make_run("run_completed", RunStatus.completed)
    updated_ids: list[str] = []

    run_repo = SimpleNamespace(
        list_runs=lambda: [pending_run, running_run, completed_run],
        update_run=lambda run: updated_ids.append(run.id),
    )

    store = ExecutionRunStore(run_repo=run_repo, engine=None)

    store.fail_ghost_runs()

    assert pending_run.status == RunStatus.failed
    assert running_run.status == RunStatus.failed
    assert completed_run.status == RunStatus.completed
    assert pending_run.error == "API process restarted during execution"
    assert running_run.error == "API process restarted during execution"
    assert pending_run.completed_at is not None
    assert running_run.completed_at is not None
    assert updated_ids == ["run_pending", "run_running"]
