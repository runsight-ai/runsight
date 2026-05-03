"""Fixture builders for git transport tests."""

from __future__ import annotations

import subprocess
from pathlib import Path


def init_git_repo(tmp: Path) -> Path:
    """Initialise a throwaway git repo with custom/workflows/ directory."""
    (tmp / "custom" / "workflows").mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@runsight.dev"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    commit_text_file(tmp, "README.md", "init", message="initial")
    return tmp


def get_head_sha(repo: Path) -> str:
    """Return the HEAD commit SHA of a repo."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def commit_text_file(repo: Path, relative_path: str, content: str, *, message: str) -> Path:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)
    return path


def commit_binary_file(repo: Path, relative_path: str, content: bytes, *, message: str) -> Path:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)
    return path
