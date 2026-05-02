"""Transport dependency factories wire read-model collaborators explicitly."""

from types import SimpleNamespace
from unittest.mock import Mock

from runsight_api.logic.services.eval_service import EvalService
from runsight_api.logic.services.run_service import RunService
from runsight_api.logic.services.workflow_service import WorkflowService
from runsight_api.transport import deps


def test_get_run_service_uses_supplied_read_model() -> None:
    run_repo = SimpleNamespace()
    workflow_repo = SimpleNamespace()
    read_model = SimpleNamespace()

    service = deps.get_run_service(
        run_repo=run_repo,
        workflow_repo=workflow_repo,
        run_read_model=read_model,
    )

    assert isinstance(service, RunService)
    assert service.run_repo is run_repo
    assert service.workflow_repo is workflow_repo
    assert service.run_read_model is read_model


def test_get_workflow_service_uses_supplied_read_model() -> None:
    workflow_repo = SimpleNamespace()
    run_repo = SimpleNamespace()
    read_model = SimpleNamespace()
    git_service = Mock()

    service = deps.get_workflow_service(
        workflow_repo=workflow_repo,
        run_repo=run_repo,
        run_read_model=read_model,
        git_service=git_service,
    )

    assert isinstance(service, WorkflowService)
    assert service.workflow_repo is workflow_repo
    assert service.run_repo is run_repo
    assert service.run_read_model is read_model
    assert service.git_service is git_service


def test_get_eval_service_uses_supplied_read_model() -> None:
    run_repo = SimpleNamespace()
    read_model = SimpleNamespace()

    service = deps.get_eval_service(run_repo=run_repo, run_read_model=read_model)

    assert isinstance(service, EvalService)
    assert service.run_repo is run_repo
    assert service.run_read_model is read_model
