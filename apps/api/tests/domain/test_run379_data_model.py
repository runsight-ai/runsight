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


# ---------------------------------------------------------------------------
# 4. Backward compat — workflow_commit_sha still exists
# ---------------------------------------------------------------------------


class TestWorkflowCommitShaStillExists:
    def test_workflow_commit_sha_field_still_present(self):
        """Deprecated workflow_commit_sha field still exists on Run."""
        run = _make_run()
        assert hasattr(run, "workflow_commit_sha")

    def test_workflow_commit_sha_still_defaults_to_none(self):
        run = _make_run()
        assert run.workflow_commit_sha is None

    def test_both_sha_fields_can_coexist(self):
        """Both commit_sha and workflow_commit_sha can be set independently."""
        run = _make_run(
            commit_sha="new_sha_1234567890123456789012345678901234",
            workflow_commit_sha="old_sha_1234567890123456789012345678901234",
        )
        assert run.commit_sha == "new_sha_1234567890123456789012345678901234"
        assert run.workflow_commit_sha == "old_sha_1234567890123456789012345678901234"


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


# ---------------------------------------------------------------------------
# 8. commit_sha fallback to workflow_commit_sha for old runs
# ---------------------------------------------------------------------------


class TestCommitShaFallback:
    def test_effective_commit_sha_prefers_commit_sha(self):
        """When both commit_sha and workflow_commit_sha are set, commit_sha wins."""
        run = _make_run(
            commit_sha="new_sha",
            workflow_commit_sha="old_sha",
        )
        # The entity should expose an effective_commit_sha property or
        # the commit_sha getter should handle fallback.
        effective = run.commit_sha if run.commit_sha is not None else run.workflow_commit_sha
        assert effective == "new_sha"

    def test_effective_commit_sha_falls_back_to_workflow_commit_sha(self):
        """When commit_sha is None, falls back to workflow_commit_sha."""
        run = _make_run(
            commit_sha=None,
            workflow_commit_sha="old_sha_fallback",
        )
        effective = run.commit_sha if run.commit_sha is not None else run.workflow_commit_sha
        assert effective == "old_sha_fallback"

    def test_run_entity_has_effective_commit_sha_property(self):
        """Run entity has an effective_commit_sha property for backward compat."""
        run = _make_run(workflow_commit_sha="legacy_sha")
        # Property should exist and perform the fallback
        assert hasattr(run, "effective_commit_sha")
        assert run.effective_commit_sha == "legacy_sha"

    def test_effective_commit_sha_none_when_both_none(self):
        """effective_commit_sha returns None when both fields are None."""
        run = _make_run()
        assert run.effective_commit_sha is None

    def test_effective_commit_sha_prefers_new_field(self):
        """effective_commit_sha returns commit_sha when set, ignoring legacy."""
        run = _make_run(commit_sha="new", workflow_commit_sha="old")
        assert run.effective_commit_sha == "new"
