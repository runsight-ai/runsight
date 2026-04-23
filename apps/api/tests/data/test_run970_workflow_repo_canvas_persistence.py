import json
import logging
from pathlib import Path

import pytest

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.domain.errors import InputValidationError


def _workflow_yaml(workflow_id: str, name: str) -> str:
    return (
        f"id: {workflow_id}\n"
        "kind: workflow\n"
        "version: '1.0'\n"
        "blocks: {}\n"
        "workflow:\n"
        f"  name: {name}\n"
        "  entry: start\n"
        "  transitions: []\n"
    )


def _canvas_state(node_id: str) -> dict:
    return {
        "nodes": [{"id": node_id, "position": {"x": 10, "y": 20}}],
        "edges": [],
        "viewport": {"x": 0.0, "y": 0.0, "zoom": 1.0},
        "selected_node_id": node_id,
        "canvas_mode": "dag",
    }


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _assert_persisted_revision(
    repo: WorkflowRepository,
    workflow_id: str,
    entity,
    expected_yaml: str,
    expected_canvas: dict,
) -> None:
    assert entity.id == workflow_id
    assert entity.yaml == expected_yaml
    assert entity.canvas_state == expected_canvas
    assert repo._get_path(workflow_id).read_text() == expected_yaml
    assert _read_json(repo._canvas_path(workflow_id)) == expected_canvas


def _install_sidecar_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    repo: WorkflowRepository,
    workflow_id: str,
    message: str = "simulated canvas write failure",
) -> None:
    real_atomic_write = repo._atomic_write
    canvas_path = repo._canvas_path(workflow_id)

    def fail_canvas_atomic_write(path: Path, content: str) -> None:
        if path == canvas_path:
            raise OSError(message)
        real_atomic_write(path, content)

    monkeypatch.setattr(repo, "_atomic_write", fail_canvas_atomic_write)


def _capture_sidecar_failure(save_call) -> InputValidationError | None:
    try:
        save_call()
    except InputValidationError as exc:
        return exc
    return None


def test_update_without_canvas_state_keeps_existing_sidecar_and_succeeds(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_id = "canvas-omitted-update"
    original_canvas = _canvas_state("original-node")
    updated_yaml = _workflow_yaml(workflow_id, "Updated Without Canvas")

    repo.create(
        {
            "yaml": _workflow_yaml(workflow_id, "Original"),
            "canvas_state": original_canvas,
        }
    )

    updated = repo.update(workflow_id, {"yaml": updated_yaml})

    assert updated.id == workflow_id
    assert repo._get_path(workflow_id).read_text() == updated_yaml
    assert _read_json(repo._canvas_path(workflow_id)) == original_canvas


def test_create_persists_yaml_and_canvas_sidecar_when_canvas_state_in_scope(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_id = "create-canvas-success"
    requested_yaml = _workflow_yaml(workflow_id, "Create Success")
    requested_canvas = _canvas_state("node-create-success")

    created = repo.create({"yaml": requested_yaml, "canvas_state": requested_canvas})

    _assert_persisted_revision(
        repo,
        workflow_id,
        created,
        requested_yaml,
        requested_canvas,
    )


def test_update_persists_yaml_and_canvas_sidecar_when_canvas_state_in_scope(tmp_path) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_id = "update-canvas-success"
    repo.create(
        {
            "yaml": _workflow_yaml(workflow_id, "Original"),
            "canvas_state": _canvas_state("node-original"),
        }
    )
    requested_yaml = _workflow_yaml(workflow_id, "Update Success")
    requested_canvas = _canvas_state("node-update-success")

    updated = repo.update(
        workflow_id,
        {"yaml": requested_yaml, "canvas_state": requested_canvas},
    )

    _assert_persisted_revision(
        repo,
        workflow_id,
        updated,
        requested_yaml,
        requested_canvas,
    )


def test_create_raises_when_canvas_sidecar_persistence_fails(tmp_path, monkeypatch) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_id = "create-sidecar-failure"
    _install_sidecar_write_failure(monkeypatch, repo, workflow_id)

    error = _capture_sidecar_failure(
        lambda: repo.create(
            {
                "yaml": _workflow_yaml(workflow_id, "Create Failure"),
                "canvas_state": _canvas_state("node-create"),
            }
        )
    )

    assert isinstance(error, InputValidationError)
    assert "simulated canvas write failure" in str(error)


def test_create_rolls_back_yaml_when_canvas_sidecar_persistence_fails(
    tmp_path, monkeypatch
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_id = "create-rolls-back"
    yaml_path = repo._get_path(workflow_id)
    canvas_path = repo._canvas_path(workflow_id)
    _install_sidecar_write_failure(monkeypatch, repo, workflow_id)

    _capture_sidecar_failure(
        lambda: repo.create(
            {
                "yaml": _workflow_yaml(workflow_id, "Create Rollback"),
                "canvas_state": _canvas_state("node-create"),
            }
        )
    )

    assert not yaml_path.exists()
    assert not canvas_path.exists()


def test_update_raises_when_canvas_sidecar_persistence_fails(tmp_path, monkeypatch) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_id = "update-sidecar-failure"
    repo.create(
        {
            "yaml": _workflow_yaml(workflow_id, "Original"),
            "canvas_state": _canvas_state("node-original"),
        }
    )
    _install_sidecar_write_failure(monkeypatch, repo, workflow_id)

    error = _capture_sidecar_failure(
        lambda: repo.update(
            workflow_id,
            {
                "yaml": _workflow_yaml(workflow_id, "Updated"),
                "canvas_state": _canvas_state("node-updated"),
            },
        )
    )

    assert isinstance(error, InputValidationError)
    assert "simulated canvas write failure" in str(error)


def test_update_preserves_prior_yaml_and_canvas_when_sidecar_persistence_fails(
    tmp_path, monkeypatch
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_id = "update-preserves-prior-state"
    original_yaml = _workflow_yaml(workflow_id, "Original")
    original_canvas = _canvas_state("node-original")
    yaml_path = repo._get_path(workflow_id)
    canvas_path = repo._canvas_path(workflow_id)
    repo.create({"yaml": original_yaml, "canvas_state": original_canvas})
    _install_sidecar_write_failure(monkeypatch, repo, workflow_id)

    _capture_sidecar_failure(
        lambda: repo.update(
            workflow_id,
            {
                "yaml": _workflow_yaml(workflow_id, "Updated"),
                "canvas_state": _canvas_state("node-updated"),
            },
        )
    )

    assert yaml_path.read_text() == original_yaml
    assert _read_json(canvas_path) == original_canvas


def test_update_preserves_original_sidecar_failure_when_restore_also_fails(
    tmp_path, monkeypatch, caplog
) -> None:
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_id = "update-restore-failure"
    original_yaml = _workflow_yaml(workflow_id, "Original")
    original_canvas = _canvas_state("node-original")
    repo.create({"yaml": original_yaml, "canvas_state": original_canvas})
    _install_sidecar_write_failure(monkeypatch, repo, workflow_id)

    def fail_restore(*_args, **_kwargs) -> None:
        raise OSError("restore failed")

    monkeypatch.setattr(repo, "_restore_canvas_sidecar", fail_restore)

    with caplog.at_level(logging.WARNING):
        error = _capture_sidecar_failure(
            lambda: repo.update(
                workflow_id,
                {
                    "yaml": _workflow_yaml(workflow_id, "Updated"),
                    "canvas_state": _canvas_state("node-updated"),
                },
            )
        )

    assert isinstance(error, InputValidationError)
    assert "simulated canvas write failure" in str(error)
    assert any(
        "Failed to restore workflow canvas sidecar after sidecar failure" in record.message
        for record in caplog.records
    )
