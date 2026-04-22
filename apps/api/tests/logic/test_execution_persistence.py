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


def test_store_branch_and_sha_without_engine_uses_run_repo_get_and_update() -> None:
    run = SimpleNamespace(
        id="run_branch_sha",
        branch="main",
        commit_sha=None,
        updated_at=None,
    )
    updated_runs = []

    run_repo = SimpleNamespace(
        get_run=lambda run_id: run if run_id == "run_branch_sha" else None,
        update_run=lambda updated_run: updated_runs.append(updated_run),
    )

    store = ExecutionRunStore(run_repo=run_repo, engine=None)

    store.store_branch_and_sha("run_branch_sha", "feature/review-fix", "abc123def456")

    assert run.branch == "feature/review-fix"
    assert run.commit_sha == "abc123def456"
    assert run.updated_at is not None
    assert updated_runs == [run]
