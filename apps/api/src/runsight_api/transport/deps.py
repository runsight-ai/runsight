from typing import Optional

from fastapi import Depends, Request
from runsight_core.llm.model_catalog import LiteLLMModelCatalog, ModelCatalogPort
from sqlmodel import Session

from ..core.config import settings
from ..core.di import engine
from ..core.secrets import SecretsEnvLoader
from ..data.filesystem.provider_repo import FileSystemProviderRepo
from ..data.filesystem.settings_repo import FileSystemSettingsRepo
from ..data.filesystem.soul_repo import SoulRepository
from ..data.filesystem.workflow_repo import WorkflowRepository
from ..data.repositories.run_repo import RunRepository
from ..logic.services.eval_service import EvalService
from ..logic.services.execution_service import ExecutionService
from ..logic.services.git_service import GitService
from ..logic.services.model_service import ModelService
from ..logic.services.provider_service import ProviderService
from ..logic.services.run_service import RunService
from ..logic.services.settings_service import SettingsService
from ..logic.services.soul_service import SoulService
from ..logic.services.workflow_service import WorkflowService


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


def get_settings_service(
    settings_repo: FileSystemSettingsRepo = Depends(get_settings_repo),
    provider_repo: FileSystemProviderRepo = Depends(get_provider_repo),
) -> SettingsService:
    return SettingsService(settings_repo=settings_repo, provider_repo=provider_repo)


def get_workflow_repo() -> WorkflowRepository:
    return WorkflowRepository(settings.base_path)


def get_soul_repo() -> SoulRepository:
    return SoulRepository(settings.base_path)


def get_git_service() -> GitService:
    return GitService(settings.base_path)


def get_workflow_service(
    workflow_repo: WorkflowRepository = Depends(get_workflow_repo),
    run_repo: RunRepository = Depends(get_run_repo),
    git_service: GitService = Depends(get_git_service),
) -> WorkflowService:
    return WorkflowService(workflow_repo, run_repo, git_service=git_service)


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


def get_soul_service(
    soul_repo: SoulRepository = Depends(get_soul_repo),
    git_service: GitService = Depends(get_git_service),
    workflow_repo: WorkflowRepository = Depends(get_workflow_repo),
    provider_repo: FileSystemProviderRepo = Depends(get_provider_repo),
) -> SoulService:
    return SoulService(
        soul_repo,
        git_service=git_service,
        workflow_repo=workflow_repo,
        provider_repo=provider_repo,
    )


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


def get_eval_service(run_repo: RunRepository = Depends(get_run_repo)) -> EvalService:
    return EvalService(run_repo)
