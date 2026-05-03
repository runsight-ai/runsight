"""Shared EvalObserver test builders.

The helpers in this module keep EvalObserver behavior tests isolated from
developer runtime state by using in-memory SQLModel engines and explicit test
rows.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest.mock import Mock

import pytest
import yaml
from runsight_core.observer import compute_soul_version
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus

EVAL_BLOCK_ID = "output_serialization_block"
EVAL_BLOCK_TYPE = "LinearBlock"
EVAL_RUN_ID = "eval-observer-run"
EVAL_WORKFLOW_ID = "eval-observer-workflow"
EVAL_WORKFLOW_NAME = "Eval Observer Workflow"
EVAL_OUTPUT = "Some output containing Sources information."
EVAL_TRANSFORM_RUN_ID = "eval-transform-run"
EVAL_TRANSFORM_WORKFLOW_ID = "eval-transform-workflow"
EVAL_TRANSFORM_WORKFLOW_NAME = "Eval Transform Workflow"
WORKFLOW_FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "eval_observer_custom_assertion"
)


def import_eval_observer():
    from runsight_api.logic.observers.eval_observer import EvalObserver

    return EvalObserver


def make_eval_observer_engine():
    """Create a test-owned in-memory SQLModel engine."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def seed_eval_run(
    engine,
    *,
    run_id: str = EVAL_RUN_ID,
    workflow_id: str = EVAL_WORKFLOW_ID,
    workflow_name: str = EVAL_WORKFLOW_NAME,
    status: RunStatus = RunStatus.pending,
) -> str:
    """Insert a Run row for isolated API tests."""
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                status=status,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()
    return run_id


def seed_eval_run_node(
    engine,
    *,
    run_id: str,
    block_id: str = EVAL_BLOCK_ID,
    block_type: str = EVAL_BLOCK_TYPE,
    status: str = "completed",
    cost_usd: float = 0.05,
    tokens_total: int = 1500,
    output: str = EVAL_OUTPUT,
    eval_score: float | None = None,
    eval_passed: bool | None = None,
    child_run_id: str | None = None,
) -> RunNode:
    """Insert a RunNode row for an evaluated block."""
    node = RunNode(
        id=f"{run_id}:{block_id}",
        run_id=run_id,
        node_id=block_id,
        block_type=block_type,
        status=status,
        cost_usd=cost_usd,
        tokens={"total": tokens_total},
        output=output,
        eval_score=eval_score,
        eval_passed=eval_passed,
        child_run_id=child_run_id,
    )
    with Session(engine) as session:
        session.add(node)
        session.commit()
        session.refresh(node)
        return node


def seed_eval_baseline_nodes(
    engine,
    soul: Soul,
    *,
    block_id: str = EVAL_BLOCK_ID,
    block_type: str = EVAL_BLOCK_TYPE,
    run_id_prefix: str = "soul-baseline-run",
    cost_usd: float = 0.04,
    tokens_total: int = 1200,
    eval_score: float = 0.9,
    count: int = 3,
) -> None:
    """Insert baseline RunNode rows for delta tests."""
    soul_version = compute_soul_version(soul)
    with Session(engine) as session:
        for index in range(count):
            run_id = f"{run_id_prefix}-{index}"
            session.add(
                RunNode(
                    id=f"{run_id}:{block_id}",
                    run_id=run_id,
                    node_id=block_id,
                    block_type=block_type,
                    status="completed",
                    soul_id=soul.id,
                    soul_version=soul_version,
                    cost_usd=cost_usd,
                    tokens={"total": tokens_total},
                    eval_score=eval_score,
                )
            )
        session.commit()


def make_eval_sse_queue():
    """Create an asyncio.Queue for SSE assertions."""
    return asyncio.Queue()


def make_eval_state(
    *,
    block_id: str = EVAL_BLOCK_ID,
    output: Any = EVAL_OUTPUT,
    total_cost_usd: float = 0.05,
    total_tokens: int = 1500,
) -> WorkflowState:
    """Create a WorkflowState with one completed block result."""
    return WorkflowState(
        total_cost_usd=total_cost_usd,
        total_tokens=total_tokens,
        results={block_id: BlockResult(output=output)},
    )


def make_eval_soul(
    *,
    soul_id: str = "researcher-v1",
    name: str = "Senior Researcher",
    role: str = "Senior Researcher",
    system_prompt: str = "You are a senior researcher.",
    model_name: str = "fixture-eval-model",
) -> Soul:
    """Create a stable Soul identity for EvalObserver tests."""
    return Soul(
        id=soul_id,
        kind="soul",
        name=name,
        role=role,
        system_prompt=system_prompt,
        model_name=model_name,
    )


def assertion_configs_for(
    block_id: str = EVAL_BLOCK_ID,
    *,
    kind: str = "contains",
    value: str = "Sources",
    weight: float = 1.0,
    threshold: float | None = None,
    assertions: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build assertion configs for one EvalObserver block."""
    if assertions is not None:
        return {block_id: assertions}

    config: dict[str, Any] = {"type": kind, "weight": weight}
    if kind == "cost":
        config["threshold"] = threshold if threshold is not None else 0.10
    else:
        config["value"] = value
    return {block_id: [config]}


def seed_eval_run_with_node(
    engine,
    *,
    run_id: str = EVAL_RUN_ID,
    workflow_id: str = EVAL_WORKFLOW_ID,
    workflow_name: str = EVAL_WORKFLOW_NAME,
    run_status: RunStatus = RunStatus.pending,
    block_id: str = EVAL_BLOCK_ID,
    block_type: str = EVAL_BLOCK_TYPE,
    cost_usd: float = 0.05,
    tokens_total: int = 1500,
    output: str = EVAL_OUTPUT,
) -> str:
    seed_eval_run(
        engine,
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        status=run_status,
    )
    seed_eval_run_node(
        engine,
        run_id=run_id,
        block_id=block_id,
        block_type=block_type,
        cost_usd=cost_usd,
        tokens_total=tokens_total,
        output=output,
    )
    return run_id


@pytest.fixture(name="transform_db_engine")
def transform_db_engine():
    return make_eval_observer_engine()


@pytest.fixture(name="transform_seed_run")
def transform_seed_run(transform_db_engine):
    run_id = EVAL_TRANSFORM_RUN_ID
    seed_eval_run(
        transform_db_engine,
        run_id=run_id,
        workflow_id=EVAL_TRANSFORM_WORKFLOW_ID,
        workflow_name=EVAL_TRANSFORM_WORKFLOW_NAME,
    )
    return transform_db_engine, run_id


@pytest.fixture(name="seed_run_with_node")
def transform_seed_run_with_node(transform_seed_run):
    engine, run_id = transform_seed_run
    seed_eval_run_node(
        engine,
        run_id=run_id,
        block_id="analyze",
        block_type="LinearBlock",
        cost_usd=0.03,
        tokens_total=800,
        output='{"result": "success", "extra": "data"}',
    )
    return engine, run_id


@pytest.fixture(name="sse_queue")
def transform_sse_queue():
    return make_eval_sse_queue()


@pytest.fixture(name="sample_soul")
def transform_sample_soul():
    return make_eval_soul(
        soul_id="analyst_v1",
        name="Data Analyst",
        role="Data Analyst",
        system_prompt="You are a data analyst.",
    )


@pytest.fixture(name="sample_state")
def transform_sample_state():
    return WorkflowState(
        total_cost_usd=0.03,
        total_tokens=800,
        results={
            "analyze": BlockResult(output='{"result": "success", "extra": "data"}'),
        },
    )


@pytest.fixture(name="transform_contains_success_configs")
def transform_contains_success_configs():
    return {
        "analyze": [
            {
                "type": "contains",
                "value": "success",
                "weight": 1.0,
                "transform": "json_path:$.result",
            },
        ],
    }


@pytest.fixture(name="transform_contains_extra_configs")
def transform_contains_extra_configs():
    return {
        "analyze": [
            {
                "type": "contains",
                "value": "extra",
                "weight": 1.0,
                "transform": "json_path:$.result",
            },
        ],
    }


@pytest.fixture(autouse=True, name="_isolate_custom_assertion_registry")
def isolate_custom_assertion_registry():
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


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def workflow_fixture_text(filename: str) -> str:
    return (WORKFLOW_FIXTURE_DIR / filename).read_text(encoding="utf-8")


def write_workflow_file(base_dir: Path, workflow_id: str, fixture_name: str) -> None:
    workflows_dir = base_dir / "custom" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / f"{workflow_id}.yaml").write_text(
        workflow_fixture_text(fixture_name),
        encoding="utf-8",
    )


def write_custom_assertion(
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
        "id": stem,
        "kind": "assertion",
        "version": "1.0",
        "name": stem.replace("_", " ").title(),
        "description": f"Custom assertion {stem}",
        "returns": returns,
        "source": f"{stem}.py",
    }
    if params is not None:
        manifest["params"] = params
    write_yaml(assertions_dir / f"{stem}.yaml", manifest)
    (assertions_dir / f"{stem}.py").write_text(dedent(code), encoding="utf-8")


def make_achat_response(content: str, cost_usd: float = 0.001, total_tokens: int = 100):
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


def git_service_for(base_dir: Path) -> Mock:
    git_service = Mock()

    def _list_files(branch: str, path_prefix: str) -> list[str]:
        del branch
        root = base_dir / path_prefix.rstrip("/")
        if not root.exists():
            return []
        return sorted(
            path.relative_to(base_dir).as_posix()
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".yaml", ".yml"}
        )

    def _read_file(workflow_path: str, branch: str) -> str:
        del branch
        path = Path(workflow_path)
        if not path.is_absolute():
            path = base_dir / workflow_path
        return path.read_text(encoding="utf-8")

    git_service.read_file.side_effect = _read_file
    git_service.get_sha.side_effect = lambda branch, workflow_path: "8" * 40
    git_service.list_files.side_effect = _list_files
    return git_service


async def wait_for_run_terminal(engine, run_id: str, timeout: float = 10.0):
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


@pytest.fixture(name="db_engine")
def custom_assertion_db_engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


def seed_custom_assertion_workspace(base_dir: Path) -> Path:
    write_workflow_file(base_dir, "promptfoo-eval-workflow", "promptfoo-eval-workflow.yaml")
    write_workflow_file(
        base_dir,
        "negated-custom-eval-workflow",
        "negated-custom-eval-workflow.yaml",
    )
    write_workflow_file(
        base_dir,
        "invalid-config-eval-workflow",
        "invalid-config-eval-workflow.yaml",
    )
    write_custom_assertion(
        base_dir,
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
    write_custom_assertion(
        base_dir,
        stem="blocked_word",
        returns="bool",
        code="""
            def get_assert(output, context):
                return context.get("config", {}).get("blocked") in output
            """,
    )
    write_custom_assertion(
        base_dir,
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
    return base_dir


@pytest.fixture(name="base_dir")
def custom_assertion_base_dir(tmp_path):
    base = tmp_path / "runtime-workspace"
    return seed_custom_assertion_workspace(base)


@pytest.fixture(name="mock_provider")
def mock_provider():
    provider = Mock()
    provider.id = "openai"
    provider.type = "openai"
    provider.api_key = "dummy-test"
    provider.is_active = True
    provider.models = ["gpt-4o"]
    return provider


def capture_eval_events(execution_service):
    captured_events: list[dict] = []
    original_unregister = execution_service._streams.unregister

    def _capture_then_unregister(rid):
        obs = execution_service._streams.get(rid)
        if obs:
            while not obs.queue.empty():
                captured_events.append(obs.queue.get_nowait())
        original_unregister(rid)

    execution_service._streams.unregister = _capture_then_unregister
    return captured_events


@pytest.fixture(name="app_with_real_services")
def app_with_real_services(db_engine, base_dir):
    from fastapi import FastAPI

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
    git_service = git_service_for(base_dir)

    mock_secrets = Mock()
    mock_secrets.resolve = Mock(return_value="dummy-fake-test-key-for-assertion-integration")
    execution_session = Session(db_engine)

    execution_service = ExecutionService(
        run_repo=RunRepository(execution_session),
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=db_engine,
        secrets=mock_secrets,
        git_service=git_service,
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
    execution_session.close()
