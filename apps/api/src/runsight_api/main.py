from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlmodel import SQLModel

from .core.di import container, engine
from .domain.errors import RunsightError
from .transport.middleware.error_handler import global_exception_handler
from .transport.routers import runs, workflows, souls, steps, tasks, settings, dashboard


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
    yield
    pass


def create_app() -> FastAPI:
    app = FastAPI(title="Runsight API", lifespan=lifespan)

    # DI Setup
    container.setup_app_state(app)

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
