"""Git operations router: status, commit, diff, log."""

import re
import subprocess
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from ...core.config import settings
from ...domain.errors import GitError, InputValidationError
from ...logic.services.git_service import GitService

router = APIRouter(prefix="/git", tags=["Git"])


# ---------------------------------------------------------------------------
# GitService instance (scoped to project base_path)
# ---------------------------------------------------------------------------

# GitService shells out via ["git", ...] with shell=False.


def _get_git_service() -> GitService:
    return GitService(repo_path=settings.base_path)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SimBranchRequest(BaseModel):
    workflow_id: str
    yaml_content: str


class SimBranchResponse(BaseModel):
    branch: str
    commit_sha: str


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


def _ensure_git_repo() -> None:
    """Raise GitError if base_path is not inside a git repo."""
    svc = _get_git_service()
    try:
        svc._run("rev-parse", "--is-inside-work-tree")
    except subprocess.CalledProcessError:
        raise GitError("Not a git repository")


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
    """Validate a file path is safe to pass to git commands."""
    if not file_path:
        raise InputValidationError("Invalid path: empty file path")

    if file_path.startswith("-"):
        raise InputValidationError("Invalid path: path must not start with '-'")

    decoded = unquote(file_path)

    if ".." in decoded:
        raise InputValidationError("Invalid path: path traversal not allowed")

    base = Path(settings.base_path).resolve()
    if decoded.startswith("/"):
        resolved = Path(decoded).resolve()
        if not str(resolved).startswith(str(base)):
            raise InputValidationError("Invalid path: absolute path outside project root")

    resolved = (base / decoded).resolve()
    if not str(resolved).startswith(str(base)):
        raise InputValidationError("Invalid path: path escapes project root")

    candidate = base / decoded
    if candidate.is_symlink():
        real = candidate.resolve()
        if not str(real).startswith(str(base)):
            raise InputValidationError(
                "Invalid path: symlink target outside project root",
            )


def _sanitize_commit_message(message: str) -> str:
    """Sanitize a commit message for safe use with git."""
    message = re.sub(r"[\x00-\x1f\x7f]", "", message)
    message = re.sub(r"\$\([^)]*\)", "", message)
    message = message.replace("`", "")
    return message.strip()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=StatusResponse)
async def git_status():
    _ensure_git_repo()
    svc = _get_git_service()

    branch = svc.current_branch() or "HEAD"

    porcelain = svc._run("status", "--porcelain", "-u", check=False)
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
    svc = _get_git_service()

    safe_message = _sanitize_commit_message(body.message)
    if not safe_message:
        raise GitError("Commit message is empty after sanitization")

    try:
        if body.files:
            for f in body.files:
                _validate_file_path(f)
            svc._run("add", "--", *body.files)
        else:
            svc._run("add", ".")
    except subprocess.CalledProcessError as exc:
        detail = _scrub_base_path(exc.stderr.strip()) or "Git add failed"
        raise GitError(detail)

    result = svc._run("commit", "-m", safe_message, check=False)
    if result.returncode != 0:
        detail = _scrub_base_path(result.stderr.strip()) or "Commit failed"
        raise GitError(detail)

    head_result = svc._run("rev-parse", "HEAD")
    commit_hash = head_result.stdout.strip()

    return CommitResponse(hash=commit_hash, message=safe_message)


@router.get("/diff", response_model=DiffResponse)
async def git_diff():
    _ensure_git_repo()
    svc = _get_git_service()

    result = svc._run("diff", "HEAD", check=False)
    return DiffResponse(diff=result.stdout)


@router.get("/log", response_model=LogResponse)
async def git_log():
    _ensure_git_repo()
    svc = _get_git_service()

    sep = "<SEP>"
    fmt = f"%H{sep}%s{sep}%ai{sep}%an"
    result = svc._run("log", "--max-count=50", f"--format={fmt}", check=False)

    if result.returncode != 0:
        raise GitError(result.stderr.strip() or "Git log failed")

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


@router.post("/sim-branch", response_model=SimBranchResponse)
async def create_sim_branch(body: SimBranchRequest):
    _ensure_git_repo()
    git = _get_git_service()
    yaml_path = f"custom/workflows/{body.workflow_id}.yaml"
    result = git.create_sim_branch(body.workflow_id, body.yaml_content, yaml_path)
    return SimBranchResponse(branch=result.branch, commit_sha=result.sha)
