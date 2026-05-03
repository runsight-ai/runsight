import logging
from pathlib import Path
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .project import resolve_base_path, scaffold_project

_DB_URL_SENTINEL = "__auto__"

logger = logging.getLogger(__name__)


def _default_base_path() -> str:
    """Compute the default base_path from the current launch directory."""
    return resolve_base_path(env_value=None)


def _parse_cors_origins(raw: str) -> List[str]:
    """Parse a comma-separated string into a list of origin URLs."""
    return [origin.strip() for origin in raw.split(",")]


def _workspace_error(workspace_root: Path, detail: str) -> SystemExit:
    return SystemExit(f"[runsight] ERROR: Workspace '{workspace_root}' is not usable: {detail}")


def _ensure_directory(path: Path, *, workspace_root: Path) -> None:
    if path.exists() and not path.is_dir():
        raise _workspace_error(
            workspace_root,
            f"Expected '{path}' to be a directory.",
        )

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        detail = exc.strerror or str(exc)
        raise _workspace_error(
            workspace_root,
            f"Could not create '{path}': {detail}",
        ) from None


class Settings(BaseSettings):
    base_path: str = Field(default_factory=_default_base_path)
    db_url: str = _DB_URL_SENTINEL
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_format: str = "json"
    external_invocation_enabled: bool = True
    public_base_url: str | None = None
    external_invocation_body_limit_bytes: int = 1_048_576
    max_concurrent_runs: int = 5
    max_pending_external_invocations: int = 32

    model_config = SettingsConfigDict(env_prefix="RUNSIGHT_")

    @model_validator(mode="after")
    def _resolve_db_url(self) -> "Settings":
        if self.db_url == _DB_URL_SENTINEL:
            db_path = Path(self.base_path).resolve() / ".runsight" / "runsight.db"
            object.__setattr__(self, "db_url", f"sqlite:///{db_path}")
        return self

    @model_validator(mode="after")
    def _split_cors_origins(self) -> "Settings":
        raw = self.cors_origins
        if isinstance(raw, str):
            object.__setattr__(self, "cors_origins", _parse_cors_origins(raw))
        return self


def ensure_project_dirs(settings: Settings) -> None:
    """Ensure the workspace skeleton, workflow canvas, and .runsight/ directories exist."""
    resolved = Path(settings.base_path).resolve()
    logger.info("Runsight base_path resolved to: %s", resolved)
    if resolved.exists() and not resolved.is_dir():
        raise _workspace_error(resolved, "The configured base path must be a directory.")

    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        detail = exc.strerror or str(exc)
        raise _workspace_error(resolved, f"Could not create workspace root: {detail}") from None

    object.__setattr__(settings, "base_path", str(resolved))
    try:
        scaffold_project(resolved)
    except OSError as exc:
        target = exc.filename or resolved
        detail = exc.strerror or str(exc)
        raise _workspace_error(resolved, f"Could not prepare '{target}': {detail}") from None

    workflows_dir = resolved / "custom" / "workflows"
    canvas_dir = workflows_dir / ".canvas"
    providers_dir = resolved / "custom" / "providers"
    runsight_dir = resolved / ".runsight"

    if providers_dir.exists() and not providers_dir.is_dir():
        raise _workspace_error(
            resolved,
            f"Expected '{providers_dir}' to be a directory.",
        )

    for directory in (workflows_dir, canvas_dir, runsight_dir):
        existed = directory.exists()
        _ensure_directory(directory, workspace_root=resolved)
        if not existed:
            logger.info("Created missing directory: %s", directory)


settings = Settings()
