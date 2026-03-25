import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlmodel import Session, select

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

from .core.config import settings as app_settings, ensure_project_dirs
from .core.logging import configure_logging
from .core.secrets import SecretsEnvLoader
from .domain.entities.run import Run, RunStatus
from .core.di import container, engine
from .data.repositories.run_repo import RunRepository
from .data.filesystem.provider_repo import FileSystemProviderRepo
from .data.filesystem.workflow_repo import WorkflowRepository
from .logic.services.execution_service import ExecutionService
from .domain.errors import RunsightError
from .transport.middleware.error_handler import global_exception_handler
from .transport.middleware.request_id import RequestIdMiddleware
from .transport.middleware.access_log import AccessLogMiddleware
from .transport.routers import (
    eval,
    runs,
    workflows,
    souls,
    steps,
    tasks,
    settings,
    dashboard,
    git,
    models,
    sse_stream,
)


def _recover_stale_runs(engine):
    """Mark any runs stuck in 'running' as failed after an API restart."""
    with Session(engine) as session:
        stale_runs = session.exec(select(Run).where(Run.status == RunStatus.running)).all()
        for run in stale_runs:
            run.status = RunStatus.failed
            run.error = "API process restarted during execution"
            run.completed_at = time.time()
            session.add(run)
        session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    alembic_cfg = AlembicConfig(str(Path(__file__).parent / "alembic.ini"))
    alembic_command.upgrade(alembic_cfg, "head")
    _recover_stale_runs(engine)
    ensure_project_dirs(app_settings)

    # Create singleton ExecutionService on app.state so _running_tasks persists
    session = Session(engine)
    run_repo = RunRepository(session)
    workflow_repo = WorkflowRepository(app_settings.base_path)
    provider_repo = FileSystemProviderRepo(base_path=app_settings.base_path)
    secrets = SecretsEnvLoader(base_path=app_settings.base_path)
    app.state.execution_service = ExecutionService(
        run_repo, workflow_repo, provider_repo, engine=engine, secrets=secrets
    )

    yield

    session.close()


def create_app() -> FastAPI:
    configure_logging(app_settings.log_level, app_settings.log_format)
    app = FastAPI(title="Runsight API", lifespan=lifespan)

    # DI Setup
    container.setup_app_state(app)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(RunsightError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Routers
    app.include_router(eval.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(workflows.router, prefix="/api")
    app.include_router(souls.router, prefix="/api")
    app.include_router(steps.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(git.router, prefix="/api")
    app.include_router(models.router, prefix="/api")
    app.include_router(sse_stream.router, prefix="/api")

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
