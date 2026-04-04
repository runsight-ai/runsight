"""Red tests for RUN-479 run list numbering and eval aggregation."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode


def _import_run_repository():
    from runsight_api.data.repositories.run_repo import RunRepository

    return RunRepository


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
    workflow_id: str,
    workflow_name: str,
    created_at: float,
    source: str = "manual",
    branch: str = "main",
) -> None:
    session.add(
        Run(
            id=run_id,
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            task_json="{}",
            source=source,
            branch=branch,
            created_at=created_at,
            updated_at=created_at,
        )
    )


def _seed_node(
    session: Session,
    run_id: str,
    node_id: str,
    *,
    eval_passed: bool | None,
) -> None:
    session.add(
        RunNode(
            id=f"{run_id}:{node_id}",
            run_id=run_id,
            node_id=node_id,
            block_type="llm",
            status="completed",
            eval_passed=eval_passed,
        )
    )


class TestRunRepositoryListMetrics:
    def test_list_runs_paginated_assigns_per_workflow_run_numbers_and_eval_pass_pct(
        self,
        db_session: Session,
    ):
        """Each list item should expose workflow-local sequence and eval aggregate."""
        RunRepository = _import_run_repository()

        _seed_run(
            db_session,
            "run_old",
            workflow_id="wf_alpha",
            workflow_name="Alpha",
            created_at=100.0,
        )
        _seed_node(db_session, "run_old", "node_1", eval_passed=True)
        _seed_node(db_session, "run_old", "node_2", eval_passed=False)

        _seed_run(
            db_session,
            "run_new",
            workflow_id="wf_alpha",
            workflow_name="Alpha",
            created_at=200.0,
        )
        _seed_node(db_session, "run_new", "node_1", eval_passed=True)
        _seed_node(db_session, "run_new", "node_2", eval_passed=True)

        _seed_run(
            db_session,
            "run_other",
            workflow_id="wf_beta",
            workflow_name="Beta",
            created_at=150.0,
        )
        db_session.commit()

        repo = RunRepository(db_session)
        items, total = repo.list_runs_paginated(offset=0, limit=10)

        assert total == 3
        assert [run.id for run in items] == ["run_new", "run_other", "run_old"]

        assert items[0].run_number == 2
        assert items[0].eval_pass_pct == pytest.approx(100.0)

        assert items[1].run_number == 1
        assert items[1].eval_pass_pct is None

        assert items[2].run_number == 1
        assert items[2].eval_pass_pct == pytest.approx(50.0)

    def test_list_runs_paginated_preserves_existing_source_and_branch_filters_while_enriching(
        self,
        db_session: Session,
    ):
        """RUN-378 filters must still work unchanged on enriched list items."""
        RunRepository = _import_run_repository()

        _seed_run(
            db_session,
            "run_keep",
            workflow_id="wf_alpha",
            workflow_name="Alpha",
            created_at=300.0,
            source="manual",
            branch="main",
        )
        _seed_node(db_session, "run_keep", "node_1", eval_passed=True)

        _seed_run(
            db_session,
            "run_wrong_source",
            workflow_id="wf_alpha",
            workflow_name="Alpha",
            created_at=250.0,
            source="simulation",
            branch="main",
        )
        _seed_run(
            db_session,
            "run_wrong_branch",
            workflow_id="wf_alpha",
            workflow_name="Alpha",
            created_at=200.0,
            source="manual",
            branch="feat/demo",
        )
        db_session.commit()

        repo = RunRepository(db_session)
        items, total = repo.list_runs_paginated(
            offset=0,
            limit=10,
            source=["manual"],
            branch="main",
        )

        assert total == 1
        assert [run.id for run in items] == ["run_keep"]
        assert items[0].run_number == 1
        assert items[0].eval_pass_pct == pytest.approx(100.0)

    def test_list_runs_paginated_keeps_simulation_runs_when_no_source_filter_is_provided(
        self,
        db_session: Session,
    ):
        """Unfiltered lists must keep simulation runs instead of excluding them by default."""
        RunRepository = _import_run_repository()

        _seed_run(
            db_session,
            "run_manual",
            workflow_id="wf_alpha",
            workflow_name="Alpha",
            created_at=100.0,
            source="manual",
        )
        _seed_node(db_session, "run_manual", "node_1", eval_passed=True)

        _seed_run(
            db_session,
            "run_sim",
            workflow_id="wf_alpha",
            workflow_name="Alpha",
            created_at=200.0,
            source="simulation",
        )
        _seed_node(db_session, "run_sim", "node_1", eval_passed=False)
        db_session.commit()

        repo = RunRepository(db_session)
        items, total = repo.list_runs_paginated(offset=0, limit=10)

        assert total == 2
        assert [run.id for run in items] == ["run_sim", "run_manual"]
        assert items[0].source == "simulation"
        assert items[0].run_number == 2
        assert items[0].eval_pass_pct == pytest.approx(0.0)
        assert items[1].source == "manual"
        assert items[1].run_number == 1
        assert items[1].eval_pass_pct == pytest.approx(100.0)
