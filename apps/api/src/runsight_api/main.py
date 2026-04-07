import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.responses import FileResponse
from sqlmodel import Session, select

from .core.config import ensure_project_dirs
from .core.config import settings as app_settings
from .core.di import container, engine
from .core.logging import configure_logging
from .core.secrets import SecretsEnvLoader
from .data.filesystem.provider_repo import FileSystemProviderRepo
from .data.filesystem.settings_repo import FileSystemSettingsRepo
from .data.filesystem.workflow_repo import WorkflowRepository
from .data.repositories.run_repo import RunRepository
from .domain.entities.run import Run, RunStatus
from .domain.errors import RunsightError
from .logic.services.execution_service import ExecutionService
from .transport.middleware.access_log import AccessLogMiddleware
from .transport.middleware.error_handler import global_exception_handler
from .transport.middleware.request_id import RequestIdMiddleware
from .transport.routers import (
    dashboard,
    eval,
    git,
    models,
    runs,
    settings,
    souls,
    sse_stream,
    steps,
    tasks,
    tools,
    workflows,
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


def _ensure_sqlite_columns(engine) -> None:
    """Backfill additive SQLite columns for older local dev databases.

    The current baseline migration uses ``create_all()``, which does not alter
    existing tables. For pre-MVP local databases we can safely add missing
    nullable/defaulted columns in place so the app can start cleanly after
    model evolution.
    """
    if engine.dialect.name != "sqlite":
        return

    additive_columns = {
        "run": {
            "error_traceback": "VARCHAR",
            "branch": "VARCHAR NOT NULL DEFAULT 'main'",
            "source": "VARCHAR NOT NULL DEFAULT 'manual'",
            "commit_sha": "VARCHAR",
            "parent_run_id": "TEXT",
            "parent_node_id": "TEXT",
            "root_run_id": "TEXT",
            "depth": "INTEGER DEFAULT 0",
            "fail_reason": "VARCHAR",
            "fail_metadata": "JSON",
        },
        "runnode": {
            "last_phase": "VARCHAR",
            "prompt_hash": "VARCHAR",
            "soul_version": "VARCHAR",
            "eval_score": "FLOAT",
            "eval_passed": "BOOLEAN",
            "eval_results": "JSON",
            "child_run_id": "TEXT",
            "exit_handle": "TEXT",
        },
    }

    with engine.begin() as conn:
        for table_name, columns in additive_columns.items():
            existing = {
                row[1]
                for row in conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
            }
            for column_name, ddl in columns.items():
                if column_name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))


def _build_alembic_config() -> AlembicConfig:
    config_dir = Path(__file__).parent
    alembic_cfg = AlembicConfig(str(config_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(config_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", app_settings.db_url)
    return alembic_cfg


@asynccontextmanager
async def lifespan(app: FastAPI):
    alembic_cfg = _build_alembic_config()
    alembic_command.upgrade(alembic_cfg, "head")
    _ensure_sqlite_columns(engine)
    _recover_stale_runs(engine)
    ensure_project_dirs(app_settings)

    # Create singleton ExecutionService on app.state so _running_tasks persists
    session = Session(engine)
    run_repo = RunRepository(session)
    workflow_repo = WorkflowRepository(app_settings.base_path)
    provider_repo = FileSystemProviderRepo(base_path=app_settings.base_path)
    settings_repo = FileSystemSettingsRepo(base_path=app_settings.base_path)
    secrets = SecretsEnvLoader(base_path=app_settings.base_path)
    app.state.execution_service = ExecutionService(
        run_repo,
        workflow_repo,
        provider_repo,
        engine=engine,
        secrets=secrets,
        settings_repo=settings_repo,
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
    app.include_router(tools.router, prefix="/api")
    app.include_router(sse_stream.router, prefix="/api")

    @app.get("/health")
    def health_check():
        return {"status": "ok"}

    # Serve built frontend static files (bundled in wheel or overridden via env)
    _pkg_static = Path(__file__).parent / "static"
    static_dir = Path(os.environ.get("RUNSIGHT_STATIC_DIR", str(_pkg_static)))
    if static_dir.is_dir():
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        index_html = static_dir / "index.html"

        @app.get("/runsight.svg")
        async def _favicon():
            return FileResponse(static_dir / "runsight.svg")

        @app.get("/{full_path:path}")
        async def _spa_catch_all(full_path: str):
            # Serve static file if it exists, otherwise index.html for SPA routing
            candidate = static_dir / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index_html)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
