"""Published package and Docker startup honor explicit workspace roots."""

from pathlib import Path

from tests.core.workspace_resolution_helpers import (
    _run_docker_startup,
    _run_package_startup,
    _seed_legacy_resolution_traps,
)


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
                "PYTEST_CURRENT_TEST": "workspace resolution regression",
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
                "PYTEST_CURRENT_TEST": "workspace resolution regression",
                "RUNSIGHT_BASE_PATH": str(base_path),
                "TMPDIR": str(base_path),
            },
        )

        assert result.returncode == 0, result.stderr
        assert str(base_path.resolve()) in result.stdout
        assert not (launch_dir / ".runsight").exists()
