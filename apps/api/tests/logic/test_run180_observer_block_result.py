"""Red tests for RUN-180: ExecutionObserver BlockResult serialization.

After RUN-177, WorkflowState.results is Dict[str, BlockResult] with auto-coercion.
ExecutionObserver must:
  - Extract .output from BlockResult when writing RunNode.output (line 113)
  - Use .model_dump() when serializing results_json (line 192)

All tests should FAIL until the implementation is updated.
"""

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus
from runsight_core.state import BlockResult, WorkflowState


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
    run_id = "run_test_180"
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
        obs.on_block_start("wf", "block_a", "LinearBlock")

        result = BlockResult(output="The analysis is complete.")
        state = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=500,
            results={"block_a": result},
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 1.0, state)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            assert node.output == "The analysis is complete."

    def test_output_is_plain_string_not_block_result_repr(self, observer):
        """node.output must be a plain string, not a BlockResult repr or model dump."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_a", "LinearBlock")

        result = BlockResult(
            output="Hello world",
            artifact_ref="s3://bucket/file.txt",
            artifact_type="text",
        )
        state = WorkflowState(
            total_cost_usd=0.01,
            total_tokens=100,
            results={"block_a": result},
        )
        obs.on_block_complete("wf", "block_a", "LinearBlock", 0.5, state)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_a")
            # Must be exactly the .output string, not a JSON dump or repr
            assert node.output == "Hello world"
            # Must NOT contain artifact_ref (that would mean a repr/dump was stored)
            assert "s3://" not in (node.output or "")

    def test_none_guard_when_block_not_in_results(self, observer):
        """When state.results does NOT have the block_id, node.output should be None."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_missing", "LinearBlock")

        # results dict has no entry for "block_missing"
        state = WorkflowState(
            total_cost_usd=0.01,
            total_tokens=100,
            results={},
        )
        obs.on_block_complete("wf", "block_missing", "LinearBlock", 0.5, state)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_missing")
            assert node.output is None

    def test_output_from_coerced_string_result(self, observer):
        """When results dict has a raw string (auto-coerced to BlockResult),
        node.output should still be the extracted .output string."""
        obs, engine, run_id = observer
        obs.on_block_start("wf", "block_c", "LinearBlock")

        # WorkflowState auto-coerces strings to BlockResult via field_validator
        state = WorkflowState(
            total_cost_usd=0.02,
            total_tokens=200,
            results={"block_c": "Auto coerced output"},
        )
        obs.on_block_complete("wf", "block_c", "LinearBlock", 0.3, state)

        with Session(engine) as session:
            node = session.get(RunNode, f"{run_id}:block_c")
            assert node.output == "Auto coerced output"


# ---------------------------------------------------------------------------
# 2. Run.results_json serialization (on_workflow_complete)
# ---------------------------------------------------------------------------


class TestResultsJsonSerialization:
    """Tests that on_workflow_complete serializes BlockResult via .model_dump()."""

    def test_results_json_is_valid_json(self, observer):
        """results_json should be valid JSON (not raise TypeError)."""
        obs, engine, run_id = observer
        state = WorkflowState(
            results={"block_a": BlockResult(output="output_a")},
        )
        obs.on_workflow_complete("wf", state, 5.0)

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
            results={"block_a": BlockResult(output="output_a")},
        )
        obs.on_workflow_complete("wf", state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            # Value should be a dict (model_dump), not a raw string
            assert isinstance(parsed["block_a"], dict), (
                f"Expected dict from model_dump(), got {type(parsed['block_a'])}: {parsed['block_a']}"
            )
            assert parsed["block_a"]["output"] == "output_a"

    def test_results_json_includes_null_optional_fields(self, observer):
        """BlockResult with no artifact_ref should serialize with null for optional fields."""
        obs, engine, run_id = observer
        state = WorkflowState(
            results={"block_a": BlockResult(output="just output")},
        )
        obs.on_workflow_complete("wf", state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            block_a = parsed["block_a"]
            assert block_a["output"] == "just output"
            assert block_a["artifact_ref"] is None
            assert block_a["artifact_type"] is None
            assert block_a["metadata"] is None

    def test_results_json_includes_artifact_ref(self, observer):
        """BlockResult with artifact_ref should include it in the JSON."""
        obs, engine, run_id = observer
        state = WorkflowState(
            results={
                "block_a": BlockResult(
                    output="generated report",
                    artifact_ref="s3://bucket/report.pdf",
                    artifact_type="pdf",
                ),
            },
        )
        obs.on_workflow_complete("wf", state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            block_a = parsed["block_a"]
            assert block_a["output"] == "generated report"
            assert block_a["artifact_ref"] == "s3://bucket/report.pdf"
            assert block_a["artifact_type"] == "pdf"

    def test_empty_results_produces_empty_json_object(self, observer):
        """Empty results dict should produce '{}'."""
        obs, engine, run_id = observer
        state = WorkflowState(results={})
        obs.on_workflow_complete("wf", state, 5.0)

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
                "block_a": BlockResult(output="output_a"),
                "block_b": BlockResult(output="output_b"),
                "block_c": BlockResult(
                    output="output_c",
                    artifact_ref="ref_c",
                    metadata={"key": "value"},
                ),
            },
        )
        obs.on_workflow_complete("wf", state, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            assert len(parsed) == 3
            for block_id in ["block_a", "block_b", "block_c"]:
                assert isinstance(parsed[block_id], dict), (
                    f"{block_id}: expected dict, got {type(parsed[block_id])}"
                )
                assert "output" in parsed[block_id]

            # Verify metadata on block_c
            assert parsed["block_c"]["metadata"] == {"key": "value"}


# ---------------------------------------------------------------------------
# 3. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for BlockResult serialization in the observer."""

    def test_mixed_results_with_and_without_artifacts(self, observer):
        """Mixed results: one block with artifact_ref, one without — both serialize correctly."""
        obs, engine, run_id = observer

        # Start both blocks
        obs.on_block_start("wf", "plain_block", "LinearBlock")
        obs.on_block_start("wf", "artifact_block", "LinearBlock")

        # Complete with mixed results
        state_plain = WorkflowState(
            total_cost_usd=0.05,
            total_tokens=500,
            results={
                "plain_block": BlockResult(output="plain output"),
                "artifact_block": BlockResult(
                    output="artifact output",
                    artifact_ref="s3://bucket/file.txt",
                    artifact_type="text",
                ),
            },
        )

        obs.on_block_complete("wf", "plain_block", "LinearBlock", 1.0, state_plain)
        obs.on_block_complete("wf", "artifact_block", "LinearBlock", 1.0, state_plain)

        with Session(engine) as session:
            plain_node = session.get(RunNode, f"{run_id}:plain_block")
            artifact_node = session.get(RunNode, f"{run_id}:artifact_block")

            # Both should have plain string outputs
            assert plain_node.output == "plain output"
            assert artifact_node.output == "artifact output"

        # Now complete the workflow and check results_json
        obs.on_workflow_complete("wf", state_plain, 5.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)

            # plain_block: no artifact
            assert parsed["plain_block"]["artifact_ref"] is None

            # artifact_block: has artifact
            assert parsed["artifact_block"]["artifact_ref"] == "s3://bucket/file.txt"

    def test_block_with_metadata_in_result(self, observer):
        """BlockResult with metadata dict should round-trip through results_json."""
        obs, engine, run_id = observer
        metadata = {"model": "gpt-4", "temperature": 0.7, "tokens_used": 1500}
        state = WorkflowState(
            results={
                "block_a": BlockResult(
                    output="some output",
                    metadata=metadata,
                ),
            },
        )
        obs.on_workflow_complete("wf", state, 3.0)

        with Session(engine) as session:
            run = session.get(Run, run_id)
            parsed = json.loads(run.results_json)
            assert parsed["block_a"]["metadata"] == metadata
