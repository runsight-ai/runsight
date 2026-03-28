"""GitService — subprocess-based Git abstraction."""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class SimBranchResult:
    """Result of creating a simulation branch."""

    branch: str
    sha: str


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

    def create_sim_branch(
        self, workflow_slug: str, yaml_content: str, yaml_path: str
    ) -> SimBranchResult:
        """Create a simulation branch with YAML content committed to it."""
        short_id = uuid.uuid4().hex[:5]
        today = date.today().strftime("%Y%m%d")
        branch_name = f"sim/{workflow_slug}/{today}/{short_id}"

        original = self.current_branch()
        self._run("branch", branch_name)
        try:
            self._run("checkout", branch_name)
            full_path = self.repo_path / yaml_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(yaml_content)
            self._run("add", "--", yaml_path)
            self._run("commit", "-m", f"Simulation snapshot: {workflow_slug}")
            sha = self._run("rev-parse", "HEAD").stdout.strip()
        finally:
            self._run("checkout", original)
            # Clean up the yaml file from working tree if it exists
            if full_path.exists():
                full_path.unlink()
                # Remove parent dir if empty
                try:
                    full_path.parent.rmdir()
                except OSError:
                    pass

        return SimBranchResult(branch=branch_name, sha=sha)

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
