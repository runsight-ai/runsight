"""GitService — subprocess-based Git abstraction."""

from __future__ import annotations

import os
import subprocess
import tempfile
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

    def _run(
        self,
        *args: str,
        check: bool = True,
        input_text: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            check=check,
            input=input_text,
            env=env,
        )

    def _normalize_repo_path(self, path: str | Path) -> str:
        candidate = Path(path)
        if candidate.is_absolute():
            try:
                return candidate.resolve().relative_to(self.repo_path.resolve()).as_posix()
            except ValueError:
                return candidate.as_posix()
        return candidate.as_posix()

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

    def read_file(self, path: str, ref: str) -> str:
        repo_path = self._normalize_repo_path(path)
        result = self._run("show", f"{ref}:{repo_path}")
        return result.stdout

    def get_sha(self, branch: str, path: str) -> Optional[str]:
        repo_path = self._normalize_repo_path(path)
        result = self._run("log", "-1", "--format=%H", branch, "--", repo_path, check=False)
        sha = result.stdout.strip()
        return sha if sha else None

    def create_sim_branch(
        self, workflow_slug: str, yaml_content: str, yaml_path: str
    ) -> SimBranchResult:
        """Create a simulation branch with the current worktree snapshot committed to it.

        The simulation snapshot starts from ``HEAD``, stages the current worktree into
        a temporary index, then force-overrides the requested workflow file with the
        in-memory YAML draft. This keeps parent/child workflow resolution branch-
        consistent even when related workflow files only exist in the local worktree.
        """
        short_id = uuid.uuid4().hex[:5]
        today = date.today().strftime("%Y%m%d")
        branch_name = f"sim/{workflow_slug}/{today}/{short_id}"
        repo_yaml_path = self._normalize_repo_path(yaml_path)
        base_commit = self._run("rev-parse", "HEAD").stdout.strip()
        blob_sha = self._run("hash-object", "-w", "--stdin", input_text=yaml_content).stdout.strip()

        with tempfile.NamedTemporaryFile() as tmp_index:
            env = {**os.environ, "GIT_INDEX_FILE": tmp_index.name}
            self._run("read-tree", base_commit, env=env)
            self._run("add", "-A", env=env)
            self._run(
                "update-index", "--add", "--cacheinfo", "100644", blob_sha, repo_yaml_path, env=env
            )
            tree_sha = self._run("write-tree", env=env).stdout.strip()

        sha = self._run(
            "commit-tree",
            tree_sha,
            "-p",
            base_commit,
            "-m",
            f"Simulation snapshot: {workflow_slug}",
        ).stdout.strip()
        self._run("branch", branch_name, sha)

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
