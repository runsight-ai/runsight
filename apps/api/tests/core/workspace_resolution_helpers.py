"""Shared subprocess helpers for workspace resolution tests."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
README = REPO_ROOT / "README.md"
DOCKER_ENTRYPOINT = REPO_ROOT / "docker-entrypoint.sh"

_SAFE_SUBPROCESS_ENV_KEYS = (
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "PYTHONIOENCODING",
    "TMP",
    "TMPDIR",
    "TEMP",
    "VIRTUAL_ENV",
)
_HOME_ENV_KEYS = ("HOME", "XDG_CONFIG_HOME", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")

_PACKAGE_STARTUP_SNIPPET = """
from pathlib import Path
from runsight_api.main import app_settings
from runsight_api.core.config import ensure_project_dirs

ensure_project_dirs(app_settings)
print(Path(app_settings.base_path).resolve())
""".strip()


def _uv_executable() -> str:
    executable = shutil.which("uv")
    assert executable, "uv must be available to exercise the published-package startup contract"
    return executable


def _minimal_subprocess_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Build a subprocess env without inheriting real provider keys or user config."""
    merged_env = {
        key: os.environ[key]
        for key in _SAFE_SUBPROCESS_ENV_KEYS
        if key in os.environ and key not in _HOME_ENV_KEYS
    }
    if os.environ.get("PYTHONPATH"):
        merged_env["PYTHONPATH"] = os.environ["PYTHONPATH"]
    merged_env.update(dict(env or {}))
    return merged_env


def _isolated_home_env(home: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    config_home = home / ".config"
    config_home.mkdir(parents=True, exist_ok=True)
    return {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(config_home),
    }


def _apply_minimal_process_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    home: Path,
    env: dict[str, str] | None = None,
) -> None:
    """Scrub the in-process env before source startup spawns git children."""
    merged_env = _minimal_subprocess_env(_isolated_home_env(home))
    merged_env.update(dict(env or {}))

    for key in tuple(os.environ):
        monkeypatch.delenv(key, raising=False)
    for key, value in merged_env.items():
        monkeypatch.setenv(key, value)


def _run_package_startup(
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        _uv_executable(),
        "run",
        "--project",
        str(REPO_ROOT),
        "--package",
        "runsight",
        "python",
        "-c",
        _PACKAGE_STARTUP_SNIPPET,
    ]
    merged_env = _minimal_subprocess_env(_isolated_home_env(cwd / ".test-home"))
    merged_env.update(dict(env or {}))
    return subprocess.run(
        command,
        cwd=cwd,
        env=merged_env,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_docker_startup(
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    mounted_workspace_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    entrypoint = DOCKER_ENTRYPOINT
    if mounted_workspace_root is not None:
        entrypoint = cwd / "docker-entrypoint.host-test.sh"
        entrypoint.write_text(
            DOCKER_ENTRYPOINT.read_text(encoding="utf-8").replace(
                "/workspace", str(mounted_workspace_root)
            ),
            encoding="utf-8",
        )
    command = [
        "sh",
        str(entrypoint),
        _uv_executable(),
        "run",
        "--project",
        str(REPO_ROOT),
        "--package",
        "runsight",
        "python",
        "-c",
        _PACKAGE_STARTUP_SNIPPET,
    ]
    merged_env = _minimal_subprocess_env(_isolated_home_env(cwd / ".test-home"))
    merged_env.update(dict(env or {}))
    return subprocess.run(
        command,
        cwd=cwd,
        env=merged_env,
        check=False,
        capture_output=True,
        text=True,
    )


def _seed_legacy_resolution_traps(workspace_root: Path) -> tuple[Path, Path]:
    redirected = workspace_root.parent / f"{workspace_root.name}-redirected"
    redirected.mkdir()
    (workspace_root / "custom" / "workflows").mkdir(parents=True)
    (workspace_root / ".runsight-project").write_text(
        f"version: 1\nbase_path: {redirected}\n",
        encoding="utf-8",
    )
    launch_dir = workspace_root / "nested" / "launch"
    launch_dir.mkdir(parents=True)
    return launch_dir, redirected
