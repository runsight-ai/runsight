"""WorkflowService exposes enabled toggling for the transport endpoint."""


def test_workflow_service_set_enabled_is_available():
    from runsight_api.logic.services.workflow_service import WorkflowService

    assert callable(getattr(WorkflowService, "set_enabled", None))
