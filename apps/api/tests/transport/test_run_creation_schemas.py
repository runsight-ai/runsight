import pytest
from pydantic import ValidationError

from tests.domain.run_entity_factories import EXPLICIT_BRANCH


def test_run_response_requires_branch_and_serializes_execution_identity_fields():
    from runsight_api.transport.schemas.runs import RunResponse

    with pytest.raises(ValidationError):
        RunResponse(
            id="run-response",
            workflow_id="workflow-data-model",
            workflow_name="Data model workflow",
            status="pending",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            total_cost_usd=0.0,
            total_tokens=0,
            created_at=1711699200.0,
            source="simulation",
            commit_sha="abc123",
        )

    resp = RunResponse(
        id="run-response",
        workflow_id="workflow-data-model",
        workflow_name="Data model workflow",
        status="pending",
        started_at=None,
        completed_at=None,
        duration_seconds=None,
        total_cost_usd=0.0,
        total_tokens=0,
        created_at=1711699200.0,
        branch="feat/test",
        source="simulation",
        commit_sha="abc123",
    )
    assert resp.branch == "feat/test"
    assert resp.source == "simulation"
    assert resp.commit_sha == "abc123"


def test_run_response_serializes_workflow_warnings():
    from runsight_api.transport.schemas.runs import RunResponse
    from runsight_api.transport.schemas.workflows import WarningItem

    warning = WarningItem(
        message="Tool definition warning",
        source="tool_definitions",
        context="fetcher",
    )
    resp = RunResponse(
        id="run-response",
        workflow_id="workflow-data-model",
        workflow_name="Data model workflow",
        status="pending",
        started_at=None,
        completed_at=None,
        duration_seconds=None,
        total_cost_usd=0.0,
        total_tokens=0,
        created_at=1711699200.0,
        branch=EXPLICIT_BRANCH,
        warnings=[warning],
    )

    assert resp.warnings == [warning]


def test_run_create_accepts_optional_branch_and_source():
    from runsight_api.transport.schemas.runs import RunCreate

    fields = RunCreate.model_fields
    assert fields["branch"].default is None
    assert not fields["branch"].is_required()
    assert "source" in fields

    assert RunCreate(workflow_id="workflow-data-model").branch is None
    assert (
        RunCreate(
            workflow_id="workflow-data-model",
            branch=EXPLICIT_BRANCH,
            source="webhook",
        ).source
        == "webhook"
    )
