"""Startup reports clear failures for unusable workspace roots."""

from pathlib import Path

from tests.core.workspace_resolution_helpers import _run_package_startup


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
