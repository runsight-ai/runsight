import logging
from pathlib import Path
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .project import resolve_base_path

_DB_URL_SENTINEL = "__auto__"

logger = logging.getLogger(__name__)


def _default_base_path() -> str:
    """Compute the default base_path using project detection.

    If ``RUNSIGHT_BASE_PATH`` is set, pydantic-settings will use it directly
    and this default is never called.  Otherwise we run the marker / auto-detect
    logic.
    """
    return resolve_base_path(env_value=None)


def _parse_cors_origins(raw: str) -> List[str]:
    """Parse a comma-separated string into a list of origin URLs."""
    return [origin.strip() for origin in raw.split(",")]


class Settings(BaseSettings):
    base_path: str = Field(default_factory=_default_base_path)
    db_url: str = _DB_URL_SENTINEL
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"
    log_format: str = "json"

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
    """Ensure the custom/workflows/, .canvas/, and .runsight/ directories exist.

    Called once at application startup. Resolves base_path to an absolute
    path and logs the result.  Creates missing directories as needed.
    """
    resolved = Path(settings.base_path).resolve()
    logger.info("Runsight base_path resolved to: %s", resolved)

    workflows_dir = resolved / "custom" / "workflows"
    canvas_dir = workflows_dir / ".canvas"
    runsight_dir = resolved / ".runsight"

    for d in (workflows_dir, canvas_dir, runsight_dir):
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            logger.info("Created missing directory: %s", d)


settings = Settings()
