"""Shared helpers for the ISO-002 IPC protocol test suites."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any


async def _send_raw_request_and_collect_frames(
    socket_path: Path,
    request: dict[str, Any],
    *,
    max_frames: int = 10,
) -> list[dict[str, Any]]:
    """Send one NDJSON request and collect response frames until done or timeout."""
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    try:
        line = json.dumps(request, separators=(",", ":")) + "\n"
        writer.write(line.encode())
        await writer.drain()

        frames: list[dict[str, Any]] = []
        for _ in range(max_frames):
            try:
                raw = await asyncio.wait_for(reader.readline(), timeout=0.2)
            except asyncio.TimeoutError:
                break
            if not raw:
                break
            frames.append(json.loads(raw))
            if frames[-1].get("done") is True:
                break
        return frames
    finally:
        writer.close()
        await writer.wait_closed()


def _make_grant_token(*, block_id: str = "test-block"):
    from runsight_core.isolation.ipc_models import GrantToken

    return GrantToken(block_id=block_id)


def _make_budget_interceptor(interceptors_module, *, session, block_id: str = "block-810"):
    BudgetInterceptor = getattr(interceptors_module, "BudgetInterceptor", None)
    assert BudgetInterceptor is not None

    constructor_candidates: list[dict[str, Any]] = [
        {"session": session, "block_id": block_id},
        {"budget_session": session, "block_id": block_id},
        {"session": session},
        {"budget_session": session},
    ]

    for kwargs in constructor_candidates:
        try:
            return BudgetInterceptor(**kwargs)
        except TypeError:
            continue

    for args in [
        (session, block_id),
        (session,),
    ]:
        try:
            return BudgetInterceptor(*args)
        except TypeError:
            continue

    raise AssertionError(
        "BudgetInterceptor must be constructible with a BudgetSession (and optional block_id)"
    )


def _make_observer_interceptor(interceptors_module, **kwargs: Any):
    ObserverInterceptor = getattr(interceptors_module, "ObserverInterceptor", None)
    assert ObserverInterceptor is not None

    constructor_candidates: list[dict[str, Any]] = [dict(kwargs), {}]
    if "tracer" in kwargs:
        constructor_candidates.append({"tracer": kwargs["tracer"]})
    if "block_id" in kwargs:
        constructor_candidates.append({"block_id": kwargs["block_id"]})

    for constructor_kwargs in constructor_candidates:
        try:
            return ObserverInterceptor(**constructor_kwargs)
        except TypeError:
            continue

    if "tracer" in kwargs:
        for args in [(kwargs["tracer"],), ()]:
            try:
                return ObserverInterceptor(*args)
            except TypeError:
                continue

    raise AssertionError(
        "ObserverInterceptor must be constructible (with optional tracer/block_id)"
    )


def _capability_response_for(
    capability_request: dict[str, Any],
    *,
    accepted: bool = True,
    active_actions: list[str] | None = None,
    error: str | None = None,
    engine_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": capability_request.get("id", ""),
        "done": True,
        "accepted": accepted,
        "active_actions": active_actions or [],
        "engine_context": engine_context
        or {
            "budget_remaining_usd": 50.0,
            "trace_id": f"trace-{uuid.uuid4().hex}",
            "run_id": f"run-{uuid.uuid4().hex}",
            "block_id": "test-block",
        },
        "error": error,
    }


def _configure_client_for_handshake(
    client,
    grant_token,
    *,
    supported_actions: list[str] | None = None,
    worker_version: str = "worker-396-test",
) -> None:
    token_value = grant_token.token if hasattr(grant_token, "token") else str(grant_token)
    if hasattr(client, "_grant_token"):
        client._grant_token = token_value
    if supported_actions is not None and hasattr(client, "_supported_actions"):
        client._supported_actions = list(supported_actions)
    if hasattr(client, "_worker_version"):
        client._worker_version = worker_version


async def _connect_client_with_grant_token(
    client,
    grant_token,
    *,
    supported_actions: list[str] | None = None,
    worker_version: str = "worker-396-test",
) -> Any:
    _configure_client_for_handshake(
        client,
        grant_token,
        supported_actions=supported_actions,
        worker_version=worker_version,
    )
    capability_response = await client.connect()
    accepted = (
        capability_response.accepted
        if hasattr(capability_response, "accepted")
        else capability_response.get("accepted")
    )
    assert accepted is True
    return capability_response


async def _raw_authenticate_with_grant_token(socket_path: Path, grant_token) -> dict[str, Any]:
    frames = await _send_raw_request_and_collect_frames(
        socket_path,
        {
            "id": "req-auth-1",
            "action": "capability_negotiation",
            "grant_token": grant_token.token,
            "supported_actions": ["http", "tool_call", "delegate", "file_io", "write_artifact"],
            "worker_version": "worker-396-test",
        },
    )
    assert len(frames) == 1
    assert frames[0]["done"] is True
    assert frames[0]["accepted"] is True
    assert frames[0]["active_actions"] is not None
    assert frames[0]["error"] is None
    return frames[0]


async def _send_raw_authenticated_request_and_collect_frames(
    socket_path: Path,
    grant_token,
    request: dict[str, Any],
    *,
    max_frames: int = 10,
) -> list[dict[str, Any]]:
    """Authenticate and send one NDJSON request on the same connection."""
    reader, writer = await asyncio.open_unix_connection(str(socket_path))
    try:
        auth_line = (
            json.dumps(
                {
                    "id": "req-auth-1",
                    "action": "capability_negotiation",
                    "grant_token": grant_token.token,
                    "supported_actions": [
                        "http",
                        "tool_call",
                        "delegate",
                        "file_io",
                        "llm_call",
                        "write_artifact",
                        "simple",
                        "stream",
                    ],
                    "worker_version": "worker-396-test",
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        writer.write(auth_line.encode())
        await writer.drain()

        auth_raw = await asyncio.wait_for(reader.readline(), timeout=0.2)
        assert auth_raw
        auth_frame = json.loads(auth_raw)
        assert auth_frame["done"] is True
        assert auth_frame["accepted"] is True
        assert auth_frame["error"] is None

        line = json.dumps(request, separators=(",", ":")) + "\n"
        writer.write(line.encode())
        await writer.drain()

        frames: list[dict[str, Any]] = []
        for _ in range(max_frames):
            try:
                raw = await asyncio.wait_for(reader.readline(), timeout=0.2)
            except asyncio.TimeoutError:
                break
            if not raw:
                break
            frames.append(json.loads(raw))
            if frames[-1].get("done") is True:
                break
        return frames
    finally:
        writer.close()
        await writer.wait_closed()
