import pytest
from pydantic import ValidationError
from sqlmodel import Session

from tests.domain.run_entity_factories import (
    EXPLICIT_BRANCH,
    in_memory_engine,
    make_run,
)


def test_run_status_defaults_to_pending_and_matches_wire_values():
    from runsight_api.domain.entities.run import RunStatus

    assert {status.value for status in RunStatus} == {
        "pending",
        "running",
        "completed",
        "failed",
        "cancelled",
    }
    assert make_run(id="run-default-status").status == RunStatus.pending


def test_run_requires_explicit_branch_and_persists_branch():
    from runsight_api.domain.entities.run import Run

    with pytest.raises(ValidationError):
        Run(
            id="run-branch-required",
            workflow_id="workflow-data-model",
            workflow_name="Data model workflow",
            task_json='{"instruction": "summarize research notes"}',
        )

    engine = in_memory_engine()
    with Session(engine) as session:
        session.add(make_run(branch="sim/test/20260329/abc", id="run-branch-db"))
        session.commit()

    with Session(engine) as session:
        loaded = session.get(Run, "run-branch-db")
        assert loaded is not None
        assert loaded.branch == "sim/test/20260329/abc"


def test_run_source_defaults_accepts_known_values_and_persists():
    from runsight_api.domain.entities.run import Run

    assert make_run(branch=EXPLICIT_BRANCH).source == "manual"
    assert make_run(source="simulation").source == "simulation"
    assert make_run(source="webhook").source == "webhook"
    assert make_run(source="schedule").source == "schedule"

    engine = in_memory_engine()
    with Session(engine) as session:
        session.add(make_run(id="run-source-db", source="webhook"))
        session.commit()

    with Session(engine) as session:
        loaded = session.get(Run, "run-source-db")
        assert loaded is not None
        assert loaded.source == "webhook"


def test_run_commit_sha_is_canonical_optional_persisted_field():
    from runsight_api.domain.entities.run import Run

    sha = "abc123def456789012345678901234567890abcd"
    run = make_run(id="run-sha", commit_sha=sha)
    assert run.commit_sha == sha
    assert "workflow_commit_sha" not in Run.model_fields
    assert not hasattr(run, "workflow_commit_sha")
    assert not hasattr(run, "effective_commit_sha")

    engine = in_memory_engine()
    with Session(engine) as session:
        session.add(make_run(id="run-sha-db", commit_sha=sha))
        session.add(make_run(id="run-sha-none"))
        session.commit()

    with Session(engine) as session:
        assert session.get(Run, "run-sha-db").commit_sha == sha
        assert session.get(Run, "run-sha-none").commit_sha is None


def test_run_warnings_round_trip_as_json():
    from runsight_api.domain.entities.run import Run

    warnings = [
        {
            "message": "Tool definition warning",
            "source": "tool_definitions",
            "context": "fetcher",
        }
    ]
    engine = in_memory_engine()
    with Session(engine) as session:
        session.add(make_run(id="run-warnings-db", warnings_json=warnings))
        session.commit()

    with Session(engine) as session:
        loaded = session.get(Run, "run-warnings-db")
        assert loaded is not None
        assert loaded.warnings_json == warnings
