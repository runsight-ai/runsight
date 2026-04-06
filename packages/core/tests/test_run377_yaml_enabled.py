"""
RUN-377 — Red tests: YAML `enabled` field gates automated triggers.

AC:
  - `enabled` field on `RunsightWorkflowFile` schema (default False)
  - Parser reads field without error
  - Engine does NOT check this field
  - New workflows default to `enabled: False`
"""

from __future__ import annotations

from runsight_core.yaml.schema import RunsightWorkflowFile

MINIMAL_WORKFLOW = {
    "workflow": {
        "name": "test-wf",
        "entry": "start",
        "transitions": [],
    },
}


# ---------------------------------------------------------------------------
# 1. Schema-level: field exists with correct default
# ---------------------------------------------------------------------------


class TestEnabledFieldSchema:
    """RunsightWorkflowFile must declare an `enabled: bool` field."""

    def test_field_exists_on_model(self) -> None:
        """The model_fields dict must contain 'enabled'."""
        assert "enabled" in RunsightWorkflowFile.model_fields

    def test_default_is_false(self) -> None:
        """When `enabled` is omitted, it must default to False."""
        wf = RunsightWorkflowFile.model_validate(MINIMAL_WORKFLOW)
        assert wf.enabled is False

    def test_explicit_true_accepted(self) -> None:
        """Setting `enabled: true` in input must parse to True."""
        data = {**MINIMAL_WORKFLOW, "enabled": True}
        wf = RunsightWorkflowFile.model_validate(data)
        assert wf.enabled is True

    def test_explicit_false_accepted(self) -> None:
        """Setting `enabled: false` in input must parse to False."""
        data = {**MINIMAL_WORKFLOW, "enabled": False}
        wf = RunsightWorkflowFile.model_validate(data)
        assert wf.enabled is False

    def test_field_type_is_bool(self) -> None:
        """The annotation for `enabled` must be bool."""
        field_info = RunsightWorkflowFile.model_fields["enabled"]
        assert field_info.annotation is bool


# ---------------------------------------------------------------------------
# 2. Engine-level: engine must NOT reference `enabled`
# ---------------------------------------------------------------------------


class TestEngineIgnoresEnabled:
    """The execution engine (Workflow, RunsightTeamRunner) must not check `enabled`."""

    def test_workflow_class_has_no_enabled_attr(self) -> None:
        """Workflow (runtime object) must not have an `enabled` attribute."""
        import inspect

        from runsight_core.workflow import Workflow

        sig = inspect.signature(Workflow.__init__)
        assert "enabled" not in sig.parameters

    def test_runner_class_has_no_enabled_attr(self) -> None:
        """RunsightTeamRunner must not have an `enabled` attribute."""
        import inspect

        from runsight_core.runner import RunsightTeamRunner

        sig = inspect.signature(RunsightTeamRunner.__init__)
        assert "enabled" not in sig.parameters

    def test_enabled_not_in_runner_source(self) -> None:
        """The word 'enabled' must not appear in runner.py source code."""
        import inspect

        from runsight_core import runner

        source = inspect.getsource(runner)
        assert "enabled" not in source

    def test_enabled_not_in_workflow_source(self) -> None:
        """The word 'enabled' must not appear in workflow.py source code."""
        import inspect

        from runsight_core import workflow

        source = inspect.getsource(workflow)
        assert "enabled" not in source
