import logging
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    base_path: str = "."
    db_url: str = "sqlite:///./runsight.db"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(env_prefix="RUNSIGHT_")


def ensure_project_dirs(settings: Settings) -> None:
    """Ensure the custom/workflows/ and .canvas/ directories exist.

    Called once at application startup. Resolves base_path to an absolute
    path and logs the result.  Creates missing directories as needed.
    """
    resolved = Path(settings.base_path).resolve()
    logger.info("Runsight base_path resolved to: %s", resolved)

    workflows_dir = resolved / "custom" / "workflows"
    canvas_dir = workflows_dir / ".canvas"

    if not workflows_dir.exists():
        workflows_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created missing directory: %s", workflows_dir)

    if not canvas_dir.exists():
        canvas_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Created missing directory: %s", canvas_dir)


settings = Settings()
