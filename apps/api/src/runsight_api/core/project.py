"""Workspace setup helpers for Runsight startup."""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _resolve_git_dir(base_path: Path) -> Path | None:
    git_path = base_path / ".git"
    if git_path.is_dir():
        return git_path
    if git_path.is_file():
        content = git_path.read_text(encoding="utf-8").strip()
        if not content.startswith("gitdir:"):
            return None
        git_dir = content.split(":", 1)[1].strip()
        candidate = Path(git_dir)
        if not candidate.is_absolute():
            candidate = (base_path / candidate).resolve()
        return candidate
    return None


def _has_git_repo(base_path: Path) -> bool:
    return _resolve_git_dir(base_path) is not None


def _resolve_git_exclude_path(base_path: Path) -> Path | None:
    if shutil.which("git") is not None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-path", "info/exclude"],
                cwd=base_path,
                capture_output=True,
                check=True,
                text=True,
            )
            exclude_path = Path(result.stdout.strip())
            if not exclude_path.is_absolute():
                exclude_path = (base_path / exclude_path).resolve()
            return exclude_path
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    git_dir = _resolve_git_dir(base_path)
    if git_dir is None:
        return None
    return git_dir / "info" / "exclude"


def _ensure_repo_local_ignores(base_path: Path, patterns: list[str]) -> None:
    exclude_path = _resolve_git_exclude_path(base_path)
    if exclude_path is None:
        return

    _append_missing_patterns(exclude_path, patterns)


def _append_missing_patterns(path: Path, patterns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    missing_patterns = [pattern for pattern in patterns if pattern not in existing]
    if not missing_patterns:
        return

    with path.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        for pattern in missing_patterns:
            handle.write(f"{pattern}\n")


def scaffold_project(base_path: Path) -> None:
    """Create or verify the Runsight workspace structure at *base_path*."""
    has_git_repo = _has_git_repo(base_path)
    is_new = not any(
        (
            (base_path / "custom").exists(),
            (base_path / ".gitignore").exists(),
            has_git_repo,
        )
    )
    legacy_marker_path = base_path / ".runsight-project"

    if legacy_marker_path.exists() and not has_git_repo:
        legacy_marker_path.unlink()
        logger.info("Removed legacy Runsight marker at %s", legacy_marker_path)

    (base_path / "custom" / "workflows").mkdir(parents=True, exist_ok=True)
    (base_path / "custom" / "souls").mkdir(parents=True, exist_ok=True)
    (base_path / "custom" / "tools").mkdir(parents=True, exist_ok=True)

    if not has_git_repo:
        _append_missing_patterns(base_path / ".gitignore", [".canvas/", ".runsight/"])
    else:
        _ensure_repo_local_ignores(base_path, [".canvas/", ".runsight/"])

    if not has_git_repo:
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
