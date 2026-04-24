"""Red tests for RUN-963: deterministic workspace resolution without markers."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from runsight_api.core.config import Settings, ensure_project_dirs
from runsight_api.core.project import resolve_base_path

REPO_ROOT = Path(__file__).resolve().parents[4]
README = REPO_ROOT / "README.md"
DOCKER_ENTRYPOINT = REPO_ROOT / "docker-entrypoint.sh"

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
    merged_env = {**os.environ}
    if env is None or "RUNSIGHT_BASE_PATH" not in env:
        merged_env.pop("RUNSIGHT_BASE_PATH", None)
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
    merged_env = {**os.environ}
    if env is None or "RUNSIGHT_BASE_PATH" not in env:
        merged_env.pop("RUNSIGHT_BASE_PATH", None)
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


class TestResolveBasePathDeterministicPolicy:
    """Workspace resolution should never depend on legacy marker walk-up."""

    def test_ignores_legacy_marker_in_launch_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        redirected = tmp_path / "redirected"
        redirected.mkdir()
        marker = tmp_path / ".runsight-project"
        marker.write_text(
            f"version: 1\nbase_path: {redirected}\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        assert resolve_base_path(env_value=None) == str(tmp_path.resolve())

    def test_does_not_walk_up_to_ancestor_custom_workflows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        (tmp_path / "custom" / "workflows").mkdir(parents=True)
        launch_dir = tmp_path / "nested" / "launch"
        launch_dir.mkdir(parents=True)
        monkeypatch.chdir(launch_dir)

        assert resolve_base_path(env_value=None) == str(launch_dir.resolve())


class TestStartupWorkspaceBootstrap:
    """Application startup should use the chosen workspace root directly."""

    def test_source_startup_uses_launch_directory_instead_of_ancestor_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        workspace_root = tmp_path / "workspace-root"
        workspace_root.mkdir()
        redirected = tmp_path / "redirected-root"
        redirected.mkdir()
        marker = workspace_root / ".runsight-project"
        marker.write_text(
            f"version: 1\nbase_path: {redirected}\n",
            encoding="utf-8",
        )
        launch_dir = workspace_root / "nested" / "launch"
        launch_dir.mkdir(parents=True)
        monkeypatch.chdir(launch_dir)
        monkeypatch.delenv("RUNSIGHT_BASE_PATH", raising=False)
        monkeypatch.delenv("RUNSIGHT_DB_URL", raising=False)

        settings = Settings()
        ensure_project_dirs(settings)

        assert Path(settings.base_path).resolve() == launch_dir.resolve()
        assert (launch_dir / ".runsight").is_dir()
        assert (launch_dir / "custom" / "workflows").is_dir()
        assert not (launch_dir / ".runsight-project").exists()
        assert not (redirected / ".runsight").exists()

    def test_bootstrap_does_not_create_legacy_marker_file(self, tmp_path: Path):
        settings = Settings(base_path=str(tmp_path))

        ensure_project_dirs(settings)

        assert (tmp_path / ".runsight").is_dir()
        assert (tmp_path / "custom" / "workflows").is_dir()
        assert (tmp_path / "custom" / "souls").is_dir()
        assert not (tmp_path / ".runsight-project").exists()

    def test_runsight_base_path_env_wins_without_writing_marker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        launch_dir = tmp_path / "launch-dir"
        launch_dir.mkdir()
        base_path = tmp_path / "explicit-workspace"
        base_path.mkdir()
        monkeypatch.chdir(launch_dir)
        monkeypatch.setenv("RUNSIGHT_BASE_PATH", str(base_path))

        settings = Settings()
        ensure_project_dirs(settings)

        assert Path(settings.base_path).resolve() == base_path.resolve()
        assert (base_path / ".runsight").is_dir()
        assert (base_path / "custom" / "workflows").is_dir()
        assert (base_path / "custom" / "souls").is_dir()
        assert not (base_path / ".runsight-project").exists()
        assert not (launch_dir / ".runsight").exists()
        assert not (launch_dir / "custom").exists()


class TestPublishedPackageAndDockerContracts:
    """Published-package and Docker launch surfaces should honor the same contract."""

    def test_published_package_defaults_to_launch_directory_without_env_override(
        self, tmp_path: Path
    ):
        workspace_root = tmp_path / "package-workspace"
        workspace_root.mkdir()
        launch_dir, redirected = _seed_legacy_resolution_traps(workspace_root)

        result = _run_package_startup(launch_dir)

        assert result.returncode == 0, result.stderr
        assert (launch_dir / ".runsight").is_dir()
        assert (launch_dir / "custom" / "workflows").is_dir()
        assert not (launch_dir / ".runsight-project").exists()
        assert not (redirected / ".runsight").exists()
        assert str(launch_dir.resolve()) in result.stdout

    def test_published_package_startup_honors_runsight_base_path_without_marker(
        self, tmp_path: Path
    ):
        base_path = tmp_path / "uvx-workspace"
        base_path.mkdir()
        launch_dir = tmp_path / "launch-dir"
        launch_dir.mkdir()

        result = _run_package_startup(
            launch_dir,
            env={"RUNSIGHT_BASE_PATH": str(base_path)},
        )

        assert result.returncode == 0, result.stderr
        assert (base_path / ".runsight").is_dir()
        assert (base_path / "custom" / "workflows").is_dir()
        assert (base_path / "custom" / "souls").is_dir()
        assert not (base_path / ".runsight-project").exists()
        assert not (launch_dir / ".runsight").exists()

    def test_published_package_honors_explicit_base_path_even_when_pytest_tmpdir_matches(
        self, tmp_path: Path
    ):
        base_path = tmp_path / "pytest-tmpdir-workspace"
        base_path.mkdir()
        launch_dir = tmp_path / "launch-dir"
        launch_dir.mkdir()
        different_tmpdir = tmp_path / "different-tmpdir"
        different_tmpdir.mkdir()

        result = _run_package_startup(
            launch_dir,
            env={
                "PYTEST_CURRENT_TEST": "RUN-963 regression",
                "RUNSIGHT_BASE_PATH": str(base_path),
                "TMPDIR": str(different_tmpdir),
            },
        )

        assert result.returncode == 0, result.stderr
        assert str(base_path.resolve()) in result.stdout
        assert not (launch_dir / ".runsight").exists()

    def test_docker_entrypoint_defaults_to_mounted_workspace_root_without_env_override(
        self, tmp_path: Path
    ):
        mounted_workspace_root = tmp_path / "docker-mounted-workspace"
        mounted_workspace_root.mkdir()
        launch_dir, redirected = _seed_legacy_resolution_traps(mounted_workspace_root)

        result = _run_docker_startup(
            launch_dir,
            mounted_workspace_root=mounted_workspace_root,
        )

        assert result.returncode == 0, result.stderr
        assert (mounted_workspace_root / ".runsight").is_dir()
        assert (mounted_workspace_root / "custom" / "workflows").is_dir()
        assert not (mounted_workspace_root / ".runsight-project").exists()
        assert not (redirected / ".runsight").exists()
        assert str(mounted_workspace_root.resolve()) in result.stdout

    def test_docker_entrypoint_uses_same_workspace_contract_without_marker(self, tmp_path: Path):
        base_path = tmp_path / "docker-workspace"
        base_path.mkdir()
        launch_dir = tmp_path / "launch-dir"
        launch_dir.mkdir()

        result = _run_docker_startup(
            launch_dir,
            env={"RUNSIGHT_BASE_PATH": str(base_path)},
        )

        assert result.returncode == 0, result.stderr
        assert (base_path / ".runsight").is_dir()
        assert (base_path / "custom" / "workflows").is_dir()
        assert (base_path / "custom" / "souls").is_dir()
        assert not (base_path / ".runsight-project").exists()
        assert not (launch_dir / ".runsight").exists()

    def test_docker_entrypoint_honors_explicit_base_path_even_when_pytest_tmpdir_matches(
        self, tmp_path: Path
    ):
        base_path = tmp_path / "docker-pytest-tmpdir-workspace"
        base_path.mkdir()
        launch_dir = tmp_path / "launch-dir"
        launch_dir.mkdir()

        result = _run_docker_startup(
            launch_dir,
            env={
                "PYTEST_CURRENT_TEST": "RUN-963 regression",
                "RUNSIGHT_BASE_PATH": str(base_path),
                "TMPDIR": str(base_path),
            },
        )

        assert result.returncode == 0, result.stderr
        assert str(base_path.resolve()) in result.stdout
        assert not (launch_dir / ".runsight").exists()


class TestStartupFailureContracts:
    """Startup should fail clearly for invalid workspaces instead of redirecting or limping on."""

    def test_published_package_reports_clear_error_for_read_only_workspace(self, tmp_path: Path):
        launch_dir = tmp_path / "launch-dir"
        launch_dir.mkdir()
        base_path = tmp_path / "read-only-workspace"
        base_path.mkdir()
        base_path.chmod(0o555)

        try:
            result = _run_package_startup(
                launch_dir,
                env={"RUNSIGHT_BASE_PATH": str(base_path)},
            )
        finally:
            base_path.chmod(0o755)

        combined_output = f"{result.stdout}\n{result.stderr}"
        lower_output = combined_output.lower()
        assert result.returncode != 0, "startup should fail for an unwritable workspace"
        assert str(base_path) in combined_output
        assert any(
            phrase in lower_output
            for phrase in ("permission", "denied", "read-only", "not writable", "write")
        ), combined_output
        assert "Traceback" not in combined_output
        assert not (launch_dir / ".runsight").exists()

    def test_published_package_rejects_partial_workspace_with_file_at_runsight_dir(
        self, tmp_path: Path
    ):
        launch_dir = tmp_path / "launch-dir"
        launch_dir.mkdir()
        base_path = tmp_path / "partial-workspace"
        base_path.mkdir()
        (base_path / ".runsight").write_text("not a directory", encoding="utf-8")

        result = _run_package_startup(
            launch_dir,
            env={"RUNSIGHT_BASE_PATH": str(base_path)},
        )

        combined_output = f"{result.stdout}\n{result.stderr}"
        assert result.returncode != 0, "startup should fail for a partial workspace"
        assert ".runsight" in combined_output
        assert "directory" in combined_output.lower()
        assert "Traceback" not in combined_output
        assert not (launch_dir / ".runsight").exists()


class TestReadmeGuidance:
    """User-facing docs must describe the Docker workspace-root persistence contract."""

    def test_readme_explains_mounting_workspace_root_for_db_and_settings_persistence(self):
        text = README.read_text(encoding="utf-8").lower()

        mentions_workspace_root = "workspace root" in text or "whole workspace" in text
        mentions_not_custom_only = "not only `custom/`" in text or "not just `custom/`" in text
        mentions_runtime_persistence = ".runsight/" in text and any(
            phrase in text for phrase in ("db", "settings", "persistence")
        )

        assert (
            mentions_workspace_root and mentions_not_custom_only and mentions_runtime_persistence
        ), (
            "README must explain that Docker users should mount the whole workspace root, not "
            "just custom/, when they want .runsight/ DB/settings persistence."
        )
