"""Git operations router: status, commit, diff, log."""

import re
import subprocess
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from ...core.config import settings

router = APIRouter(prefix="/git", tags=["Git"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CommitRequest(BaseModel):
    message: str
    files: Optional[List[str]] = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Commit message must not be empty")
        return v


class UncommittedFile(BaseModel):
    path: str
    status: str


class StatusResponse(BaseModel):
    branch: str
    uncommitted_files: List[UncommittedFile]
    is_clean: bool


class CommitResponse(BaseModel):
    hash: str
    message: str


class DiffResponse(BaseModel):
    diff: str


class CommitEntry(BaseModel):
    hash: str
    message: str
    date: str
    author: str


class LogResponse(BaseModel):
    commits: List[CommitEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_MAP = {
    "M": "modified",
    "A": "added",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "U": "unmerged",
    "?": "untracked",
    "!": "ignored",
}


def _run_git(*args: str) -> subprocess.CompletedProcess:
    """Run a git command in settings.base_path with shell=False."""
    result = subprocess.run(
        ["git", *args],
        cwd=settings.base_path,
        capture_output=True,
        text=True,
    )
    return result


def _ensure_git_repo() -> None:
    """Raise 400 if base_path is not inside a git repo."""
    result = _run_git("rev-parse", "--is-inside-work-tree")
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail="Not a git repository")


def _scrub_base_path(text: str) -> str:
    """Remove any occurrence of the base_path from error text."""
    base = settings.base_path
    if base:
        text = text.replace(base, "<project>")
    return text


# ---------------------------------------------------------------------------
# Security: path validation & message sanitization
# ---------------------------------------------------------------------------


def _validate_file_path(file_path: str) -> None:
    """Validate a file path is safe to pass to git commands.

    Rejects:
    - Empty paths
    - Paths starting with ``-`` (flag injection)
    - Paths containing ``..`` after URL-decoding (traversal)
    - Absolute paths outside base_path
    - Symlinks that resolve outside base_path
    """
    if not file_path:
        raise HTTPException(status_code=400, detail="Invalid path: empty file path")

    # Flag injection: paths starting with -
    if file_path.startswith("-"):
        raise HTTPException(status_code=400, detail="Invalid path: path must not start with '-'")

    # URL-decode then check for traversal
    decoded = unquote(file_path)

    # Reject .. components
    if ".." in decoded:
        raise HTTPException(status_code=400, detail="Invalid path: path traversal not allowed")

    # Reject absolute paths outside base_path
    base = Path(settings.base_path).resolve()
    if decoded.startswith("/"):
        resolved = Path(decoded).resolve()
        if not str(resolved).startswith(str(base)):
            raise HTTPException(
                status_code=400, detail="Invalid path: absolute path outside project root"
            )

    # Check resolved path stays within base_path
    resolved = (base / decoded).resolve()
    if not str(resolved).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path: path escapes project root")

    # Symlink check: if the path exists and is a symlink, verify target
    candidate = base / decoded
    if candidate.is_symlink():
        real = candidate.resolve()
        if not str(real).startswith(str(base)):
            raise HTTPException(
                status_code=400,
                detail="Invalid path: symlink target outside project root",
            )


def _sanitize_commit_message(message: str) -> str:
    """Sanitize a commit message for safe use with git.

    Strips:
    - Control characters (except space)
    - Shell substitution syntax: $(...) and backticks
    - Newlines (collapse to single line)
    """
    # Strip control characters (ASCII 0x00-0x1F except 0x20 space, plus 0x7F)
    message = re.sub(r"[\x00-\x1f\x7f]", "", message)
    # Strip $(...) sequences
    message = re.sub(r"\$\([^)]*\)", "", message)
    # Strip backticks
    message = message.replace("`", "")
    return message.strip()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=StatusResponse)
async def git_status():
    _ensure_git_repo()

    # Branch name
    branch_result = _run_git("rev-parse", "--abbrev-ref", "HEAD")
    branch = branch_result.stdout.strip() or "HEAD"

    # Uncommitted files (porcelain v1 format: XY <path>)
    porcelain = _run_git("status", "--porcelain", "-u")
    files: List[UncommittedFile] = []
    for line in porcelain.stdout.splitlines():
        if not line.strip():
            continue
        xy = line[:2].strip()
        path = line[3:].strip()
        status = _STATUS_MAP.get(xy[0] if xy else "?", xy)
        files.append(UncommittedFile(path=path, status=status))

    return StatusResponse(
        branch=branch,
        uncommitted_files=files,
        is_clean=len(files) == 0,
    )


@router.post("/commit", response_model=CommitResponse)
async def git_commit(body: CommitRequest):
    _ensure_git_repo()

    # Validate file paths
    if body.files:
        for f in body.files:
            _validate_file_path(f)
        # Stage only specified files
        _run_git("add", "--", *body.files)
    else:
        # Stage all changes
        _run_git("add", ".")

    # Sanitize commit message
    safe_message = _sanitize_commit_message(body.message)
    if not safe_message:
        raise HTTPException(status_code=400, detail="Commit message is empty after sanitization")

    result = _run_git("commit", "-m", safe_message)
    if result.returncode != 0:
        detail = _scrub_base_path(result.stderr.strip()) or "Commit failed"
        raise HTTPException(status_code=400, detail=detail)

    # Get the hash of the new commit
    hash_result = _run_git("rev-parse", "HEAD")
    commit_hash = hash_result.stdout.strip()

    return CommitResponse(hash=commit_hash, message=safe_message)


@router.get("/diff", response_model=DiffResponse)
async def git_diff():
    _ensure_git_repo()

    # Show staged + unstaged diff against HEAD
    result = _run_git("diff", "HEAD")
    return DiffResponse(diff=result.stdout)


@router.get("/log", response_model=LogResponse)
async def git_log():
    _ensure_git_repo()

    # Format: hash<SEP>message<SEP>date<SEP>author
    sep = "<SEP>"
    fmt = f"%H{sep}%s{sep}%ai{sep}%an"
    result = _run_git("log", "--max-count=50", f"--format={fmt}")

    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "Git log failed")

    commits: List[CommitEntry] = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split(sep)
        if len(parts) >= 4:
            commits.append(
                CommitEntry(
                    hash=parts[0],
                    message=parts[1],
                    date=parts[2],
                    author=parts[3],
                )
            )

    return LogResponse(commits=commits)
