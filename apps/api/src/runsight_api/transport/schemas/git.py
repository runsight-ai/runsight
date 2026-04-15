"""Request and response schemas for the git API (RUN-859)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, field_validator


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


class FileReadResponse(BaseModel):
    content: str
    ref: str
