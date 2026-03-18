"""Git operations router: status, commit, diff, log."""

import subprocess
from typing import List, Optional

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

    if body.files:
        # Stage only specified files
        _run_git("add", "--", *body.files)
    else:
        # Stage all changes
        _run_git("add", ".")

    result = _run_git("commit", "-m", body.message)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr.strip() or "Commit failed")

    # Get the hash of the new commit
    hash_result = _run_git("rev-parse", "HEAD")
    commit_hash = hash_result.stdout.strip()

    return CommitResponse(hash=commit_hash, message=body.message)


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
