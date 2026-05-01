"""
Tracked artifact boundary governance.

Owner: repo maintenance and workspace owners for apps/api, apps/gui, packages,
and testing.
Boundary: source workspaces must not track generated, backup, compiled, or
local-data artifacts, and root .gitignore must keep guardrails for those classes.
Exit criteria: delete this governance suite once a repo-wide tracked-artifact
scanner owns the same policy in tools or CI.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_GITIGNORE = REPO_ROOT / ".gitignore"
SOURCE_WORKSPACES = ("apps/api", "apps/gui", "packages", "testing")

AUDITED_INVALID_TRACKED_ARTIFACTS = (
    "apps/api/skeleton.xml",
    "apps/gui/skeleton.xml",
    "packages/ui/components.json.bak",
)

EXPECTED_GITIGNORE_PATTERNS = (
    "*.xml",
    "*.bak",
    "*.db",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".DS_Store",
)


def _tracked_source_workspace_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", *SOURCE_WORKSPACES],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _tracked_invalid_artifacts() -> list[str]:
    invalid: list[str] = []

    for relative_path in _tracked_source_workspace_files():
        path = Path(relative_path)

        if path.name == "skeleton.xml":
            invalid.append(relative_path)
            continue

        if path.suffix in {".bak", ".pyc", ".pyo", ".pyd"}:
            invalid.append(relative_path)
            continue

        if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache"} for part in path.parts):
            invalid.append(relative_path)
            continue

        if path.name == ".DS_Store":
            invalid.append(relative_path)

    return invalid


class TestTrackedArtifactGuardrails:
    """Owner: repo maintenance. Exit: CI scanner owns ignore-rule validation."""

    def test_root_gitignore_covers_audited_artifact_classes(self):
        text = ROOT_GITIGNORE.read_text(encoding="utf-8")

        missing = [pattern for pattern in EXPECTED_GITIGNORE_PATTERNS if pattern not in text]
        assert missing == [], f"Root .gitignore is missing artifact guardrails: {missing}"


class TestTrackedSourceWorkspaceArtifacts:
    """Owner: source workspace owners. Exit: CI scanner owns tracked-artifact checks."""

    def test_source_workspaces_do_not_track_invalid_artifact_classes(self):
        invalid = _tracked_invalid_artifacts()
        assert invalid == [], (
            "Tracked source workspaces still contain generated/backup/compiled/local-data detritus:\n"
            + "\n".join(f"  - {path}" for path in invalid)
        )

    def test_audited_invalid_artifacts_are_removed_from_git(self):
        tracked = set(_tracked_source_workspace_files())
        remaining = [path for path in AUDITED_INVALID_TRACKED_ARTIFACTS if path in tracked]

        assert remaining == [], (
            "Audited invalid tracked artifacts still exist in source workspaces:\n"
            + "\n".join(f"  - {path}" for path in remaining)
        )
