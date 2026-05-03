"""EvalObserver import, no-op, defensive handling, and protocol basics."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

from runsight_core.state import WorkflowState
from sqlmodel import Session

from runsight_api.domain.entities.run import RunNode
from eval_observer_helpers import (
    EVAL_BLOCK_ID,
    EVAL_BLOCK_TYPE,
    EVAL_WORKFLOW_ID,
    assertion_configs_for,
    import_eval_observer,
    make_eval_observer_engine,
    make_eval_soul,
    make_eval_sse_queue,
    make_eval_state,
    seed_eval_run,
    seed_eval_run_with_node,
)


def test_constructor_accepts_required_kwargs() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run(engine)
    EvalObserver = import_eval_observer()

    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=make_eval_sse_queue(),
        assertion_configs=assertion_configs_for(value="x"),
    )

    assert obs is not None


def test_module_uses_public_registry_sync_runner() -> None:
    import runsight_api.logic.observers.eval_observer as eval_observer_module
    from runsight_core.assertions import registry as assertion_registry

    source = Path(eval_observer_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    defined_functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert hasattr(assertion_registry, "run_assertions_sync")
    assert "_run_assertion_sync" not in defined_functions
    assert "_run_assertions_sync" not in defined_functions
    assert getattr(eval_observer_module, "run_assertions_sync") is (
        assertion_registry.run_assertions_sync
    )


def test_no_assertion_configs_do_not_write_db_or_emit_sse() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run_with_node(engine)
    sse_queue = make_eval_sse_queue()
    EvalObserver = import_eval_observer()
    obs = EvalObserver(engine=engine, run_id=run_id, sse_queue=sse_queue, assertion_configs=None)

    obs.on_block_complete(
        EVAL_WORKFLOW_ID,
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(),
        soul=None,
    )

    with Session(engine) as session:
        node = session.get(RunNode, f"{run_id}:{EVAL_BLOCK_ID}")
        assert node.eval_score is None
        assert node.eval_passed is None
        assert node.eval_results is None
    assert sse_queue.empty()


def test_block_missing_from_assertion_configs_is_noop() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run_with_node(engine)
    sse_queue = make_eval_sse_queue()
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=sse_queue,
        assertion_configs=assertion_configs_for("other_block", value="x"),
    )

    obs.on_block_complete(
        EVAL_WORKFLOW_ID,
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(),
        soul=None,
    )

    with Session(engine) as session:
        node = session.get(RunNode, f"{run_id}:{EVAL_BLOCK_ID}")
        assert node.eval_score is None
    assert sse_queue.empty()


def test_empty_assertion_list_for_block_is_noop() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run_with_node(engine)
    sse_queue = make_eval_sse_queue()
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=sse_queue,
        assertion_configs=assertion_configs_for(assertions=[]),
    )

    obs.on_block_complete(
        EVAL_WORKFLOW_ID,
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(),
        soul=None,
    )

    with Session(engine) as session:
        node = session.get(RunNode, f"{run_id}:{EVAL_BLOCK_ID}")
        assert node.eval_score is None
    assert sse_queue.empty()


def test_on_block_complete_does_not_raise_with_broken_assertion_config() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run_with_node(engine)
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=make_eval_sse_queue(),
        assertion_configs=assertion_configs_for(
            assertions=[
                {"type": "nonexistent_assertion_type_xyz", "value": "x", "weight": 1.0},
            ],
        ),
    )

    obs.on_block_complete(
        EVAL_WORKFLOW_ID,
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(),
        soul=make_eval_soul(),
    )


def test_on_block_complete_does_not_raise_with_db_error() -> None:
    broken_engine = MagicMock()
    broken_engine.connect.side_effect = Exception("DB connection failed")
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=broken_engine,
        run_id="broken-engine-run",
        sse_queue=make_eval_sse_queue(),
        assertion_configs=assertion_configs_for(),
    )

    obs.on_block_complete(
        EVAL_WORKFLOW_ID,
        EVAL_BLOCK_ID,
        EVAL_BLOCK_TYPE,
        2.5,
        make_eval_state(),
        soul=make_eval_soul(),
    )


def test_on_workflow_complete_does_not_raise_with_db_error() -> None:
    broken_engine = MagicMock()
    broken_engine.connect.side_effect = Exception("DB connection failed")
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=broken_engine,
        run_id="broken-engine-run",
        sse_queue=make_eval_sse_queue(),
        assertion_configs=None,
    )

    obs.on_workflow_complete(EVAL_WORKFLOW_ID, make_eval_state(), 5.0)


def test_protocol_noop_methods_do_not_raise() -> None:
    engine = make_eval_observer_engine()
    run_id = seed_eval_run(engine)
    soul = make_eval_soul()
    EvalObserver = import_eval_observer()
    obs = EvalObserver(
        engine=engine,
        run_id=run_id,
        sse_queue=make_eval_sse_queue(),
        assertion_configs=None,
    )

    obs.on_block_start(EVAL_WORKFLOW_ID, EVAL_BLOCK_ID, EVAL_BLOCK_TYPE, soul=soul)
    obs.on_workflow_start(EVAL_WORKFLOW_ID, WorkflowState())
