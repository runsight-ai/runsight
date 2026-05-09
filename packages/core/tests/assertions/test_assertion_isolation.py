"""Assertion isolation via workspace harness coverage."""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.assertions.base import AssertionContext, GradingResult
from runsight_core.assertions.registry import register_assertion, run_assertions
from runsight_core.assertions.scoring import AssertionsResult
from runsight_core.budget_enforcement import BudgetSession, _active_budget
from runsight_core.isolation.envelope import ResultEnvelope
from runsight_core.isolation.workspace import WorkspaceRunRequest

pytestmark = pytest.mark.real_subprocess_isolation


def _make_context(**overrides: Any) -> AssertionContext:
    defaults = dict(
        output="The candidate answer.",
        prompt="Grade the candidate answer.",
        prompt_hash="prompt-hash-isolation",
        soul_id="isolated-assertion-soul",
        soul_version="v-isolation",
        block_id="isolated-assertion-block",
        block_type="linear",
        cost_usd=0.01,
        total_tokens=120,
        latency_ms=95.0,
        variables={"topic": "quality"},
        run_id="isolated-assertion-run",
        workflow_id="isolated-assertion-workflow",
    )
    defaults.update(overrides)
    return AssertionContext(**defaults)


class TestSmartAssertionIsolation:
    @pytest.mark.asyncio
    async def test_llm_judge_runs_via_harness_and_deserializes_result_envelope_output(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        import runsight_core.assertions.custom as custom_module
        import runsight_core.assertions.registry as registry_module
        import runsight_core.isolation as isolation_module

        captured: dict[str, Any] = {}

        class FakeHarness:
            def __init__(self, **kwargs: Any) -> None:
                captured["harness_kwargs"] = dict(kwargs)

            async def run(self, request: WorkspaceRunRequest) -> ResultEnvelope:
                captured["request"] = request
                envelope = request.envelope
                return ResultEnvelope(
                    block_id=envelope.block_id,
                    output=json.dumps(
                        {
                            "passed": True,
                            "score": 0.85,
                            "reason": "judge accepted output",
                            "named_scores": {"coherence": 0.85},
                            "assertion_type": "llm_judge",
                            "metadata": {"judge_model": "gpt-4o-mini"},
                        }
                    ),
                    exit_handle="done",
                    cost_usd=0.02,
                    total_tokens=44,
                    tool_calls_made=0,
                    delegate_artifacts={},
                    conversation_history=[],
                    error=None,
                    error_type=None,
                )

        monkeypatch.setattr(
            custom_module,
            "_run_plugin_sync",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("llm_judge must not run via custom plugin sync path")
            ),
        )
        monkeypatch.setattr(registry_module, "UnixLocalHarness", FakeHarness, raising=False)
        monkeypatch.setattr(isolation_module, "UnixLocalHarness", FakeHarness, raising=False)

        result = await run_assertions(
            [
                {
                    "type": "llm_judge",
                    "config": {
                        "rubric": "Score factual quality",
                        "judge_soul": {
                            "id": "quality-judge",
                            "role": "Judge",
                            "system_prompt": "Grade output quality.",
                            "model_name": "gpt-4o-mini",
                        },
                    },
                }
            ],
            output="The candidate answer.",
            context=_make_context(),
            api_keys={"openai": "dummy-engine-openai-key"},
        )

        assert captured["harness_kwargs"] == {}
        request = captured["request"]
        assert isinstance(request, WorkspaceRunRequest)
        assert request.host_bindings is not None
        assert request.host_bindings.api_keys == {"openai": "dummy-engine-openai-key"}
        assert request.worker_tools == []
        assert request.host_bindings.host_tools.tools == []
        assert request.manifest.working_dir == "."
        assert request.envelope.block_type == "assertion"
        assert request.envelope.block_config["assertion"]["type"] == "llm_judge"
        assert request.envelope.block_config["output_to_grade"] == "The candidate answer."
        assert request.envelope.block_config["judge_soul"]["model_name"] == "gpt-4o-mini"
        assert request.envelope.timeout_seconds == 30
        assert request.envelope.max_output_bytes == 1_000_000

        assert isinstance(result, AssertionsResult)
        assert len(result.results) == 1
        grading = result.results[0]
        assert isinstance(grading, GradingResult)
        assert grading.passed is True
        assert grading.score == pytest.approx(0.85)
        assert grading.reason == "judge accepted output"
        assert grading.named_scores["coherence"] == pytest.approx(0.85)
        assert grading.metadata["judge_model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_llm_judge_accrues_assertion_cost_and_tokens_into_active_budget_session(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        import runsight_core.assertions.registry as registry_module
        import runsight_core.isolation as isolation_module

        workflow_budget = BudgetSession(
            scope_name="workflow:isolation-run",
            cost_cap_usd=5.0,
            token_cap=5000,
            on_exceed="fail",
        )
        budget_token = _active_budget.set(workflow_budget)

        class FakeHarness:
            def __init__(self, **kwargs: Any) -> None:
                self._kwargs = dict(kwargs)

            async def run(self, request: WorkspaceRunRequest) -> ResultEnvelope:
                active_budget = _active_budget.get(None)
                if isinstance(active_budget, BudgetSession):
                    active_budget.accrue(cost_usd=0.10, tokens=15)
                envelope = request.envelope
                return ResultEnvelope(
                    block_id=envelope.block_id,
                    output=json.dumps(
                        {
                            "passed": True,
                            "score": 0.85,
                            "reason": "judge accepted output",
                            "named_scores": {"coherence": 0.85},
                            "assertion_type": "llm_judge",
                            "metadata": {"judge_model": "gpt-4o-mini"},
                        }
                    ),
                    exit_handle="done",
                    cost_usd=0.10,
                    total_tokens=15,
                    tool_calls_made=0,
                    delegate_artifacts={},
                    conversation_history=[],
                    error=None,
                    error_type=None,
                )

        monkeypatch.setattr(registry_module, "UnixLocalHarness", FakeHarness, raising=False)
        monkeypatch.setattr(isolation_module, "UnixLocalHarness", FakeHarness, raising=False)

        try:
            _ = await run_assertions(
                [
                    {
                        "type": "llm_judge",
                        "config": {
                            "rubric": "Score factual quality",
                            "judge_soul": {
                                "id": "quality-judge",
                                "role": "Judge",
                                "system_prompt": "Grade output quality.",
                                "model_name": "gpt-4o-mini",
                            },
                        },
                    }
                ],
                output="The candidate answer.",
                context=_make_context(),
                api_keys={"openai": "dummy-engine-openai-key"},
            )
        finally:
            _active_budget.reset(budget_token)

        assert workflow_budget.cost_usd == pytest.approx(0.10)
        assert workflow_budget.tokens == 15

    @pytest.mark.asyncio
    async def test_simple_custom_assertion_keeps_minimal_env_and_never_uses_ipc_harness(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ):
        import runsight_core.assertions.custom as custom_module

        plugin_name = "simple_custom_no_llm"
        adapter_cls = custom_module._build_adapter_class(
            plugin_name,
            """
def get_assert(output, context):
    return {"passed": True, "score": 1.0, "reason": "simple plugin pass"}
""",
            "grading_result",
        )
        register_assertion(f"custom:{plugin_name}", adapter_cls)

        captured_env: dict[str, str] = {}

        class _FakeProc:
            returncode = 0

            async def communicate(self, input: bytes | None = None):
                return (
                    b'{"passed": true, "score": 1.0, "reason": "simple plugin pass"}',
                    b"",
                )

        async def fake_create_subprocess_exec(*args: Any, **kwargs: Any):
            nonlocal captured_env
            captured_env = dict(kwargs.get("env", {}))
            return _FakeProc()

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "grant-isolation-should-not-leak")
        monkeypatch.setenv("RUNSIGHT_IPC_SOCKET", "/tmp/rs-isolation.sock")
        monkeypatch.setenv("RUNSIGHT_BLOCK_API_KEY", "dummy-block-api-key-should-not-leak")
        monkeypatch.setattr(
            custom_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
        )

        result = await run_assertions(
            [{"type": f"custom:{plugin_name}", "config": {"mode": "simple"}}],
            output="plain text output",
            context=_make_context(),
        )

        assert len(result.results) == 1
        assert result.results[0].passed is True
        assert "RUNSIGHT_GRANT_TOKEN" not in captured_env
        assert "RUNSIGHT_IPC_SOCKET" not in captured_env
        assert "RUNSIGHT_BLOCK_API_KEY" not in captured_env
