"""ExecutionObserver BlockResult serialization.

ExecutionObserver must:
  - Extract .output from BlockResult when writing RunNode.output
  - Use .model_dump() when serializing results_json
"""

import json

import pytest
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus

BLOCK_RESULT_WORKFLOW_ID = "block-result-workflow"
BLOCK_RESULT_WORKFLOW_NAME = "Block Result Workflow"

# ---------------------------------------------------------------------------
# Deferred import helper
# ---------------------------------------------------------------------------


def _import_execution_observer():
    from runsight_api.logic.observers.execution_observer import ExecutionObserver

    return ExecutionObserver


# ---------------------------------------------------------------------------
# Shared fixtures (same pattern as test_execution_observer.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine with all needed tables."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def seed_run(db_engine):
    """Insert a pending Run record and return (engine, run_id)."""
    run_id = "block-result-run"
    with Session(db_engine) as session:
        run = Run(
            id=run_id,
            workflow_id=BLOCK_RESULT_WORKFLOW_ID,
            workflow_name=BLOCK_RESULT_WORKFLOW_NAME,
            status=RunStatus.running,
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


# ---------------------------------------------------------------------------
# 1. RunNode.output extraction (on_block_complete)
# ---------------------------------------------------------------------------


class TestRunNodeOutputExtraction:
    """Tests that on_block_complete extracts the .output string from BlockResult."""

    def test_output_contains_block_result_output_text(self, observer):
        """When state.results has a BlockResult, node.output should be the .output string."""
        obs, engine, run_id = observer
        obs.on_block_start(BLOCK_RESULT_WORKFLOW_ID, "output_serialization_block", "LinearBlock")

        result = BlockResult(output="The analysis is complete.")
        state = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=500,
            results={"output_serialization_block": result},
        )
        obs.on_block_complete(
            BLOCK_RESULT_WORKFLOW_ID, "output_serialization_block", "LinearBlock", 1.0, state
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:output_serialization_block")
            assert node.output == "The analysis is complete."

    def test_output_is_plain_string_not_block_result_repr(self, observer):
        """node.output must be a plain string, not a BlockResult repr or model dump."""
        obs, engine, run_id = observer
        obs.on_block_start(BLOCK_RESULT_WORKFLOW_ID, "output_serialization_block", "LinearBlock")

        result = BlockResult(
            output="Hello world",
            artifact_ref="artifact://fixture/file.txt",
            artifact_type="text",
        )
        state = WorkflowState(
            total_cost_usd=0.01,
            total_tokens=100,
            results={"output_serialization_block": result},
        )
        obs.on_block_complete(
            BLOCK_RESULT_WORKFLOW_ID, "output_serialization_block", "LinearBlock", 0.5, state
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:output_serialization_block")
            # Must be exactly the .output string, not a JSON dump or repr
            assert node.output == "Hello world"
            # Must NOT contain artifact_ref (that would mean a repr/dump was stored)
            assert "artifact://" not in (node.output or "")

    def test_none_guard_when_block_not_in_results(self, observer):
        """When state.results does NOT have the block_id, node.output should be None."""
        obs, engine, run_id = observer
        obs.on_block_start(BLOCK_RESULT_WORKFLOW_ID, "missing_result_block", "LinearBlock")

        # results dict has no entry for "missing_result_block"
        state = WorkflowState(
            total_cost_usd=0.01,
            total_tokens=100,
            results={},
        )
        obs.on_block_complete(
            BLOCK_RESULT_WORKFLOW_ID, "missing_result_block", "LinearBlock", 0.5, state
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:missing_result_block")
            assert node.output is None

    def test_output_from_block_result(self, observer):
        """When results contains a BlockResult, node.output uses its .output value."""
        obs, engine, run_id = observer
        obs.on_block_start(BLOCK_RESULT_WORKFLOW_ID, "block_result_output_block", "LinearBlock")

        # Auto-coercion is retired; pass BlockResult explicitly.
        state = WorkflowState(
            total_cost_usd=0.02,
            total_tokens=200,
            results={"block_result_output_block": BlockResult(output="Block result output")},
        )
        obs.on_block_complete(
            BLOCK_RESULT_WORKFLOW_ID, "block_result_output_block", "LinearBlock", 0.3, state
        )

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_result_output_block")
            assert node.output == "Block result output"


# ---------------------------------------------------------------------------
# 2. Run.results_json serialization (on_workflow_complete)
# ---------------------------------------------------------------------------


class TestResultsJsonSerialization:
    """Tests that on_workflow_complete serializes BlockResult via .model_dump()."""

    def test_results_json_is_valid_json(self, observer):
        """results_json should be valid JSON (not raise TypeError)."""
        obs, engine, run_id = observer
        state = WorkflowState(
            results={"output_serialization_block": BlockResult(output="output_a")},
        )
        obs.on_workflow_complete(BLOCK_RESULT_WORKFLOW_ID, state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.results_json is not None
            # Should not raise json.JSONDecodeError
            parsed = json.loads(run.results_json)
            assert isinstance(parsed, dict)

    def test_results_json_contains_full_block_result_structure(self, observer):
        """Each value in results_json should be a dict with 'output' key, not a plain string."""
        obs, engine, run_id = observer
        state = WorkflowState(
            results={"output_serialization_block": BlockResult(output="output_a")},
        )
        obs.on_workflow_complete(BLOCK_RESULT_WORKFLOW_ID, state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            # Value should be a dict (model_dump), not a raw string
            assert isinstance(parsed["output_serialization_block"], dict), (
                f"Expected dict from model_dump(), got {type(parsed['output_serialization_block'])}: {parsed['output_serialization_block']}"
            )
            assert parsed["output_serialization_block"]["output"] == "output_a"

    def test_results_json_includes_null_optional_fields(self, observer):
        """BlockResult with no artifact_ref should serialize with null for optional fields."""
        obs, engine, run_id = observer
        state = WorkflowState(
            results={"output_serialization_block": BlockResult(output="just output")},
        )
        obs.on_workflow_complete(BLOCK_RESULT_WORKFLOW_ID, state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            output_serialization_block = parsed["output_serialization_block"]
            assert output_serialization_block["output"] == "just output"
            assert output_serialization_block["artifact_ref"] is None
            assert output_serialization_block["artifact_type"] is None
            assert output_serialization_block["metadata"] is None

    def test_results_json_includes_artifact_ref(self, observer):
        """BlockResult with artifact_ref should include it in the JSON."""
        obs, engine, run_id = observer
        state = WorkflowState(
            results={
                "output_serialization_block": BlockResult(
                    output="generated report",
                    artifact_ref="artifact://fixture/report.pdf",
                    artifact_type="pdf",
                ),
            },
        )
        obs.on_workflow_complete(BLOCK_RESULT_WORKFLOW_ID, state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            output_serialization_block = parsed["output_serialization_block"]
            assert output_serialization_block["output"] == "generated report"
            assert output_serialization_block["artifact_ref"] == "artifact://fixture/report.pdf"
            assert output_serialization_block["artifact_type"] == "pdf"

    def test_empty_results_produces_empty_json_object(self, observer):
        """Empty results dict should produce '{}'."""
        obs, engine, run_id = observer
        state = WorkflowState(results={})
        obs.on_workflow_complete(BLOCK_RESULT_WORKFLOW_ID, state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run.results_json is not None
            parsed = json.loads(run.results_json)
            assert parsed == {}

    def test_multiple_blocks_all_serialize_as_dicts(self, observer):
        """Multiple BlockResults should all serialize as dicts with 'output' key."""
        obs, engine, run_id = observer
        state = WorkflowState(
            results={
                "output_serialization_block": BlockResult(output="output_a"),
                "secondary_result_block": BlockResult(output="output_b"),
                "block_result_output_block": BlockResult(
                    output="output_c",
                    artifact_ref="ref_c",
                    metadata={"key": "value"},
                ),
            },
        )
        obs.on_workflow_complete(BLOCK_RESULT_WORKFLOW_ID, state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            assert len(parsed) == 3
            for block_id in [
                "output_serialization_block",
                "secondary_result_block",
                "block_result_output_block",
            ]:
                assert isinstance(parsed[block_id], dict), (
                    f"{block_id}: expected dict, got {type(parsed[block_id])}"
                )
                assert "output" in parsed[block_id]

            # Verify metadata on block_result_output_block
            assert parsed["block_result_output_block"]["metadata"] == {"key": "value"}


# ---------------------------------------------------------------------------
# 3. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for BlockResult serialization in the observer."""

    def test_mixed_results_with_and_without_artifacts(self, observer):
        """Mixed results: one block with artifact_ref, one without — both serialize correctly."""
        obs, engine, run_id = observer

        # Start both blocks
        obs.on_block_start(BLOCK_RESULT_WORKFLOW_ID, "plain_block", "LinearBlock")
        obs.on_block_start(BLOCK_RESULT_WORKFLOW_ID, "artifact_block", "LinearBlock")

        # Complete with mixed results
        state_plain = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=500,
            results={
                "plain_block": BlockResult(output="plain output"),
                "artifact_block": BlockResult(
                    output="artifact output",
                    artifact_ref="artifact://fixture/file.txt",
                    artifact_type="text",
                ),
            },
        )

        obs.on_block_complete(
            BLOCK_RESULT_WORKFLOW_ID, "plain_block", "LinearBlock", 1.0, state_plain
        )
        obs.on_block_complete(
            BLOCK_RESULT_WORKFLOW_ID, "artifact_block", "LinearBlock", 1.0, state_plain
        )

        with Session(engine) as session:
            plain_node = session.get(RunNode, f"{run_id}:plain_block")
            artifact_node = session.get(RunNode, f"{run_id}:artifact_block")

            # Both should have plain string outputs
            assert plain_node.output == "plain output"
            assert artifact_node.output == "artifact output"

        # Now complete the workflow and check results_json
        obs.on_workflow_complete(BLOCK_RESULT_WORKFLOW_ID, state_plain, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)

            # plain_block: no artifact
            assert parsed["plain_block"]["artifact_ref"] is None

            # artifact_block: has artifact
            assert parsed["artifact_block"]["artifact_ref"] == "artifact://fixture/file.txt"

    def test_block_with_metadata_in_result(self, observer):
        """BlockResult with metadata dict should round-trip through results_json."""
        obs, engine, run_id = observer
        metadata = {"model": "fixture-metadata-model", "temperature": 0.7, "tokens_used": 1500}
        state = WorkflowState(
            results={
                "output_serialization_block": BlockResult(
                    output="some output",
                    metadata=metadata,
                ),
            },
        )
        obs.on_workflow_complete(BLOCK_RESULT_WORKFLOW_ID, state, 3.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            assert parsed["output_serialization_block"]["metadata"] == metadata
