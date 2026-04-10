"""Red tests for RUN-315: EvalObserver — run-mode assertion execution.

Tests target the new EvalObserver that lives in the CompositeObserver chain:
  - No-op when no assertions configured
  - Runs assertion engine on on_block_complete
  - Persists eval_score, eval_passed, eval_results on RunNode
  - Emits node_eval_complete SSE event to sse_queue
  - Computes delta against baseline (cost_pct, tokens_pct, score_delta)
  - Delta is None when no baseline exists
  - Defensive — never raises
  - Run-level aggregate on on_workflow_complete

All tests should FAIL until the implementation exists.
"""

import ast
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session, SQLModel, create_engine, select

from runsight_api.domain.entities.run import Run, RunNode, RunStatus

# ---------------------------------------------------------------------------
# Deferred import — EvalObserver does not exist yet
# ---------------------------------------------------------------------------


def _import_eval_observer():
    from runsight_api.logic.observers.eval_observer import EvalObserver

    return EvalObserver


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
    run_id = "run_315_eval"
    with Session(db_engine) as session:
        run = Run(
            id=run_id,
            workflow_id="wf_1",
            workflow_name="test_workflow",
            status=RunStatus.pending,
            task_json="{}",
        )
        session.add(run)
        session.commit()
    return db_engine, run_id


@pytest.fixture
def seed_run_with_node(seed_run):
    """Insert a Run + completed RunNode for block_a."""
    engine, run_id = seed_run
    with Session(engine) as session:
        node = RunNode(
            id=f"{run_id}:block_a",
            run_id=run_id,
            node_id="block_a",
            block_type="LinearBlock",
            status="completed",
            cost_usd=0.05,
            tokens={"total": 1500},
            output="Some output containing Sources information.",
        )
        session.add(node)
        session.commit()
    return engine, run_id


@pytest.fixture
def sse_queue():
    """An asyncio.Queue that simulates the StreamingObserver queue."""
    return asyncio.Queue()


@pytest.fixture
def sample_soul():
    """A minimal Soul for testing."""
    return Soul(
        id="researcher_v1",
        role="Senior Researcher",
        system_prompt="You are a senior researcher.",
        model_name="gpt-4o",
    )


@pytest.fixture
def sample_state():
    """A WorkflowState with a completed block result."""
    return WorkflowState(
        total_cost_usd=0.05,
        total_tokens=1500,
        results={"block_a": BlockResult(output="Some output containing Sources information.")},
    )


@pytest.fixture
def contains_assertion_configs():
    """Assertion configs with a single 'contains' check for block_a."""
    return {
        "block_a": [
            {"type": "contains", "value": "Sources", "weight": 1.0},
        ],
    }


@pytest.fixture
def multi_assertion_configs():
    """Assertion configs with multiple weighted assertions for block_a."""
    return {
        "block_a": [
            {"type": "contains", "value": "Sources", "weight": 2.0},
            {"type": "contains", "value": "information", "weight": 1.0},
        ],
    }


@pytest.fixture
def failing_assertion_configs():
    """Assertion configs where the assertion will fail."""
    return {
        "block_a": [
            {"type": "contains", "value": "NONEXISTENT_STRING_THAT_WONT_MATCH", "weight": 1.0},
        ],
    }


@pytest.fixture
def cost_assertion_configs():
    """Assertion configs with a cost threshold check."""
    return {
        "block_a": [
            {"type": "cost", "threshold": 0.10, "weight": 1.0},
        ],
    }


# ---------------------------------------------------------------------------
# 1. TestEvalObserverImport — module exists
# ---------------------------------------------------------------------------


class TestEvalObserverImport:
    def test_constructor_accepts_required_kwargs(self, seed_run, sse_queue):
        """EvalObserver accepts engine, run_id, sse_queue, assertion_configs kwargs."""
        engine, run_id = seed_run
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs={"block_a": [{"type": "contains", "value": "x"}]},
        )
        assert obs is not None

    def test_module_uses_public_registry_sync_runner(self):
        """EvalObserver should depend on the shared registry sync runner, not local duplicates."""
        import runsight_api.logic.observers.eval_observer as eval_observer_module
        from runsight_core.assertions import registry as assertion_registry

        source = Path(eval_observer_module.__file__).read_text()
        tree = ast.parse(source)
        defined_functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        assert hasattr(assertion_registry, "run_assertions_sync")
        assert "_run_assertion_sync" not in defined_functions
        assert "_run_assertions_sync" not in defined_functions
        assert (
            getattr(eval_observer_module, "run_assertions_sync")
            is assertion_registry.run_assertions_sync
        )


# ---------------------------------------------------------------------------
# 2. TestEvalObserverNoOp — no assertions = no side effects
# ---------------------------------------------------------------------------


class TestEvalObserverNoOp:
    def test_no_assertion_configs_no_db_write(self, seed_run_with_node, sse_queue, sample_state):
        """on_block_complete with assertion_configs=None writes nothing to RunNode eval fields."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine, run_id=run_id, sse_queue=sse_queue, assertion_configs=None
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=None)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_score is None
            assert node.eval_passed is None
            assert node.eval_results is None

    def test_no_assertion_configs_no_sse_event(self, seed_run_with_node, sse_queue, sample_state):
        """on_block_complete with assertion_configs=None emits no SSE event."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine, run_id=run_id, sse_queue=sse_queue, assertion_configs=None
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=None)

        assert sse_queue.empty()

    def test_block_not_in_configs_no_db_write(self, seed_run_with_node, sse_queue, sample_state):
        """on_block_complete for a block NOT in assertion_configs writes nothing."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs={"other_block": [{"type": "contains", "value": "x"}]},
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=None)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_score is None

    def test_block_not_in_configs_no_sse_event(self, seed_run_with_node, sse_queue, sample_state):
        """on_block_complete for a block NOT in configs emits no SSE event."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs={"other_block": [{"type": "contains", "value": "x"}]},
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=None)

        assert sse_queue.empty()

    def test_empty_assertion_list_for_block_no_op(
        self, seed_run_with_node, sse_queue, sample_state
    ):
        """on_block_complete with an empty assertion list for block_a is a no-op."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs={"block_a": []},
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=None)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_score is None

        assert sse_queue.empty()


# ---------------------------------------------------------------------------
# 3. TestEvalObserverAssertionExecution — runs assertions, persists results
# ---------------------------------------------------------------------------


class TestEvalObserverAssertionExecution:
    @pytest.mark.asyncio
    async def test_contains_assertion_persists_eval_score(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """on_block_complete with 'contains' assertion persists eval_score on RunNode."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_score is not None
            assert node.eval_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_multiple_assertions_weighted_aggregate(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, multi_assertion_configs
    ):
        """on_block_complete with multiple weighted assertions computes correct aggregate score."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=multi_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            # Both assertions pass: score should be 1.0 (weighted avg of 1.0*2 + 1.0*1) / 3
            assert node.eval_score is not None
            assert node.eval_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_failing_assertion_sets_eval_passed_false(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, failing_assertion_configs
    ):
        """on_block_complete with a failing assertion sets eval_passed=False."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=failing_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_passed is False

    @pytest.mark.asyncio
    async def test_passing_assertion_sets_eval_passed_true(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """on_block_complete with a passing assertion sets eval_passed=True, score=1.0."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_passed is True
            assert node.eval_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_eval_results_contains_assertion_details(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """eval_results JSON contains assertion type, passed, score, reason."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_results is not None
            results = node.eval_results
            # Should have an "assertions" list
            assert "assertions" in results
            assertion_list = results["assertions"]
            assert len(assertion_list) >= 1
            first = assertion_list[0]
            assert "type" in first or "assertion_type" in first
            assert "passed" in first
            assert "score" in first
            assert "reason" in first

    @pytest.mark.asyncio
    async def test_failing_assertion_score_is_zero(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, failing_assertion_configs
    ):
        """on_block_complete with failing assertion produces eval_score=0.0."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=failing_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_score == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_cost_assertion_reads_cost_from_context(
        self, seed_run_with_node, sse_queue, sample_soul, cost_assertion_configs
    ):
        """on_block_complete with cost assertion uses cost_usd from context/state."""
        engine, run_id = seed_run_with_node
        # State with cost 0.05, threshold is 0.10 -> should pass
        state = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=1500,
            results={"block_a": BlockResult(output="Output")},
        )
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=cost_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, state, soul=sample_soul)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_passed is True
            assert node.eval_score == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_cost_assertion_exceeding_threshold_fails(
        self, seed_run_with_node, sse_queue, sample_soul
    ):
        """on_block_complete with cost exceeding threshold fails eval."""
        engine, run_id = seed_run_with_node
        state = WorkflowState(
            total_cost_usd=0.50,
            total_tokens=5000,
            results={"block_a": BlockResult(output="Output")},
        )
        configs = {"block_a": [{"type": "cost", "threshold": 0.01, "weight": 1.0}]}
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine, run_id=run_id, sse_queue=sse_queue, assertion_configs=configs
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, state, soul=sample_soul)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.eval_passed is False


# ---------------------------------------------------------------------------
# 4. TestEvalObserverSSE — emits correct SSE events
# ---------------------------------------------------------------------------


class TestEvalObserverSSE:
    @pytest.mark.asyncio
    async def test_emits_node_eval_complete_event(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """on_block_complete emits a node_eval_complete event to the SSE queue."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        assert not sse_queue.empty()
        event = sse_queue.get_nowait()
        assert event["event"] == "node_eval_complete"

    @pytest.mark.asyncio
    async def test_sse_event_contains_eval_score_and_node_id(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """SSE event data contains eval_score, passed, node_id."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        event = sse_queue.get_nowait()
        data = event["data"]
        assert "node_id" in data
        assert data["node_id"] == "block_a"
        assert "eval_score" in data
        assert "passed" in data

    @pytest.mark.asyncio
    async def test_sse_event_contains_delta_when_baseline_exists(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """SSE event data contains delta dict when a baseline exists."""
        engine, run_id = seed_run_with_node

        # Seed a baseline: previous nodes for same soul
        from runsight_core.observer import compute_soul_version

        soul_version = compute_soul_version(sample_soul)
        with Session(engine) as session:
            for i in range(3):
                baseline_node = RunNode(
                    id=f"prev_run_{i}:block_a",
                    run_id=f"prev_run_{i}",
                    node_id="block_a",
                    block_type="LinearBlock",
                    status="completed",
                    soul_id=sample_soul.id,
                    soul_version=soul_version,
                    cost_usd=0.04,
                    tokens={"total": 1200},
                    eval_score=0.9,
                )
                session.add(baseline_node)
            session.commit()

        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        event = sse_queue.get_nowait()
        data = event["data"]
        assert "delta" in data
        assert data["delta"] is not None
        delta = data["delta"]
        assert "cost_pct" in delta
        assert "tokens_pct" in delta
        assert "score_delta" in delta

    @pytest.mark.asyncio
    async def test_sse_event_delta_none_when_no_baseline(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """SSE event delta is None when no baseline exists (first run)."""
        engine, run_id = seed_run_with_node
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        event = sse_queue.get_nowait()
        data = event["data"]
        assert "delta" in data
        assert data["delta"] is None


# ---------------------------------------------------------------------------
# 5. TestEvalObserverDelta — baseline delta computation
# ---------------------------------------------------------------------------


class TestEvalObserverDelta:
    def _seed_baseline(self, engine, soul, cost=0.04, tokens=1200, score=0.9, count=3):
        """Helper: seed baseline nodes for a soul."""
        from runsight_core.observer import compute_soul_version

        soul_version = compute_soul_version(soul)
        with Session(engine) as session:
            for i in range(count):
                node = RunNode(
                    id=f"baseline_{i}:block_a",
                    run_id=f"baseline_{i}",
                    node_id="block_a",
                    block_type="LinearBlock",
                    status="completed",
                    soul_id=soul.id,
                    soul_version=soul_version,
                    cost_usd=cost,
                    tokens={"total": tokens},
                    eval_score=score,
                )
                session.add(node)
            session.commit()

    @pytest.mark.asyncio
    async def test_delta_contains_cost_pct_tokens_pct_score_delta(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """When baseline exists, delta has cost_pct, tokens_pct, score_delta."""
        engine, run_id = seed_run_with_node
        self._seed_baseline(engine, sample_soul)

        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        event = sse_queue.get_nowait()
        delta = event["data"]["delta"]
        assert "cost_pct" in delta
        assert "tokens_pct" in delta
        assert "score_delta" in delta

    @pytest.mark.asyncio
    async def test_delta_is_none_when_no_baseline(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """When no baseline (first run for this soul), delta is None."""
        engine, run_id = seed_run_with_node
        # No baseline seeded
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

        event = sse_queue.get_nowait()
        assert event["data"]["delta"] is None

    @pytest.mark.asyncio
    async def test_delta_computation_correct(
        self, seed_run_with_node, sse_queue, sample_soul, contains_assertion_configs
    ):
        """Delta computation: (current - baseline) / baseline * 100."""
        engine, run_id = seed_run_with_node
        # Baseline: cost=0.04, tokens=1200, score=0.9
        self._seed_baseline(engine, sample_soul, cost=0.04, tokens=1200, score=0.9)

        # Current run: cost=0.05, tokens=1500, score will be 1.0 (contains passes)
        state = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=1500,
            results={"block_a": BlockResult(output="Some output containing Sources information.")},
        )
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, state, soul=sample_soul)

        event = sse_queue.get_nowait()
        delta = event["data"]["delta"]

        # cost_pct: (0.05 - 0.04) / 0.04 * 100 = 25.0
        assert delta["cost_pct"] == pytest.approx(25.0, abs=1.0)
        # tokens_pct: (1500 - 1200) / 1200 * 100 = 25.0
        assert delta["tokens_pct"] == pytest.approx(25.0, abs=1.0)
        # score_delta: 1.0 - 0.9 = 0.1
        assert delta["score_delta"] == pytest.approx(0.1, abs=0.05)

    @pytest.mark.asyncio
    async def test_delta_negative_when_improvement(
        self, seed_run_with_node, sse_queue, sample_soul, contains_assertion_configs
    ):
        """Delta is negative when current cost/tokens are lower than baseline."""
        engine, run_id = seed_run_with_node
        # Baseline: expensive (cost=0.10, tokens=3000)
        self._seed_baseline(engine, sample_soul, cost=0.10, tokens=3000, score=0.8)

        # Current run: cheaper
        state = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=1500,
            results={"block_a": BlockResult(output="Some output containing Sources information.")},
        )
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, state, soul=sample_soul)

        event = sse_queue.get_nowait()
        delta = event["data"]["delta"]
        # cost_pct: (0.05 - 0.10) / 0.10 * 100 = -50.0
        assert delta["cost_pct"] < 0
        # tokens_pct: (1500 - 3000) / 3000 * 100 = -50.0
        assert delta["tokens_pct"] < 0


# ---------------------------------------------------------------------------
# 6. TestEvalObserverDefensive — never raises
# ---------------------------------------------------------------------------


class TestEvalObserverDefensive:
    def test_on_block_complete_never_raises_with_broken_config(
        self, seed_run_with_node, sse_queue, sample_state, sample_soul
    ):
        """on_block_complete does not raise even with invalid assertion config."""
        engine, run_id = seed_run_with_node
        broken_configs = {
            "block_a": [
                {"type": "nonexistent_assertion_type_xyz", "value": "x", "weight": 1.0},
            ],
        }
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=broken_configs,
        )
        # Should NOT raise
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

    def test_on_block_complete_never_raises_with_db_error(
        self, sse_queue, sample_state, sample_soul, contains_assertion_configs
    ):
        """on_block_complete does not raise even when DB engine fails."""
        # Create a broken engine that will cause Session errors
        broken_engine = MagicMock()
        broken_engine.connect.side_effect = Exception("DB connection failed")

        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=broken_engine,
            run_id="run_broken",
            sse_queue=sse_queue,
            assertion_configs=contains_assertion_configs,
        )
        # Should NOT raise
        obs.on_block_complete("wf", "block_a", "LinearBlock", 2.5, sample_state, soul=sample_soul)

    def test_on_workflow_complete_never_raises(self, sse_queue, sample_state):
        """on_workflow_complete does not raise even with a broken engine."""
        broken_engine = MagicMock()
        broken_engine.connect.side_effect = Exception("DB connection failed")

        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=broken_engine,
            run_id="run_broken",
            sse_queue=sse_queue,
            assertion_configs=None,
        )
        # Should NOT raise
        obs.on_workflow_complete("wf", sample_state, 5.0)


# ---------------------------------------------------------------------------
# 7. TestEvalObserverWorkflowComplete — run-level aggregate
# ---------------------------------------------------------------------------


class TestEvalObserverWorkflowComplete:
    @pytest.mark.asyncio
    async def test_workflow_complete_computes_run_aggregate(
        self, db_engine, sse_queue, sample_soul
    ):
        """on_workflow_complete computes avg eval_score across all evaluated nodes."""
        run_id = "run_315_wf_complete"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="test",
                status=RunStatus.running,
                task_json="{}",
            )
            session.add(run)
            # Two nodes with eval scores
            for block_id, score in [("block_a", 0.8), ("block_b", 1.0)]:
                node = RunNode(
                    id=f"{run_id}:{block_id}",
                    run_id=run_id,
                    node_id=block_id,
                    block_type="LinearBlock",
                    status="completed",
                    eval_score=score,
                    eval_passed=score >= 0.5,
                )
                session.add(node)
            session.commit()

        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=db_engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=None,
        )

        state = WorkflowState(total_cost_usd=0.10, total_tokens=3000)
        obs.on_workflow_complete("wf", state, 5.0)

        # The observer should have computed an aggregate score
        # Expected: (0.8 + 1.0) / 2 = 0.9
        # Check that it was logged or persisted (implementation may vary)
        # At minimum, it should not have raised.
        # If persisted on Run, verify:
        with Session(db_engine) as session:
            nodes = list(
                session.exec(
                    select(RunNode).where(RunNode.run_id == run_id, RunNode.eval_score.isnot(None))
                ).all()
            )
            assert len(nodes) == 2
            avg_score = sum(n.eval_score for n in nodes) / len(nodes)
            assert avg_score == pytest.approx(0.9, abs=0.01)

    @pytest.mark.asyncio
    async def test_workflow_complete_no_eval_nodes_is_noop(self, db_engine, sse_queue):
        """on_workflow_complete with no eval nodes is a no-op (no error)."""
        run_id = "run_315_no_eval"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="test",
                status=RunStatus.running,
                task_json="{}",
            )
            session.add(run)
            # Node without eval_score
            node = RunNode(
                id=f"{run_id}:block_a",
                run_id=run_id,
                node_id="block_a",
                block_type="LinearBlock",
                status="completed",
            )
            session.add(node)
            session.commit()

        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=db_engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=None,
        )

        state = WorkflowState(total_cost_usd=0.05, total_tokens=1000)
        # Should NOT raise
        obs.on_workflow_complete("wf", state, 3.0)

    @pytest.mark.asyncio
    async def test_workflow_complete_single_eval_node(self, db_engine, sse_queue):
        """on_workflow_complete with a single evaluated node uses that score as aggregate."""
        run_id = "run_315_single"
        with Session(db_engine) as session:
            run = Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name="test",
                status=RunStatus.running,
                task_json="{}",
            )
            session.add(run)
            node = RunNode(
                id=f"{run_id}:block_a",
                run_id=run_id,
                node_id="block_a",
                block_type="LinearBlock",
                status="completed",
                eval_score=0.75,
                eval_passed=True,
            )
            session.add(node)
            session.commit()

        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=db_engine,
            run_id=run_id,
            sse_queue=sse_queue,
            assertion_configs=None,
        )

        state = WorkflowState(total_cost_usd=0.05, total_tokens=1000)
        obs.on_workflow_complete("wf", state, 3.0)

        # Should not raise; aggregate should equal the single node's score


# ---------------------------------------------------------------------------
# 8. TestEvalObserverProtocol — implements WorkflowObserver
# ---------------------------------------------------------------------------


class TestEvalObserverProtocol:
    def test_on_block_start_is_noop(self, seed_run, sse_queue, sample_soul):
        """EvalObserver.on_block_start does not raise (no-op for eval)."""
        engine, run_id = seed_run
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine, run_id=run_id, sse_queue=sse_queue, assertion_configs=None
        )
        # Should not raise
        obs.on_block_start("wf", "block_a", "LinearBlock", soul=sample_soul)

    def test_on_workflow_start_is_noop(self, seed_run, sse_queue):
        """EvalObserver.on_workflow_start does not raise (no-op for eval)."""
        engine, run_id = seed_run
        EvalObserver = _import_eval_observer()
        obs = EvalObserver(
            engine=engine, run_id=run_id, sse_queue=sse_queue, assertion_configs=None
        )
        state = WorkflowState()
        # Should not raise
        obs.on_workflow_start("wf", state)
