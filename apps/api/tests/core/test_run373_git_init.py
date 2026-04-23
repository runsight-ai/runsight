"""Tests for git initialization during workspace scaffolding."""

import subprocess
from pathlib import Path

from runsight_api.core.project import scaffold_project


class TestGitInitOnFreshDirectory:
    def test_git_directory_created(self, tmp_path: Path):
        scaffold_project(tmp_path)

        assert (tmp_path / ".git").is_dir(), ".git directory was not created"

    def test_git_log_returns_at_least_one_commit(self, tmp_path: Path):
        scaffold_project(tmp_path)

        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"git log failed: {result.stderr}"
        assert result.stdout.strip(), "Expected at least one initial commit"

    def test_initial_commit_tracks_workspace_scaffold_without_marker(self, tmp_path: Path):
        scaffold_project(tmp_path)

        result = subprocess.run(
            ["git", "ls-tree", "--name-only", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"git ls-tree failed: {result.stderr}"
        tracked = result.stdout.strip().splitlines()
        assert ".gitignore" in tracked
        assert ".runsight-project" not in tracked

    def test_working_tree_is_clean_after_scaffold(self, tmp_path: Path):
        scaffold_project(tmp_path)

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"git status failed: {result.stderr}"
        assert result.stdout.strip() == "", (
            f"Working tree is not clean after scaffold:\n{result.stdout}"
        )


class TestExistingRepoNotReinitialized:
    def _init_repo_with_commit(self, base: Path) -> str:
        subprocess.run(["git", "init"], cwd=base, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=base,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=base,
            capture_output=True,
            check=True,
        )
        sentinel = base / "existing.txt"
        sentinel.write_text("I was here before scaffold", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=base, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "pre-existing commit"],
            cwd=base,
            capture_output=True,
            check=True,
        )
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=base,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def test_commit_count_unchanged(self, tmp_path: Path):
        self._init_repo_with_commit(tmp_path)
        result_before = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        scaffold_project(tmp_path)

        result_after = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert int(result_after.stdout.strip()) == int(result_before.stdout.strip())

    def test_original_commit_hash_preserved(self, tmp_path: Path):
        original_hash = self._init_repo_with_commit(tmp_path)

        scaffold_project(tmp_path)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.stdout.strip() == original_hash

    def test_git_dir_not_recreated(self, tmp_path: Path):
        self._init_repo_with_commit(tmp_path)
        sentinel = tmp_path / ".git" / "runsight_test_sentinel"
        sentinel.write_text("proof", encoding="utf-8")

        scaffold_project(tmp_path)

        assert sentinel.is_file()
        assert sentinel.read_text(encoding="utf-8") == "proof"


class TestGitignoreContainsRunsight:
    def test_gitignore_contains_runsight_entry(self, tmp_path: Path):
        scaffold_project(tmp_path)

        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")

        assert ".runsight/" in content

    def test_existing_gitignore_gets_runsight_entry(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n.env\n", encoding="utf-8")

        scaffold_project(tmp_path)

        content = gitignore.read_text(encoding="utf-8")
        assert ".runsight/" in content
