"""Behavior-only identity-message smoke coverage."""

from __future__ import annotations

import json
import logging
from unittest.mock import Mock

import pytest
from runsight_core.observer import LoggingObserver
from runsight_core.state import WorkflowState
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.log import LogEntry
from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.domain.errors import SoulInUse, SoulNotFound
from runsight_api.domain.value_objects import SoulEntity, WorkflowEntity
from runsight_api.logic.observers.execution_observer import ExecutionObserver
from runsight_api.logic.services.soul_service import SoulService


def _workflow_entity(id: str, name: str, yaml: str | None) -> WorkflowEntity:
    return WorkflowEntity(kind="workflow", id=id, name=name, yaml=yaml)


def test_soul_service_missing_soul_errors_use_kind_qualified_refs() -> None:
    soul_repo = Mock()
    soul_repo.get_by_id.return_value = None
    service = SoulService(soul_repo)

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
            "workflow_review_one",
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
                branch="main",
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
