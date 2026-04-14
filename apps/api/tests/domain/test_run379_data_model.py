"""Red tests for RUN-379: Run data model — add branch + source fields (ADR-001).

Tests cover:
1. Run entity has `branch` field (default "main")
2. Run entity has `source` field (default "manual")
3. Run entity has `commit_sha` field (optional, default None)
4. `workflow_commit_sha` still exists (deprecated, backward compat)
5. RunResponse exposes branch, source, commit_sha
6. RunCreate accepts source (optional)
7. create_run() populates branch and source
8. commit_sha falls back to workflow_commit_sha for old runs
"""

from unittest.mock import Mock

from sqlmodel import Session, SQLModel, create_engine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(**overrides):
    """Create a Run with minimal required fields, applying overrides."""
    from runsight_api.domain.entities.run import Run

    defaults = dict(
        id="run-379-test",
        workflow_id="wf-1",
        workflow_name="Test WF",
        task_json='{"instruction": "go"}',
    )
    defaults.update(overrides)
    return Run(**defaults)


def _in_memory_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# 1. Run entity — branch field
# ---------------------------------------------------------------------------


class TestRunBranchField:
    def test_run_has_branch_attribute(self):
        """Run entity exposes a `branch` attribute."""
        run = _make_run()
        assert hasattr(run, "branch")

    def test_branch_defaults_to_main(self):
        """branch defaults to 'main' when not provided."""
        run = _make_run()
        assert run.branch == "main"

    def test_branch_accepts_custom_value(self):
        """branch can be set to a custom string."""
        run = _make_run(branch="feat/experiment")
        assert run.branch == "feat/experiment"

    def test_branch_persists_in_db(self):
        """branch round-trips through SQLite."""
        engine = _in_memory_engine()
        with Session(engine) as session:
            session.add(_make_run(id="run-branch-db", branch="sim/test/20260329/abc"))
            session.commit()
        with Session(engine) as session:
            from runsight_api.domain.entities.run import Run

            loaded = session.get(Run, "run-branch-db")
            assert loaded.branch == "sim/test/20260329/abc"

    def test_branch_default_persists_in_db(self):
        """Default branch='main' round-trips through SQLite."""
        engine = _in_memory_engine()
        with Session(engine) as session:
            session.add(_make_run(id="run-branch-default-db"))
            session.commit()
        with Session(engine) as session:
            from runsight_api.domain.entities.run import Run

            loaded = session.get(Run, "run-branch-default-db")
            assert loaded.branch == "main"


# ---------------------------------------------------------------------------
# 2. Run entity — source field
# ---------------------------------------------------------------------------


class TestRunSourceField:
    def test_run_has_source_attribute(self):
        """Run entity exposes a `source` attribute."""
        run = _make_run()
        assert hasattr(run, "source")

    def test_source_defaults_to_manual(self):
        """source defaults to 'manual' when not provided."""
        run = _make_run()
        assert run.source == "manual"

    def test_source_accepts_simulation(self):
        run = _make_run(source="simulation")
        assert run.source == "simulation"

    def test_source_accepts_webhook(self):
        run = _make_run(source="webhook")
        assert run.source == "webhook"

    def test_source_accepts_schedule(self):
        run = _make_run(source="schedule")
        assert run.source == "schedule"

    def test_source_persists_in_db(self):
        """source round-trips through SQLite."""
        engine = _in_memory_engine()
        with Session(engine) as session:
            session.add(_make_run(id="run-source-db", source="webhook"))
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
        run = _make_run()
        assert hasattr(run, "commit_sha")

    def test_commit_sha_defaults_to_none(self):
        """commit_sha defaults to None when not provided."""
        run = _make_run()
        assert run.commit_sha is None

    def test_commit_sha_accepts_string(self):
        sha = "abc123def456789012345678901234567890abcd"
        run = _make_run(commit_sha=sha)
        assert run.commit_sha == sha

    def test_commit_sha_persists_in_db(self):
        """commit_sha round-trips through SQLite."""
        engine = _in_memory_engine()
        sha = "abc123def456789012345678901234567890abcd"
        with Session(engine) as session:
            session.add(_make_run(id="run-csha-db", commit_sha=sha))
            session.commit()
        with Session(engine) as session:
            from runsight_api.domain.entities.run import Run

            loaded = session.get(Run, "run-csha-db")
            assert loaded.commit_sha == sha


class TestRunWarningsJsonField:
    def test_run_has_warnings_json_attribute(self):
        """Run entity exposes a `warnings_json` attribute."""
        run = _make_run()
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
            session.add(_make_run(id="run-warnings-db", warnings_json=warnings))
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

        run = _make_run()
        assert "workflow_commit_sha" not in Run.model_fields
        assert not hasattr(run, "workflow_commit_sha")

    def test_workflow_commit_sha_accessor_is_removed(self):
        """Run no longer exposes an effective_commit_sha compatibility accessor."""
        run = _make_run()
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

    def test_run_response_serializes_new_fields(self):
        """RunResponse can be instantiated with branch, source, commit_sha."""
        from runsight_api.transport.schemas.runs import RunResponse

        resp = RunResponse(
            id="run-1",
            workflow_id="wf-1",
            workflow_name="Test",
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
            id="run-1",
            workflow_id="wf-1",
            workflow_name="Test",
            status="pending",
            started_at=None,
            completed_at=None,
            duration_seconds=None,
            total_cost_usd=0.0,
            total_tokens=0,
            created_at=1711699200.0,
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

        body = RunCreate(workflow_id="wf-1")
        # Should default to "manual" or None — either way, the field must exist
        assert hasattr(body, "source")

    def test_run_create_source_accepts_value(self):
        """RunCreate.source can be set explicitly."""
        from runsight_api.transport.schemas.runs import RunCreate

        body = RunCreate(workflow_id="wf-1", source="webhook")
        assert body.source == "webhook"


# ---------------------------------------------------------------------------
# 7. create_run() populates branch and source
# ---------------------------------------------------------------------------


class TestCreateRunPopulatesNewFields:
    def test_create_run_sets_branch_default(self):
        """create_run() sets branch='main' on the new Run."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Test WF"
        mock_workflow.id = "wf-1"
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run("wf-1", {"instruction": "go"})

        assert run.branch == "main"

    def test_create_run_sets_source_default(self):
        """create_run() sets source='manual' by default."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Test WF"
        mock_workflow.id = "wf-1"
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run("wf-1", {"instruction": "go"})

        assert run.source == "manual"

    def test_create_run_accepts_source_parameter(self):
        """create_run() accepts and stores a custom source value."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Test WF"
        mock_workflow.id = "wf-1"
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run("wf-1", {"instruction": "go"}, source="webhook")

        assert run.source == "webhook"

    def test_create_run_snapshots_workflow_warnings(self):
        """create_run() snapshots workflow warnings into run.warnings_json."""
        from runsight_api.logic.services.run_service import RunService

        mock_run_repo = Mock()
        mock_run_repo.create_run.side_effect = lambda r: r

        mock_workflow = Mock()
        mock_workflow.name = "Test WF"
        mock_workflow.id = "wf-1"
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
        run = svc.create_run("wf-1", {"instruction": "go"})

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
        mock_workflow.name = "Test WF"
        mock_workflow.id = "wf-1"
        mock_workflow.warnings = []
        mock_wf_repo = Mock()
        mock_wf_repo.get_by_id.return_value = mock_workflow

        svc = RunService(run_repo=mock_run_repo, workflow_repo=mock_wf_repo)
        run = svc.create_run("wf-1", {"instruction": "go"})

        assert run.warnings_json is None


# ---------------------------------------------------------------------------
# 8. commit_sha does not fallback to workflow_commit_sha for old runs
# ---------------------------------------------------------------------------


class TestCommitShaFallback:
    def test_commit_sha_does_not_fall_back_to_workflow_commit_sha(self):
        """Run no longer derives a commit SHA from workflow_commit_sha."""
        run = _make_run(commit_sha=None, workflow_commit_sha="old_sha_fallback")
        assert run.commit_sha is None
        assert not hasattr(run, "workflow_commit_sha")
        assert not hasattr(run, "effective_commit_sha")
