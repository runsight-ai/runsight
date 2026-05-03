"""Shared builders for sensitive workflow input redaction tests."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

from runsight_core.context_governance import ContextGovernancePolicy, ContextResolver
from runsight_core.state import BlockResult, WorkflowState
from runsight_core.workflow import Workflow
from runsight_core.yaml.schema import WorkflowInputDef

SENSITIVE_VALUE = "orchid-sensitive-value"
PUBLIC_VALUE = "orchid-public-value"
REDACTED = "[redacted]"


def redactor(*values: object) -> Any:
    from runsight_core.redaction import SensitiveValueRedactor

    instance = SensitiveValueRedactor()
    for value in values:
        instance.register(value)
    return instance


def state_with_redactor(
    *,
    input_redactor: Any | None = None,
    workflow_inputs: dict[str, Any] | None = None,
    results: dict[str, Any] | None = None,
    shared_memory: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    execution_log: list[dict[str, str]] | None = None,
) -> WorkflowState:
    return WorkflowState(
        input_redactor=input_redactor,
        workflow_inputs=workflow_inputs or {},
        results=results or {},
        shared_memory=shared_memory or {},
        metadata=metadata or {},
        execution_log=execution_log or [],
    )


def resolver() -> ContextResolver:
    return ContextResolver(
        policy=ContextGovernancePolicy(),
        run_id="redaction-context-run",
        workflow_name="redaction_context",
    )


class CapturingRedactionWorkflow:
    name = "redaction_context_workflow"

    def __init__(self) -> None:
        self.received_state: WorkflowState | None = None

    async def run(self, state: WorkflowState, **kwargs: Any) -> WorkflowState:
        self.received_state = state
        return WorkflowState(
            input_redactor=state.input_redactor,
            workflow_inputs=dict(state.workflow_inputs),
            results={"echo": BlockResult(output=state.workflow_inputs["private_note"])},
            artifact_store=state.artifact_store,
        )


def sensitive_input_workflow(
    *, raw_return: bool = False
) -> tuple[Workflow, dict[str, WorkflowState]]:
    invoked = Workflow(
        name="sensitive_input_workflow",
        input_schema={"invoked_secret": WorkflowInputDef(type="string", sensitive=True)},
    )
    captured: dict[str, WorkflowState] = {}

    async def _run(state: WorkflowState, **kwargs: Any) -> WorkflowState:
        captured["received_state"] = state
        invoked_secret = state.workflow_inputs["invoked_secret"]
        output = invoked_secret
        log_content = f"invoked workflow saw {invoked_secret}"
        if not raw_return:
            assert state.input_redactor is not None
            redacted_payload = state.input_redactor.redact(
                {"invoked_secret": invoked_secret, "public_note": PUBLIC_VALUE}
            )
            output = json.dumps(redacted_payload)
            log_content = state.input_redactor.redact_text(log_content)
        returned_state = WorkflowState(
            input_redactor=state.input_redactor,
            workflow_inputs=dict(state.workflow_inputs),
            results={"sensitive_result": BlockResult(output=output)},
            execution_log=[{"role": "system", "content": log_content}],
        )
        captured["returned_state"] = returned_state
        return returned_state

    invoked.run = AsyncMock(side_effect=_run)
    return invoked, captured


def raising_sensitive_input_workflow() -> Workflow:
    invoked = Workflow(
        name="raising_sensitive_input_workflow",
        input_schema={"invoked_secret": WorkflowInputDef(type="string", sensitive=True)},
    )

    async def _run(state: WorkflowState, **kwargs: Any) -> WorkflowState:
        raise RuntimeError(
            f"invoked workflow failed with {state.workflow_inputs['invoked_secret']}"
        )

    invoked.run = AsyncMock(side_effect=_run)
    return invoked


class ParentErrorObserver:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.state: WorkflowState | None = None

    def on_block_start(
        self, workflow_name: str, block_id: str, block_type: str, **kwargs: Any
    ) -> None:
        return None

    def on_block_error(
        self,
        workflow_name: str,
        block_id: str,
        block_type: str,
        duration_s: float,
        error: Exception,
        state: WorkflowState,
    ) -> None:
        self.error = error
        self.state = state
