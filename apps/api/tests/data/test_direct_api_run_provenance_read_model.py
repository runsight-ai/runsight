"""Direct API run provenance read-model coverage."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run

COMMITTED_MAIN_SHA = "abc123def4567890abc123def4567890abc123de"


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_run(
    session: Session,
    run_id: str,
    *,
    workflow_id: str = "wf-direct-provenance",
    workflow_name: str = "Direct API Workflow",
    created_at: float,
    source: str = "manual",
    branch: str = "main",
    commit_sha: str | None = None,
    source_correlation_id: str | None = None,
    source_metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        Run(
            id=run_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            task_json="{}",
            source=source,
            branch=branch,
            commit_sha=commit_sha,
            source_correlation_id=source_correlation_id,
            source_metadata=source_metadata,
            created_at=created_at,
            updated_at=created_at,
        )
    )


class TestDirectApiRunReadModelProvenance:
    def test_list_runs_paginated_preserves_api_provenance_and_old_run_defaults(
        self,
        db_session: Session,
    ) -> None:
        """Read models should distinguish API runs while keeping old rows readable."""
        from runsight_api.data.repositories.run_read_model import RunReadModel

        _seed_run(
            db_session,
            "run-manual-old",
            created_at=100.0,
            source="legacy-runner",
            branch="main",
        )
        _seed_run(
            db_session,
            "run-simulation",
            created_at=200.0,
            source="simulation",
            branch="sim/direct-provenance",
        )
        _seed_run(
            db_session,
            "run-api",
            created_at=300.0,
            source="api",
            branch="main",
            commit_sha=COMMITTED_MAIN_SHA,
            source_correlation_id="corr-direct-provenance",
            source_metadata={
                "entry_path": "direct_api",
                "client_request_id": "req-direct-provenance",
            },
        )
        db_session.commit()

        read_model = RunReadModel(db_session)
        api_items, api_total = read_model.list_runs_paginated(
            offset=0,
            limit=10,
            source=["api"],
        )
        all_items, all_total = read_model.list_runs_paginated(offset=0, limit=10)

        assert api_total == 1
        assert [run.id for run in api_items] == ["run-api"]
        assert api_items[0].source == "api"
        assert api_items[0].branch == "main"
        assert api_items[0].commit_sha == COMMITTED_MAIN_SHA
        assert api_items[0].source_correlation_id == "corr-direct-provenance"
        assert api_items[0].source_metadata == {
            "entry_path": "direct_api",
            "client_request_id": "req-direct-provenance",
        }

        assert all_total == 3
        old_run = next(run for run in all_items if run.id == "run-manual-old")
        assert old_run.source == "legacy-runner"
        assert old_run.source_correlation_id is None
        assert old_run.source_metadata == {}

        simulation_run = next(run for run in all_items if run.id == "run-simulation")
        assert simulation_run.source == "simulation"
