"""Red tests for RUN-812: smart assertion isolation via subprocess harness."""

from __future__ import annotations

import json
from typing import Any

import pytest
from runsight_core.assertions.base import AssertionContext, GradingResult
from runsight_core.assertions.registry import register_assertion, run_assertions
from runsight_core.assertions.scoring import AssertionsResult
from runsight_core.budget_enforcement import BudgetSession, _active_budget
from runsight_core.isolation.envelope import ResultEnvelope


def _make_context(**overrides: Any) -> AssertionContext:
    defaults = dict(
        output="The candidate answer.",
        prompt="Grade the candidate answer.",
        prompt_hash="prompt-hash-812",
        soul_id="soul-812",
        soul_version="v812",
        block_id="block-812",
        block_type="linear",
        cost_usd=0.01,
        total_tokens=120,
        latency_ms=95.0,
        variables={"topic": "quality"},
        run_id="run-812",
        workflow_id="wf-812",
    )
    defaults.update(overrides)
    return AssertionContext(**defaults)


class TestRUN812SmartAssertionIsolation:
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
            def __init__(self, *, api_keys: dict[str, str], **kwargs: Any) -> None:
                captured["api_keys"] = dict(api_keys)

            async def run(self, envelope: Any) -> ResultEnvelope:
                captured["envelope"] = envelope
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
        monkeypatch.setattr(registry_module, "SubprocessHarness", FakeHarness, raising=False)
        monkeypatch.setattr(isolation_module, "SubprocessHarness", FakeHarness, raising=False)

        result = await run_assertions(
            [
                {
                    "type": "llm_judge",
                    "config": {
                        "rubric": "Score factual quality",
                        "judge_soul": {
                            "id": "judge-1",
                            "role": "Judge",
                            "system_prompt": "Grade output quality.",
                            "model_name": "gpt-4o-mini",
                        },
                    },
                }
            ],
            output="The candidate answer.",
            context=_make_context(),
            api_keys={"openai": "sk-engine-openai"},
        )

        assert captured["api_keys"] == {"openai": "sk-engine-openai"}
        assert captured["envelope"].block_type == "assertion"
        assert captured["envelope"].block_config["assertion"]["type"] == "llm_judge"
        assert captured["envelope"].block_config["output_to_grade"] == "The candidate answer."
        assert captured["envelope"].block_config["judge_soul"]["model_name"] == "gpt-4o-mini"

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
            scope_name="workflow:run812",
            cost_cap_usd=5.0,
            token_cap=5000,
            on_exceed="fail",
        )
        budget_token = _active_budget.set(workflow_budget)

        class FakeHarness:
            def __init__(self, *, api_keys: dict[str, str], **kwargs: Any) -> None:
                self._api_keys = dict(api_keys)

            async def run(self, envelope: Any) -> ResultEnvelope:
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

        monkeypatch.setattr(registry_module, "SubprocessHarness", FakeHarness, raising=False)
        monkeypatch.setattr(isolation_module, "SubprocessHarness", FakeHarness, raising=False)

        try:
            _ = await run_assertions(
                [
                    {
                        "type": "llm_judge",
                        "config": {
                            "rubric": "Score factual quality",
                            "judge_soul": {
                                "id": "judge-1",
                                "role": "Judge",
                                "system_prompt": "Grade output quality.",
                                "model_name": "gpt-4o-mini",
                            },
                        },
                    }
                ],
                output="The candidate answer.",
                context=_make_context(),
                api_keys={"openai": "sk-engine-openai"},
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
        import runsight_core.assertions.registry as registry_module

        plugin_name = "run812_simple_no_llm"
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

        class _ForbiddenHarness:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise AssertionError("simple custom assertions must not use SubprocessHarness")

        monkeypatch.setenv("RUNSIGHT_GRANT_TOKEN", "grant-812-should-not-leak")
        monkeypatch.setenv("RUNSIGHT_IPC_SOCKET", "/tmp/rs-812.sock")
        monkeypatch.setenv("RUNSIGHT_BLOCK_API_KEY", "sk-raw-should-not-leak")
        monkeypatch.setattr(
            custom_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec
        )
        monkeypatch.setattr(registry_module, "SubprocessHarness", _ForbiddenHarness, raising=False)

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
