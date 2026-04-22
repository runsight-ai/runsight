"""SSE streaming endpoint for real-time run execution events."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ...domain.errors import RunNotFound, ServiceUnavailable
from ...domain.events import SSE_TERMINAL_EVENTS
from ...logic.services.execution_service import ExecutionService
from ...logic.services.run_service import RunService
from ..context_audit import parse_context_audit_message
from ..deps import get_execution_service, get_run_service

router = APIRouter(prefix="/runs", tags=["SSE Stream"])
logger = logging.getLogger(__name__)


def _log_timestamp_value(log) -> float | None:
    timestamp = getattr(log, "timestamp", None)
    return float(timestamp) if isinstance(timestamp, int | float) else None


def _replay_payload(log) -> dict:
    try:
        data = json.loads(log.message)
        if not isinstance(data, dict):
            data = {"message": log.message}
    except (json.JSONDecodeError, TypeError):
        data = {"message": log.message}

    log_id = getattr(log, "id", None)
    if isinstance(log_id, int) and "id" not in data:
        data["id"] = log_id

    timestamp = _log_timestamp_value(log)
    if timestamp is not None and "timestamp" not in data:
        data["timestamp"] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    level = getattr(log, "level", None)
    if isinstance(level, str) and "level" not in data and "event" not in data:
        data["level"] = level

    return data


@router.get("/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    execution_service: Optional[ExecutionService] = Depends(get_execution_service),
):
    """SSE endpoint that streams real-time execution events for a run."""
    run = run_service.get_run(run_id)
    if run is None:
        raise RunNotFound(f"Run {run_id} not found")

    if execution_service is None:
        raise ServiceUnavailable("Execution service not available")

    async def event_generator():
        try:
            logs = run_service.get_run_logs(run_id)
            for log in logs:
                try:
                    audit_event = parse_context_audit_message(log.message)
                    if audit_event is not None:
                        data = audit_event.model_dump(mode="json")
                        yield f"event:context_resolution\ndata:{json.dumps(data)}\n\n"
                        continue
                    data = _replay_payload(log)
                except Exception:
                    data = _replay_payload(log)
                yield f"event:replay\ndata:{json.dumps(data)}\n\n"
        except Exception:
            logger.warning("SSE replay failed", exc_info=True)

        async for event in execution_service.subscribe_stream(run_id):
            event_type = event["event"]
            event_data = json.dumps(event["data"])
            yield f"event:{event_type}\ndata:{event_data}\n\n"

            if event_type in SSE_TERMINAL_EVENTS:
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
