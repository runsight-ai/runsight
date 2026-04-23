from types import SimpleNamespace

import pytest

from runsight_api.domain.entities.run import RunStatus
from runsight_api.logic.services.execution_persistence import ExecutionRunStore


def _make_run(run_id: str, status: RunStatus):
    return SimpleNamespace(
        id=run_id,
        status=status,
        error=None,
        branch=None,
        commit_sha=None,
        completed_at=None,
        updated_at=None,
    )


def _poison_session(monkeypatch: pytest.MonkeyPatch) -> None:
    class EnginePathTouched(BaseException):
        pass

    def _fail_if_session_is_used(*args, **kwargs):
        raise EnginePathTouched(
            "ExecutionRunStore must not open a Session for lifecycle persistence"
        )

    monkeypatch.setattr("sqlmodel.Session", _fail_if_session_is_used)


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


def test_fail_prepare_uses_repo_contract_even_when_engine_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _poison_session(monkeypatch)
    run = _make_run("run_prepare", RunStatus.pending)
    updated_runs: list[object] = []
    run_repo = SimpleNamespace(
        get_run=lambda run_id: run if run_id == "run_prepare" else None,
        update_run=lambda updated: updated_runs.append(updated),
    )

    store = ExecutionRunStore(run_repo=run_repo, engine=object())
    store.fail_prepare("run_prepare", RuntimeError("snapshot read failed"))

    assert run.status == RunStatus.failed
    assert run.error == "snapshot read failed"
    assert run.completed_at is not None
    assert updated_runs == [run]


def test_set_status_uses_repo_contract_even_when_engine_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _poison_session(monkeypatch)
    run = _make_run("run_status", RunStatus.pending)
    updated_runs: list[object] = []
    run_repo = SimpleNamespace(
        get_run=lambda run_id: run if run_id == "run_status" else None,
        update_run=lambda updated: updated_runs.append(updated),
    )

    store = ExecutionRunStore(run_repo=run_repo, engine=object())
    changed = store.set_status("run_status", RunStatus.running, error=RuntimeError("started"))

    assert changed is True
    assert run.status == RunStatus.running
    assert run.error == "started"
    assert run.updated_at is not None
    assert updated_runs == [run]


def test_store_branch_and_sha_uses_repo_contract_even_when_engine_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _poison_session(monkeypatch)
    run = _make_run("run_snapshot", RunStatus.pending)
    updated_runs: list[object] = []
    run_repo = SimpleNamespace(
        get_run=lambda run_id: run if run_id == "run_snapshot" else None,
        update_run=lambda updated: updated_runs.append(updated),
    )

    store = ExecutionRunStore(run_repo=run_repo, engine=object())
    store.store_branch_and_sha("run_snapshot", "feature/red", "abc123")

    assert run.branch == "feature/red"
    assert run.commit_sha == "abc123"
    assert run.updated_at is not None
    assert updated_runs == [run]


def test_is_run_cancelled_uses_repo_contract_even_when_engine_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _poison_session(monkeypatch)
    run_repo = SimpleNamespace(
        get_run=lambda run_id: _make_run(run_id, RunStatus.cancelled),
        update_run=lambda run: None,
    )

    store = ExecutionRunStore(run_repo=run_repo, engine=object())

    assert store.is_run_cancelled("run_cancelled") is True


@pytest.mark.parametrize(
    ("method_name", "run_repo", "args", "kwargs"),
    [
        (
            "fail_prepare",
            SimpleNamespace(update_run=lambda run: None),
            ("run_missing_get", RuntimeError("boom")),
            {},
        ),
        (
            "fail_prepare",
            SimpleNamespace(get_run=lambda run_id: _make_run(run_id, RunStatus.pending)),
            ("run_missing_update", RuntimeError("boom")),
            {},
        ),
        (
            "set_status",
            SimpleNamespace(update_run=lambda run: None),
            ("run_missing_get", RunStatus.running),
            {},
        ),
        (
            "set_status",
            SimpleNamespace(get_run=lambda run_id: _make_run(run_id, RunStatus.pending)),
            ("run_missing_update", RunStatus.running),
            {},
        ),
        (
            "store_branch_and_sha",
            SimpleNamespace(update_run=lambda run: None),
            ("run_missing_get", "feature/red", "abc123"),
            {},
        ),
        (
            "store_branch_and_sha",
            SimpleNamespace(get_run=lambda run_id: _make_run(run_id, RunStatus.pending)),
            ("run_missing_update", "feature/red", "abc123"),
            {},
        ),
        (
            "is_run_cancelled",
            SimpleNamespace(update_run=lambda run: None),
            ("run_missing_get",),
            {},
        ),
    ],
)
def test_lifecycle_methods_require_explicit_repo_collaborators(
    method_name: str,
    run_repo: object,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    store = ExecutionRunStore(run_repo=run_repo, engine=None)

    with pytest.raises(AttributeError):
        getattr(store, method_name)(*args, **kwargs)
