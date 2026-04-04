"""Red tests for RUN-135: Simulation branch creation + branch-aware file read.

Tests verify that GitService exposes a ``create_sim_branch`` method that:

- Creates a branch matching ``sim/{workflow-slug}/{YYYYMMDD}/{short-uuid}``
- Commits the provided YAML content to that branch (not main)
- Returns a result containing the branch name and commit SHA
- Allows ``read_file`` to read YAML from the sim branch without checkout
- Supports multiple sim branches coexisting for the same workflow
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BRANCH_PATTERN = re.compile(r"^sim/[a-z0-9-]+/\d{8}/[a-z0-9]{5}$")

SAMPLE_YAML = """\
name: research-review
steps:
  - id: summarize
    soul: researcher
"""


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside *repo* and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> Path:
    """Create a bare-bones git repo with one commit on main."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# hello")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")
    return repo


# ---------------------------------------------------------------------------
# 1. Branch naming convention
# ---------------------------------------------------------------------------


class TestSimBranchNaming:
    """Sim branch name must match ``sim/{slug}/{YYYYMMDD}/{short-uuid}``."""

    def test_branch_name_matches_convention(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        assert BRANCH_PATTERN.match(result.branch), (
            f"Branch name '{result.branch}' does not match pattern "
            f"'sim/{{slug}}/{{YYYYMMDD}}/{{short-id}}'"
        )

    def test_branch_name_contains_workflow_slug(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="my-cool-workflow",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/my-cool-workflow.yaml",
        )

        parts = result.branch.split("/")
        assert parts[0] == "sim"
        assert parts[1] == "my-cool-workflow"

    def test_branch_name_contains_today_date(self, tmp_path: Path):
        from datetime import date

        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        today = date.today().strftime("%Y%m%d")
        parts = result.branch.split("/")
        assert parts[2] == today, f"Expected date segment '{today}', got '{parts[2]}'"

    def test_short_uuid_is_5_lowercase_alphanumeric(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        short_id = result.branch.split("/")[3]
        assert len(short_id) == 5
        assert re.match(r"^[a-z0-9]{5}$", short_id), (
            f"Short UUID '{short_id}' must be 5 lowercase alphanumeric chars"
        )


# ---------------------------------------------------------------------------
# 2. YAML committed to sim branch (not main)
# ---------------------------------------------------------------------------


class TestSimBranchCommit:
    """YAML content must be committed to the sim branch, not main."""

    def test_yaml_file_exists_on_sim_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        # Verify the file exists on the sim branch via git show
        content = _git(repo, "show", f"{result.branch}:workflows/research-review.yaml")
        assert content == SAMPLE_YAML.strip()

    def test_yaml_not_committed_to_main(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        # The YAML file must NOT exist on main
        check = subprocess.run(
            ["git", "show", "main:workflows/research-review.yaml"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert check.returncode != 0, "YAML file must not be on main branch"

    def test_main_branch_unchanged_after_sim_creation(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        main_sha_before = _git(repo, "rev-parse", "main")

        svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        main_sha_after = _git(repo, "rev-parse", "main")
        assert main_sha_before == main_sha_after, (
            "Main branch SHA must not change after sim branch creation"
        )

    def test_current_branch_stays_on_main(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        assert svc.current_branch() == "main", (
            "Working tree must remain on main after sim branch creation"
        )


# ---------------------------------------------------------------------------
# 3. Return value: branch name + commit SHA
# ---------------------------------------------------------------------------


class TestSimBranchReturnValue:
    """create_sim_branch must return an object with .branch and .sha."""

    def test_returns_object_with_branch_attr(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        assert hasattr(result, "branch")
        assert isinstance(result.branch, str)
        assert len(result.branch) > 0

    def test_returns_object_with_sha_attr(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        assert hasattr(result, "sha")
        assert isinstance(result.sha, str)
        assert len(result.sha) == 40
        assert all(c in "0123456789abcdef" for c in result.sha)

    def test_sha_matches_actual_commit(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        actual_sha = _git(repo, "rev-parse", result.branch)
        assert result.sha == actual_sha


# ---------------------------------------------------------------------------
# 4. read_file works from sim branch without checkout
# ---------------------------------------------------------------------------


class TestReadFileFromSimBranch:
    """Existing read_file must retrieve YAML from a sim branch."""

    def test_read_yaml_from_sim_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        content = svc.read_file("workflows/research-review.yaml", result.branch)
        assert "research-review" in content
        assert "summarize" in content

    def test_read_file_without_checking_out_branch(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        result = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        # Confirm we are still on main
        assert svc.current_branch() == "main"

        # read_file should work via git show, not checkout
        content = svc.read_file("workflows/research-review.yaml", result.branch)
        assert content.strip() == SAMPLE_YAML.strip()

        # Still on main after read
        assert svc.current_branch() == "main"


# ---------------------------------------------------------------------------
# 5. Multiple sim branches coexist for the same workflow
# ---------------------------------------------------------------------------


class TestMultipleSimBranches:
    """Multiple sim branches for the same workflow must coexist."""

    def test_two_sim_branches_have_different_names(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        r1 = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )
        r2 = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=SAMPLE_YAML,
            yaml_path="workflows/research-review.yaml",
        )

        assert r1.branch != r2.branch

    def test_two_sim_branches_have_different_shas(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        yaml_v1 = "name: v1\nsteps: []\n"
        yaml_v2 = "name: v2\nsteps: []\n"

        r1 = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=yaml_v1,
            yaml_path="workflows/research-review.yaml",
        )
        r2 = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=yaml_v2,
            yaml_path="workflows/research-review.yaml",
        )

        assert r1.sha != r2.sha

    def test_each_sim_branch_has_its_own_yaml(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        yaml_v1 = "name: version-one\n"
        yaml_v2 = "name: version-two\n"

        r1 = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=yaml_v1,
            yaml_path="workflows/research-review.yaml",
        )
        r2 = svc.create_sim_branch(
            workflow_slug="research-review",
            yaml_content=yaml_v2,
            yaml_path="workflows/research-review.yaml",
        )

        content_1 = svc.read_file("workflows/research-review.yaml", r1.branch)
        content_2 = svc.read_file("workflows/research-review.yaml", r2.branch)

        assert "version-one" in content_1
        assert "version-two" in content_2

    def test_three_sim_branches_all_listed(self, tmp_path: Path):
        from runsight_api.logic.services.git_service import GitService

        repo = _init_repo(tmp_path)
        svc = GitService(repo_path=str(repo))

        branches = []
        for i in range(3):
            r = svc.create_sim_branch(
                workflow_slug="research-review",
                yaml_content=f"version: {i}\n",
                yaml_path="workflows/research-review.yaml",
            )
            branches.append(r.branch)

        # All three branches must exist in git
        all_branches = _git(repo, "branch", "--list", "sim/*")
        for b in branches:
            assert b in all_branches, f"Branch '{b}' not found in git branch list"
