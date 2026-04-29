"""Run list numbering and eval aggregation."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode


def _import_run_read_model():
    from runsight_api.data.repositories.run_read_model import RunReadModel

    return RunReadModel


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


class TestRunReadModelListMetrics:
    def test_list_runs_paginated_assigns_per_workflow_run_numbers_and_eval_pass_pct(
        self,
        db_session: Session,
    ):
        """Each list item should expose workflow-local sequence and eval aggregate."""
        RunReadModel = _import_run_read_model()

        _seed_run(
            db_session,
            "alpha_run_early",
            workflow_id="alpha_workflow",
            workflow_name="Alpha",
            created_at=100.0,
        )
        _seed_node(db_session, "alpha_run_early", "primary_eval_node", eval_passed=True)
        _seed_node(db_session, "alpha_run_early", "secondary_eval_node", eval_passed=False)

        _seed_run(
            db_session,
            "alpha_run_late",
            workflow_id="alpha_workflow",
            workflow_name="Alpha",
            created_at=200.0,
        )
        _seed_node(db_session, "alpha_run_late", "primary_eval_node", eval_passed=True)
        _seed_node(db_session, "alpha_run_late", "secondary_eval_node", eval_passed=True)

        _seed_run(
            db_session,
            "beta_run",
            workflow_id="beta_workflow",
            workflow_name="Beta",
            created_at=150.0,
        )
        db_session.commit()

        read_model = RunReadModel(db_session)
        items, total = read_model.list_runs_paginated(offset=0, limit=10)

        assert total == 3
        assert [run.id for run in items] == ["alpha_run_late", "beta_run", "alpha_run_early"]

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
        """Filters must still work unchanged on enriched list items."""
        RunReadModel = _import_run_read_model()

        _seed_run(
            db_session,
            "kept_manual_run",
            workflow_id="alpha_workflow",
            workflow_name="Alpha",
            created_at=300.0,
            source="manual",
            branch="main",
        )
        _seed_node(db_session, "kept_manual_run", "primary_eval_node", eval_passed=True)

        _seed_run(
            db_session,
            "filtered_simulation_run",
            workflow_id="alpha_workflow",
            workflow_name="Alpha",
            created_at=250.0,
            source="simulation",
            branch="main",
        )
        _seed_run(
            db_session,
            "filtered_branch_run",
            workflow_id="alpha_workflow",
            workflow_name="Alpha",
            created_at=200.0,
            source="manual",
            branch="feat/demo",
        )
        db_session.commit()

        read_model = RunReadModel(db_session)
        items, total = read_model.list_runs_paginated(
            offset=0,
            limit=10,
            source=["manual"],
            branch="main",
        )

        assert total == 1
        assert [run.id for run in items] == ["kept_manual_run"]
        assert items[0].run_number == 1
        assert items[0].eval_pass_pct == pytest.approx(100.0)

    def test_list_runs_paginated_keeps_simulation_runs_when_no_source_filter_is_provided(
        self,
        db_session: Session,
    ):
        """Unfiltered lists must keep simulation runs instead of excluding them by default."""
        RunReadModel = _import_run_read_model()

        _seed_run(
            db_session,
            "manual_alpha_run",
            workflow_id="alpha_workflow",
            workflow_name="Alpha",
            created_at=100.0,
            source="manual",
        )
        _seed_node(db_session, "manual_alpha_run", "primary_eval_node", eval_passed=True)

        _seed_run(
            db_session,
            "simulation_alpha_run",
            workflow_id="alpha_workflow",
            workflow_name="Alpha",
            created_at=200.0,
            source="simulation",
        )
        _seed_node(db_session, "simulation_alpha_run", "primary_eval_node", eval_passed=False)
        db_session.commit()

        read_model = RunReadModel(db_session)
        items, total = read_model.list_runs_paginated(offset=0, limit=10)

        assert total == 2
        assert [run.id for run in items] == ["simulation_alpha_run", "manual_alpha_run"]
        assert items[0].source == "simulation"
        assert items[0].run_number == 2
        assert items[0].eval_pass_pct == pytest.approx(0.0)
        assert items[1].source == "manual"
        assert items[1].run_number == 1
        assert items[1].eval_pass_pct == pytest.approx(100.0)
