"""Assertion config wiring test fixtures."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from runsight_core.redaction import RunRedactor
from runsight_core.yaml.parser import parse_workflow_yaml
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.execution_service import PreparedRunInputs

ASSERTION_WIRING_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "assertion_wiring"


def write_soul_file(base_dir: Path, name: str, content: str) -> None:
    """Create a soul YAML file at custom/souls/<name>.yaml."""
    souls_dir = base_dir / "custom" / "souls"
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / f"{name}.yaml").write_text(dedent(content), encoding="utf-8")


class AssertionWiringWorkspace:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir()

    def parse_block_assertion_workflow(self) -> object:
        write_soul_file(
            self.base_dir,
            "analyst",
            """\
            id: analyst
            kind: soul
            name: Analyst
            role: Analyst
            system_prompt: You are a careful analyst.
            """,
        )
        return self._parse_fixture("block-with-assertions.yaml")

    def parse_step_assertion_workflow(self) -> object:
        write_soul_file(
            self.base_dir,
            "researcher",
            """\
            id: researcher
            kind: soul
            name: Researcher
            role: Researcher
            system_prompt: You research data.
            """,
        )
        write_soul_file(
            self.base_dir,
            "analyst",
            """\
            id: analyst
            kind: soul
            name: Analyst
            role: Analyst
            system_prompt: You are a careful analyst.
            """,
        )
        return self._parse_fixture("step-with-assertions.yaml")

    def _parse_fixture(self, filename: str) -> object:
        workflow_file = self.base_dir / "workflow.yaml"
        workflow_file.write_text(workflow_fixture_yaml(filename), encoding="utf-8")
        return parse_workflow_yaml(str(workflow_file))


def workflow_fixture_yaml(filename: str) -> str:
    return (ASSERTION_WIRING_FIXTURES / filename).read_text(encoding="utf-8")


def prepared_inputs(inputs: dict[str, object]) -> PreparedRunInputs:
    return PreparedRunInputs(
        normalized_inputs=dict(inputs),
        input_redactor=RunRedactor(),
    )


@pytest.fixture(name="assertion_wiring_workspace")
def assertion_wiring_workspace(tmp_path: Path) -> AssertionWiringWorkspace:
    return AssertionWiringWorkspace(tmp_path / "assertion-wiring-workspace")


@pytest.fixture(name="db_engine")
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def seed_run(engine, run_id: str, workflow_name: str) -> None:
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id="block-assertion-workflow",
                workflow_name=workflow_name,
                status=RunStatus.pending,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()


def fake_result(output: str = "This analysis includes the requested details.") -> Mock:
    result = Mock()
    result.output = output
    result.cost_usd = 0.005
    result.total_tokens = 300
    result.exit_handle = None
    return result


def drain_queue(queue):
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events


def workflow_namespace(blocks: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(_blocks=blocks)
