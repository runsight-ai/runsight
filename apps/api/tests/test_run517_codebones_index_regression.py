"""
Red tests for RUN-517: adopt the fixed code indexer flow and verify stale-index cleanup.

This ticket stays intentionally narrow:
- prove a local reindex drops symbols for deleted files
- guard against stale rows surfacing in empty-query search results
- require contributor-facing docs for a verified codebones install/upgrade flow
- require explicit cache lifecycle guidance for rebuilding or invalidating local indexes
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
README = REPO_ROOT / "README.md"
TOOLS_README = REPO_ROOT / "tools" / "README.md"
DOC_PATHS = (README, TOOLS_README)


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)


def _codebones_executable() -> str:
    executable = shutil.which("codebones")
    assert executable, (
        "codebones CLI must be available for RUN-517 regression coverage. "
        "Run `uv sync --dev` from the repo root so the managed dev dependency is on PATH."
    )
    return executable


def _codebones_index(cwd: Path) -> None:
    result = _run([_codebones_executable(), "index", "."], cwd=cwd)
    assert result.returncode == 0, (
        f"codebones index . failed unexpectedly\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _codebones_search(cwd: Path, query: str) -> list[str]:
    result = _run([_codebones_executable(), "search", query], cwd=cwd)
    assert result.returncode == 0, (
        f"codebones search {query!r} failed unexpectedly\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def _seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_result = _run(["git", "init", "-q"], cwd=repo)
    assert init_result.returncode == 0, init_result.stderr

    (repo / "alpha.py").write_text(
        "def alpha_symbol():\n    return 1\n",
        encoding="utf-8",
    )
    return repo


def _exercise_deleted_file_reindex(tmp_path: Path) -> tuple[list[str], list[str], list[str]]:
    repo = _seed_repo(tmp_path)

    _codebones_index(repo)
    initial_hits = _codebones_search(repo, "alpha_symbol")
    assert any("alpha_symbol" in line and "alpha.py" in line for line in initial_hits), (
        "sanity check failed: initial index did not include alpha_symbol from alpha.py"
    )

    (repo / "alpha.py").unlink()

    _codebones_index(repo)
    named_hits_after_delete = _codebones_search(repo, "alpha_symbol")
    empty_hits_after_delete = _codebones_search(repo, "")
    return initial_hits, named_hits_after_delete, empty_hits_after_delete


def _combined_doc_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in DOC_PATHS)


class TestCodebonesDeletedFileRegression:
    """Deleted files must disappear from local codebones results after reindex."""

    def test_reindex_removes_deleted_symbol_from_named_search(self, tmp_path: Path):
        _, named_hits_after_delete, _ = _exercise_deleted_file_reindex(tmp_path)

        assert all("alpha_symbol" not in line for line in named_hits_after_delete), (
            "Reindexing after deleting alpha.py should remove alpha_symbol from named search "
            f"results, but got: {named_hits_after_delete}"
        )

    def test_reindex_does_not_surface_deleted_symbol_in_empty_query_results(self, tmp_path: Path):
        _, _, empty_hits_after_delete = _exercise_deleted_file_reindex(tmp_path)

        assert all(
            "alpha_symbol" not in line and "alpha.py" not in line
            for line in empty_hits_after_delete
        ), (
            "Empty-query search should not surface stale rows for deleted alpha.py after reindex, "
            f"but got: {empty_hits_after_delete}"
        )


class TestCodebonesContributorGuidance:
    """Contributor docs must explain how to install, verify, and reset the local index."""

    def test_repo_docs_describe_verified_codebones_install_or_upgrade_flow(self):
        text = _combined_doc_text().lower()

        has_uv_install_flow = any(
            marker in text
            for marker in (
                "uv tool install",
                "uv tool upgrade",
            )
        )
        has_verification_step = any(
            marker in text
            for marker in (
                "uv tool list",
                "codebones --version",
            )
        )

        assert has_uv_install_flow and has_verification_step, (
            "Contributor docs must describe how to install or upgrade codebones via uv and how "
            "to verify the usable CLI, so local indexing uses the fixed behavior."
        )

    def test_repo_docs_explain_reindex_and_cache_reset_lifecycle(self):
        text = _combined_doc_text().lower()

        mentions_reindex = "codebones index" in text and any(
            word in text for word in ("reindex", "rebuild")
        )
        mentions_cache_artifact = "codebones.db" in text
        mentions_reset_action = any(
            word in text for word in ("delete", "remove", "rm ", "invalidate")
        )
        mentions_checkout_scope = any(word in text for word in ("worktree", "checkout", "clone"))

        assert (
            mentions_reindex
            and mentions_cache_artifact
            and mentions_reset_action
            and mentions_checkout_scope
        ), (
            "Contributor docs must explain when to rerun codebones index, which cache artifact "
            "owns the local index, how to invalidate it when old caches break, and that the "
            "guidance applies per checkout/worktree."
        )
