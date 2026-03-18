import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlmodel import Session, SQLModel, select

from .core.config import settings as app_settings, ensure_project_dirs
from .domain.entities.run import Run, RunStatus
from .core.di import container, engine
from .data.repositories.run_repo import RunRepository
from .data.repositories.provider_repo import ProviderRepository
from .data.filesystem.workflow_repo import WorkflowRepository
from .logic.services.execution_service import ExecutionService
from .domain.errors import RunsightError
from .transport.middleware.error_handler import global_exception_handler
from .transport.routers import runs, workflows, souls, steps, tasks, settings, dashboard


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


def _migrate_schema(engine):
    """Add columns that create_all won't add to existing tables."""
    import sqlalchemy

    with engine.connect() as conn:
        inspector = sqlalchemy.inspect(engine)
        if "provider" in inspector.get_table_names():
            columns = {c["name"] for c in inspector.get_columns("provider")}
            if "models_json" not in columns:
                conn.execute(sqlalchemy.text("ALTER TABLE provider ADD COLUMN models_json TEXT"))
                conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    _migrate_schema(engine)
    _recover_stale_runs(engine)
    ensure_project_dirs(app_settings)

    # Create singleton ExecutionService on app.state so _running_tasks persists
    session = Session(engine)
    run_repo = RunRepository(session)
    workflow_repo = WorkflowRepository(app_settings.base_path)
    provider_repo = ProviderRepository(session)
    app.state.execution_service = ExecutionService(
        run_repo, workflow_repo, provider_repo, engine=engine
    )

    yield

    session.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Runsight API", lifespan=lifespan)

    # DI Setup
    container.setup_app_state(app)

    # CORS
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    # Middleware
    app.add_exception_handler(RunsightError, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # Routers
    app.include_router(runs.router, prefix="/api")
    app.include_router(workflows.router, prefix="/api")
    app.include_router(souls.router, prefix="/api")
    app.include_router(steps.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
