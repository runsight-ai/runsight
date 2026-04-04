from fastapi import APIRouter, Depends

from ...domain.errors import EvalNotFound
from ...logic.services.eval_service import EvalService
from ..deps import get_eval_service
from ..schemas.eval import RunEvalResponse, SoulEvalHistoryResponse

router = APIRouter(tags=["eval"])


@router.get("/runs/{run_id}/eval", response_model=RunEvalResponse)
def get_run_eval(run_id: str, eval_service: EvalService = Depends(get_eval_service)):
    result = eval_service.get_run_eval(run_id)
    if result is None:
        raise EvalNotFound(f"Run {run_id} not found")
    return result


@router.get("/souls/{soul_id}/eval/history", response_model=SoulEvalHistoryResponse)
def get_soul_eval_history(soul_id: str, eval_service: EvalService = Depends(get_eval_service)):
    return eval_service.get_soul_eval_history(soul_id)
