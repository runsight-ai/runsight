"""Shared EvalObserver test builders.

The helpers in this module keep EvalObserver behavior tests isolated from
developer runtime state by using in-memory SQLModel engines and explicit test
rows.
"""

from __future__ import annotations

import asyncio
from typing import Any

from runsight_core.observer import compute_soul_version
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session, SQLModel, create_engine

from runsight_api.domain.entities.run import Run, RunNode, RunStatus

EVAL_BLOCK_ID = "output_serialization_block"
EVAL_BLOCK_TYPE = "LinearBlock"
EVAL_RUN_ID = "eval-observer-run"
EVAL_WORKFLOW_ID = "eval-observer-workflow"
EVAL_WORKFLOW_NAME = "Eval Observer Workflow"
EVAL_OUTPUT = "Some output containing Sources information."


def import_eval_observer():
    from runsight_api.logic.observers.eval_observer import EvalObserver

    return EvalObserver


def make_eval_observer_engine():
    """Create a test-owned in-memory SQLModel engine."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def seed_eval_run(
    engine,
    *,
    run_id: str = EVAL_RUN_ID,
    workflow_id: str = EVAL_WORKFLOW_ID,
    workflow_name: str = EVAL_WORKFLOW_NAME,
    status: RunStatus = RunStatus.pending,
) -> str:
    """Insert a Run row for isolated API tests."""
    with Session(engine) as session:
        session.add(
            Run(
                id=run_id,
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                status=status,
                task_json="{}",
                branch="main",
            )
        )
        session.commit()
    return run_id


def seed_eval_run_node(
    engine,
    *,
    run_id: str,
    block_id: str = EVAL_BLOCK_ID,
    block_type: str = EVAL_BLOCK_TYPE,
    status: str = "completed",
    cost_usd: float = 0.05,
    tokens_total: int = 1500,
    output: str = EVAL_OUTPUT,
    eval_score: float | None = None,
    eval_passed: bool | None = None,
    child_run_id: str | None = None,
) -> RunNode:
    """Insert a RunNode row for an evaluated block."""
    node = RunNode(
        id=f"{run_id}:{block_id}",
        run_id=run_id,
        node_id=block_id,
        block_type=block_type,
        status=status,
        cost_usd=cost_usd,
        tokens={"total": tokens_total},
        output=output,
        eval_score=eval_score,
        eval_passed=eval_passed,
        child_run_id=child_run_id,
    )
    with Session(engine) as session:
        session.add(node)
        session.commit()
        session.refresh(node)
        return node


def seed_eval_baseline_nodes(
    engine,
    soul: Soul,
    *,
    block_id: str = EVAL_BLOCK_ID,
    block_type: str = EVAL_BLOCK_TYPE,
    run_id_prefix: str = "soul-baseline-run",
    cost_usd: float = 0.04,
    tokens_total: int = 1200,
    eval_score: float = 0.9,
    count: int = 3,
) -> None:
    """Insert baseline RunNode rows for delta tests."""
    soul_version = compute_soul_version(soul)
    with Session(engine) as session:
        for index in range(count):
            run_id = f"{run_id_prefix}-{index}"
            session.add(
                RunNode(
                    id=f"{run_id}:{block_id}",
                    run_id=run_id,
                    node_id=block_id,
                    block_type=block_type,
                    status="completed",
                    soul_id=soul.id,
                    soul_version=soul_version,
                    cost_usd=cost_usd,
                    tokens={"total": tokens_total},
                    eval_score=eval_score,
                )
            )
        session.commit()


def make_eval_sse_queue():
    """Create an asyncio.Queue for SSE assertions."""
    return asyncio.Queue()


def make_eval_state(
    *,
    block_id: str = EVAL_BLOCK_ID,
    output: Any = EVAL_OUTPUT,
    total_cost_usd: float = 0.05,
    total_tokens: int = 1500,
) -> WorkflowState:
    """Create a WorkflowState with one completed block result."""
    return WorkflowState(
        total_cost_usd=total_cost_usd,
        total_tokens=total_tokens,
        results={block_id: BlockResult(output=output)},
    )


def make_eval_soul(
    *,
    soul_id: str = "researcher-v1",
    name: str = "Senior Researcher",
    role: str = "Senior Researcher",
    system_prompt: str = "You are a senior researcher.",
    model_name: str = "fixture-eval-model",
) -> Soul:
    """Create a stable Soul identity for EvalObserver tests."""
    return Soul(
        id=soul_id,
        kind="soul",
        name=name,
        role=role,
        system_prompt=system_prompt,
        model_name=model_name,
    )


def assertion_configs_for(
    block_id: str = EVAL_BLOCK_ID,
    *,
    kind: str = "contains",
    value: str = "Sources",
    weight: float = 1.0,
    threshold: float | None = None,
    assertions: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build assertion configs for one EvalObserver block."""
    if assertions is not None:
        return {block_id: assertions}

    config: dict[str, Any] = {"type": kind, "weight": weight}
    if kind == "cost":
        config["threshold"] = threshold if threshold is not None else 0.10
    else:
        config["value"] = value
    return {block_id: [config]}


def seed_eval_run_with_node(
    engine,
    *,
    run_id: str = EVAL_RUN_ID,
    workflow_id: str = EVAL_WORKFLOW_ID,
    workflow_name: str = EVAL_WORKFLOW_NAME,
    run_status: RunStatus = RunStatus.pending,
    block_id: str = EVAL_BLOCK_ID,
    block_type: str = EVAL_BLOCK_TYPE,
    cost_usd: float = 0.05,
    tokens_total: int = 1500,
    output: str = EVAL_OUTPUT,
) -> str:
    seed_eval_run(
        engine,
        run_id=run_id,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        status=run_status,
    )
    seed_eval_run_node(
        engine,
        run_id=run_id,
        block_id=block_id,
        block_type=block_type,
        cost_usd=cost_usd,
        tokens_total=tokens_total,
        output=output,
    )
    return run_id
