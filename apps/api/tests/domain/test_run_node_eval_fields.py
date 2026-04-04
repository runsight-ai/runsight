"""Red tests for RUN-313: New RunNode fields — prompt_hash, soul_version, eval_*.

Tests target new fields on RunNode model:
  - prompt_hash: str | None
  - soul_version: str | None
  - eval_score: float | None
  - eval_passed: bool | None
  - eval_results: dict | None  (JSON blob)

All tests should FAIL until the implementation exists.
"""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import RunNode

# ---------------------------------------------------------------------------
# Fixture: in-memory DB with RunNode table
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# 1. Field existence on the model
# ---------------------------------------------------------------------------


class TestRunNodeFieldExistence:
    def test_has_prompt_hash_field(self):
        """RunNode model has a prompt_hash field."""
        assert hasattr(RunNode, "prompt_hash"), "RunNode must have prompt_hash field"

    def test_has_soul_version_field(self):
        """RunNode model has a soul_version field."""
        assert hasattr(RunNode, "soul_version"), "RunNode must have soul_version field"

    def test_has_eval_score_field(self):
        """RunNode model has an eval_score field."""
        assert hasattr(RunNode, "eval_score"), "RunNode must have eval_score field"

    def test_has_eval_passed_field(self):
        """RunNode model has an eval_passed field."""
        assert hasattr(RunNode, "eval_passed"), "RunNode must have eval_passed field"

    def test_has_eval_results_field(self):
        """RunNode model has an eval_results field."""
        assert hasattr(RunNode, "eval_results"), "RunNode must have eval_results field"


# ---------------------------------------------------------------------------
# 2. Default values are None
# ---------------------------------------------------------------------------


class TestRunNodeFieldDefaults:
    def test_prompt_hash_defaults_to_none(self):
        """prompt_hash defaults to None when not provided."""
        node = RunNode(id="run1:b1", run_id="run1", node_id="b1", block_type="LinearBlock")
        assert node.prompt_hash is None

    def test_soul_version_defaults_to_none(self):
        """soul_version defaults to None when not provided."""
        node = RunNode(id="run1:b1", run_id="run1", node_id="b1", block_type="LinearBlock")
        assert node.soul_version is None

    def test_eval_score_defaults_to_none(self):
        """eval_score defaults to None when not provided."""
        node = RunNode(id="run1:b1", run_id="run1", node_id="b1", block_type="LinearBlock")
        assert node.eval_score is None

    def test_eval_passed_defaults_to_none(self):
        """eval_passed defaults to None when not provided."""
        node = RunNode(id="run1:b1", run_id="run1", node_id="b1", block_type="LinearBlock")
        assert node.eval_passed is None

    def test_eval_results_defaults_to_none(self):
        """eval_results defaults to None when not provided."""
        node = RunNode(id="run1:b1", run_id="run1", node_id="b1", block_type="LinearBlock")
        assert node.eval_results is None


# ---------------------------------------------------------------------------
# 3. Can be created with explicit values
# ---------------------------------------------------------------------------


class TestRunNodeFieldCreation:
    def test_create_with_prompt_hash(self):
        """RunNode can be instantiated with prompt_hash value."""
        node = RunNode(
            id="run1:b1",
            run_id="run1",
            node_id="b1",
            block_type="LinearBlock",
            prompt_hash="abc123def456",
        )
        assert node.prompt_hash == "abc123def456"

    def test_create_with_soul_version(self):
        """RunNode can be instantiated with soul_version value."""
        node = RunNode(
            id="run1:b1",
            run_id="run1",
            node_id="b1",
            block_type="LinearBlock",
            soul_version="def789ghi012",
        )
        assert node.soul_version == "def789ghi012"

    def test_create_with_eval_score(self):
        """RunNode can be instantiated with eval_score value."""
        node = RunNode(
            id="run1:b1",
            run_id="run1",
            node_id="b1",
            block_type="LinearBlock",
            eval_score=0.95,
        )
        assert node.eval_score == pytest.approx(0.95)

    def test_create_with_eval_passed(self):
        """RunNode can be instantiated with eval_passed value."""
        node = RunNode(
            id="run1:b1",
            run_id="run1",
            node_id="b1",
            block_type="LinearBlock",
            eval_passed=True,
        )
        assert node.eval_passed is True

    def test_create_with_eval_results_dict(self):
        """RunNode can be instantiated with eval_results as a dict (JSON blob)."""
        results = {"accuracy": 0.92, "latency_ms": 150, "checks": ["format", "tone"]}
        node = RunNode(
            id="run1:b1",
            run_id="run1",
            node_id="b1",
            block_type="LinearBlock",
            eval_results=results,
        )
        assert node.eval_results == results
        assert node.eval_results["accuracy"] == 0.92


# ---------------------------------------------------------------------------
# 4. DB round-trip — fields persist and load correctly
# ---------------------------------------------------------------------------


class TestRunNodeFieldPersistence:
    def test_prompt_hash_persists(self, db_session):
        """prompt_hash survives a DB write + read cycle."""
        node = RunNode(
            id="run1:b1",
            run_id="run1",
            node_id="b1",
            block_type="LinearBlock",
            prompt_hash="sha256hash_prompt",
        )
        db_session.add(node)
        db_session.commit()

        loaded = db_session.get(RunNode, "run1:b1")
        assert loaded.prompt_hash == "sha256hash_prompt"

    def test_soul_version_persists(self, db_session):
        """soul_version survives a DB write + read cycle."""
        node = RunNode(
            id="run1:b2",
            run_id="run1",
            node_id="b2",
            block_type="LinearBlock",
            soul_version="sha256hash_soul",
        )
        db_session.add(node)
        db_session.commit()

        loaded = db_session.get(RunNode, "run1:b2")
        assert loaded.soul_version == "sha256hash_soul"

    def test_eval_fields_persist(self, db_session):
        """eval_score, eval_passed, eval_results all survive a DB round-trip."""
        node = RunNode(
            id="run1:b3",
            run_id="run1",
            node_id="b3",
            block_type="LinearBlock",
            eval_score=0.88,
            eval_passed=False,
            eval_results={"metric": "f1", "value": 0.88},
        )
        db_session.add(node)
        db_session.commit()

        loaded = db_session.get(RunNode, "run1:b3")
        assert loaded.eval_score == pytest.approx(0.88)
        assert loaded.eval_passed is False
        assert loaded.eval_results["metric"] == "f1"

    def test_none_fields_persist_as_null(self, db_session):
        """None values for new fields persist as NULL in DB."""
        node = RunNode(
            id="run1:b4",
            run_id="run1",
            node_id="b4",
            block_type="LinearBlock",
        )
        db_session.add(node)
        db_session.commit()

        loaded = db_session.get(RunNode, "run1:b4")
        assert loaded.prompt_hash is None
        assert loaded.soul_version is None
        assert loaded.eval_score is None
        assert loaded.eval_passed is None
        assert loaded.eval_results is None
