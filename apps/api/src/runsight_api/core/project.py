"""Workspace setup helpers for Runsight startup."""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def scaffold_project(base_path: Path) -> None:
    """Create or verify the Runsight workspace structure at *base_path*."""
    is_new = not any(
        (
            (base_path / "custom").exists(),
            (base_path / ".gitignore").exists(),
            (base_path / ".git").exists(),
        )
    )
    legacy_marker_path = base_path / ".runsight-project"

    if legacy_marker_path.exists():
        legacy_marker_path.unlink()
        logger.info("Removed legacy Runsight marker at %s", legacy_marker_path)

    (base_path / "custom" / "workflows").mkdir(parents=True, exist_ok=True)
    (base_path / "custom" / "souls").mkdir(parents=True, exist_ok=True)
    (base_path / "custom" / "tools").mkdir(parents=True, exist_ok=True)

    gitignore_path = base_path / ".gitignore"
    if not gitignore_path.is_file():
        gitignore_path.write_text(".canvas/\n.runsight/\n", encoding="utf-8")
    else:
        content = gitignore_path.read_text(encoding="utf-8")
        if ".runsight/" not in content:
            with gitignore_path.open("a", encoding="utf-8") as f:
                if content and not content.endswith("\n"):
                    f.write("\n")
                f.write(".runsight/\n")

    if not (base_path / ".git").is_dir():
        if shutil.which("git") is None:
            logger.warning(
                "Git executable is unavailable; GitOps disabled for workspace at %s",
                base_path,
            )
        else:
            try:
                subprocess.run(["git", "init"], cwd=base_path, capture_output=True, check=True)
                subprocess.run(
                    ["git", "config", "user.email", "runsight@localhost"],
                    cwd=base_path,
                    capture_output=True,
                    check=True,
                )
                subprocess.run(
                    ["git", "config", "user.name", "Runsight"],
                    cwd=base_path,
                    capture_output=True,
                    check=True,
                )
                subprocess.run(["git", "add", "."], cwd=base_path, capture_output=True, check=True)
                subprocess.run(
                    ["git", "commit", "-m", "Initial Runsight project"],
                    cwd=base_path,
                    capture_output=True,
                    check=True,
                )
            except FileNotFoundError:
                logger.warning(
                    "Git executable is unavailable; GitOps disabled for workspace at %s",
                    base_path,
                    exc_info=True,
                )
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or exc.stdout or str(exc)).strip()
                logger.warning(
                    "Git initialization failed; GitOps disabled for workspace at %s: %s",
                    base_path,
                    detail,
                )

    if is_new:
        logger.info("Created new Runsight workspace at %s", base_path)
    else:
        logger.info("Found existing Runsight workspace at %s", base_path)


def resolve_base_path(env_value: str | None = None) -> str:
    """Resolve the Runsight workspace root from env or the launch directory."""
    if env_value is not None:
        logger.info("base_path from RUNSIGHT_BASE_PATH env var: %s", env_value)
        return env_value

    cwd = Path.cwd().resolve()
    logger.info("RUNSIGHT_BASE_PATH not set, using launch directory: %s", cwd)
    return str(cwd)
