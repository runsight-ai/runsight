"""Red tests for RUN-346: wire block-level assertions into execution."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from runsight_core.observer import compute_soul_version
from runsight_core.yaml.parser import parse_workflow_yaml
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus


YAML_BLOCK_WITH_ASSERTIONS = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst_v1
    role: Analyst
    system_prompt: You are a careful analyst.
blocks:
  analyze:
    type: linear
    soul_ref: analyst
    assertions:
      - type: contains
        value: analysis
workflow:
  name: block_assertion_test
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""


YAML_SOUL_ONLY_ASSERTIONS = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst_v1
    role: Analyst
    system_prompt: You are a careful analyst.
    assertions:
      - type: contains
        value: analysis
blocks:
  analyze:
    type: linear
    soul_ref: analyst
workflow:
  name: soul_only_assertion_test
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
    role: Analyst
    system_prompt: You are a careful analyst.
    assertions:
      - type: cost
        threshold: 0.10
blocks:
  analyze:
    type: linear
    soul_ref: analyst
    assertions:
      - type: contains
        value: analysis
workflow:
  name: soul_and_block_assertion_test
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _seed_run(engine, run_id: str, workflow_name: str) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="wf_1",
                workflow_name=workflow_name,
                status=RunStatus.pending,
                task_json="{}",
            )
        )
        session.commit()


def _fake_result(output: str = "This analysis includes the requested details."):
    result = Mock()
    result.output = output
    result.cost_usd = 0.005
    result.total_tokens = 300
    return result


def _drain_queue(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


class TestParserPropagatesAssertions:
    """Workflow parsing should attach block-owned assertions to runtime blocks."""

    def test_runtime_block_has_assertions_after_parse(self):
        wf = parse_workflow_yaml(YAML_BLOCK_WITH_ASSERTIONS)

        block = wf._blocks["analyze"]
        assert block.assertions is not None
        assert len(block.assertions) == 1

    def test_block_assertions_preserve_yaml_fields(self):
        wf = parse_workflow_yaml(YAML_BLOCK_WITH_ASSERTIONS)

        block = wf._blocks["analyze"]
        assert block.assertions is not None
        assert block.assertions[0]["type"] == "contains"
        assert block.assertions[0]["value"] == "analysis"

    def test_block_without_assertions_stays_none_even_if_soul_has_assertions(self):
        wf = parse_workflow_yaml(YAML_SOUL_ONLY_ASSERTIONS)

        block = wf._blocks["analyze"]
        assert hasattr(block, "assertions")
        assert block.assertions is None


class TestExecutionServiceBuildsAssertionConfigs:
    """ExecutionService should source eval configs from block.assertions only."""

    def test_build_assertion_configs_reads_runtime_block_assertions(self):
        from runsight_api.logic.services.execution_service import ExecutionService

        wf = SimpleNamespace(
            _blocks={
                "analyze": SimpleNamespace(
                    assertions=[{"type": "contains", "value": "analysis"}],
                    soul=SimpleNamespace(assertions=[{"type": "cost", "threshold": 0.10}]),
                )
            }
        )

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs == {"analyze": [{"type": "contains", "value": "analysis"}]}

    def test_build_assertion_configs_ignores_soul_assertions_when_block_has_none(self):
        from runsight_api.logic.services.execution_service import ExecutionService

        wf = SimpleNamespace(
            _blocks={
                "analyze": SimpleNamespace(
                    assertions=None,
                    soul=SimpleNamespace(assertions=[{"type": "contains", "value": "analysis"}]),
                )
            }
        )

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is None

    def test_build_assertion_configs_does_not_merge_soul_and_block_assertions(self):
        from runsight_api.logic.services.execution_service import ExecutionService

        wf = SimpleNamespace(
            _blocks={
                "analyze": SimpleNamespace(
                    assertions=[{"type": "contains", "value": "analysis"}],
                    soul=SimpleNamespace(assertions=[{"type": "cost", "threshold": 0.10}]),
                )
            }
        )

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is not None
        assert configs["analyze"] == [{"type": "contains", "value": "analysis"}]


class TestIntegrationEvalScoreViaService:
    """ExecutionService should wire block assertions through EvalObserver."""

    @pytest.mark.asyncio
    async def test_block_assertions_populate_eval_score(self, db_engine):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_346_block_eval"
        _seed_run(db_engine, run_id, "block_assertion_test")
        wf = parse_workflow_yaml(YAML_BLOCK_WITH_ASSERTIONS)

        with patch(
            "runsight_core.runner.RunsightTeamRunner.execute_task",
            new_callable=AsyncMock,
            return_value=_fake_result(),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None
            assert node.eval_score is not None
            assert node.eval_results is not None

    @pytest.mark.asyncio
    async def test_soul_only_assertions_do_not_trigger_eval(self, db_engine):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_346_soul_only"
        _seed_run(db_engine, run_id, "soul_only_assertion_test")
        wf = parse_workflow_yaml(YAML_SOUL_ONLY_ASSERTIONS)

        with patch(
            "runsight_core.runner.RunsightTeamRunner.execute_task",
            new_callable=AsyncMock,
            return_value=_fake_result(),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None
            assert node.eval_score is None
            assert node.eval_passed is None
            assert node.eval_results is None

    @pytest.mark.asyncio
    async def test_block_assertions_still_emit_baseline_delta_using_soul_identity(self, db_engine):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )
        svc.unregister_observer = Mock()

        run_id = "run_346_baseline_delta"
        _seed_run(db_engine, run_id, "block_assertion_test")
        wf = parse_workflow_yaml(YAML_BLOCK_WITH_ASSERTIONS)
        soul = wf._blocks["analyze"].soul
        soul_version = compute_soul_version(soul)

        with Session(db_engine) as session:
            session.add(
                RunNode(
                    id="baseline_1:analyze",
                    run_id="baseline_1",
                    node_id="analyze",
                    block_type="LinearBlock",
                    status="completed",
                    soul_id=soul.id,
                    soul_version=soul_version,
                    cost_usd=0.004,
                    tokens={"total": 250},
                    eval_score=0.75,
                )
            )
            session.commit()

        with patch(
            "runsight_core.runner.RunsightTeamRunner.execute_task",
            new_callable=AsyncMock,
            return_value=_fake_result(),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        observer = svc.get_observer(run_id)
        assert observer is not None

        events = _drain_queue(observer.queue)
        assert any(event["event"] == "node_eval_complete" for event in events)
        eval_event = next(event for event in events if event["event"] == "node_eval_complete")
        assert eval_event["data"]["delta"] is not None
        assert eval_event["data"]["delta"]["baseline_run_count"] == 1


class TestExecutionServiceIgnoresSoulLevelMerging:
    """When both locations exist, runtime evaluation should follow block ownership."""

    @pytest.mark.asyncio
    async def test_block_assertions_win_over_soul_assertions_during_execution(self, db_engine):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_346_block_wins"
        _seed_run(db_engine, run_id, "soul_and_block_assertion_test")
        wf = parse_workflow_yaml(YAML_SOUL_AND_BLOCK_ASSERTIONS)

        with patch(
            "runsight_core.runner.RunsightTeamRunner.execute_task",
            new_callable=AsyncMock,
            return_value=_fake_result(output="This output omits the expected keyword."),
        ):
            await svc._run_workflow(run_id, wf, {"instruction": "Analyze the data"})

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None
            assert node.eval_score == 0.0
            assert node.eval_passed is False
