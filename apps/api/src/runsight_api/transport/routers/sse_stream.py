"""SSE streaming endpoint for real-time run execution events."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import get_run_service, get_execution_service
from ...logic.services.run_service import RunService
from ...logic.services.execution_service import ExecutionService

router = APIRouter(prefix="/runs", tags=["SSE Stream"])


@router.get("/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    execution_service: Optional[ExecutionService] = Depends(get_execution_service),
):
    """SSE endpoint that streams real-time execution events for a run."""
    # 404 if run doesn't exist
    run = run_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if execution_service is None:
        raise HTTPException(status_code=503, detail="Execution service not available")

    async def event_generator():
        # Late-join: replay missed events from DB logs
        try:
            logs = run_service.get_run_logs(run_id)
            for log in logs:
                try:
                    data = json.loads(log.message)
                except (json.JSONDecodeError, TypeError):
                    data = {"message": log.message}
                yield f"event:replay\ndata:{json.dumps(data)}\n\n"
        except Exception:
            pass  # No logs to replay is fine

        # Stream live events
        async for event in execution_service.subscribe_stream(run_id):
            event_type = event["event"]
            event_data = json.dumps(event["data"])
            yield f"event:{event_type}\ndata:{event_data}\n\n"

            # Stop after terminal events
            if event_type in ("run_completed", "run_failed"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
