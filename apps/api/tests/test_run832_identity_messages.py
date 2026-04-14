from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import Mock

import pytest
from runsight_core.observer import LoggingObserver
from runsight_core.state import WorkflowState
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.errors import SoulInUse, SoulNotFound
from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.domain.value_objects import SoulEntity, WorkflowEntity
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_api.logic.services.soul_service import SoulService


def _workflow_entity(id: str, name: str, yaml: str | None) -> WorkflowEntity:
    return WorkflowEntity(kind="workflow", id=id, name=name, yaml=yaml)


def make_service() -> tuple[Mock, SoulService]:
    soul_repo = Mock()
    service = SoulService(soul_repo)
    return soul_repo, service


def test_router_and_data_layer_identity_errors_use_qualified_refs() -> None:
    api_src = Path(__file__).resolve().parents[1] / "src" / "runsight_api"
    forbidden_snippets = {
        api_src / "data/filesystem/provider_repo.py": (
            "Provider with id",
            "Provider {provider_id} not found",
            "Provider id {update_id!r} does not match requested id {provider_id!r}",
        ),
        api_src / "data/filesystem/workflow_repo.py": (
            "Workflow {workflow_id} not found",
            "Workflow {stem} already exists",
        ),
        api_src / "data/filesystem/_base_yaml_repo.py": (
            "{self.entity_label} {id} not found",
            "{self.entity_label} id {entity_id!r} does not match requested id {id!r}",
        ),
        api_src / "data/repositories/run_repo.py": ("Workflow {workflow_id} has active runs",),
        api_src / "logic/services/execution_service.py": (
            "Workflow {workflow_id} not found",
            "provider '{provider_id}'",
        ),
        api_src / "logic/services/run_service.py": ("Workflow {workflow_id} not found",),
        api_src / "transport/routers/settings.py": ("Provider {provider_id} not found",),
        api_src / "transport/routers/workflows.py": ("Workflow {id} not found",),
        api_src / "transport/routers/souls.py": ("Soul {id} not found",),
    }

    for source_path, snippets in forbidden_snippets.items():
        source = source_path.read_text()
        for snippet in snippets:
            assert snippet not in source, (
                f"{source_path} still contains a bare YAML identity template: {snippet}"
            )


def test_soul_service_missing_soul_errors_use_kind_qualified_refs() -> None:
    soul_repo, service = make_service()
    soul_repo.get_by_id.return_value = None

    with pytest.raises(SoulNotFound, match=r"soul:missing"):
        service.get_soul_usages("missing", workflow_repo=Mock())

    with pytest.raises(SoulNotFound, match=r"soul:missing"):
        service.update_soul("missing", {"role": "New"})

    with pytest.raises(SoulNotFound, match=r"soul:missing"):
        service.delete_soul("missing")


def test_soul_service_delete_in_use_message_mentions_kind_qualified_soul_ref() -> None:
    soul_repo = Mock()
    workflow_repo = Mock()
    soul_repo.get_by_id.return_value = SoulEntity(
        id="reviewer",
        kind="soul",
        name="Reviewer",
        role="Reviewer",
    )
    workflow_repo.list_all.return_value = [
        _workflow_entity(
            "wf_1",
            "Review One",
            """
blocks:
  one:
    type: linear
    soul_ref: reviewer
""",
        )
    ]
    service = SoulService(soul_repo)

    with pytest.raises(SoulInUse, match=r"soul:reviewer"):
        service.delete_soul("reviewer", workflow_repo=workflow_repo)


def test_logging_observer_workflow_start_keeps_display_names_raw(caplog) -> None:
    observer = LoggingObserver(level=logging.INFO)

    with caplog.at_level(logging.INFO, logger="runsight.workflow"):
        observer.on_workflow_start("Research & Review", WorkflowState())

    assert "[Research & Review] Workflow started" in caplog.text
    assert "workflow:Research & Review" not in caplog.text


def test_execution_observer_workflow_start_persists_raw_display_name_ref() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    run_id = "run_observer_identity"

    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="research-review",
                workflow_name="Research & Review",
                status=RunStatus.pending,
                task_json="{}",
            )
        )
        session.commit()

    observer = ExecutionObserver(engine=engine, run_id=run_id)
    observer.on_workflow_start("Research & Review", WorkflowState())

    with Session(engine) as session:
        rows = session.exec(
            select(LogEntry).where(LogEntry.run_id == run_id).where(LogEntry.level == "info")
        ).all()

    assert rows, "Expected on_workflow_start to persist an info log entry"
    payload = json.loads(rows[-1].message)
    assert payload["workflow_name"] == "Research & Review"
    assert payload["workflow_ref"] == "Research & Review"
    assert "workflow:Research & Review" not in rows[-1].message
