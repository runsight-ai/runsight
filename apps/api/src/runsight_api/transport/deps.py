from typing import Optional

from fastapi import Depends, Request
from sqlmodel import Session
from ..core.di import engine
from ..core.config import settings
from ..core.secrets import SecretsEnvLoader
from ..data.repositories.run_repo import RunRepository
from ..data.filesystem.provider_repo import FileSystemProviderRepo
from ..data.filesystem.settings_repo import FileSystemSettingsRepo
from ..data.filesystem.workflow_repo import WorkflowRepository
from ..data.filesystem.soul_repo import SoulRepository
from ..data.filesystem.task_repo import TaskRepository
from ..data.filesystem.step_repo import StepRepository
from ..logic.services.provider_service import ProviderService
from ..logic.services.run_service import RunService
from ..logic.services.soul_service import SoulService
from ..logic.services.registry_service import RegistryService
from ..logic.services.workflow_service import WorkflowService
from ..logic.services.execution_service import ExecutionService
from ..logic.services.model_service import ModelService
from runsight_core.llm.model_catalog import ModelCatalogPort, LiteLLMModelCatalog


def get_session():
    with Session(engine) as session:
        yield session


def get_run_repo(session: Session = Depends(get_session)) -> RunRepository:
    return RunRepository(session)


def get_provider_repo() -> FileSystemProviderRepo:
    return FileSystemProviderRepo(base_path=settings.base_path)


def get_secrets_loader() -> SecretsEnvLoader:
    return SecretsEnvLoader(base_path=settings.base_path)


def get_settings_repo() -> FileSystemSettingsRepo:
    return FileSystemSettingsRepo(base_path=settings.base_path)


def get_provider_service(
    repo: FileSystemProviderRepo = Depends(get_provider_repo),
    secrets: SecretsEnvLoader = Depends(get_secrets_loader),
) -> ProviderService:
    return ProviderService(repo, secrets)


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


def get_execution_service(
    request: Request,
) -> Optional[ExecutionService]:
    try:
        return request.app.state.execution_service
    except AttributeError:
        return None


def get_soul_service(soul_repo: SoulRepository = Depends(get_soul_repo)) -> SoulService:
    return SoulService(soul_repo)


def get_registry_service() -> RegistryService:
    return RegistryService(f"{settings.base_path}/custom")


def get_task_repo() -> TaskRepository:
    return TaskRepository(settings.base_path)


def get_step_repo() -> StepRepository:
    return StepRepository(settings.base_path)


def get_model_catalog(request: Request) -> ModelCatalogPort:
    if not hasattr(request.app.state, "model_catalog"):
        request.app.state.model_catalog = LiteLLMModelCatalog()
    return request.app.state.model_catalog


def get_model_service(
    request: Request,
    catalog: ModelCatalogPort = Depends(get_model_catalog),
    provider_repo: FileSystemProviderRepo = Depends(get_provider_repo),
) -> ModelService:
    return ModelService(catalog=catalog, provider_repo=provider_repo)
