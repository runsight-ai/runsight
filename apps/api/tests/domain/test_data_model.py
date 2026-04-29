"""Run data model branch, source, and commit SHA coverage.

Tests cover:
1. Run entity has `branch` field and requires it explicitly
2. Run entity has `source` field (default "manual")
3. Run entity has `commit_sha` field (optional, default None)
5. RunResponse exposes branch, source, commit_sha
6. RunCreate allows omitted branch and accepts source (optional)
7. create_run() requires branch and stores it explicitly
8. commit_sha stays independent from workflow_commit_sha
"""

from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine

EXPLICIT_BRANCH = "sim/test/20260330/abc12"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(*, branch: str, **overrides):
    """Create a Run with minimal required fields, applying overrides."""
    from runsight_api.domain.entities.run import Run

    defaults = dict(
        id="run-data-model",
        workflow_id="workflow-data-model",
        workflow_name="Data model workflow",
        task_json='{"instruction": "go"}',
        branch=branch,
    )
    defaults.update(overrides)
    return Run(**defaults)


def _in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _prepared(inputs: dict[str, object] | None = None):
    from runsight_core.redaction import RunRedactor

    from runsight_api.logic.services.execution_service import PreparedRunInputs

    return PreparedRunInputs(
        normalized_inputs=inputs or {},
        input_redactor=RunRedactor(),
        workflow_inputs={},
        workflow_input_schema={},
    )


# ---------------------------------------------------------------------------
# 1. Run entity — branch field
# ---------------------------------------------------------------------------


class TestRunBranchField:
    def test_run_has_branch_attribute(self):
        """Run entity exposes a `branch` attribute."""
        run = _make_run(branch=EXPLICIT_BRANCH)
        assert hasattr(run, "branch")

    def test_branch_requires_explicit_value(self):
        """Constructing Run without branch should raise validation error."""
        from runsight_api.domain.entities.run import Run

        with pytest.raises(ValidationError):
            Run(
                id="run-branch-required",
                workflow_id="workflow-data-model",
                workflow_name="Data model workflow",
                task_json='{"instruction": "go"}',
            )

    def test_branch_accepts_custom_value(self):
        """branch can be set to a custom string."""
        run = _make_run(branch="feat/experiment")
        assert run.branch == "feat/experiment"

    def test_branch_persists_in_db(self):
        """branch round-trips through SQLite."""
        engine = _in_memory_engine()
        with Session(engine) as session:
            session.add(
                _make_run(
                    branch="sim/test/20260329/abc",
                    id="run-branch-db",
                )
            )
            session.commit()
        with Session(engine) as session:
            from runsight_api.domain.entities.run import Run

            loaded = session.get(Run, "run-branch-db")
            assert loaded.branch == "sim/test/20260329/abc"

    def test_branch_missing_is_rejected_by_model(self):
        """Run should not silently backfill a branch when one is omitted."""
        from runsight_api.domain.entities.run import Run

        with pytest.raises(ValidationError):
            Run(
                id="run-branch-missing",
                workflow_id="workflow-data-model",
                workflow_name="Data model workflow",
                task_json='{"instruction": "go"}',
                source="manual",
            )


# ---------------------------------------------------------------------------
# 2. Run entity — source field
# ---------------------------------------------------------------------------


class TestRunSourceField:
    def test_run_has_source_attribute(self):
        """Run entity exposes a `source` attribute."""
        run = _make_run(branch=EXPLICIT_BRANCH)
        assert hasattr(run, "source")

    def test_source_defaults_to_manual(self):
        """source defaults to 'manual' when not provided."""
        run = _make_run(branch=EXPLICIT_BRANCH)
        assert run.source == "manual"

    def test_source_accepts_simulation(self):
        run = _make_run(branch=EXPLICIT_BRANCH, source="simulation")
        assert run.source == "simulation"

    def test_source_accepts_webhook(self):
        run = _make_run(branch=EXPLICIT_BRANCH, source="webhook")
        assert run.source == "webhook"

    def test_source_accepts_schedule(self):
        run = _make_run(branch=EXPLICIT_BRANCH, source="schedule")
        assert run.source == "schedule"

    def test_source_persists_in_db(self):
        """source round-trips through SQLite."""
        engine = _in_memory_engine()
        with Session(engine) as session:
            session.add(
                _make_run(
                    branch=EXPLICIT_BRANCH,
                    id="run-source-db",
                    source="webhook",
                )
            )
            session.commit()
        with Session(engine) as session:
            from runsight_api.domain.entities.run import Run

            loaded = session.get(Run, "run-source-db")
            assert loaded.source == "webhook"


# ---------------------------------------------------------------------------
# 3. Run entity — commit_sha field (new, alongside deprecated workflow_commit_sha)
# ---------------------------------------------------------------------------


class TestRunCommitShaField:
    def test_run_has_commit_sha_attribute(self):
        """Run entity exposes a `commit_sha` attribute."""
        run = _make_run(branch=EXPLICIT_BRANCH)
        assert hasattr(run, "commit_sha")

    def test_commit_sha_defaults_to_none(self):
        """commit_sha defaults to None when not provided."""
        run = _make_run(branch=EXPLICIT_BRANCH)
        assert run.commit_sha is None

    def test_commit_sha_accepts_string(self):
        sha = "abc123def456789012345678901234567890abcd"
        run = _make_run(branch=EXPLICIT_BRANCH, commit_sha=sha)
        assert run.commit_sha == sha

    def test_commit_sha_persists_in_db(self):
        """commit_sha round-trips through SQLite."""
        engine = _in_memory_engine()
        sha = "abc123def456789012345678901234567890abcd"
        with Session(engine) as session:
            session.add(
                _make_run(
                    branch=EXPLICIT_BRANCH,
                    id="run-csha-db",
                    commit_sha=sha,
                )
            )
            session.commit()
        with Session(engine) as session:
            from runsight_api.domain.entities.run import Run

            loaded = session.get(Run, "run-csha-db")
            assert loaded.commit_sha == sha


class TestRunWarningsJsonField:
    def test_run_has_warnings_json_attribute(self):
        """Run entity exposes a `warnings_json` attribute."""
        run = _make_run(branch=EXPLICIT_BRANCH)
        assert hasattr(run, "warnings_json")

    def test_warnings_json_accepts_and_round_trips_in_db(self):
        """warnings_json round-trips through SQLite as JSON."""
        engine = _in_memory_engine()
        warnings = [
            {
                "message": "Tool definition warning",
                "source": "tool_definitions",
                "context": "fetcher",
            }
        ]
        with Session(engine) as session:
            session.add(
                _make_run(
                    branch=EXPLICIT_BRANCH,
                    id="run-warnings-db",
                    warnings_json=warnings,
                )
            )
            session.commit()
        with Session(engine) as session:
            from runsight_api.domain.entities.run import Run

            loaded = session.get(Run, "run-warnings-db")
            assert loaded.warnings_json == warnings


# ---------------------------------------------------------------------------
# 4. Backward compat removed — workflow_commit_sha and effective_commit_sha are gone
# ---------------------------------------------------------------------------


class TestWorkflowCommitShaRemoved:
    def test_workflow_commit_sha_field_is_removed(self):
        """Run no longer exposes a workflow_commit_sha field."""
        from runsight_api.domain.entities.run import Run

        run = _make_run(branch=EXPLICIT_BRANCH)
        assert "workflow_commit_sha" not in Run.model_fields
        assert not hasattr(run, "workflow_commit_sha")

    def test_workflow_commit_sha_accessor_is_removed(self):
        """Run no longer exposes an effective_commit_sha compatibility accessor."""
        run = _make_run(branch=EXPLICIT_BRANCH)
        assert not hasattr(run, "effective_commit_sha")


# ---------------------------------------------------------------------------
# 5. RunResponse — exposes branch, source, commit_sha
# ---------------------------------------------------------------------------


class TestRunResponseNewFields:
    def test_run_response_has_branch(self):
        """RunResponse schema includes a `branch` field."""
        from runsight_api.transport.schemas.runs import RunResponse

        fields = RunResponse.model_fields
        assert "branch" in fields, "RunResponse must have a 'branch' field"

    def test_run_response_has_source(self):
        """RunResponse schema includes a `source` field."""
        from runsight_api.transport.schemas.runs import RunResponse

        fields = RunResponse.model_fields
        assert "source" in fields, "RunResponse must have a 'source' field"

    def test_run_response_has_commit_sha(self):
        """RunResponse schema includes a `commit_sha` field."""
        from runsight_api.transport.schemas.runs import RunResponse

        fields = RunResponse.model_fields
        assert "commit_sha" in fields, "RunResponse must have a 'commit_sha' field"

    def test_run_response_requires_branch(self):
        """RunResponse should not backfill branch when omitted."""
        from runsight_api.transport.schemas.runs import RunResponse

        with pytest.raises(ValidationError):
            RunResponse(
                id="run-response",
                workflow_id="workflow-data-model",
                workflow_name="Data model workflow",
                status="pending",
                started_at=None,
                completed_at=None,
                duration_seconds=None,
                total_cost_usd=0.0,
                total_tokens=0,
                created_at=1711699200.0,
                source="simulation",
                commit_sha="abc123",
            )

    def test_run_response_serializes_new_fields(self):
        """RunResponse can be instantiated with branch, source, commit_sha."""
        from runsight_api.transport.schemas.runs import RunResponse

        resp = RunResponse(
            id="run-response",
            workflow_id="workflow-data-model",
            workflow_name="Data model workflow",
            status="pending",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            total_cost_usd=0.0,
            total_tokens=0,
            created_at=1711699200.0,
            branch="feat/test",
            source="simulation",
            commit_sha="abc123",
        )
        assert resp.branch == "feat/test"
        assert resp.source == "simulation"
        assert resp.commit_sha == "abc123"


class TestRunResponseWarningsField:
    def test_run_response_has_warnings(self):
        """RunResponse schema includes a `warnings` field."""
        from runsight_api.transport.schemas.runs import RunResponse

        fields = RunResponse.model_fields
        assert "warnings" in fields, "RunResponse must have a 'warnings' field"

    def test_run_response_serializes_warnings(self):
        """RunResponse can be instantiated with canonical warning payloads."""
        from runsight_api.transport.schemas.runs import RunResponse
        from runsight_api.transport.schemas.workflows import WarningItem

        warning = WarningItem(
            message="Tool definition warning",
            source="tool_definitions",
            context="fetcher",
        )
        resp = RunResponse(
            id="run-response",
            workflow_id="workflow-data-model",
            workflow_name="Data model workflow",
            status="pending",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            total_cost_usd=0.0,
            total_tokens=0,
            created_at=1711699200.0,
            branch=EXPLICIT_BRANCH,
            warnings=[warning],
        )
        assert resp.warnings == [warning]


# ---------------------------------------------------------------------------
# 6. RunCreate — accepts source (optional)
# ---------------------------------------------------------------------------


class TestRunCreateSourceField:
    def test_run_create_has_source_field(self):
        """RunCreate schema includes an optional `source` field."""
        from runsight_api.transport.schemas.runs import RunCreate

        fields = RunCreate.model_fields
        assert "source" in fields, "RunCreate must have a 'source' field"

    def test_run_create_source_defaults(self):
        """RunCreate.source defaults when not provided."""
        from runsight_api.transport.schemas.runs import RunCreate

        body = RunCreate(workflow_id="workflow-data-model", branch=EXPLICIT_BRANCH)
        # Should default to "manual" or None — either way, the field must exist
        assert hasattr(body, "source")

    def test_run_create_source_accepts_value(self):
        """RunCreate.source can be set explicitly."""
        from runsight_api.transport.schemas.runs import RunCreate

        body = RunCreate(
            workflow_id="workflow-data-model", branch=EXPLICIT_BRANCH, source="webhook"
        )
        assert body.source == "webhook"


class TestRunCreateBranchField:
    def test_run_create_has_branch_field(self):
        """RunCreate schema includes an optional branch field."""
        from runsight_api.transport.schemas.runs import RunCreate

        field = RunCreate.model_fields.get("branch")
        assert field is not None
        assert not field.is_required()
        assert field.default is None

    def test_run_create_allows_omitted_branch_for_working_tree_path(self):
        """RunCreate omits branch to request the working-tree execution path."""
        from runsight_api.transport.schemas.runs import RunCreate

        body = RunCreate(workflow_id="workflow-data-model")

        assert body.branch is None


# ---------------------------------------------------------------------------
# 7. create_run() populates branch and source
# ---------------------------------------------------------------------------


class TestCreateRunPopulatesNewFields:
    def test_create_run_requires_branch_argument(self):
        """create_run() should require branch instead of defaulting it."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Data model workflow"
        mock_workflow.id = "workflow-data-model"
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        with pytest.raises(TypeError):
            svc.create_run("workflow-data-model", _prepared({"instruction": "go"}))

    def test_create_run_sets_source_default(self):
        """create_run() sets source='manual' by default."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Data model workflow"
        mock_workflow.id = "workflow-data-model"
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run(
            "workflow-data-model", _prepared({"instruction": "go"}), branch=EXPLICIT_BRANCH
        )

        assert run.source == "manual"

    def test_create_run_accepts_source_parameter(self):
        """create_run() accepts and stores a custom source value."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Data model workflow"
        mock_workflow.id = "workflow-data-model"
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run(
            "workflow-data-model",
            _prepared({"instruction": "go"}),
            branch=EXPLICIT_BRANCH,
            source="webhook",
        )

        assert run.branch == EXPLICIT_BRANCH
        assert run.source == "webhook"

    def test_create_run_snapshots_workflow_warnings(self):
        """create_run() snapshots workflow warnings into run.warnings_json."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Data model workflow"
        mock_workflow.id = "workflow-data-model"
        mock_workflow.warnings = [
            {
                "message": "Tool definition warning",
                "source": "tool_definitions",
                "context": "fetcher",
            }
        ]
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run(
            "workflow-data-model", _prepared({"instruction": "go"}), branch=EXPLICIT_BRANCH
        )

        assert run.warnings_json == mock_workflow.warnings
        assert run.warnings_json is not mock_workflow.warnings

        mock_workflow.warnings[0]["message"] = "mutated after creation"
        assert run.warnings_json[0]["message"] == "Tool definition warning"

    def test_create_run_sets_warnings_json_none_when_workflow_has_no_warnings(self):
        """create_run() should default warnings_json to None when no warnings exist."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Data model workflow"
        mock_workflow.id = "workflow-data-model"
        mock_workflow.warnings = []
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run(
            "workflow-data-model", _prepared({"instruction": "go"}), branch=EXPLICIT_BRANCH
        )

        assert run.warnings_json is None

    def test_create_run_sets_warnings_json_none_when_workflow_warnings_missing(self):
        """Guardrail: missing workflow.warnings on a Mock must not become stored warnings."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Data model workflow"
        mock_workflow.id = "workflow-data-model"
        # Intentionally leave .warnings unset to exercise Mock getattr behavior.
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run(
            "workflow-data-model", _prepared({"instruction": "go"}), branch=EXPLICIT_BRANCH
        )

        assert run.warnings_json is None

    def test_create_run_ignores_non_list_workflow_warnings(self):
        """Guardrail: only non-empty list warnings are snapshotted."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Data model workflow"
        mock_workflow.id = "workflow-data-model"
        mock_workflow.warnings = Mock(name="not_a_warning_list")
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run(
            "workflow-data-model", _prepared({"instruction": "go"}), branch=EXPLICIT_BRANCH
        )

        assert run.warnings_json is None


# ---------------------------------------------------------------------------
# 8. commit_sha does not fallback to workflow_commit_sha for old runs
# ---------------------------------------------------------------------------


class TestCommitShaFallback:
    def test_commit_sha_does_not_fall_back_to_workflow_commit_sha(self):
        """Run with no commit SHA stays empty and exposes no legacy accessors."""
        run = _make_run(branch=EXPLICIT_BRANCH, commit_sha=None)
        assert run.commit_sha is None
        assert not hasattr(run, "workflow_commit_sha")
        assert not hasattr(run, "effective_commit_sha")
