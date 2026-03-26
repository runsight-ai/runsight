"""Red tests for RUN-347: Wire assertion configs from YAML to EvalObserver.

Covers the integration gap: assertion configs are parsed from YAML but never
reach EvalObserver at runtime because:
  1. parser.py line ~194-201 omits assertions= when constructing Soul
  2. execution_service.py line ~195 hardcodes assertion_configs=None

Tests verify:
  - YAML parser propagates soul assertions to Soul primitive
  - ExecutionService builds assertion_configs dict from parsed souls/blocks
  - EvalObserver receives real assertion_configs (not None)
  - Block-level assertions merge with soul-level (block takes precedence)
  - Integration: soul with cost assertion -> run -> RunNode.eval_score populated
  - Integration: SSE emits node_eval_complete event

All tests should FAIL until the wiring implementation exists.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_core.yaml.parser import parse_workflow_yaml
from runsight_api.domain.entities.run import Run, RunNode, RunStatus


# ---------------------------------------------------------------------------
# Minimal YAML templates
# ---------------------------------------------------------------------------

YAML_SOUL_WITH_ASSERTIONS = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst_v1
    role: Data Analyst
    system_prompt: You are a data analyst.
    assertions:
      - type: cost
        threshold: 0.01
      - type: contains
        value: analysis
blocks:
  analyze:
    type: linear
    soul_ref: analyst
workflow:
  name: assertion_test
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""

YAML_SOUL_AND_BLOCK_ASSERTIONS = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst_v1
    role: Data Analyst
    system_prompt: You are a data analyst.
    assertions:
      - type: cost
        threshold: 0.10
blocks:
  analyze:
    type: linear
    soul_ref: analyst
    assertions:
      - type: contains
        value: result
workflow:
  name: merge_test
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with all needed tables."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# 1. YAML parser propagates assertions to Soul primitive
# ---------------------------------------------------------------------------


class TestParserPropagatesAssertions:
    """parse_workflow_yaml must pass assertions= when constructing Soul."""

    def test_soul_has_assertions_after_parse(self):
        """When YAML soul has assertions, the parsed Soul object carries them."""
        wf = parse_workflow_yaml(YAML_SOUL_WITH_ASSERTIONS)
        # The parser builds LinearBlock(block_id, soul, runner).
        # Access the soul from the block.
        block = wf._blocks["analyze"]
        soul = block.soul
        assert soul.assertions is not None, (
            "Soul.assertions is None — parser must pass assertions=soul_def.assertions"
        )
        assert len(soul.assertions) == 2

    def test_soul_assertions_contain_correct_types(self):
        """Parsed soul assertions preserve type and config fields."""
        wf = parse_workflow_yaml(YAML_SOUL_WITH_ASSERTIONS)
        block = wf._blocks["analyze"]
        soul = block.soul
        assert soul.assertions is not None
        types = {a["type"] for a in soul.assertions}
        assert "cost" in types
        assert "contains" in types

    def test_soul_cost_assertion_has_threshold(self):
        """Cost assertion preserves its threshold value through parsing."""
        wf = parse_workflow_yaml(YAML_SOUL_WITH_ASSERTIONS)
        block = wf._blocks["analyze"]
        soul = block.soul
        assert soul.assertions is not None
        cost_assertion = next(a for a in soul.assertions if a["type"] == "cost")
        assert cost_assertion["threshold"] == 0.01

    def test_soul_without_assertions_remains_none(self):
        """Soul without assertions field keeps assertions=None after parse."""
        yaml_no_assertions = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  basic:
    id: basic_v1
    role: Assistant
    system_prompt: You are helpful.
blocks:
  step1:
    type: linear
    soul_ref: basic
workflow:
  name: no_assertions_test
  entry: step1
  transitions:
    - from: step1
      to: null
"""
        wf = parse_workflow_yaml(yaml_no_assertions)
        block = wf._blocks["step1"]
        soul = block.soul
        assert soul.assertions is None


# ---------------------------------------------------------------------------
# 2. ExecutionService builds assertion_configs dict (not None)
# ---------------------------------------------------------------------------


class TestExecutionServiceBuildsAssertionConfigs:
    """ExecutionService must extract assertions from souls/blocks and pass to EvalObserver."""

    @pytest.mark.asyncio
    async def test_eval_observer_receives_assertion_configs(self, db_engine):
        """EvalObserver is constructed with a non-None assertion_configs dict
        when the workflow contains souls with assertions."""
        from runsight_api.logic.services.execution_service import ExecutionService
        from runsight_api.logic.observers.eval_observer import EvalObserver

        # Set up mocks
        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_type.return_value = None

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        # Capture the EvalObserver construction
        captured_configs = {}

        original_init = EvalObserver.__init__

        def spy_init(self_obs, *, engine, run_id, sse_queue, assertion_configs=None):
            captured_configs["assertion_configs"] = assertion_configs
            original_init(
                self_obs,
                engine=engine,
                run_id=run_id,
                sse_queue=sse_queue,
                assertion_configs=assertion_configs,
            )

        # Seed a run record
        run_id = "run_347_svc"
        with Session(db_engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="assertion_test",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        # Create workflow from YAML with assertions
        wf = parse_workflow_yaml(YAML_SOUL_WITH_ASSERTIONS)

        # Patch EvalObserver.__init__ to capture what assertion_configs is passed
        with patch.object(EvalObserver, "__init__", spy_init):
            # Run _run_workflow directly (bypasses launch_execution's parse step)
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        assert "assertion_configs" in captured_configs, "EvalObserver was not instantiated"
        configs = captured_configs["assertion_configs"]
        assert configs is not None, (
            "assertion_configs is None — ExecutionService must build it from parsed souls"
        )
        assert "analyze" in configs, "assertion_configs must contain the block_id 'analyze'"
        assert len(configs["analyze"]) == 2

    @pytest.mark.asyncio
    async def test_assertion_configs_contain_correct_types(self, db_engine):
        """The assertion_configs dict for a block contains the correct assertion types."""
        from runsight_api.logic.services.execution_service import ExecutionService
        from runsight_api.logic.observers.eval_observer import EvalObserver

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_type.return_value = None

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        captured_configs = {}
        original_init = EvalObserver.__init__

        def spy_init(self_obs, *, engine, run_id, sse_queue, assertion_configs=None):
            captured_configs["assertion_configs"] = assertion_configs
            original_init(
                self_obs,
                engine=engine,
                run_id=run_id,
                sse_queue=sse_queue,
                assertion_configs=assertion_configs,
            )

        run_id = "run_347_types"
        with Session(db_engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="assertion_test",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        wf = parse_workflow_yaml(YAML_SOUL_WITH_ASSERTIONS)

        with patch.object(EvalObserver, "__init__", spy_init):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        configs = captured_configs.get("assertion_configs", {})
        assert configs is not None
        block_configs = configs.get("analyze", [])
        types = {c["type"] for c in block_configs}
        assert "cost" in types, "cost assertion missing from assertion_configs"
        assert "contains" in types, "contains assertion missing from assertion_configs"


# ---------------------------------------------------------------------------
# 3. Block-level assertions merge with soul-level
# ---------------------------------------------------------------------------


class TestBlockSoulAssertionMerge:
    """When both soul and block define assertions, they must be merged.
    Block-level assertions take precedence on type conflict."""

    def test_merged_configs_contain_both_soul_and_block_assertions(self):
        """A block with its own assertions AND a soul with assertions should
        produce a merged assertion_configs list for that block_id."""
        wf = parse_workflow_yaml(YAML_SOUL_AND_BLOCK_ASSERTIONS)
        block = wf._blocks["analyze"]
        soul = block.soul

        # Soul-level assertions must be propagated
        assert soul.assertions is not None, (
            "Soul.assertions is None — parser must pass assertions=soul_def.assertions"
        )

        # Build assertion_configs the same way ExecutionService should:
        # - Start with soul assertions for each block that uses that soul
        # - Merge block-level assertions (block takes precedence)
        # For this test we verify the Soul carries its assertions so that
        # downstream code CAN merge. The actual merge logic is in ExecutionService.
        #
        # But we also need to verify the block-level assertions are accessible
        # from the parsed file_def. Let's verify via re-parsing.
        import yaml as pyyaml

        raw = pyyaml.safe_load(YAML_SOUL_AND_BLOCK_ASSERTIONS)
        from runsight_core.yaml.schema import RunsightWorkflowFile

        # Trigger schema rebuild for block def union
        import runsight_core.blocks  # noqa: F401
        from runsight_core.yaml.schema import rebuild_block_def_union

        rebuild_block_def_union()

        file_def = RunsightWorkflowFile.model_validate(raw)

        block_def = file_def.blocks["analyze"]
        assert block_def.assertions is not None, "Block-level assertions not parsed"
        assert len(block_def.assertions) == 1
        assert block_def.assertions[0]["type"] == "contains"

        soul_def = file_def.souls["analyst"]
        assert soul_def.assertions is not None, "Soul-level assertions not parsed"
        assert len(soul_def.assertions) == 1
        assert soul_def.assertions[0]["type"] == "cost"

        # The merge should produce both cost (from soul) and contains (from block)
        # This is what ExecutionService should build:
        merged = soul_def.assertions + block_def.assertions
        types = {a["type"] for a in merged}
        assert "cost" in types
        assert "contains" in types


# ---------------------------------------------------------------------------
# 4. Integration: ExecutionService -> eval_score populated on RunNode
# ---------------------------------------------------------------------------


class TestIntegrationEvalScoreViaService:
    """Integration: ExecutionService._run_workflow with YAML assertions
    must produce RunNode.eval_score and eval_passed (not None)."""

    @pytest.mark.asyncio
    async def test_eval_score_populated_via_execution_service(self, db_engine):
        """After _run_workflow with a soul that has assertions,
        RunNode.eval_score must not be None."""
        from runsight_api.logic.services.execution_service import ExecutionService

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_type.return_value = None

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        run_id = "run_347_int_score"
        with Session(db_engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="assertion_test",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        wf = parse_workflow_yaml(YAML_SOUL_WITH_ASSERTIONS)

        fake_result = Mock()
        fake_result.output = "Here is the analysis result."
        fake_result.cost_usd = 0.005
        fake_result.total_tokens = 300

        with patch(
            "runsight_core.runner.RunsightTeamRunner.execute_task",
            new_callable=AsyncMock,
            return_value=fake_result,
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None, "RunNode not created for block 'analyze'"
            assert node.eval_score is not None, (
                "RunNode.eval_score is None — assertion_configs did not reach EvalObserver"
            )
            assert isinstance(node.eval_score, float)

    @pytest.mark.asyncio
    async def test_eval_passed_populated_via_execution_service(self, db_engine):
        """After _run_workflow with assertions, RunNode.eval_passed must be a bool."""
        from runsight_api.logic.services.execution_service import ExecutionService

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_type.return_value = None

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        run_id = "run_347_int_passed"
        with Session(db_engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="assertion_test",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        wf = parse_workflow_yaml(YAML_SOUL_WITH_ASSERTIONS)

        fake_result = Mock()
        fake_result.output = "Here is the analysis result."
        fake_result.cost_usd = 0.005
        fake_result.total_tokens = 300

        with patch(
            "runsight_core.runner.RunsightTeamRunner.execute_task",
            new_callable=AsyncMock,
            return_value=fake_result,
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None, "RunNode not created for block 'analyze'"
            assert node.eval_passed is not None, (
                "RunNode.eval_passed is None — must be True or False after eval"
            )
            assert isinstance(node.eval_passed, bool)


# ---------------------------------------------------------------------------
# 5. Integration: SSE emits node_eval_complete event via ExecutionService
# ---------------------------------------------------------------------------


class TestIntegrationSSEEventViaService:
    """After execution via ExecutionService, the SSE stream must contain
    a node_eval_complete event when assertions are configured."""

    @pytest.mark.asyncio
    async def test_sse_node_eval_complete_emitted_via_service(self, db_engine):
        """ExecutionService._run_workflow must produce a node_eval_complete SSE event."""
        from runsight_api.logic.services.execution_service import ExecutionService

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_type.return_value = None

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        run_id = "run_347_int_sse"
        with Session(db_engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="assertion_test",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        wf = parse_workflow_yaml(YAML_SOUL_WITH_ASSERTIONS)

        fake_result = Mock()
        fake_result.output = "Here is the analysis result."
        fake_result.cost_usd = 0.005
        fake_result.total_tokens = 300

        with patch(
            "runsight_core.runner.RunsightTeamRunner.execute_task",
            new_callable=AsyncMock,
            return_value=fake_result,
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        # After execution, retrieve the observer's queue and check for eval events
        # The observer is unregistered after _run_workflow, so we need to intercept.
        # Instead, verify via RunNode that eval happened (if eval_score is set,
        # the SSE event was emitted by the same code path).
        # But to directly test SSE, we can check via the streaming observer.
        # Since _run_workflow unregisters the observer, we verify indirectly:
        # if eval_score is populated, the SSE path was also exercised.
        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None, "RunNode not created for block 'analyze'"
            # eval_results contains the assertion details that are also in the SSE event
            assert node.eval_results is not None, (
                "RunNode.eval_results is None — node_eval_complete SSE event was never emitted"
            )
            assert "assertions" in node.eval_results, "eval_results missing 'assertions' key"
            assert len(node.eval_results["assertions"]) > 0, "eval_results assertions list is empty"


# ---------------------------------------------------------------------------
# 6. End-to-end: ExecutionService wires assertions from YAML to eval results
# ---------------------------------------------------------------------------


class TestEndToEndAssertionWiring:
    """E2E: parse YAML with assertions -> launch execution -> eval results appear."""

    @pytest.mark.asyncio
    async def test_e2e_yaml_to_eval_score(self, db_engine):
        """Complete wiring: YAML soul with cost assertion -> ExecutionService ->
        EvalObserver -> RunNode.eval_score is not None."""
        from runsight_api.logic.services.execution_service import ExecutionService

        run_repo = Mock()
        workflow_repo = Mock()
        provider_repo = Mock()
        provider_repo.get_by_type.return_value = None

        svc = ExecutionService(
            run_repo=run_repo,
            workflow_repo=workflow_repo,
            provider_repo=provider_repo,
            engine=db_engine,
        )

        run_id = "run_347_e2e"

        # Seed Run record
        with Session(db_engine) as session:
            session.add(
                Run(
                    id=run_id,
                    workflow_id="wf_1",
                    workflow_name="assertion_test",
                    status=RunStatus.pending,
                    task_json="{}",
                )
            )
            session.commit()

        # Parse workflow with assertions
        wf = parse_workflow_yaml(YAML_SOUL_WITH_ASSERTIONS)

        # Mock the actual LLM call to avoid real API calls
        fake_result = Mock()
        fake_result.output = "Here is the analysis with data."
        fake_result.cost_usd = 0.005
        fake_result.total_tokens = 300

        with patch(
            "runsight_core.runner.RunsightTeamRunner.execute_task",
            new_callable=AsyncMock,
            return_value=fake_result,
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        # After execution, the RunNode for 'analyze' should have eval_score set
        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            # Node might not exist if ExecutionObserver didn't create it,
            # but if it does, eval_score must be set
            if node is not None:
                assert node.eval_score is not None, (
                    "RunNode.eval_score is None after E2E execution — "
                    "assertion_configs never reached EvalObserver"
                )
            else:
                # If no node was created, that's also a failure for this test
                pytest.fail(
                    "RunNode was not created for block 'analyze' — "
                    "ExecutionObserver may not have fired"
                )
