"""Red tests for RUN-373: Git init on first launch.

ADR-001: "Git is required. On first launch, if no Git repo exists,
Runsight runs git init."

Tests for scaffold_project(base_path) which should:
- Run `git init` when no .git directory exists
- Create an initial commit so git log/show/branch work
- NOT re-initialize an existing git repo
- Include .runsight/ in .gitignore
"""

import subprocess
from pathlib import Path

from runsight_api.core.project import MARKER_FILE, scaffold_project


class TestGitInitOnFreshDirectory:
    """Fresh directory with no .git -> scaffold_project runs git init."""

    def test_git_directory_created(self, tmp_path: Path):
        """After scaffold_project(), .git directory must exist."""
        scaffold_project(tmp_path)
        assert (tmp_path / ".git").is_dir(), ".git directory was not created"

    def test_git_log_returns_at_least_one_commit(self, tmp_path: Path):
        """After scaffold_project(), `git log` must return at least one commit."""
        scaffold_project(tmp_path)
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"git log failed: {result.stderr}"
        commits = [line for line in result.stdout.strip().splitlines() if line]
        assert len(commits) >= 1, "Expected at least one initial commit"

    def test_initial_commit_includes_scaffolded_files(self, tmp_path: Path):
        """The initial commit should contain the scaffolded files."""
        scaffold_project(tmp_path)
        result = subprocess.run(
            ["git", "ls-tree", "--name-only", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"git ls-tree failed: {result.stderr}"
        tracked = result.stdout.strip().splitlines()
        assert ".gitignore" in tracked, ".gitignore should be in the initial commit"
        assert MARKER_FILE in tracked, f"{MARKER_FILE} should be in the initial commit"

    def test_working_tree_is_clean_after_scaffold(self, tmp_path: Path):
        """After scaffold + initial commit, working tree should be clean."""
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
    """Existing git repo -> scaffold_project must NOT re-initialize."""

    def _init_repo_with_commit(self, base: Path) -> str:
        """Create a git repo with one commit and return its hash."""
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
        sentinel.write_text("I was here before scaffold")
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
        """scaffold_project on existing repo must not add extra commits."""
        self._init_repo_with_commit(tmp_path)
        result_before = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        count_before = int(result_before.stdout.strip())

        scaffold_project(tmp_path)

        result_after = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        count_after = int(result_after.stdout.strip())
        assert count_after == count_before, (
            f"Commit count changed from {count_before} to {count_after}; "
            "scaffold_project should not add commits to an existing repo"
        )

    def test_original_commit_hash_preserved(self, tmp_path: Path):
        """The original HEAD commit hash must remain unchanged."""
        original_hash = self._init_repo_with_commit(tmp_path)

        scaffold_project(tmp_path)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == original_hash, (
            "HEAD changed after scaffold_project on existing repo"
        )

    def test_git_dir_not_recreated(self, tmp_path: Path):
        """The .git directory must not be wiped and recreated."""
        self._init_repo_with_commit(tmp_path)
        git_dir = tmp_path / ".git"
        # Add a sentinel inside .git to prove it's the same directory
        sentinel = git_dir / "runsight_test_sentinel"
        sentinel.write_text("proof")

        scaffold_project(tmp_path)

        assert sentinel.is_file(), ".git directory was recreated (sentinel lost)"
        assert sentinel.read_text() == "proof"


class TestGitignoreContainsRunsight:
    """.gitignore must include .runsight/ directory."""

    def test_gitignore_contains_runsight_entry(self, tmp_path: Path):
        scaffold_project(tmp_path)
        gitignore = tmp_path / ".gitignore"
        assert gitignore.is_file(), ".gitignore was not created"
        content = gitignore.read_text(encoding="utf-8")
        assert ".runsight/" in content, (
            f".gitignore does not contain '.runsight/' entry. Content:\n{content}"
        )

    def test_existing_gitignore_gets_runsight_entry(self, tmp_path: Path):
        """If .gitignore already exists but lacks .runsight/, it should be added."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n.env\n", encoding="utf-8")

        scaffold_project(tmp_path)

        content = gitignore.read_text(encoding="utf-8")
        assert ".runsight/" in content, ".runsight/ should be added to existing .gitignore"
