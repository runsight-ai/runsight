"""Shared fixtures and helpers for API SSE streaming tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from sqlmodel import SQLModel, Session, create_engine

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.domain.events import SSE_TERMINAL_EVENTS
from runsight_api.logic.services.execution_service import PreparedRunInputs
from runsight_core.redaction import RunRedactor

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sse_streaming"
_WORKFLOW_FIXTURES = {
    "single-block": "single-block.yaml",
    "two-block": "two-block.yaml",
    "parent-workflow": "parent-workflow.yaml",
    "child-workflow": "child-workflow.yaml",
}


def workflow_fixture_text(workflow_id: str) -> str:
    return (_FIXTURE_DIR / _WORKFLOW_FIXTURES[workflow_id]).read_text(encoding="utf-8")


def _write_workflow_file(base_dir: Path, workflow_id: str, content: str) -> None:
    wf_dir = base_dir / "custom" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    canvas_dir = wf_dir / ".canvas"
    canvas_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / f"{workflow_id}.yaml").write_text(content, encoding="utf-8")


def write_fixture_workflows(base_dir: Path) -> None:
    for workflow_id in _WORKFLOW_FIXTURES:
        _write_workflow_file(base_dir, workflow_id, workflow_fixture_text(workflow_id))


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


def _git_service_for(base_dir: Path) -> Mock:
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
    git_service.get_sha.side_effect = lambda branch, workflow_path: "7" * 40
    git_service.list_files.side_effect = _list_files
    return git_service


def _seed_run(engine, run_id: str, workflow_name: str) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="sse-stream-fixture-workflow",
                workflow_name=workflow_name,
                branch="main",
                status=RunStatus.pending,
                task_json="{}",
            )
        )
        session.commit()


def _mock_provider():
    mock = Mock()
    mock.id = "openai"
    mock.type = "openai"
    mock.api_key = "dummy-test"
    mock.is_active = True
    mock.models = ["gpt-4o"]
    return mock


def _parse_sse_events(raw: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = []

    for line in raw.split("\n"):
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data.append(line[len("data:") :].strip())
        elif line == "" and current_event is not None:
            data_str = "\n".join(current_data)
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = data_str
            events.append({"event": current_event, "data": data})
            current_event = None
            current_data = []

    return events


def _gated_achat(gate: asyncio.Event, content: str = "Done."):
    """Create an async mock for LiteLLMClient.achat that waits on a gate."""

    async def _achat(*args, **kwargs):
        await gate.wait()
        return _make_achat_response(content)

    return _achat


@pytest.fixture
def db_engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def base_dir(tmp_path: Path) -> Path:
    write_fixture_workflows(tmp_path)
    return tmp_path


@pytest.fixture
def execution_service(db_engine, base_dir):
    """Build a real ExecutionService backed by in-memory DB and temp filesystem."""
    from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo
    from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
    from runsight_api.data.repositories.run_repo import RunRepository
    from runsight_api.logic.services.execution_service import ExecutionService

    workflow_repo = WorkflowRepository(str(base_dir))
    provider_repo = FileSystemProviderRepo(base_path=str(base_dir))
    git_service = _git_service_for(base_dir)

    mock_secrets = Mock()
    mock_secrets.resolve = Mock(return_value="dummy-fake-test-key-for-sse-integration")
    execution_session = Session(db_engine)

    yield ExecutionService(
        run_repo=RunRepository(execution_session),
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
        engine=db_engine,
        secrets=mock_secrets,
        git_service=git_service,
        settings_repo=None,
    )
    execution_session.close()


def _parse_workflow(yaml_content: str):
    """Parse a workflow YAML string into a runnable Workflow object."""
    from runsight_core.yaml.parser import parse_workflow_yaml

    import yaml

    raw = yaml.safe_load(yaml_content)
    return parse_workflow_yaml(raw)


def parse_workflow_fixture(workflow_id: str):
    return _parse_workflow(workflow_fixture_text(workflow_id))


async def _wait_for_observer(execution_service, run_id: str, timeout: float = 5.0):
    """Wait until the observer for run_id is registered."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if execution_service._streams.get(run_id) is not None:
            return
        await asyncio.sleep(0.005)
    raise TimeoutError(f"Observer for {run_id} was never registered")


async def _collect_stream_events(
    execution_service, run_id: str, timeout: float = 10.0
) -> list[dict]:
    """Collect all events from subscribe_stream until a terminal event or timeout."""
    events: list[dict] = []
    deadline = asyncio.get_event_loop().time() + timeout

    async for event in execution_service.subscribe_stream(run_id):
        events.append(event)
        if event["event"] in SSE_TERMINAL_EVENTS:
            break
        if asyncio.get_event_loop().time() > deadline:
            break

    return events


async def _run_and_collect(
    execution_service,
    run_id: str,
    wf,
    task_data: dict[str, Any],
    gate: asyncio.Event,
    mock_provider,
) -> list[dict]:
    """Run workflow and collect stream events concurrently."""
    with (
        patch(
            "runsight_core.llm.client.LiteLLMClient.achat",
            side_effect=_gated_achat(gate),
        ),
        patch.object(
            execution_service.provider_repo,
            "list_all",
            return_value=[mock_provider],
        ),
    ):
        prepared_inputs = PreparedRunInputs(
            normalized_inputs=task_data,
            input_redactor=RunRedactor(),
            workflow_inputs={},
            workflow_input_schema={},
        )
        run_task = asyncio.create_task(execution_service._run_workflow(run_id, wf, prepared_inputs))

        await _wait_for_observer(execution_service, run_id)

        collect_task = asyncio.create_task(_collect_stream_events(execution_service, run_id))

        gate.set()

        events = await collect_task
        await run_task

    return events
