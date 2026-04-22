import inspect
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


def test_fail_ghost_runs_uses_canonical_list_runs_path_without_legacy_status_probe() -> None:
    pending_run = _make_run("run_pending", RunStatus.pending)
    running_run = _make_run("run_running", RunStatus.running)
    completed_run = _make_run("run_completed", RunStatus.completed)
    updated_ids: list[str] = []

    def _unexpected_get_by_status(status):
        raise AssertionError(
            f"fail_ghost_runs must not probe legacy get_by_status({status!r}) fallbacks"
        )

    run_repo = SimpleNamespace(
        get_by_status=_unexpected_get_by_status,
        list_runs=lambda: [pending_run, running_run, completed_run],
        update_run=lambda run: updated_ids.append(run.id),
    )

    store = ExecutionRunStore(run_repo=run_repo, engine=None)
    store.fail_ghost_runs()

    assert pending_run.status == RunStatus.failed
    assert running_run.status == RunStatus.failed
    assert completed_run.status == RunStatus.completed
    assert updated_ids == ["run_pending", "run_running"]


def test_execution_run_store_source_has_no_ghost_run_compatibility_fallbacks() -> None:
    fail_ghost_runs_source = inspect.getsource(ExecutionRunStore.fail_ghost_runs)
    store_branch_source = inspect.getsource(ExecutionRunStore.store_branch_and_sha)

    assert "get_by_status" not in fail_ghost_runs_source
    assert 'getattr(self.run_repo, "update_run", None)' not in fail_ghost_runs_source
    assert 'getattr(self.run_repo, "get_run", None)' not in store_branch_source
    assert 'getattr(self.run_repo, "update_run", None)' not in store_branch_source
