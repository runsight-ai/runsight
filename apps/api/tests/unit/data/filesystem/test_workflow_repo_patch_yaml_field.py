"""WorkflowRepository patches YAML fields while preserving file safety."""


class TestWorkflowRepoPatchYamlFieldContract:
    """WorkflowRepository must expose a patch_yaml_field method."""

    def test_workflow_repo_has_patch_yaml_field_method(self):
        """WorkflowRepository must have a patch_yaml_field method."""
        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

        assert hasattr(WorkflowRepository, "patch_yaml_field"), (
            "WorkflowRepository must implement patch_yaml_field method"
        )

    def test_patch_yaml_field_is_callable(self):
        """patch_yaml_field must be a callable method."""
        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

        assert callable(getattr(WorkflowRepository, "patch_yaml_field", None)), (
            "WorkflowRepository.patch_yaml_field must be callable"
        )


# ---------------------------------------------------------------------------
# 9. YAML comments preserved through patch_yaml_field
# ---------------------------------------------------------------------------


class TestPatchYamlFieldPreservesComments:
    """patch_yaml_field must preserve YAML comments when toggling fields."""

    def test_yaml_comments_survive_enabled_toggle(self, tmp_path):
        """Toggling enabled via patch_yaml_field must not strip YAML comments."""
        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

        yaml_with_comments = (
            "# Top-level comment\n"
            "id: test-wf-abc12\n"
            "kind: workflow\n"
            "workflow:\n"
            "  name: My Workflow  # inline comment\n"
            "  entry: start\n"
            "  transitions: []\n"
            "  # description comment\n"
            "blocks: {}\n"
            "enabled: false\n"
        )

        # Set up a workflow file on disk
        wf_dir = tmp_path / "custom" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / ".canvas").mkdir()
        wf_file = wf_dir / "test-wf-abc12.yaml"
        wf_file.write_text(yaml_with_comments)

        repo = WorkflowRepository(base_path=str(tmp_path))
        repo.patch_yaml_field("test-wf-abc12", "enabled", True)

        result = wf_file.read_text()
        assert "# Top-level comment" in result, "Top-level comment was stripped"
        assert "# inline comment" in result, "Inline comment was stripped"
        assert "# description comment" in result, "Description comment was stripped"


# ---------------------------------------------------------------------------
# 10. patch_yaml_field delegates to _atomic_write
# ---------------------------------------------------------------------------


class TestPatchYamlFieldAtomicWrite:
    """patch_yaml_field must write files atomically via _atomic_write."""

    def test_patch_yaml_field_calls_atomic_write(self, tmp_path):
        """patch_yaml_field must delegate file writing to _atomic_write."""
        from unittest.mock import patch as mock_patch

        from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

        yaml_content = (
            "id: test-wf-abc12\n"
            "kind: workflow\n"
            "workflow:\n"
            "  name: Test\n"
            "  entry: start\n"
            "  transitions: []\n"
            "blocks: {}\n"
            "enabled: false\n"
        )

        wf_dir = tmp_path / "custom" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / ".canvas").mkdir()
        wf_file = wf_dir / "test-wf-abc12.yaml"
        wf_file.write_text(yaml_content)

        repo = WorkflowRepository(base_path=str(tmp_path))

        with mock_patch.object(repo, "_atomic_write") as mock_aw:
            repo.patch_yaml_field("test-wf-abc12", "enabled", True)
            mock_aw.assert_called_once()
            call_args = mock_aw.call_args
            # First positional arg should be the workflow file path
            assert str(call_args[0][0]).endswith("test-wf-abc12.yaml")
