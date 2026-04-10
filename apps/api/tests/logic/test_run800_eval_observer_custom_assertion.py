"""RUN-800 live-path coverage through ExecutionService workflow loading."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from textwrap import dedent
from unittest.mock import AsyncMock, Mock, patch

import pytest
import yaml
from sqlmodel import SQLModel, Session, create_engine

from runsight_api.domain.entities.run import Run, RunStatus


@pytest.fixture(autouse=True)
def _isolate_custom_assertion_registry():
    from runsight_core.assertions.custom import _PARAM_SCHEMAS
    from runsight_core.assertions.registry import _REGISTRY

    saved_registry = dict(_REGISTRY)
    saved_param_schemas = dict(_PARAM_SCHEMAS)

    for key in list(_REGISTRY):
        if key.startswith("custom:"):
            _REGISTRY.pop(key, None)
    _PARAM_SCHEMAS.clear()

    yield

    _REGISTRY.clear()
    _REGISTRY.update(saved_registry)
    _PARAM_SCHEMAS.clear()
    _PARAM_SCHEMAS.update(saved_param_schemas)


_PROMPTFOO_WORKFLOW_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst
    role: Analyst
    system_prompt: You are a careful analyst.
    provider: openai
    model_name: gpt-4o
blocks:
  analyze:
    type: linear
    soul_ref: analyst
    assertions:
      - type: custom:tone_check
        config:
          prefix: calm
      - type: contains
        value: "calm"
workflow:
  name: run800_promptfoo_live_path
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""

_NEGATED_CUSTOM_WORKFLOW_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst
    role: Analyst
    system_prompt: You are a careful analyst.
    provider: openai
    model_name: gpt-4o
blocks:
  analyze:
    type: linear
    soul_ref: analyst
    assertions:
      - type: not-custom:blocked_word
        config:
          blocked: storm
      - type: contains
        value: "calm"
workflow:
  name: run800_negated_custom_live_path
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""

_INVALID_CONFIG_WORKFLOW_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
souls:
  analyst:
    id: analyst
    role: Analyst
    system_prompt: You are a careful analyst.
    provider: openai
    model_name: gpt-4o
blocks:
  analyze:
    type: linear
    soul_ref: analyst
    assertions:
      - type: custom:budget_guard
        config: {}
workflow:
  name: run800_invalid_config_live_path
  entry: analyze
  transitions:
    - from: analyze
      to: null
"""


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    workflows_dir = base_dir / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / f"{workflow_id}.yaml").write_text(content, encoding="utf-8")


def _write_custom_assertion(
    base_dir: Path,
    *,
    stem: str,
    returns: str,
    code: str,
    params: dict | None = None,
) -> None:
    assertions_dir = base_dir / "custom" / "assertions"
    assertions_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": "1.0",
        "name": stem.replace("_", " ").title(),
        "description": f"Custom assertion {stem}",
        "returns": returns,
        "source": f"{stem}.py",
    }
    if params is not None:
        manifest["params"] = params
    _write_yaml(assertions_dir / f"{stem}.yaml", manifest)
    (assertions_dir / f"{stem}.py").write_text(dedent(code), encoding="utf-8")


def _make_achat_response(content: str, cost_usd: float = 0.001, total_tokens: int = 100):
    return {
        "content": content,
        "cost_usd": cost_usd,
        "prompt_tokens": 50,
        "completion_tokens": 50,
        "total_tokens": total_tokens,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


async def _wait_for_run_terminal(engine, run_id: str, timeout: float = 10.0):
    terminal = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run and run.status in terminal:
                return run
        await asyncio.sleep(0.1)
    with Session(engine) as session:
        return session.get(Run, run_id)


@pytest.fixture
def db_engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def base_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        _write_workflow_file(base, "run800-promptfoo", _PROMPTFOO_WORKFLOW_YAML)
        _write_workflow_file(base, "run800-negated-custom", _NEGATED_CUSTOM_WORKFLOW_YAML)
        _write_workflow_file(base, "run800-invalid-config", _INVALID_CONFIG_WORKFLOW_YAML)
        _write_custom_assertion(
            base,
            stem="tone_check",
            returns="grading_result",
            code="""
            def get_assert(output, context):
                config = context.get("config", {})
                return {
                    "pass": output.startswith(config.get("prefix", "")),
                    "score": 0.9,
                    "reason": f"prefix={config.get('prefix', '')}",
                }
            """,
        )
        _write_custom_assertion(
            base,
            stem="blocked_word",
            returns="bool",
            code="""
            def get_assert(output, context):
                return context.get("config", {}).get("blocked") in output
            """,
        )
        _write_custom_assertion(
            base,
            stem="budget_guard",
            returns="bool",
            params={
                "type": "object",
                "properties": {"budget": {"type": "number"}},
                "required": ["budget"],
            },
            code="""
            def get_assert(output, context):
                return True
            """,
        )
        yield base


@pytest.fixture
def app_with_real_services(db_engine, base_dir):
    from fastapi import FastAPI
    from sqlmodel import Session

    from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.data.repositories.run_repo import RunRepository
    from runsight_api.logic.services.eval_service import EvalService
    from runsight_api.logic.services.execution_service import ExecutionService
    from runsight_api.logic.services.run_service import RunService
    from runsight_api.transport.deps import (
        get_eval_service,
        get_execution_service,
        get_run_service,
    )
    from runsight_api.transport.routers import runs

    app = FastAPI()
    app.include_router(runs.router, prefix="/api")

    workflow_repo = WorkflowRepository(str(base_dir))
    provider_repo = FileSystemProviderRepo(base_path=str(base_dir))

    mock_secrets = Mock()
    mock_secrets.resolve = Mock(return_value="sk-fake-test-key-for-e2e")

    execution_service = ExecutionService(
        run_repo=None,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=db_engine,
        secrets=mock_secrets,
        settings_repo=None,
    )
    app.state.execution_service = execution_service

    def _get_run_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        return RunService(run_repo, workflow_repo)

    def _get_execution_service(request=None):
        return execution_service

    def _get_eval_service():
        session = Session(db_engine)
        run_repo = RunRepository(session)
        return EvalService(run_repo)

    app.dependency_overrides[get_run_service] = _get_run_service
    app.dependency_overrides[get_execution_service] = _get_execution_service
    app.dependency_overrides[get_eval_service] = _get_eval_service

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
def mock_provider():
    provider = Mock()
    provider.id = "openai"
    provider.type = "openai"
    provider.api_key = "sk-test"
    provider.is_active = True
    provider.models = ["gpt-4o"]
    return provider


def _capture_eval_events(execution_service):
    captured_events: list[dict] = []
    original_unregister = execution_service.unregister_observer

    def _capture_then_unregister(rid):
        obs = execution_service.get_observer(rid)
        if obs:
            while not obs.queue.empty():
                captured_events.append(obs.queue.get_nowait())
        original_unregister(rid)

    execution_service.unregister_observer = _capture_then_unregister
    return captured_events


class TestRun800LiveCustomAssertionPath:
    @pytest.mark.asyncio
    async def test_api_run_persists_promptfoo_custom_assertion_results_and_sse(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        execution_service = app_with_real_services.state.execution_service
        captured_events = _capture_eval_events(execution_service)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("calm response"),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "run800-promptfoo",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        analyze_node = next(node for node in nodes_response.json() if node["node_id"] == "analyze")
        assert analyze_node["eval_passed"] is True
        assert analyze_node["eval_score"] == pytest.approx(0.95)
        assert analyze_node["eval_results"] is not None
        assert analyze_node["eval_results"]["assertions"][0]["type"] == "custom:tone_check"
        assert analyze_node["eval_results"]["assertions"][0]["passed"] is True

        eval_events = [
            event for event in captured_events if event.get("event") == "node_eval_complete"
        ]
        assert len(eval_events) >= 1
        assert eval_events[0]["data"]["assertions"][0]["type"] == "custom:tone_check"
        assert eval_events[0]["data"]["passed"] is True

    @pytest.mark.asyncio
    async def test_api_run_supports_negated_custom_assertions_with_builtin_regression(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        execution_service = app_with_real_services.state.execution_service
        captured_events = _capture_eval_events(execution_service)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("calm response"),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "run800-negated-custom",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        analyze_node = next(node for node in nodes_response.json() if node["node_id"] == "analyze")
        assert analyze_node["eval_passed"] is True
        assert analyze_node["eval_score"] == pytest.approx(1.0)
        assert analyze_node["eval_results"] is not None
        assert analyze_node["eval_results"]["assertions"][0]["type"] == "custom:blocked_word"
        assert analyze_node["eval_results"]["assertions"][0]["passed"] is True

        eval_events = [
            event for event in captured_events if event.get("event") == "node_eval_complete"
        ]
        assert len(eval_events) >= 1
        assert eval_events[0]["data"]["passed"] is True

    @pytest.mark.asyncio
    async def test_api_run_persists_invalid_config_failure_and_sse_via_real_load_path(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        execution_service = app_with_real_services.state.execution_service
        captured_events = _capture_eval_events(execution_service)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("calm response"),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "run800-invalid-config",
                        "task_data": {"instruction": "Analyze this"},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        analyze_node = next(node for node in nodes_response.json() if node["node_id"] == "analyze")
        assert analyze_node["eval_passed"] is False
        assert analyze_node["eval_score"] == pytest.approx(0.0)
        assert analyze_node["eval_results"] is not None
        assert analyze_node["eval_results"]["assertions"][0]["type"] == "custom:budget_guard"
        assert analyze_node["eval_results"]["assertions"][0]["reason"].startswith(
            "Config validation failed:"
        )

        eval_events = [
            event for event in captured_events if event.get("event") == "node_eval_complete"
        ]
        assert len(eval_events) >= 1
        assert eval_events[0]["data"]["assertions"][0]["reason"].startswith(
            "Config validation failed:"
        )
