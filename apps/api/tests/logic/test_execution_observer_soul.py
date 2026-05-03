"""ExecutionObserver soul parameter integration.

Tests target ExecutionObserver changes:
  - on_block_start  accepts soul keyword argument
  - on_block_complete  accepts soul keyword argument
  - on_block_complete  with soul populates prompt_hash and soul_version on RunNode
  - on_block_complete  without soul (None) leaves prompt_hash/soul_version as None
"""

import hashlib

import pytest
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus

# ---------------------------------------------------------------------------
# Deferred import
# ---------------------------------------------------------------------------


def _import_execution_observer():
    from runsight_api.logic.observers.execution_observer import ExecutionObserver

    return ExecutionObserver


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with all needed tables."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def seed_run(db_engine):
    """Insert a pending Run record and return (engine, run_id)."""
    run_id = "observer-soul-run"
    with Session(db_engine) as session:
        run = Run(
            id=run_id,
            workflow_id="observer-soul-workflow",
            workflow_name="Observer Soul Workflow",
            status=RunStatus.pending,
            task_json="{}",
            branch="main",
        )
        session.add(run)
        session.commit()
    return db_engine, run_id


@pytest.fixture
def observer(seed_run):
    """Create an ExecutionObserver pointing at the seeded DB."""
    engine, run_id = seed_run
    ExecutionObserver = _import_execution_observer()
    return ExecutionObserver(engine=engine, run_id=run_id), engine, run_id


@pytest.fixture
def sample_soul():
    """A minimal Soul for testing."""
    return Soul(
        id="researcher-v1",
        kind="soul",
        name="Senior Researcher",
        role="Senior Researcher",
        system_prompt="You are a senior researcher.",
        model_name="fixture-chat-model",
    )


# ---------------------------------------------------------------------------
# 1. on_block_start accepts soul kwarg
# ---------------------------------------------------------------------------


class TestOnBlockStartSoul:
    def test_on_block_start_with_soul_does_not_error(self, observer, sample_soul):
        """on_block_start(... soul=soul) does not raise TypeError."""
        obs, engine, run_id = observer
        obs.on_block_start(
            "observer-soul-workflow", "soul_hash_block", "LinearBlock", soul=sample_soul
        )

    def test_on_block_start_with_none_soul_does_not_error(self, observer):
        """on_block_start(... soul=None) does not raise."""
        obs, engine, run_id = observer
        obs.on_block_start(
            "observer-soul-workflow", "none_soul_start_block", "LinearBlock", soul=None
        )

    def test_on_block_start_without_soul_kwarg_backward_compat(self, observer):
        """on_block_start called without soul keyword still works (backward compat)."""
        obs, engine, run_id = observer
        obs.on_block_start("observer-soul-workflow", "omitted_soul_start_block", "LinearBlock")


# ---------------------------------------------------------------------------
# 2. on_block_complete with soul populates prompt_hash and soul_version
# ---------------------------------------------------------------------------


class TestOnBlockCompleteSoulHashes:
    def _start_and_complete_with_soul(self, obs, engine, run_id, soul):
        """Helper: start then complete a block with a soul."""
        obs.on_block_start("observer-soul-workflow", "soul_hash_block", "LinearBlock", soul=soul)
        state = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=1500,
            results={"soul_hash_block": BlockResult(output="Some output")},
        )
        obs.on_block_complete(
            "observer-soul-workflow", "soul_hash_block", "LinearBlock", 2.5, state, soul=soul
        )

    def test_populates_prompt_hash_from_soul(self, observer, sample_soul):
        """on_block_complete with soul sets RunNode.prompt_hash to SHA-256 of system_prompt."""
        obs, engine, run_id = observer
        self._start_and_complete_with_soul(obs, engine, run_id, sample_soul)

        expected_hash = hashlib.sha256(sample_soul.system_prompt.encode()).hexdigest()

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:soul_hash_block")
            assert node is not None
            assert node.prompt_hash == expected_hash

    def test_populates_soul_version_from_soul(self, observer, sample_soul):
        """on_block_complete with soul sets RunNode.soul_version to SHA-256 of full soul JSON."""
        obs, engine, run_id = observer
        self._start_and_complete_with_soul(obs, engine, run_id, sample_soul)

        expected_version = hashlib.sha256(sample_soul.model_dump_json().encode()).hexdigest()

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:soul_hash_block")
            assert node is not None
            assert node.soul_version == expected_version

    def test_none_soul_leaves_hashes_none(self, observer):
        """on_block_complete with soul=None leaves prompt_hash and soul_version as None."""
        obs, engine, run_id = observer
        obs.on_block_start("observer-soul-workflow", "none_soul_block", "LinearBlock", soul=None)
        state = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=500,
            results={"none_soul_block": BlockResult(output="Output")},
        )
        obs.on_block_complete(
            "observer-soul-workflow", "none_soul_block", "LinearBlock", 1.0, state, soul=None
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:none_soul_block")
            assert node is not None
            assert node.prompt_hash is None
            assert node.soul_version is None

    def test_omitted_soul_leaves_hashes_none(self, observer):
        """on_block_complete without soul keyword leaves prompt_hash/soul_version as None."""
        obs, engine, run_id = observer
        obs.on_block_start("observer-soul-workflow", "omitted_soul_block", "LinearBlock")
        state = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=500,
            results={"omitted_soul_block": BlockResult(output="Output")},
        )
        obs.on_block_complete(
            "observer-soul-workflow", "omitted_soul_block", "LinearBlock", 1.0, state
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:omitted_soul_block")
            assert node is not None
            assert node.prompt_hash is None
            assert node.soul_version is None


# ---------------------------------------------------------------------------
# 3. Different souls produce different hashes
# ---------------------------------------------------------------------------


class TestHashVariation:
    def test_different_soul_produces_different_hashes(self, seed_run):
        """Two blocks with different souls get different prompt_hash/soul_version."""
        engine, run_id = seed_run
        ExecutionObserver = _import_execution_observer()
        obs = ExecutionObserver(engine=engine, run_id=run_id)

        soul_a = Soul(
            id="researcher",
            kind="soul",
            name="Researcher",
            role="Researcher",
            system_prompt="Research things.",
            model_name="fixture-chat-model",
        )
        soul_b = Soul(
            id="coder",
            kind="soul",
            name="Coder",
            role="Coder",
            system_prompt="Write code.",
            model_name="fixture-chat-model",
        )

        # Block A with soul_a
        obs.on_block_start("observer-soul-workflow", "research-block", "LinearBlock", soul=soul_a)
        state_a = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=500,
            results={"research-block": BlockResult(output="Research output")},
        )
        obs.on_block_complete(
            "observer-soul-workflow", "research-block", "LinearBlock", 1.0, state_a, soul=soul_a
        )

        # Block B with soul_b
        obs.on_block_start("observer-soul-workflow", "coding-block", "LinearBlock", soul=soul_b)
        state_b = WorkflowState(
            total_cost_usd=0.10,
            total_tokens=1000,
            results={"coding-block": BlockResult(output="Code output")},
        )
        obs.on_block_complete(
            "observer-soul-workflow", "coding-block", "LinearBlock", 1.5, state_b, soul=soul_b
        )

        with Session(engine) as session:
            node_a = session.get(RunNode, f"{run_id}:research-block")
            node_b = session.get(RunNode, f"{run_id}:coding-block")
            assert node_a.prompt_hash != node_b.prompt_hash
            assert node_a.soul_version != node_b.soul_version
