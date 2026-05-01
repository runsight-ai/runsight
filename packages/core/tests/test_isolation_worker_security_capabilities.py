"""Isolation worker security, capability, and assertion block contracts."""

from __future__ import annotations

import io
import json
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from isolation_worker_helpers import (
    make_context_envelope,
    parse_result_envelope,
    run_worker_subprocess,
    worker_socket_path,
)
from runsight_core.isolation.envelope import ResultEnvelope, ToolDefEnvelope


class TestWorkerImportBoundary:
    """Worker must not import runsight_core.workflow, observer, or api modules."""

    def test_no_workflow_import(self):
        """Worker source must not import runsight_core.workflow."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_core.workflow" not in source, (
            "Worker must not import runsight_core.workflow"
        )

    def test_no_observer_import(self):
        """Worker source must not import runsight_core.observer."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_core.observer" not in source, (
            "Worker must not import runsight_core.observer"
        )

    def test_no_api_import(self):
        """Worker source must not import runsight_api."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_api" not in source, "Worker must not import runsight_api"

    def test_no_sqlmodel_import(self):
        """Worker source must not import sqlmodel."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "sqlmodel" not in source, "Worker must not import sqlmodel"


class TestWorkerGrantTokenContract:
    """Worker authenticates via grant token, not raw API key env injection."""

    def test_worker_source_does_not_reference_block_api_key_env_var(self):
        """Security contract: worker must not read RUNSIGHT_BLOCK_API_KEY at all."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "RUNSIGHT_BLOCK_API_KEY" not in source

    def test_worker_does_not_fail_for_missing_block_api_key_when_grant_token_present(self):
        envelope = make_context_envelope(block_type="nonexistent_block_type_xyz")
        result = run_worker_subprocess(
            envelope,
            {
                "RUNSIGHT_GRANT_TOKEN": "grant-token-fixture",
                "RUNSIGHT_IPC_SOCKET": worker_socket_path("grant-contract"),
            },
            omit=("RUNSIGHT_BLOCK_API_KEY",),
        )

        stdout = result.stdout.strip()
        assert stdout, "Expected ResultEnvelope on stdout"
        result_env = parse_result_envelope(stdout)
        assert result_env.error is not None
        assert "RUNSIGHT_BLOCK_API_KEY" not in result_env.error


class TestWorkerCapabilityNegotiationStartup:
    """Worker startup uses IPCClient.connect capability handshake."""

    @pytest.mark.asyncio
    async def test_tool_stub_uses_connect_handshake_without_legacy_capability_request(self):
        from runsight_core.isolation.worker_proxies import create_tool_stubs

        tool_defs = [
            ToolDefEnvelope(
                source="fixture/echo",
                config={},
                exits=["done"],
                name="echo_tool",
                description="Echoes a string",
                parameters={"type": "object", "properties": {"value": {"type": "string"}}},
                tool_type="custom",
            )
        ]

        call_log: list[tuple[str, str | None]] = []

        class FakeIPCClient:
            def __init__(self, *, socket_path: str) -> None:
                self._socket_path = socket_path

            async def connect(self):
                call_log.append(("connect", None))
                return {
                    "id": "cap-worker-capability",
                    "done": True,
                    "accepted": True,
                    "active_actions": ["tool_call"],
                    "engine_context": {
                        "budget_remaining_usd": 15.0,
                        "trace_id": "trace-worker-capability",
                        "run_id": "worker-capability-run",
                        "block_id": "worker_block",
                    },
                    "error": None,
                }

            async def request(self, action: str, payload: dict[str, object]):
                call_log.append(("request", action))
                if action == "tool_call":
                    return {"output": f"echo:{payload['arguments']['value']}"}
                return {"error": "unexpected action"}

        ipc_client = FakeIPCClient(socket_path=worker_socket_path("capability"))
        await ipc_client.connect()
        stub = create_tool_stubs(tool_defs, ipc_client=ipc_client)[0]
        result = await stub.execute({"value": "hello"})

        assert call_log[0] == ("connect", None)
        assert ("request", "capability_negotiation") not in call_log
        assert ("request", "tool_call") in call_log
        assert result == "echo:hello"


class TestWorkerAssertionBlockContract:
    """Worker must construct assertion adapters for assertion block envelopes."""

    def test_create_block_supports_assertion_block_type_and_returns_executable_adapter(self):
        from runsight_core.isolation.worker_support import _create_block, reconstruct_soul

        envelope = make_context_envelope(
            block_id="assertion_quality_block",
            block_type="assertion",
            block_config={
                "assertion": {
                    "type": "llm_judge",
                    "config": {"rubric": "Score factual quality"},
                },
                "output_to_grade": "Candidate response to grade",
                "judge_soul": {
                    "id": "judge_quality_soul",
                    "role": "LLM Judge",
                    "system_prompt": "Grade this answer against the rubric.",
                    "model_name": "gpt-4o-mini",
                },
            },
            scoped_results={
                "target_block": {
                    "output": "Candidate response to grade",
                    "exit_handle": "done",
                }
            },
        )

        fallback_soul = reconstruct_soul(envelope.soul)
        block = _create_block(envelope, fallback_soul, runner=object())

        assert callable(getattr(block, "execute", None))

    @pytest.mark.asyncio
    async def test_assertion_block_execution_serializes_grading_result_json(self):
        from runsight_core.assertions.base import GradingResult
        from runsight_core.assertions.scoring import AssertionsResult
        from runsight_core.isolation import worker

        async def fake_run_assertions(*args, **kwargs) -> AssertionsResult:
            agg = AssertionsResult()
            agg.add_result(
                GradingResult(
                    passed=True,
                    score=0.85,
                    reason="judge accepted output",
                    named_scores={"coherence": 0.85},
                    assertion_type="llm_judge",
                    metadata={"judge_model": "gpt-4o-mini"},
                )
            )
            return agg

        with patch("runsight_core.assertions.registry.run_assertions", fake_run_assertions):
            envelope = make_context_envelope(
                block_id="assertion_serialize",
                block_type="assertion",
                block_config={
                    "assertion": {
                        "type": "llm_judge",
                        "config": {"rubric": "Score factual quality"},
                    },
                    "output_to_grade": "Candidate response to grade",
                    "judge_soul": {
                        "id": "judge_quality_soul",
                        "role": "LLM Judge",
                        "system_prompt": "Grade this answer against the rubric.",
                        "model_name": "gpt-4o-mini",
                    },
                },
                scoped_results={
                    "target_block": {
                        "output": "Candidate response to grade",
                        "exit_handle": "done",
                    }
                },
            )
            soul = worker._support.reconstruct_soul(envelope.soul)
            runner = worker._proxies.create_runner(
                model_name=envelope.soul.model_name, ipc_client=object()
            )
            block = worker._support._create_block(envelope, soul, runner=runner)
            state = worker._support.build_scoped_state(envelope)
            from runsight_core.block_io import BlockContext

            ctx = BlockContext(
                block_id=envelope.block_id,
                instruction=envelope.prompt.instruction,
                context=None,
                inputs={},
                conversation_history=[],
                soul=soul,
                model_name=envelope.soul.model_name,
                state_snapshot=state,
            )
            block_output = await block.execute(ctx)

        serialized = block_output.output
        assert isinstance(serialized, str)
        payload = json.loads(serialized)
        assert payload["passed"] is True
        assert payload["score"] == pytest.approx(0.85)
        assert payload["reason"] == "judge accepted output"
        assert payload["named_scores"]["coherence"] == pytest.approx(0.85)
        assert payload["metadata"]["judge_model"] == "gpt-4o-mini"

    def test_assertion_main_rejects_execution_when_capability_handshake_not_accepted(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.isolation import worker

        envelope = make_context_envelope(
            block_id="assertion_auth_fail",
            block_type="assertion",
            block_config={
                "assertion": {"type": "llm_judge", "config": {"rubric": "strict"}},
                "output_to_grade": "Candidate response",
                "judge_soul": {
                    "id": "judge_quality_soul",
                    "role": "LLM Judge",
                    "system_prompt": "Grade this answer against the rubric.",
                    "model_name": "gpt-4o-mini",
                },
            },
        )

        class FakeIPCClient:
            instances: list["FakeIPCClient"] = []

            def __init__(self, *, socket_path: str) -> None:
                self.socket_path = socket_path
                self.connect_calls = 0
                FakeIPCClient.instances.append(self)

            async def connect(self):
                self.connect_calls += 1
                return {
                    "id": "cap-assertion",
                    "done": True,
                    "accepted": False,
                    "active_actions": [],
                    "engine_context": {},
                    "error": "grant token rejected",
                }

        create_block_called = {"value": False}

        def _forbidden_create_block(*args, **kwargs):
            create_block_called["value"] = True
            raise AssertionError("_create_block must not run when capability auth fails")

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "grant-assertion")
        monkeypatch.setenv("RUNSIGHT_IPC_SOCKET", worker_socket_path("assert-auth"))
        monkeypatch.setattr(worker, "_emit_heartbeat", lambda *args, **kwargs: None)
        monkeypatch.setattr(worker, "_heartbeat_loop", lambda interval=5.0: None)
        monkeypatch.setattr(worker, "_heartbeat_stop", threading.Event())
        monkeypatch.setattr(worker.isolation_ipc, "IPCClient", FakeIPCClient)
        monkeypatch.setattr(worker._support, "_create_block", _forbidden_create_block)
        monkeypatch.setattr(sys, "stdin", io.StringIO(envelope.model_dump_json()))
        captured_stdout = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured_stdout)

        with pytest.raises(SystemExit) as exc_info:
            worker.main()

        result_env = ResultEnvelope.model_validate_json(captured_stdout.getvalue().strip())

        assert exc_info.value.code == 1
        assert len(FakeIPCClient.instances) == 1
        assert FakeIPCClient.instances[0].connect_calls == 1
        assert create_block_called["value"] is False
        assert result_env.error is not None
        assert "IPC auth failed" in result_env.error

    def test_assertion_main_uses_connect_handshake_before_assertion_execution(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from runsight_core.isolation import worker

        envelope = make_context_envelope(
            block_id="assertion_auth_ok",
            block_type="assertion",
            block_config={
                "assertion": {"type": "llm_judge", "config": {"rubric": "strict"}},
                "output_to_grade": "Candidate response",
                "judge_soul": {
                    "id": "judge_quality_soul",
                    "role": "LLM Judge",
                    "system_prompt": "Grade this answer against the rubric.",
                    "model_name": "gpt-4o-mini",
                },
            },
        )

        class FakeIPCClient:
            instances: list["FakeIPCClient"] = []

            def __init__(self, *, socket_path: str) -> None:
                self.socket_path = socket_path
                self.connect_calls = 0
                self.request_calls: list[str] = []
                FakeIPCClient.instances.append(self)

            async def connect(self):
                self.connect_calls += 1
                return {
                    "id": "cap-assertion",
                    "done": True,
                    "accepted": True,
                    "active_actions": ["llm_call", "tool_call"],
                    "engine_context": {},
                    "error": None,
                }

            async def request(self, action: str, payload: dict[str, object]):
                self.request_calls.append(action)
                return {"output": "unused"}

            async def request_stream(self, action: str, payload: dict[str, object]):
                self.request_calls.append(action)
                yield {
                    "content": "unused",
                    "cost_usd": 0.0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "tool_calls": [],
                    "finish_reason": "stop",
                }

        class _FakeAssertionBlock:
            def __init__(self, block_id: str) -> None:
                self._block_id = block_id

            async def execute(self, ctx):
                from runsight_core.block_io import BlockOutput

                return BlockOutput(output="assertion-ok", exit_handle="done")

        def _fake_create_block(envelope_arg, soul_arg, runner_arg):
            assert envelope_arg.block_type == "assertion"
            return _FakeAssertionBlock(envelope_arg.block_id)

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "grant-assertion")
        monkeypatch.setenv("RUNSIGHT_IPC_SOCKET", worker_socket_path("assert-ok"))
        monkeypatch.setattr(worker, "_emit_heartbeat", lambda *args, **kwargs: None)
        monkeypatch.setattr(worker, "_heartbeat_loop", lambda interval=5.0: None)
        monkeypatch.setattr(worker, "_heartbeat_stop", threading.Event())
        monkeypatch.setattr(worker.isolation_ipc, "IPCClient", FakeIPCClient)
        monkeypatch.setattr(worker._support, "_create_block", _fake_create_block)
        monkeypatch.setattr(sys, "stdin", io.StringIO(envelope.model_dump_json()))
        captured_stdout = io.StringIO()
        monkeypatch.setattr(sys, "stdout", captured_stdout)

        with pytest.raises(SystemExit) as exc_info:
            worker.main()

        result_env = ResultEnvelope.model_validate_json(captured_stdout.getvalue().strip())

        assert exc_info.value.code == 0
        assert len(FakeIPCClient.instances) == 1
        assert FakeIPCClient.instances[0].connect_calls == 1
        assert "capability_negotiation" not in FakeIPCClient.instances[0].request_calls
        assert result_env.error is None
        assert result_env.output == "assertion-ok"
