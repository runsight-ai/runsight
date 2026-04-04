"""Red tests for RUN-313: RunRepository.get_baseline() query.

Tests target the new baseline query method on RunRepository:
  - get_baseline(soul_id, soul_version, limit=100) -> BaselineStats | None
  - Returns None when no matching runs exist
  - Returns correct averages over matching RunNode records
  - Filters by both soul_id AND soul_version
  - Respects the limit parameter

Also tests the BaselineStats model itself.

All tests should FAIL until the implementation exists.
"""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import RunNode

# ---------------------------------------------------------------------------
# Deferred imports — BaselineStats and get_baseline do not exist yet
# ---------------------------------------------------------------------------


def _import_baseline_stats():
    from runsight_api.domain.entities.run import BaselineStats

    return BaselineStats


def _import_run_repository():
    from runsight_api.data.repositories.run_repo import RunRepository

    return RunRepository


# ---------------------------------------------------------------------------
# Fixture: in-memory DB
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# 1. BaselineStats model
# ---------------------------------------------------------------------------


class TestBaselineStatsModel:
    def test_avg_score_can_be_none(self):
        """BaselineStats.avg_score can be None (no eval data)."""
        BaselineStats = _import_baseline_stats()
        instance = BaselineStats(
            avg_cost=0.05,
            avg_tokens=1500.0,
            avg_score=None,
            run_count=5,
        )
        assert instance.avg_score is None


# ---------------------------------------------------------------------------
# 2. get_baseline — returns None when no runs
# ---------------------------------------------------------------------------


class TestGetBaselineNoData:
    def test_returns_none_when_no_matching_nodes(self, db_session):
        """get_baseline returns None when no RunNode matches soul_id + soul_version."""
        RunRepository = _import_run_repository()
        repo = RunRepository(db_session)
        result = repo.get_baseline("nonexistent_soul", "nonexistent_version")
        assert result is None


# ---------------------------------------------------------------------------
# 4. get_baseline — correct averages
# ---------------------------------------------------------------------------


class TestGetBaselineAverages:
    def _seed_nodes(self, session, soul_id, soul_version, costs, tokens, scores=None):
        """Insert RunNode records matching a given soul_id + soul_version."""
        for i, (cost, tok) in enumerate(zip(costs, tokens)):
            node = RunNode(
                id=f"run{i}:block{i}",
                run_id=f"run{i}",
                node_id=f"block{i}",
                block_type="LinearBlock",
                status="completed",
                soul_id=soul_id,
                soul_version=soul_version,
                cost_usd=cost,
                tokens={"total": tok},
            )
            if scores is not None:
                node.eval_score = scores[i]
            session.add(node)
        session.commit()

    def test_returns_correct_avg_cost(self, db_session):
        """get_baseline computes correct avg_cost over matching nodes."""
        RunRepository = _import_run_repository()
        self._seed_nodes(
            db_session,
            "soul_1",
            "v1hash",
            costs=[0.10, 0.20, 0.30],
            tokens=[100, 200, 300],
        )
        repo = RunRepository(db_session)
        stats = repo.get_baseline("soul_1", "v1hash")
        assert stats is not None
        assert stats.avg_cost == pytest.approx(0.20, abs=0.001)

    def test_returns_correct_avg_tokens(self, db_session):
        """get_baseline computes correct avg_tokens over matching nodes."""
        RunRepository = _import_run_repository()
        self._seed_nodes(
            db_session,
            "soul_1",
            "v1hash",
            costs=[0.10, 0.20, 0.30],
            tokens=[100, 200, 300],
        )
        repo = RunRepository(db_session)
        stats = repo.get_baseline("soul_1", "v1hash")
        assert stats is not None
        assert stats.avg_tokens == pytest.approx(200.0, abs=1.0)

    def test_returns_correct_avg_score(self, db_session):
        """get_baseline computes correct avg_score when eval_score is present."""
        RunRepository = _import_run_repository()
        self._seed_nodes(
            db_session,
            "soul_1",
            "v1hash",
            costs=[0.10, 0.20],
            tokens=[100, 200],
            scores=[0.80, 0.90],
        )
        repo = RunRepository(db_session)
        stats = repo.get_baseline("soul_1", "v1hash")
        assert stats is not None
        assert stats.avg_score == pytest.approx(0.85, abs=0.01)

    def test_avg_score_none_when_no_eval_scores(self, db_session):
        """get_baseline returns avg_score=None when no nodes have eval_score."""
        RunRepository = _import_run_repository()
        self._seed_nodes(
            db_session,
            "soul_1",
            "v1hash",
            costs=[0.10, 0.20],
            tokens=[100, 200],
        )
        repo = RunRepository(db_session)
        stats = repo.get_baseline("soul_1", "v1hash")
        assert stats is not None
        assert stats.avg_score is None

    def test_returns_correct_run_count(self, db_session):
        """get_baseline returns correct run_count."""
        RunRepository = _import_run_repository()
        self._seed_nodes(
            db_session,
            "soul_1",
            "v1hash",
            costs=[0.10, 0.20, 0.30],
            tokens=[100, 200, 300],
        )
        repo = RunRepository(db_session)
        stats = repo.get_baseline("soul_1", "v1hash")
        assert stats is not None
        assert stats.run_count == 3


# ---------------------------------------------------------------------------
# 5. get_baseline — filters by soul_id AND soul_version
# ---------------------------------------------------------------------------


class TestGetBaselineFiltering:
    def _seed_mixed_nodes(self, session):
        """Insert nodes with different soul_id / soul_version combos."""
        nodes = [
            # soul_1 / v1hash — target
            RunNode(
                id="r1:b1",
                run_id="r1",
                node_id="b1",
                block_type="L",
                soul_id="soul_1",
                soul_version="v1hash",
                cost_usd=0.10,
                tokens={"total": 100},
                status="completed",
            ),
            RunNode(
                id="r2:b2",
                run_id="r2",
                node_id="b2",
                block_type="L",
                soul_id="soul_1",
                soul_version="v1hash",
                cost_usd=0.20,
                tokens={"total": 200},
                status="completed",
            ),
            # soul_1 / v2hash — different version, should be excluded
            RunNode(
                id="r3:b3",
                run_id="r3",
                node_id="b3",
                block_type="L",
                soul_id="soul_1",
                soul_version="v2hash",
                cost_usd=1.00,
                tokens={"total": 9999},
                status="completed",
            ),
            # soul_2 / v1hash — different soul, should be excluded
            RunNode(
                id="r4:b4",
                run_id="r4",
                node_id="b4",
                block_type="L",
                soul_id="soul_2",
                soul_version="v1hash",
                cost_usd=2.00,
                tokens={"total": 8888},
                status="completed",
            ),
        ]
        for node in nodes:
            session.add(node)
        session.commit()

    def test_filters_by_soul_id_and_version(self, db_session):
        """get_baseline only includes nodes matching both soul_id AND soul_version."""
        RunRepository = _import_run_repository()
        self._seed_mixed_nodes(db_session)
        repo = RunRepository(db_session)
        stats = repo.get_baseline("soul_1", "v1hash")
        assert stats is not None
        # Should average over 0.10 and 0.20, not 1.00 or 2.00
        assert stats.run_count == 2
        assert stats.avg_cost == pytest.approx(0.15, abs=0.001)

    def test_different_version_returns_different_stats(self, db_session):
        """Querying a different soul_version returns that version's stats only."""
        RunRepository = _import_run_repository()
        self._seed_mixed_nodes(db_session)
        repo = RunRepository(db_session)
        stats = repo.get_baseline("soul_1", "v2hash")
        assert stats is not None
        assert stats.run_count == 1
        assert stats.avg_cost == pytest.approx(1.00, abs=0.001)


# ---------------------------------------------------------------------------
# 6. get_baseline — respects limit
# ---------------------------------------------------------------------------


class TestGetBaselineLimit:
    def test_limit_restricts_node_count(self, db_session):
        """get_baseline(... limit=2) only averages the most recent 2 nodes."""
        RunRepository = _import_run_repository()

        # Insert 5 nodes with increasing cost: 0.10, 0.20, 0.30, 0.40, 0.50
        for i in range(5):
            node = RunNode(
                id=f"r{i}:b{i}",
                run_id=f"r{i}",
                node_id=f"b{i}",
                block_type="LinearBlock",
                status="completed",
                soul_id="soul_1",
                soul_version="v1hash",
                cost_usd=0.10 * (i + 1),
                tokens={"total": 100 * (i + 1)},
                created_at=1000.0 + i,  # increasing time
            )
            db_session.add(node)
        db_session.commit()

        repo = RunRepository(db_session)
        stats = repo.get_baseline("soul_1", "v1hash", limit=2)
        assert stats is not None
        # With limit=2, should only consider the 2 most recent nodes
        assert stats.run_count == 2

    def test_default_limit_is_100(self, db_session):
        """get_baseline default limit is 100."""
        RunRepository = _import_run_repository()
        import inspect

        sig = inspect.signature(RunRepository.get_baseline)
        limit_param = sig.parameters.get("limit")
        assert limit_param is not None, "get_baseline must have a 'limit' parameter"
        assert limit_param.default == 100, "Default limit should be 100"
