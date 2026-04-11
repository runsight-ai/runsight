"""RUN-814 E2E coverage for the RUN-391 isolation boundary.

These tests intentionally use the real SubprocessHarness/worker/IPCServer path
with engine-side fake handlers so they do not call external LLM providers.
"""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from runsight_core.assertions.base import AssertionContext
from runsight_core.assertions.registry import run_assertions
from runsight_core.blocks.dispatch import DispatchBlock, DispatchBranch
from runsight_core.blocks.linear import LinearBlock
from runsight_core.budget_enforcement import BudgetKilledException, BudgetSession, _active_budget
from runsight_core.isolation import (
    ContextEnvelope,
    GrantToken,
    IPCClient,
    IPCServer,
    IsolatedBlockWrapper,
    SoulEnvelope,
    SubprocessHarness,
    TaskEnvelope,
)
from runsight_core.isolation import interceptors as interceptors_module
from runsight_core.primitives import Soul, Task
from runsight_core.state import WorkflowState
from runsight_core.tools import ToolInstance
from runsight_core.yaml.schema import BlockLimitsDef


def _soul(
    soul_id: str = "soul-e2e",
    *,
    role: str = "Tester",
    system_prompt: str = "You are an E2E test soul.",
    required_tool_calls: list[str] | None = None,
    max_tool_iterations: int = 3,
) -> Soul:
    return Soul(
        id=soul_id,
        role=role,
        system_prompt=system_prompt,
        model_name="gpt-4o-mini",
        provider="openai",
        temperature=0.0,
        required_tool_calls=required_tool_calls or [],
        max_tool_iterations=max_tool_iterations,
    )


def _soul_payload(soul: Soul) -> dict[str, Any]:
    return {
        "id": soul.id,
        "role": soul.role,
        "system_prompt": soul.system_prompt,
        "model_name": soul.model_name,
        "provider": soul.provider,
        "temperature": soul.temperature,
        "max_tool_iterations": soul.max_tool_iterations,
    }


def _soul_envelope(soul: Soul | None = None) -> SoulEnvelope:
    soul = soul or _soul()
    return SoulEnvelope(
        id=soul.id,
        role=soul.role,
        system_prompt=soul.system_prompt,
        model_name=soul.model_name or "gpt-4o-mini",
        provider=soul.provider or "openai",
        temperature=soul.temperature,
        required_tool_calls=list(soul.required_tool_calls or []),
        max_tool_iterations=soul.max_tool_iterations,
    )


def _context_envelope(
    *,
    block_id: str,
    block_type: str,
    block_config: dict[str, Any] | None = None,
    soul: Soul | None = None,
    scoped_results: dict[str, Any] | None = None,
    task_instruction: str = "Execute the isolated block.",
    task_context: dict[str, Any] | None = None,
) -> ContextEnvelope:
    return ContextEnvelope(
        block_id=block_id,
        block_type=block_type,
        block_config=block_config or {},
        soul=_soul_envelope(soul),
        tools=[],
        task=TaskEnvelope(
            id=f"task-{block_id}",
            instruction=task_instruction,
            context=task_context or {},
        ),
        scoped_results=scoped_results or {},
        scoped_shared_memory={},
        conversation_history=[],
        timeout_seconds=30,
        max_output_bytes=1_000_000,
    )


def _patch_llm_stream(
    monkeypatch: pytest.MonkeyPatch,
    responder: Callable[[dict[str, Any], int], dict[str, Any] | list[dict[str, Any]]],
) -> dict[str, Any]:
    import runsight_core.isolation.handlers as handlers_module

    captured: dict[str, Any] = {"api_keys": None, "payloads": []}

    def fake_make_llm_call_handler(api_keys: dict[str, str]):
        captured["api_keys"] = dict(api_keys)

        def _handler(payload: dict[str, Any]):
            captured["payloads"].append(payload)
            call_number = len(captured["payloads"])
            response = responder(payload, call_number)
            chunks = response if isinstance(response, list) else [response]

            async def _stream():
                for chunk in chunks:
                    yield chunk

            return _stream()

        return _handler

    monkeypatch.setattr(
        handlers_module,
        "make_llm_call_handler",
        fake_make_llm_call_handler,
    )
    return captured


async def _raw_capability(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    grant_token: str,
    supported_actions: list[str],
    request_id: str = "cap-run814",
) -> dict[str, Any]:
    writer.write(
        (
            json.dumps(
                {
                    "id": request_id,
                    "action": "capability_negotiation",
                    "grant_token": grant_token,
                    "supported_actions": supported_actions,
                    "worker_version": "worker-run814",
                },
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
    )
    await writer.drain()
    return json.loads(await reader.readline())


async def _raw_request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    action: str,
    payload: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    writer.write(
        (
            json.dumps(
                {"id": request_id, "action": action, "payload": payload},
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
    )
    await writer.drain()
    return json.loads(await reader.readline())


async def _start_ipc_server(
    tmp_path: Path,
    *,
    handlers: dict[str, Any],
    registry: Any | None = None,
    block_id: str = "run814",
) -> tuple[IPCServer, asyncio.Task[None], socket.socket, Path, GrantToken]:
    sock_path = tmp_path / f"{block_id}.sock"
    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(str(sock_path))
    server_sock.listen(1)
    grant_token = GrantToken(block_id=block_id)
    server = IPCServer(
        sock=server_sock,
        handlers=handlers,
        registry=registry,
        grant_token=grant_token,
    )
    server_task = asyncio.create_task(server.serve())
    return server, server_task, server_sock, sock_path, grant_token


async def _stop_ipc_server(
    server: IPCServer,
    server_task: asyncio.Task[None],
    server_sock: socket.socket,
    sock_path: Path,
) -> None:
    await server.shutdown()
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    server_sock.close()
    sock_path.unlink(missing_ok=True)


class TestRUN814BlockTypeE2E:
    @pytest.mark.asyncio
    async def test_linear_wrapper_real_subprocess_routes_llm_and_reconciles_budget(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        captured = _patch_llm_stream(
            monkeypatch,
            lambda _payload, _call_number: {
                "content": "linear subprocess output",
                "cost_usd": 0.03,
                "prompt_tokens": 4,
                "completion_tokens": 8,
                "total_tokens": 12,
                "tool_calls": [],
                "finish_reason": "stop",
            },
        )
        workflow_budget = BudgetSession(
            scope_name="workflow:run814-linear",
            cost_cap_usd=1.0,
            token_cap=1000,
            on_exceed="fail",
        )
        token = _active_budget.set(workflow_budget)

        soul = _soul("linear-soul")
        inner = LinearBlock("run814-linear", soul, MagicMock())
        inner.limits = BlockLimitsDef(cost_cap_usd=1.0, token_cap=100)
        harness = SubprocessHarness(api_keys={"openai": "sk-test-openai"})
        wrapper = IsolatedBlockWrapper("run814-linear", inner, harness=harness)
        state = WorkflowState(
            current_task=Task(
                id="task-linear",
                instruction="Write the isolated answer.",
                context="topic: budget",
            )
        )

        try:
            next_state = await wrapper.execute(state)
        finally:
            _active_budget.reset(token)

        assert captured["api_keys"] == {"openai": "sk-test-openai"}
        assert captured["payloads"][0]["model"] == "gpt-4o-mini"
        assert next_state.results["run814-linear"].output == "linear subprocess output"
        assert next_state.results["run814-linear"].exit_handle == "done"
        assert next_state.total_cost_usd == pytest.approx(0.03)
        assert next_state.total_tokens == 12
        assert workflow_budget.cost_usd == pytest.approx(0.03)
        assert workflow_budget.tokens == 12
        assert harness._grant_token is not None
        assert harness._grant_token.consumed is True

    @pytest.mark.asyncio
    async def test_gate_worker_builds_from_eval_key_and_returns_pass_exit(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _patch_llm_stream(
            monkeypatch,
            lambda _payload, _call_number: {
                "content": "PASS",
                "cost_usd": 0.01,
                "total_tokens": 5,
                "tool_calls": [],
            },
        )
        harness = SubprocessHarness(api_keys={"openai": "sk-test-openai"})
        envelope = _context_envelope(
            block_id="run814-gate",
            block_type="gate",
            block_config={
                "eval_key": "draft",
                "extract_field": "answer",
                "gate_soul": _soul_payload(_soul("gate-soul", role="Gate")),
            },
            scoped_results={
                "draft": {
                    "output": json.dumps([{"answer": "ship this answer"}]),
                    "exit_handle": "done",
                }
            },
        )

        result = await harness.run(envelope)

        assert result.error is None
        assert result.output == "ship this answer"
        assert result.exit_handle == "pass"
        assert result.cost_usd == pytest.approx(0.01)
        assert result.total_tokens == 5

    @pytest.mark.asyncio
    async def test_synthesize_worker_builds_from_two_inputs_and_returns_output(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        captured = _patch_llm_stream(
            monkeypatch,
            lambda payload, _call_number: {
                "content": "synthesized alpha and beta",
                "cost_usd": 0.02,
                "total_tokens": 9,
                "tool_calls": [],
                "seen_prompt": payload["messages"][-1]["content"],
            },
        )
        harness = SubprocessHarness(api_keys={"openai": "sk-test-openai"})
        synth_soul = _soul("synth-soul", role="Synthesizer")
        envelope = _context_envelope(
            block_id="run814-synth",
            block_type="synthesize",
            block_config={
                "input_block_ids": ["alpha", "beta"],
                "synthesizer_soul": _soul_payload(synth_soul),
            },
            soul=synth_soul,
            scoped_results={
                "alpha": {"output": "alpha output", "exit_handle": "done"},
                "beta": {"output": "beta output", "exit_handle": "done"},
            },
        )

        result = await harness.run(envelope)

        assert result.error is None
        assert result.output == "synthesized alpha and beta"
        assert result.exit_handle == "done"
        assert "alpha output" in captured["payloads"][0]["messages"][-1]["content"]
        assert "beta output" in captured["payloads"][0]["messages"][-1]["content"]

    @pytest.mark.asyncio
    async def test_dispatch_wrapper_real_subprocess_returns_three_per_exit_results(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        def dispatch_response(payload: dict[str, Any], _call_number: int) -> dict[str, Any]:
            prompt = payload["messages"][-1]["content"]
            if "North branch task" in prompt:
                content = "north result"
            elif "South branch task" in prompt:
                content = "south result"
            elif "West branch task" in prompt:
                content = "west result"
            else:
                content = f"unexpected prompt: {prompt}"
            return {
                "content": content,
                "cost_usd": 0.01,
                "total_tokens": 4,
                "tool_calls": [],
            }

        _patch_llm_stream(monkeypatch, dispatch_response)
        branches = [
            DispatchBranch("north", "North", _soul("north-soul"), "North branch task"),
            DispatchBranch("south", "South", _soul("south-soul"), "South branch task"),
            DispatchBranch("west", "West", _soul("west-soul"), "West branch task"),
        ]
        inner = DispatchBlock("run814-dispatch", branches, MagicMock())
        harness = SubprocessHarness(api_keys={"openai": "sk-test-openai"})
        wrapper = IsolatedBlockWrapper("run814-dispatch", inner, harness=harness)
        state = WorkflowState(
            current_task=Task(
                id="task-dispatch",
                instruction="Fan out.",
                context="subject: directions",
            )
        )

        next_state = await wrapper.execute(state)

        assert next_state.results["run814-dispatch.north"].output == "north result"
        assert next_state.results["run814-dispatch.north"].exit_handle == "north"
        assert next_state.results["run814-dispatch.south"].output == "south result"
        assert next_state.results["run814-dispatch.south"].exit_handle == "south"
        assert next_state.results["run814-dispatch.west"].output == "west result"
        assert next_state.results["run814-dispatch.west"].exit_handle == "west"


class TestRUN814SmartAssertionAndToolsE2E:
    @pytest.mark.asyncio
    async def test_llm_judge_assertion_runs_through_harness_and_tracks_assertion_cost(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _patch_llm_stream(
            monkeypatch,
            lambda _payload, _call_number: {
                "content": json.dumps(
                    {
                        "passed": True,
                        "score": 0.91,
                        "reason": "judge accepted via IPC",
                        "named_scores": {"factuality": 0.91},
                        "assertion_type": "llm_judge",
                        "metadata": {"path": "subprocess"},
                    }
                ),
                "cost_usd": 0.04,
                "prompt_tokens": 10,
                "completion_tokens": 11,
                "total_tokens": 21,
                "tool_calls": [],
            },
        )
        budget = BudgetSession(
            scope_name="workflow:run814-assertion",
            cost_cap_usd=1.0,
            token_cap=1000,
            on_exceed="fail",
        )
        token = _active_budget.set(budget)
        context = AssertionContext(
            output="Candidate answer",
            prompt="Grade candidate answer",
            prompt_hash="hash-run814",
            soul_id="answerer",
            soul_version="v1",
            block_id="assert-run814",
            block_type="linear",
            cost_usd=0.0,
            total_tokens=0,
            latency_ms=0.0,
            variables={},
            run_id="run814",
            workflow_id="wf-run814",
        )

        try:
            result = await run_assertions(
                [
                    {
                        "type": "llm_judge",
                        "config": {
                            "rubric": "Score factuality.",
                            "judge_soul": {
                                "id": "judge-run814",
                                "role": "Judge",
                                "system_prompt": "Return JSON grading only.",
                                "model_name": "gpt-4o-mini",
                                "provider": "openai",
                            },
                        },
                    }
                ],
                output="Candidate answer",
                context=context,
                api_keys={"openai": "sk-test-openai"},
            )
        finally:
            _active_budget.reset(token)

        assert len(result.results) == 1
        grading = result.results[0]
        assert grading.passed is True
        assert grading.score == pytest.approx(0.91)
        assert grading.reason == "judge accepted via IPC"
        assert grading.named_scores["factuality"] == pytest.approx(0.91)
        assert grading.metadata["path"] == "subprocess"
        assert budget.cost_usd == pytest.approx(0.04)
        assert budget.tokens == 21

    @pytest.mark.asyncio
    async def test_subprocess_tool_call_uses_engine_side_resolved_tool(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        tool_calls_seen: list[dict[str, Any]] = []

        async def echo_tool(args: dict[str, Any]) -> str:
            tool_calls_seen.append(dict(args))
            return f"engine-tool:{args['value']}"

        first_tool_call = {
            "id": "call-echo-1",
            "type": "function",
            "function": {
                "name": "echo_tool",
                "arguments": json.dumps({"value": "from subprocess"}),
            },
        }

        def tool_loop_response(payload: dict[str, Any], call_number: int) -> dict[str, Any]:
            if call_number == 1:
                return {
                    "content": "",
                    "cost_usd": 0.01,
                    "total_tokens": 6,
                    "tool_calls": [first_tool_call],
                    "raw_message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [first_tool_call],
                    },
                }
            assert any(
                message.get("role") == "tool"
                and message.get("content") == "engine-tool:from subprocess"
                for message in payload["messages"]
            )
            return {
                "content": "final after engine tool",
                "cost_usd": 0.02,
                "total_tokens": 8,
                "tool_calls": [],
            }

        _patch_llm_stream(monkeypatch, tool_loop_response)
        soul = _soul(
            "tool-soul",
            required_tool_calls=["echo_tool"],
            max_tool_iterations=3,
        )
        soul.resolved_tools = [
            ToolInstance(
                name="echo_tool",
                description="Echo through the engine",
                parameters={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
                execute=echo_tool,
            )
        ]
        inner = LinearBlock("run814-tool", soul, MagicMock())
        harness = SubprocessHarness(api_keys={"openai": "sk-test-openai"})
        wrapper = IsolatedBlockWrapper("run814-tool", inner, harness=harness)
        state = WorkflowState(current_task=Task(id="task-tool", instruction="Use echo_tool once."))

        next_state = await wrapper.execute(state)

        assert tool_calls_seen == [{"value": "from subprocess"}]
        assert next_state.results["run814-tool"].output == "final after engine tool"
        assert next_state.total_cost_usd == pytest.approx(0.03)
        assert next_state.total_tokens == 14


class TestRUN814BudgetAndAdversarialE2E:
    @pytest.mark.asyncio
    async def test_tight_cap_returns_paid_response_then_kills_next_llm_before_handler(
        self,
        tmp_path: Path,
    ):
        registry = interceptors_module.InterceptorRegistry()
        session = BudgetSession(
            scope_name="block:run814-budget",
            cost_cap_usd=0.01,
            token_cap=100,
            on_exceed="fail",
        )
        registry.register(
            interceptors_module.BudgetInterceptor(session=session, block_id="run814-budget")
        )
        handler_calls: list[dict[str, Any]] = []

        async def llm_handler(payload: dict[str, Any]) -> dict[str, Any]:
            handler_calls.append(payload)
            return {
                "content": f"paid response {len(handler_calls)}",
                "cost_usd": 0.02,
                "total_tokens": 5,
            }

        server, server_task, server_sock, sock_path, grant_token = await _start_ipc_server(
            tmp_path,
            handlers={"llm_call": llm_handler},
            registry=registry,
            block_id="run814-budget",
        )
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.open_unix_connection(str(sock_path))
            capability = await _raw_capability(
                reader,
                writer,
                grant_token=grant_token.token,
                supported_actions=["llm_call"],
            )
            assert capability["accepted"] is True

            first = await _raw_request(
                reader,
                writer,
                action="llm_call",
                payload={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "1"}]},
                request_id="run814-budget-1",
            )
            second = await _raw_request(
                reader,
                writer,
                action="llm_call",
                payload={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "2"}]},
                request_id="run814-budget-2",
            )

            assert first["error"] is None
            assert first["payload"]["content"] == "paid response 1"
            assert first["engine_context"]["budget_remaining_usd"] == pytest.approx(-0.01)
            assert second["payload"]["error_type"] == "BudgetKilledException"
            assert second["payload"]["block_id"] == "run814-budget"
            assert second["payload"]["actual_value"] == pytest.approx(0.02)
            assert "budget" in (second["error"] or "").lower()
            assert len(handler_calls) == 1
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()
            await _stop_ipc_server(server, server_task, server_sock, sock_path)

    @pytest.mark.asyncio
    async def test_consumed_grant_token_replay_from_malicious_subprocess_is_rejected(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        async def llm_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"content": "ok", "cost_usd": 0.0, "total_tokens": 0}

        server, server_task, server_sock, sock_path, grant_token = await _start_ipc_server(
            tmp_path,
            handlers={"llm_call": llm_handler},
            block_id="run814-grant-replay",
        )
        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", grant_token.token)
        client = IPCClient(socket_path=str(sock_path))
        try:
            capability = await client.connect()
            assert capability.accepted is True

            replay_reader, replay_writer = await asyncio.open_unix_connection(str(sock_path))
            try:
                replay = await _raw_capability(
                    replay_reader,
                    replay_writer,
                    grant_token=grant_token.token,
                    supported_actions=["llm_call"],
                    request_id="cap-run814-replay",
                )
            finally:
                replay_writer.close()
                await replay_writer.wait_closed()

            assert replay["accepted"] is False
            assert "rejected" in (replay["error"] or "").lower()
        finally:
            await client.close()
            await _stop_ipc_server(server, server_task, server_sock, sock_path)

    @pytest.mark.asyncio
    async def test_malicious_subprocess_many_llm_calls_is_killed_after_budget_exceeded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        registry = interceptors_module.InterceptorRegistry()
        session = BudgetSession(
            scope_name="block:run814-many-calls",
            cost_cap_usd=0.01,
            token_cap=100,
            on_exceed="fail",
        )
        registry.register(
            interceptors_module.BudgetInterceptor(session=session, block_id="run814-many-calls")
        )
        handler_calls = 0

        async def llm_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            nonlocal handler_calls
            handler_calls += 1
            return {
                "content": f"call {handler_calls}",
                "cost_usd": 0.006,
                "total_tokens": 3,
            }

        server, server_task, server_sock, sock_path, grant_token = await _start_ipc_server(
            tmp_path,
            handlers={"llm_call": llm_handler},
            registry=registry,
            block_id="run814-many-calls",
        )
        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", grant_token.token)
        client = IPCClient(socket_path=str(sock_path))
        try:
            capability = await client.connect()
            assert capability.accepted is True

            first = await client.request(
                "llm_call",
                {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "1"}]},
            )
            second = await client.request(
                "llm_call",
                {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "2"}]},
            )
            with pytest.raises(BudgetKilledException) as exc_info:
                await client.request(
                    "llm_call",
                    {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "3"}]},
                )

            assert first["content"] == "call 1"
            assert second["content"] == "call 2"
            assert exc_info.value.limit_kind == "cost_usd"
            assert exc_info.value.actual_value == pytest.approx(0.012)
            assert handler_calls == 2
        finally:
            await client.close()
            await _stop_ipc_server(server, server_task, server_sock, sock_path)

    @pytest.mark.asyncio
    async def test_ipc_server_rejects_request_action_not_in_negotiated_active_actions(
        self,
        tmp_path: Path,
    ):
        async def llm_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"content": "llm ok"}

        async def tool_handler(_payload: dict[str, Any]) -> dict[str, Any]:
            return {"output": "tool should not run"}

        server, server_task, server_sock, sock_path, grant_token = await _start_ipc_server(
            tmp_path,
            handlers={"llm_call": llm_handler, "tool_call": tool_handler},
            block_id="run814-negotiated-actions",
        )
        reader: asyncio.StreamReader | None = None
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.open_unix_connection(str(sock_path))
            capability = await _raw_capability(
                reader,
                writer,
                grant_token=grant_token.token,
                supported_actions=["llm_call"],
            )
            assert capability["accepted"] is True
            assert capability["active_actions"] == ["llm_call"]

            response = await _raw_request(
                reader,
                writer,
                action="tool_call",
                payload={"name": "echo_tool", "arguments": {}},
                request_id="run814-unnegotiated-tool",
            )

            assert response["payload"] is None
            assert response["error"] is not None
            assert "negotiated" in response["error"].lower()
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()
            await _stop_ipc_server(server, server_task, server_sock, sock_path)
