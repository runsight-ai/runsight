from fastapi import APIRouter, Depends, HTTPException
from ..schemas.git import GitStatusResponse, GitDiffResponse, GitLogResponse, CommitRequest
from ..deps import get_git_service
from ...logic.services.git_service import GitService

router = APIRouter(prefix="/git", tags=["Git"])


@router.get("/status", response_model=GitStatusResponse)
async def get_status(service: GitService = Depends(get_git_service)):
    try:
        return service.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diff", response_model=GitDiffResponse)
async def get_diff(service: GitService = Depends(get_git_service)):
    try:
        return {"diff": service.get_diff()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/log", response_model=GitLogResponse)
async def get_log(limit: int = 10, service: GitService = Depends(get_git_service)):
    try:
        logs = service.get_log(limit)
        return {"items": logs, "total": len(logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/commit")
async def commit(body: CommitRequest, service: GitService = Depends(get_git_service)):
    try:
        return service.commit(body.message, body.files)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
