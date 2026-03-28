"""GitService — subprocess-based Git abstraction."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class GitService:
    """Thin wrapper around git CLI commands scoped to a repository path."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path)

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            check=check,
        )

    def current_branch(self) -> str:
        result = self._run("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    def is_clean(self) -> bool:
        result = self._run("status", "--porcelain")
        return result.stdout.strip() == ""

    def create_branch(self, name: str) -> None:
        self._run("branch", name)

    def delete_branch(self, name: str) -> None:
        self._run("branch", "-D", name)

    def read_file(self, path: str, branch: str) -> str:
        result = self._run("show", f"{branch}:{path}")
        return result.stdout

    def get_sha(self, branch: str, path: str) -> Optional[str]:
        result = self._run("log", "-1", "--format=%H", branch, "--", path, check=False)
        sha = result.stdout.strip()
        return sha if sha else None

    def commit_to_branch(self, branch: str, files: list[str], message: str) -> str:
        if not message.strip():
            raise ValueError("Commit message must not be empty")

        # Verify target branch exists
        self._run("rev-parse", "--verify", branch)

        original = self.current_branch()
        try:
            self._run("checkout", branch)
            self._run("add", "--", *files)
            self._run("commit", "-m", message)
            result = self._run("rev-parse", "HEAD")
            return result.stdout.strip()
        finally:
            self._run("checkout", original)
