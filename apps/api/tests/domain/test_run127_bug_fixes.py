"""Red tests for RUN-127: Bug fixes.

1. WorkflowEntity.name populated from YAML workflow.name (currently always None)
2. Run.started_at default changed from time.time() to None
3. Default model_name fallback to 'gpt-4o' when config.model_name is missing
"""

# ---------------------------------------------------------------------------
# 1. WorkflowEntity.name from YAML
# ---------------------------------------------------------------------------


class TestWorkflowEntityNameFromYaml:
    def test_workflow_entity_name_populated_from_yaml(self):
        """When a workflow YAML has workflow.name, the WorkflowEntity.name should reflect it."""
        import tempfile

        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = WorkflowRepository(tmpdir)

            yaml_content = """workflow:
  name: My Cool Workflow
  entry: b1
  transitions: []
blocks:
  b1:
    type: placeholder
    description: test
souls: {}
config: {}
"""
            entity = repo.create({"name": "My Cool Workflow", "yaml": yaml_content})

            # The entity.name should be "My Cool Workflow" (from YAML workflow.name)
            assert entity.name == "My Cool Workflow"

    def test_workflow_entity_name_from_yaml_on_get(self):
        """get_by_id returns entity with name populated from the YAML workflow.name field."""
        import tempfile

        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = WorkflowRepository(tmpdir)

            yaml_content = """workflow:
  name: Research Pipeline
  entry: b1
  transitions: []
blocks:
  b1:
    type: placeholder
    description: test
souls: {}
config: {}
"""
            created = repo.create({"name": "Research Pipeline", "yaml": yaml_content})
            retrieved = repo.get_by_id(created.id)

            assert retrieved is not None
            assert retrieved.name == "Research Pipeline"

    def test_workflow_entity_name_from_yaml_on_list(self):
        """list_all returns entities with name populated from YAML workflow.name."""
        import tempfile

        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = WorkflowRepository(tmpdir)

            yaml_content = """workflow:
  name: Listed Workflow
  entry: b1
  transitions: []
blocks:
  b1:
    type: placeholder
    description: test
souls: {}
config: {}
"""
            repo.create({"name": "Listed Workflow", "yaml": yaml_content})
            all_wfs = repo.list_all()

            assert len(all_wfs) >= 1
            names = [w.name for w in all_wfs]
            assert "Listed Workflow" in names


# ---------------------------------------------------------------------------
# 2. Run.started_at defaults to None
# ---------------------------------------------------------------------------


class TestRunStartedAtDefault:
    def test_run_started_at_default_is_none(self):
        """Run.started_at should default to None (not time.time())."""
        from runsight_api.domain.entities.run import Run, RunStatus

        run = Run(
            id="run_test",
            workflow_id="wf_1",
            workflow_name="wf_1",
            status=RunStatus.pending,
            task_json="{}",
        )
        # started_at should be None by default — it was previously defaulting to time.time()
        assert run.started_at is None

    def test_run_started_at_can_be_set_explicitly(self):
        """Run.started_at can still be set to a float value explicitly."""
        from runsight_api.domain.entities.run import Run, RunStatus

        run = Run(
            id="run_test2",
            workflow_id="wf_1",
            workflow_name="wf_1",
            status=RunStatus.pending,
            task_json="{}",
            started_at=999.0,
        )
        assert run.started_at == 999.0


# ---------------------------------------------------------------------------
# 3. create_run should NOT set started_at
# ---------------------------------------------------------------------------


class TestCreateRunStartedAt:
    def test_create_run_does_not_set_started_at(self):
        """RunService.create_run should leave started_at as None (pending, not yet running)."""
        from unittest.mock import Mock

        from runsight_api.logic.services.run_service import RunService
        from runsight_api.domain.entities.run import RunStatus

        run_repo = Mock()
        workflow_repo = Mock()
        workflow_repo.get_by_id.return_value = Mock(id="wf_1")
        run_repo.create_run.return_value = None

        svc = RunService(run_repo, workflow_repo)
        run = svc.create_run("wf_1", {"instruction": "test"})

        # started_at should be None — execution hasn't started yet
        assert run.started_at is None
        assert run.status == RunStatus.pending
