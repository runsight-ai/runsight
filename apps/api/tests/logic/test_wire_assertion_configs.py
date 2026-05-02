"""Block assertion wiring without soul-level assertion configs."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError
from runsight_core.observer import compute_soul_version
from runsight_core.primitives import Step
from runsight_core.yaml.parser import parse_workflow_yaml
from sqlmodel import Session

from runsight_api.domain.entities.run import RunNode
from apps.api.tests.logic.assertion_config_fixtures import (
    assertion_wiring_workspace as _assertion_wiring_workspace_fixture,  # noqa: F401
    db_engine as _db_engine_fixture,  # noqa: F401
    drain_queue as _drain_queue,
    fake_result as _fake_result,
    prepared_inputs as _prepared_inputs,
    seed_run as _seed_run,
    workflow_fixture_yaml as _workflow_fixture_yaml,
)


class TestParserPropagatesAssertions:
    """Workflow parsing should attach block-owned assertions to runtime blocks."""

    def test_runtime_block_has_assertions_after_parse(self, assertion_wiring_workspace):
        wf = assertion_wiring_workspace.parse_block_assertion_workflow()

        block = wf._blocks["analyze"]
        assert block.assertions is not None
        assert len(block.assertions) == 1

    def test_block_assertions_preserve_yaml_fields(self, assertion_wiring_workspace):
        wf = assertion_wiring_workspace.parse_block_assertion_workflow()

        block = wf._blocks["analyze"]
        assert block.assertions is not None
        assert block.assertions[0]["type"] == "contains"
        assert block.assertions[0]["value"] == "analysis"

    def test_soul_level_assertions_raise_validation_error(self):
        with pytest.raises(ValidationError):
            parse_workflow_yaml(_workflow_fixture_yaml("soul-only-assertions.yaml"))


class TestExecutionServiceBuildsAssertionConfigs:
    """ExecutionService should source eval configs from block.assertions only."""

    def test_build_assertion_configs_reads_runtime_block_assertions(self):
        from runsight_api.logic.services.execution_service import ExecutionService

        wf = SimpleNamespace(
            _blocks={
                "analyze": SimpleNamespace(
                    assertions=[{"type": "contains", "value": "analysis"}],
                )
            }
        )

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs == {"analyze": [{"type": "contains", "value": "analysis"}]}

    def test_build_assertion_configs_returns_none_when_no_blocks_define_assertions(self):
        from runsight_api.logic.services.execution_service import ExecutionService

        wf = SimpleNamespace(
            _blocks={
                "analyze": SimpleNamespace(assertions=None),
                "summarize": SimpleNamespace(assertions=None),
            }
        )

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is None

    def test_build_assertion_configs_does_not_require_soul_on_runtime_block(self):
        from runsight_api.logic.services.execution_service import ExecutionService

        wf = SimpleNamespace(
            _blocks={
                "analyze": SimpleNamespace(assertions=[{"type": "contains", "value": "analysis"}]),
            }
        )

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is not None
        assert configs["analyze"] == [{"type": "contains", "value": "analysis"}]

    def test_build_assertion_configs_reads_assertions_through_step_wrapper(self):
        from runsight_api.logic.services.execution_service import ExecutionService

        inner_block = SimpleNamespace(assertions=[{"type": "contains", "value": "analysis"}])
        step = Step(block=inner_block, declared_inputs={"data": "fetch.output"})
        wf = SimpleNamespace(_blocks={"analyze": step})

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs == {"analyze": [{"type": "contains", "value": "analysis"}]}

    def test_build_assertion_configs_returns_none_for_step_without_assertions(self):
        from runsight_api.logic.services.execution_service import ExecutionService

        inner_block = SimpleNamespace(assertions=None)
        step = Step(block=inner_block, declared_inputs={"data": "fetch.output"})
        wf = SimpleNamespace(_blocks={"analyze": step})

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is None

    def test_build_assertion_configs_reads_parsed_step_wrapped_assertions(
        self, assertion_wiring_workspace
    ):
        from runsight_api.logic.services.execution_service import ExecutionService

        wf = assertion_wiring_workspace.parse_step_assertion_workflow()

        configs = ExecutionService._build_assertion_configs(wf)

        assert configs is not None
        assert configs["analyze"] == [
            {"type": "contains", "value": "analysis"},
            {"type": "cost", "threshold": 0.05},
        ]


class TestIntegrationEvalScoreViaService:
    """ExecutionService should wire block assertions through EvalObserver."""

    @pytest.mark.asyncio
    async def test_block_assertions_populate_eval_score(
        self, db_engine, assertion_wiring_workspace
    ):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )

        run_id = "run_block_eval"
        _seed_run(db_engine, run_id, "block_assertion_test")
        wf = assertion_wiring_workspace.parse_block_assertion_workflow()

        with patch(
            "runsight_core.runner.RunsightTeamRunner.execute",
            new_callable=AsyncMock,
            return_value=_fake_result(),
        ):
            await svc._run_workflow(
                run_id,
                wf,
                _prepared_inputs({"instruction": "Analyze the data"}),
            )

        with Session(db_engine) as session:
            node = session.get(RunNode, f"{run_id}:analyze")
            assert node is not None
            assert node.eval_score is not None
            assert node.eval_results is not None

    @pytest.mark.asyncio
    async def test_block_assertions_still_emit_baseline_delta_using_soul_identity(
        self, db_engine, assertion_wiring_workspace
    ):
        from runsight_api.logic.services.execution_service import ExecutionService

        svc = ExecutionService(
            run_repo=Mock(),
            workflow_repo=Mock(),
            provider_repo=Mock(),
            engine=db_engine,
        )
        original_unregister = svc._streams.unregister
        captured_events: list[dict] = []

        def _capture_then_unregister(rid):
            observer = svc._streams.get(rid)
            if observer is not None:
                captured_events.extend(_drain_queue(observer.queue))
            original_unregister(rid)

        svc._streams.unregister = _capture_then_unregister

        run_id = "run_baseline_delta"
        _seed_run(db_engine, run_id, "block_assertion_test")
        wf = assertion_wiring_workspace.parse_block_assertion_workflow()
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
            "runsight_core.runner.RunsightTeamRunner.execute",
            new_callable=AsyncMock,
            return_value=_fake_result(),
        ):
            await svc._run_workflow(
                run_id,
                wf,
                _prepared_inputs({"instruction": "Analyze the data"}),
            )

        assert any(event["event"] == "node_eval_complete" for event in captured_events)
        eval_event = next(
            event for event in captured_events if event["event"] == "node_eval_complete"
        )
        assert eval_event["data"]["delta"] is not None
        assert eval_event["data"]["delta"]["baseline_run_count"] == 1


class TestInvalidSoulAssertionYaml:
    """Soul-level assertions should be rejected before execution begins."""

    def test_soul_only_assertions_fail_validation_before_execution(self):
        with pytest.raises(ValidationError):
            parse_workflow_yaml(_workflow_fixture_yaml("soul-only-assertions.yaml"))

    def test_soul_and_block_assertions_fail_validation_before_execution(self):
        with pytest.raises(ValidationError):
            parse_workflow_yaml(_workflow_fixture_yaml("soul-and-block-assertions.yaml"))
