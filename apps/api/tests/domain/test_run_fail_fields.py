from sqlmodel import Session

from tests.domain.run_entity_factories import in_memory_engine, make_run
from runsight_api.domain.entities.run import Run, RunStatus


def test_budget_fail_reason_and_metadata_default_to_none():
    run = make_run(id="run-without-budget-failure")

    assert run.fail_reason is None
    assert run.fail_metadata is None


def test_budget_fail_metadata_round_trips_with_existing_error_fields():
    metadata = {
        "scope": "block",
        "block_id": "budgeted-block",
        "limit_kind": "cost_usd",
        "limit_value": 0.5,
        "actual_value": 0.75,
    }
    engine = in_memory_engine()
    with Session(engine) as session:
        session.add(
            make_run(
                id="run-with-budget-error-fields",
                status=RunStatus.failed,
                error="Budget limit exceeded",
                error_traceback="Traceback (most recent call last):\n  ...",
                fail_reason="budget_exceeded",
                fail_metadata=metadata,
            )
        )
        session.commit()

    with Session(engine) as session:
        loaded = session.get(Run, "run-with-budget-error-fields")
        assert loaded is not None
        assert loaded.status == RunStatus.failed
        assert loaded.error is not None
        assert loaded.error_traceback is not None
        assert loaded.fail_reason == "budget_exceeded"
        assert loaded.fail_metadata == metadata
