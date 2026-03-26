"""Red-phase tests for RUN-124: Git subprocess security hardening.

Tests cover:
- Path traversal prevention (relative and absolute)
- Symlink escape prevention
- Command injection in commit messages
- Control character sanitization in commit messages
- Branch name injection prevention
- Flag injection via file paths starting with `-`
- Error response scrubbing (no filesystem paths leaked)
- shell=False enforcement (source code audit)

These tests assert against *explicit* validation behaviour that the router
must implement.  They will FAIL until the Green Team adds input-sanitisation
guards to the git router.
"""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from runsight_api.main import app
from runsight_api.core.config import settings


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _init_git_repo(tmp: Path) -> Path:
    """Initialise a throwaway git repo with custom/workflows/ directory."""
    (tmp / "custom" / "workflows").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
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
    (tmp / "README.md").write_text("init")
    subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    return tmp


@pytest.fixture()
def git_repo(tmp_path):
    """Yield a temporary git repo path and override settings.base_path."""
    repo = _init_git_repo(tmp_path)
    original = settings.base_path
    settings.base_path = str(repo)
    yield repo
    settings.base_path = original


client = TestClient(app)

# Keyword that the router should use in its rejection detail messages
# for path-related validation failures.
_PATH_REJECTION_KEYWORD = "path"


# ===================================================================
# Path Traversal Prevention
# ===================================================================


class TestPathTraversal:
    """File paths passed to git commands must be validated by the router,
    not just rejected by git itself.  The detail message must mention 'path'
    so we know the router did the validation."""

    def test_relative_path_traversal_rejected(self, git_repo):
        """../../etc/passwd in file list -> 400 with path validation message."""
        resp = client.post(
            "/api/git/commit",
            json={
                "message": "innocent commit",
                "files": ["../../etc/passwd"],
            },
        )
        assert resp.status_code == 400
        detail = (
            resp.json()
            .get("error", resp.json().get("error", resp.json().get("detail", "")))
            .lower()
        )
        assert _PATH_REJECTION_KEYWORD in detail, (
            f"Router must explicitly reject path traversal; got: {detail!r}"
        )

    def test_absolute_path_outside_base_rejected(self, git_repo):
        """/etc/passwd in file list -> 400 with path validation message."""
        resp = client.post(
            "/api/git/commit",
            json={
                "message": "innocent commit",
                "files": ["/etc/passwd"],
            },
        )
        assert resp.status_code == 400
        detail = (
            resp.json()
            .get("error", resp.json().get("error", resp.json().get("detail", "")))
            .lower()
        )
        assert _PATH_REJECTION_KEYWORD in detail, (
            f"Router must explicitly reject absolute paths outside base; got: {detail!r}"
        )

    def test_dot_dot_in_middle_of_path_rejected(self, git_repo):
        """custom/../../../etc/passwd -> 400 with path validation message."""
        resp = client.post(
            "/api/git/commit",
            json={
                "message": "sneaky commit",
                "files": ["custom/../../../etc/passwd"],
            },
        )
        assert resp.status_code == 400
        detail = (
            resp.json()
            .get("error", resp.json().get("error", resp.json().get("detail", "")))
            .lower()
        )
        assert _PATH_REJECTION_KEYWORD in detail

    def test_encoded_traversal_rejected(self, git_repo):
        """URL-encoded traversal sequences in file paths must be rejected."""
        resp = client.post(
            "/api/git/commit",
            json={
                "message": "encoded traversal",
                "files": ["custom%2F..%2F..%2Fetc%2Fpasswd"],
            },
        )
        # Must be rejected or at least the router must validate
        assert resp.status_code == 400

    def test_empty_string_file_path_rejected(self, git_repo):
        """An empty string in the files list must be rejected."""
        resp = client.post(
            "/api/git/commit",
            json={
                "message": "empty path",
                "files": [""],
            },
        )
        assert resp.status_code == 400


# ===================================================================
# Symlink Escape Prevention
# ===================================================================


class TestSymlinkEscape:
    """Symlinks pointing outside base_path must be rejected."""

    def test_symlink_outside_base_path_rejected(self, git_repo):
        """A symlinked file pointing outside base_path must not be staged."""
        # Create a symlink inside the repo pointing to /etc/hosts
        link_path = git_repo / "custom" / "workflows" / "evil_link.yaml"
        target = Path("/etc/hosts")
        if not target.exists():
            pytest.skip("/etc/hosts not available on this system")
        link_path.symlink_to(target)

        resp = client.post(
            "/api/git/commit",
            json={
                "message": "symlink escape",
                "files": ["custom/workflows/evil_link.yaml"],
            },
        )
        assert resp.status_code == 400
        detail = (
            resp.json()
            .get("error", resp.json().get("error", resp.json().get("detail", "")))
            .lower()
        )
        assert "symlink" in detail or _PATH_REJECTION_KEYWORD in detail


# ===================================================================
# Command Injection in Commit Messages
# ===================================================================


class TestCommitMessageSanitization:
    """Commit messages must be sanitized: no injection, no control chars."""

    def test_command_substitution_in_message_sanitized(self, git_repo):
        """$(rm -rf /) in a commit message must be sanitized or rejected."""
        wf = git_repo / "custom" / "workflows" / "safe.yaml"
        wf.write_text("name: safe\n")

        resp = client.post(
            "/api/git/commit",
            json={
                "message": "$(rm -rf /)",
            },
        )
        # Either rejected (400) or accepted but with sanitized message
        if resp.status_code == 200:
            body = resp.json()
            # The stored message must not contain the raw shell substitution
            assert "$(" not in body["message"], (
                "Commit message must strip shell substitution syntax"
            )
        else:
            assert resp.status_code == 400

    def test_backtick_injection_in_message_sanitized(self, git_repo):
        """`rm -rf /` in a commit message must be sanitized or rejected."""
        wf = git_repo / "custom" / "workflows" / "safe2.yaml"
        wf.write_text("name: safe2\n")

        resp = client.post(
            "/api/git/commit",
            json={
                "message": "`rm -rf /`",
            },
        )
        if resp.status_code == 200:
            body = resp.json()
            assert "`" not in body["message"], "Commit message must strip backtick injection"
        else:
            assert resp.status_code == 400

    def test_control_characters_stripped_from_message(self, git_repo):
        """Control characters (\\x07, \\x08, etc.) must be stripped."""
        wf = git_repo / "custom" / "workflows" / "ctrl.yaml"
        wf.write_text("name: ctrl\n")

        resp = client.post(
            "/api/git/commit",
            json={
                "message": "hello\x07world\x08test",
            },
        )
        if resp.status_code == 200:
            body = resp.json()
            assert "\x07" not in body["message"], (
                "Control char BEL must be stripped from commit message"
            )
            assert "\x08" not in body["message"], (
                "Control char BS must be stripped from commit message"
            )
        else:
            assert resp.status_code == 400

    def test_newline_injection_in_message(self, git_repo):
        r"""Newlines in commit message should not allow header injection."""
        wf = git_repo / "custom" / "workflows" / "nl.yaml"
        wf.write_text("name: nl\n")

        resp = client.post(
            "/api/git/commit",
            json={
                "message": "legit message\n\nSigned-off-by: attacker",
            },
        )
        if resp.status_code == 200:
            body = resp.json()
            # Multi-line injection should be stripped to single line
            assert "\n" not in body["message"], (
                "Newlines in commit message must be stripped to prevent header injection"
            )
        else:
            assert resp.status_code == 400


# ===================================================================
# Branch Name Injection
# ===================================================================


class TestBranchNameInjection:
    """Branch names with shell metacharacters must never be executed."""

    def test_shell_false_prevents_branch_injection(self):
        """Verify the _run_git helper uses shell=False (list args) by source audit."""
        git_router_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "runsight_api"
            / "transport"
            / "routers"
            / "git.py"
        )
        source = git_router_path.read_text()
        assert "shell=True" not in source, "git.py must never use shell=True in subprocess calls"


# ===================================================================
# Flag Injection via File Paths
# ===================================================================


class TestFlagInjection:
    """File paths starting with `-` could be interpreted as git flags."""

    def test_file_path_starting_with_double_dash_rejected(self, git_repo):
        """A file path like --exec=bad must be rejected."""
        resp = client.post(
            "/api/git/commit",
            json={
                "message": "flag injection",
                "files": ["--exec=whoami"],
            },
        )
        assert resp.status_code == 400
        detail = (
            resp.json()
            .get("error", resp.json().get("error", resp.json().get("detail", "")))
            .lower()
        )
        assert _PATH_REJECTION_KEYWORD in detail or "invalid" in detail, (
            f"Router must explicitly reject flag-like paths; got: {detail!r}"
        )

    def test_file_path_starting_with_single_dash_rejected(self, git_repo):
        """A file path like -n must be rejected."""
        resp = client.post(
            "/api/git/commit",
            json={
                "message": "dash injection",
                "files": ["-n"],
            },
        )
        assert resp.status_code == 400
        detail = (
            resp.json()
            .get("error", resp.json().get("error", resp.json().get("detail", "")))
            .lower()
        )
        assert _PATH_REJECTION_KEYWORD in detail or "invalid" in detail


# ===================================================================
# Error Response Scrubbing
# ===================================================================


class TestErrorResponseScrubbing:
    """Error responses must not leak filesystem paths."""

    def test_commit_failure_does_not_leak_base_path(self, git_repo):
        """On commit failure, error detail must not contain the base_path value."""
        base = settings.base_path

        # Commit with nothing staged should fail
        resp = client.post(
            "/api/git/commit",
            json={"message": "nothing to commit"},
        )
        if resp.status_code >= 400:
            body = resp.json()
            detail = body.get("error", body.get("detail", ""))
            assert base not in detail, f"Error response leaked base_path: {detail!r}"

    def test_commit_error_with_bad_file_does_not_leak_path(self, git_repo):
        """Committing a nonexistent file must not leak filesystem details."""
        base = settings.base_path

        resp = client.post(
            "/api/git/commit",
            json={
                "message": "nonexistent file",
                "files": ["does/not/exist.yaml"],
            },
        )
        if resp.status_code >= 400:
            body = resp.json()
            detail = body.get("error", body.get("detail", ""))
            assert base not in detail, f"Error response leaked base_path: {detail!r}"

    def test_git_stderr_not_forwarded_raw(self, git_repo):
        """When git fails, its raw stderr (which may contain paths)
        must be scrubbed before inclusion in the HTTP response."""
        # Force a commit failure — nothing staged
        resp = client.post(
            "/api/git/commit",
            json={"message": "force fail"},
        )
        if resp.status_code >= 400:
            detail = resp.json().get("error", resp.json().get("detail", ""))
            # stderr from git often says "On branch X\nnothing to commit"
            # but should not contain the cwd
            base = settings.base_path
            assert base not in detail


# ===================================================================
# Source Code Audit: shell=False Enforcement
# ===================================================================


class TestShellFalseEnforcement:
    """Verify at the source level that shell=True is never used."""

    def test_no_shell_true_in_git_router(self):
        """The git router source must not contain shell=True."""
        git_router_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "runsight_api"
            / "transport"
            / "routers"
            / "git.py"
        )
        source = git_router_path.read_text()
        assert "shell=True" not in source

    def test_subprocess_run_uses_list_args(self):
        """All subprocess.run calls in git.py must use list args (not string)."""
        git_router_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "runsight_api"
            / "transport"
            / "routers"
            / "git.py"
        )
        source = git_router_path.read_text()
        assert '["git"' in source or "['git'" in source, (
            "subprocess.run must be called with a list, not a string"
        )
