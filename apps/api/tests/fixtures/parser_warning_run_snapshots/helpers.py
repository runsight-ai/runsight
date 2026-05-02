from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlmodel import SQLModel, Session, create_engine

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import PreparedRunInputs
from runsight_core.redaction import RunRedactor

FIXTURE_DIR = Path(__file__).parent


def write_warning_soul(base_dir: Path, soul_key: str) -> None:
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{soul_key}.yaml").write_text(
        "\n".join(
            [
                f"id: {soul_key}",
                "kind: soul",
                "name: Warning Soul",
                "role: Warning Soul",
                "system_prompt: You are a warning-only soul.",
                "provider: openai",
                "model_name: gpt-4o",
                "tools: [http]",
                "",
            ]
        ),
        encoding="utf-8",
    )


def prepared_inputs(inputs: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=dict(inputs),
        input_redactor=RunRedactor(),
    )


def write_openai_provider(base_dir: Path) -> None:
    provider_dir = base_dir / "custom" / "providers"
    provider_dir.mkdir(parents=True, exist_ok=True)
    (provider_dir / "openai.yaml").write_text(
        "\n".join(
            [
                "id: openai",
                "kind: provider",
                "name: openai",
                "type: openai",
                "api_key: ${OPENAI_API_KEY}",
                "is_active: true",
                "models:",
                "  - gpt-4o",
                "",
            ]
        ),
        encoding="utf-8",
    )


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


def write_corrupt_custom_tool(base_dir: Path, tool_id: str) -> None:
    tools_dir = base_dir / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / f"{tool_id}.yaml").write_text(
        "\n".join(
            [
                'version: "1.0"',
                f"id: {tool_id}",
                "kind: tool",
                "type: custom",
                "executor: python",
                "name: Broken lookup",
                "description: Intentionally broken metadata",
                "parameters:",
                "  type: object",
                "code: |",
                "  def main(args):",
                "      return {'broken':",
                "",
            ]
        ),
        encoding="utf-8",
    )


def warning_workflow_yaml(soul_key: str, *, declare_http: bool) -> str:
    tools_section = "tools:\n  - http\n" if declare_http else ""
    return (
        'version: "1.0"\n'
        "id: parser-warning-workflow\n"
        "kind: workflow\n"
        "config:\n"
        "  model_name: gpt-4o\n"
        f"{tools_section}"
        "blocks:\n"
        "  analyze:\n"
        "    type: linear\n"
        f"    soul_ref: {soul_key}\n"
        "workflow:\n"
        "  name: parser_warning_workflow\n"
        "  entry: analyze\n"
        "  transitions:\n"
        "    - from: analyze\n"
        "      to: null\n"
    )


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def make_achat_response(content: str):
    return {
        "content": content,
        "cost_usd": 0.001,
        "prompt_tokens": 50,
        "completion_tokens": 50,
        "total_tokens": 100,
        "tool_calls": None,
        "finish_reason": "stop",
        "raw_message": {"role": "assistant", "content": content},
    }


async def wait_for_run_terminal(engine, run_id: str, timeout: float = 10.0):
    deadline = asyncio.get_running_loop().time() + timeout
    terminal = {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}
    while asyncio.get_running_loop().time() < deadline:
        with Session(engine) as session:
            run = session.get(Run, run_id)
            if run is not None and run.status in terminal:
                return run
        await asyncio.sleep(0.1)
    with Session(engine) as session:
        return session.get(Run, run_id)


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def base_dir(tmp_path):
    workspace = tmp_path / "runtime-workspace"
    workspace.mkdir()
    yield workspace
