from fastapi import Depends
from sqlmodel import Session
from ..core.di import engine
from ..core.config import settings
from ..data.repositories.run_repo import RunRepository
from ..data.repositories.provider_repo import ProviderRepository
from ..data.filesystem.workflow_repo import WorkflowRepository
from ..data.filesystem.soul_repo import SoulRepository
from ..data.filesystem.task_repo import TaskRepository
from ..data.filesystem.step_repo import StepRepository
from ..logic.services.provider_service import ProviderService
from ..logic.services.run_service import RunService
from ..logic.services.soul_service import SoulService
from ..logic.services.registry_service import RegistryService
from ..logic.services.workflow_service import WorkflowService


def get_session():
    with Session(engine) as session:
        yield session


def get_run_repo(session: Session = Depends(get_session)) -> RunRepository:
    return RunRepository(session)


def get_provider_repo(session: Session = Depends(get_session)) -> ProviderRepository:
    return ProviderRepository(session)


def get_provider_service(
    repo: ProviderRepository = Depends(get_provider_repo),
) -> ProviderService:
    return ProviderService(repo)


def get_workflow_repo() -> WorkflowRepository:
    return WorkflowRepository(settings.base_path)


def get_soul_repo() -> SoulRepository:
    return SoulRepository(settings.base_path)


def get_workflow_service(
    workflow_repo: WorkflowRepository = Depends(get_workflow_repo),
) -> WorkflowService:
    return WorkflowService(workflow_repo)


def get_run_service(
    run_repo: RunRepository = Depends(get_run_repo),
    workflow_repo: WorkflowRepository = Depends(get_workflow_repo),
) -> RunService:
    return RunService(run_repo, workflow_repo)


def get_soul_service(soul_repo: SoulRepository = Depends(get_soul_repo)) -> SoulService:
    return SoulService(soul_repo)


def get_registry_service() -> RegistryService:
    return RegistryService(f"{settings.base_path}/custom")


def get_task_repo() -> TaskRepository:
    return TaskRepository(settings.base_path)


def get_step_repo() -> StepRepository:
    return StepRepository(settings.base_path)
