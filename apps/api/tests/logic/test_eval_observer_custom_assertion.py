"""Custom assertion live-path coverage through ExecutionService workflow loading."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from apps.api.tests.logic.eval_observer_helpers import (
    app_with_real_services as _app_with_real_services_fixture,  # noqa: F401
    custom_assertion_base_dir as _base_dir_fixture,  # noqa: F401
    custom_assertion_db_engine as _db_engine_fixture,  # noqa: F401
    capture_eval_events as _capture_eval_events,
    isolate_custom_assertion_registry as _isolate_custom_assertion_registry_fixture,  # noqa: F401
    make_achat_response as _make_achat_response,
    mock_provider as _mock_provider_fixture,  # noqa: F401
    wait_for_run_terminal as _wait_for_run_terminal,
)


class TestLiveCustomAssertionPath:
    @pytest.mark.asyncio
    async def test_api_run_persists_promptfoo_custom_assertion_results_and_sse(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        execution_service = app_with_real_services.state.execution_service
        captured_events = _capture_eval_events(execution_service)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://api.fixture.test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("calm response"),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "promptfoo-eval-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        analyze_node = next(node for node in nodes_response.json() if node["node_id"] == "analyze")
        assert analyze_node["eval_passed"] is True
        assert analyze_node["eval_score"] == pytest.approx(0.95)
        assert analyze_node["eval_results"] is not None
        assert analyze_node["eval_results"]["assertions"][0]["type"] == "custom:tone_check"
        assert analyze_node["eval_results"]["assertions"][0]["passed"] is True

        eval_events = [
            event for event in captured_events if event.get("event") == "node_eval_complete"
        ]
        assert len(eval_events) >= 1
        assert eval_events[0]["data"]["assertions"][0]["type"] == "custom:tone_check"
        assert eval_events[0]["data"]["passed"] is True

    @pytest.mark.asyncio
    async def test_api_run_supports_negated_custom_assertions_with_builtin_regression(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        execution_service = app_with_real_services.state.execution_service
        captured_events = _capture_eval_events(execution_service)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://api.fixture.test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("calm response"),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "negated-custom-eval-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        analyze_node = next(node for node in nodes_response.json() if node["node_id"] == "analyze")
        assert analyze_node["eval_passed"] is True
        assert analyze_node["eval_score"] == pytest.approx(1.0)
        assert analyze_node["eval_results"] is not None
        assert analyze_node["eval_results"]["assertions"][0]["type"] == "custom:blocked_word"
        assert analyze_node["eval_results"]["assertions"][0]["passed"] is True

        eval_events = [
            event for event in captured_events if event.get("event") == "node_eval_complete"
        ]
        assert len(eval_events) >= 1
        assert eval_events[0]["data"]["passed"] is True

    @pytest.mark.asyncio
    async def test_api_run_persists_invalid_config_failure_and_sse_via_real_load_path(
        self, app_with_real_services, db_engine, mock_provider
    ):
        from httpx import ASGITransport, AsyncClient

        execution_service = app_with_real_services.state.execution_service
        captured_events = _capture_eval_events(execution_service)

        async with AsyncClient(
            transport=ASGITransport(app=app_with_real_services),
            base_url="http://api.fixture.test",
        ) as client:
            with (
                patch(
                    "runsight_core.llm.client.LiteLLMClient.achat",
                    new_callable=AsyncMock,
                    return_value=_make_achat_response("calm response"),
                ),
                patch.object(
                    execution_service.provider_repo,
                    "list_all",
                    return_value=[mock_provider],
                ),
            ):
                response = await client.post(
                    "/api/runs",
                    json={
                        "workflow_id": "invalid-config-eval-workflow",
                        "branch": "main",
                        "inputs": {},
                    },
                )
                assert response.status_code == 200
                run_id = response.json()["id"]
                await _wait_for_run_terminal(db_engine, run_id)

            nodes_response = await client.get(f"/api/runs/{run_id}/nodes")

        assert nodes_response.status_code == 200
        analyze_node = next(node for node in nodes_response.json() if node["node_id"] == "analyze")
        assert analyze_node["eval_passed"] is False
        assert analyze_node["eval_score"] == pytest.approx(0.0)
        assert analyze_node["eval_results"] is not None
        assert analyze_node["eval_results"]["assertions"][0]["type"] == "custom:budget_guard"
        assert analyze_node["eval_results"]["assertions"][0]["reason"].startswith(
            "Config validation failed:"
        )

        eval_events = [
            event for event in captured_events if event.get("event") == "node_eval_complete"
        ]
        assert len(eval_events) >= 1
        assert eval_events[0]["data"]["assertions"][0]["reason"].startswith(
            "Config validation failed:"
        )
