from __future__ import annotations

import re
import subprocess
from pathlib import Path

BRANCH_PATTERN = re.compile(r"^sim/[a-z0-9-]+/\d{8}/[a-z0-9]{5}$")
SIM_BRANCH_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "sim_branches"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@test.com")
    git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# hello", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial commit")
    return repo


def sample_yaml() -> str:
    return (SIM_BRANCH_FIXTURE_ROOT / "research-review.yaml").read_text(encoding="utf-8")
