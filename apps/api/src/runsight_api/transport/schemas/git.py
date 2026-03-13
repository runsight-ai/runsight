from pydantic import BaseModel
from typing import List, Optional


class GitFileStatus(BaseModel):
    path: str
    status: str


class GitStatusResponse(BaseModel):
    branch: str
    files: List[GitFileStatus]
    is_clean: bool


class GitDiffResponse(BaseModel):
    diff: str


class GitLogEntry(BaseModel):
    hash: str
    author: str
    date: str
    message: str


class GitLogResponse(BaseModel):
    items: List[GitLogEntry]
    total: int


class CommitRequest(BaseModel):
    message: str
    files: Optional[List[str]] = None
