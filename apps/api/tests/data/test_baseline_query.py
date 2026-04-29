"""RunReadModel.get_baseline() query.

Tests target the baseline query method on RunReadModel:
  - get_baseline(soul_id, soul_version, limit=100) -> BaselineStats | None
  - Returns None when no matching runs exist
  - Returns correct averages over matching RunNode records
  - Filters by both soul_id AND soul_version
  - Respects the limit parameter

Also tests the BaselineStats model itself.

"""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import RunNode

# ---------------------------------------------------------------------------
# Deferred imports — BaselineStats and RunReadModel are imported lazily for test isolation
# ---------------------------------------------------------------------------


def _import_baseline_stats():
    from runsight_api.domain.entities.run import BaselineStats

    return BaselineStats


def _import_run_read_model():
    from runsight_api.data.repositories.run_read_model import RunReadModel

    return RunReadModel


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
        RunReadModel = _import_run_read_model()
        read_model = RunReadModel(db_session)
        result = read_model.get_baseline("nonexistent_soul", "nonexistent_version")
        assert result is None


# ---------------------------------------------------------------------------
# 4. get_baseline — correct averages
# ---------------------------------------------------------------------------


class TestGetBaselineAverages:
    def _seed_nodes(self, session, soul_id, soul_version, costs, tokens, scores=None):
        """Insert RunNode records matching a given soul_id + soul_version."""
        for i, (cost, tok) in enumerate(zip(costs, tokens)):
            node = RunNode(
                id=f"baseline_run_{i}:baseline_block_{i}",
                run_id=f"baseline_run_{i}",
                node_id=f"baseline_block_{i}",
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
        RunReadModel = _import_run_read_model()
        self._seed_nodes(
            db_session,
            "baseline_soul",
            "baseline_version_hash",
            costs=[0.10, 0.20, 0.30],
            tokens=[100, 200, 300],
        )
        read_model = RunReadModel(db_session)
        stats = read_model.get_baseline("baseline_soul", "baseline_version_hash")
        assert stats is not None
        assert stats.avg_cost == pytest.approx(0.20, abs=0.001)

    def test_returns_correct_avg_tokens(self, db_session):
        """get_baseline computes correct avg_tokens over matching nodes."""
        RunReadModel = _import_run_read_model()
        self._seed_nodes(
            db_session,
            "baseline_soul",
            "baseline_version_hash",
            costs=[0.10, 0.20, 0.30],
            tokens=[100, 200, 300],
        )
        read_model = RunReadModel(db_session)
        stats = read_model.get_baseline("baseline_soul", "baseline_version_hash")
        assert stats is not None
        assert stats.avg_tokens == pytest.approx(200.0, abs=1.0)

    def test_returns_correct_avg_score(self, db_session):
        """get_baseline computes correct avg_score when eval_score is present."""
        RunReadModel = _import_run_read_model()
        self._seed_nodes(
            db_session,
            "baseline_soul",
            "baseline_version_hash",
            costs=[0.10, 0.20],
            tokens=[100, 200],
            scores=[0.80, 0.90],
        )
        read_model = RunReadModel(db_session)
        stats = read_model.get_baseline("baseline_soul", "baseline_version_hash")
        assert stats is not None
        assert stats.avg_score == pytest.approx(0.85, abs=0.01)

    def test_avg_score_none_when_no_eval_scores(self, db_session):
        """get_baseline returns avg_score=None when no nodes have eval_score."""
        RunReadModel = _import_run_read_model()
        self._seed_nodes(
            db_session,
            "baseline_soul",
            "baseline_version_hash",
            costs=[0.10, 0.20],
            tokens=[100, 200],
        )
        read_model = RunReadModel(db_session)
        stats = read_model.get_baseline("baseline_soul", "baseline_version_hash")
        assert stats is not None
        assert stats.avg_score is None

    def test_returns_correct_run_count(self, db_session):
        """get_baseline returns correct run_count."""
        RunReadModel = _import_run_read_model()
        self._seed_nodes(
            db_session,
            "baseline_soul",
            "baseline_version_hash",
            costs=[0.10, 0.20, 0.30],
            tokens=[100, 200, 300],
        )
        read_model = RunReadModel(db_session)
        stats = read_model.get_baseline("baseline_soul", "baseline_version_hash")
        assert stats is not None
        assert stats.run_count == 3


# ---------------------------------------------------------------------------
# 5. get_baseline — filters by soul_id AND soul_version
# ---------------------------------------------------------------------------


class TestGetBaselineFiltering:
    def _seed_mixed_nodes(self, session):
        """Insert nodes with different soul_id / soul_version combos."""
        nodes = [
            # baseline_soul / baseline_version_hash — target
            RunNode(
                id="target_baseline_run_first:target_baseline_block_first",
                run_id="target_baseline_run_first",
                node_id="target_baseline_block_first",
                block_type="L",
                soul_id="baseline_soul",
                soul_version="baseline_version_hash",
                cost_usd=0.10,
                tokens={"total": 100},
                status="completed",
            ),
            RunNode(
                id="target_baseline_run_second:target_baseline_block_second",
                run_id="target_baseline_run_second",
                node_id="target_baseline_block_second",
                block_type="L",
                soul_id="baseline_soul",
                soul_version="baseline_version_hash",
                cost_usd=0.20,
                tokens={"total": 200},
                status="completed",
            ),
            # baseline_soul / candidate_version_hash — different version, should be excluded
            RunNode(
                id="candidate_version_run:candidate_version_block",
                run_id="candidate_version_run",
                node_id="candidate_version_block",
                block_type="L",
                soul_id="baseline_soul",
                soul_version="candidate_version_hash",
                cost_usd=1.00,
                tokens={"total": 9999},
                status="completed",
            ),
            # comparison_soul / baseline_version_hash — different soul, should be excluded
            RunNode(
                id="comparison_soul_run:comparison_soul_block",
                run_id="comparison_soul_run",
                node_id="comparison_soul_block",
                block_type="L",
                soul_id="comparison_soul",
                soul_version="baseline_version_hash",
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
        RunReadModel = _import_run_read_model()
        self._seed_mixed_nodes(db_session)
        read_model = RunReadModel(db_session)
        stats = read_model.get_baseline("baseline_soul", "baseline_version_hash")
        assert stats is not None
        # Should average over 0.10 and 0.20, not 1.00 or 2.00
        assert stats.run_count == 2
        assert stats.avg_cost == pytest.approx(0.15, abs=0.001)

    def test_different_version_returns_different_stats(self, db_session):
        """Querying a different soul_version returns that version's stats only."""
        RunReadModel = _import_run_read_model()
        self._seed_mixed_nodes(db_session)
        read_model = RunReadModel(db_session)
        stats = read_model.get_baseline("baseline_soul", "candidate_version_hash")
        assert stats is not None
        assert stats.run_count == 1
        assert stats.avg_cost == pytest.approx(1.00, abs=0.001)


# ---------------------------------------------------------------------------
# 6. get_baseline — respects limit
# ---------------------------------------------------------------------------


class TestGetBaselineLimit:
    def test_limit_restricts_node_count(self, db_session):
        """get_baseline(... limit=2) only averages the most recent 2 nodes."""
        RunReadModel = _import_run_read_model()

        # Insert 5 nodes with increasing cost: 0.10, 0.20, 0.30, 0.40, 0.50
        for i in range(5):
            node = RunNode(
                id=f"limited_baseline_run_{i}:limited_baseline_block_{i}",
                run_id=f"limited_baseline_run_{i}",
                node_id=f"limited_baseline_block_{i}",
                block_type="LinearBlock",
                status="completed",
                soul_id="baseline_soul",
                soul_version="baseline_version_hash",
                cost_usd=0.10 * (i + 1),
                tokens={"total": 100 * (i + 1)},
                created_at=1000.0 + i,  # increasing time
            )
            db_session.add(node)
        db_session.commit()

        read_model = RunReadModel(db_session)
        stats = read_model.get_baseline("baseline_soul", "baseline_version_hash", limit=2)
        assert stats is not None
        # With limit=2, should only consider the 2 most recent nodes
        assert stats.run_count == 2

    def test_default_limit_is_100(self, db_session):
        """get_baseline default limit is 100."""
        RunReadModel = _import_run_read_model()
        import inspect

        sig = inspect.signature(RunReadModel.get_baseline)
        limit_param = sig.parameters.get("limit")
        assert limit_param is not None, "get_baseline must have a 'limit' parameter"
        assert limit_param.default == 100, "Default limit should be 100"
