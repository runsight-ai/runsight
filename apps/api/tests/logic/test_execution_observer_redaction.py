"""ExecutionObserver persistence redaction behavior."""

from __future__ import annotations

import json

from runsight_core.state import BlockResult, WorkflowState
from sqlmodel import Session

from runsight_api.domain.entities.run import Run, RunNode
from runsight_api.logic.observers.execution_observer import ExecutionObserver

from sensitive_redaction_helpers import (
    PUBLIC_VALUE,
    REDACTED,
    SENSITIVE_VALUE,
    collect_sensitive_log_messages,
    make_sensitive_db_engine,
    make_sensitive_execution_service,
    make_sensitive_redactor,
    make_sensitive_state,
    mixed_structured_sensitive_workflow_yaml,
    seed_sensitive_run,
)


def test_execution_observer_redacts_node_output_and_execution_log_before_persisting() -> None:
    engine = make_sensitive_db_engine()
    seed_sensitive_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_sensitive_api")
    observer.on_block_start("wf", "emit_secret", "CodeBlock")
    state = make_sensitive_state(
        results={
            "emit_secret": BlockResult(
                output=json.dumps(
                    {
                        "private_note": SENSITIVE_VALUE,
                        "public_note": PUBLIC_VALUE,
                    }
                )
            )
        },
        execution_log=[{"role": "system", "content": f"raw execution detail: {SENSITIVE_VALUE}"}],
    )

    observer.on_block_complete("wf", "emit_secret", "CodeBlock", 0.1, state)

    with Session(engine) as session:
        node = session.get(RunNode, "run_sensitive_api:emit_secret")
    assert node is not None
    assert SENSITIVE_VALUE not in node.output
    assert REDACTED in node.output
    assert PUBLIC_VALUE in node.output
    assert SENSITIVE_VALUE not in "\n".join(collect_sensitive_log_messages(engine))


def test_execution_observer_redacts_results_serialization_before_run_persistence() -> None:
    engine = make_sensitive_db_engine()
    seed_sensitive_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_sensitive_api")
    state = make_sensitive_state(
        results={
            "final": BlockResult(
                output=json.dumps(
                    {
                        "private_note": SENSITIVE_VALUE,
                        "public_note": PUBLIC_VALUE,
                    }
                )
            )
        }
    )

    observer.on_workflow_complete("wf", state, 0.2)

    with Session(engine) as session:
        run = session.get(Run, "run_sensitive_api")
    assert run is not None
    assert run.results_json is not None
    assert SENSITIVE_VALUE not in run.results_json
    assert REDACTED in run.results_json
    assert PUBLIC_VALUE in run.results_json


def test_execution_observer_redacts_mixed_structured_sensitive_unique_leaf_in_runtime_surfaces() -> (
    None
):
    service = make_sensitive_execution_service(yaml=mixed_structured_sensitive_workflow_yaml())
    credentials = {"token": "SECRET-UNIQUE", "a": "dup", "b": "dup"}
    prepared = service.prepare_run_inputs(
        "sensitive_inputs_workflow",
        {"credentials": credentials},
        branch=None,
    )
    engine = make_sensitive_db_engine()
    seed_sensitive_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_sensitive_api")
    observer.on_block_start("wf", "emit_secret", "CodeBlock")
    state = WorkflowState(
        input_redactor=prepared.input_redactor,
        results={
            "emit_secret": BlockResult(
                output=json.dumps(
                    {
                        "raw_credentials": credentials,
                        "text": "failed with SECRET-UNIQUE and dup",
                        "public_note": PUBLIC_VALUE,
                    }
                )
            )
        },
        execution_log=[
            {
                "role": "system",
                "content": "raw execution detail: SECRET-UNIQUE and dup",
            }
        ],
    )

    observer.on_block_complete("wf", "emit_secret", "CodeBlock", 0.1, state)

    with Session(engine) as session:
        node = session.get(RunNode, "run_sensitive_api:emit_secret")
    assert node is not None
    persisted = "\n".join([node.output or "", *collect_sensitive_log_messages(engine)])
    assert "SECRET-UNIQUE" not in persisted
    assert "dup" not in persisted
    assert REDACTED in persisted
    assert PUBLIC_VALUE in persisted


def test_execution_observer_redacts_error_and_traceback_when_state_is_available() -> None:
    engine = make_sensitive_db_engine()
    seed_sensitive_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_sensitive_api")
    observer.on_block_start("wf", "fail_secret", "CodeBlock")
    state = make_sensitive_state()

    try:
        raise RuntimeError(f"failed while handling {SENSITIVE_VALUE}")
    except RuntimeError as exc:
        observer.on_block_error("wf", "fail_secret", "CodeBlock", 0.1, exc, state=state)

    with Session(engine) as session:
        node = session.get(RunNode, "run_sensitive_api:fail_secret")
    assert node is not None
    assert SENSITIVE_VALUE not in (node.error or "")
    assert SENSITIVE_VALUE not in (node.error_traceback or "")
    assert REDACTED in (node.error or "")
    assert REDACTED in (node.error_traceback or "")
    assert SENSITIVE_VALUE not in "\n".join(collect_sensitive_log_messages(engine))


def test_execution_observer_redacts_json_escaped_sensitive_value_in_error_surfaces() -> None:
    secret = 'alpha"beta\\gamma\nline2'
    serialized = json.dumps({"token": secret})
    escaped_secret = json.dumps(secret)[1:-1]
    engine = make_sensitive_db_engine()
    seed_sensitive_run(engine)
    observer = ExecutionObserver(engine=engine, run_id="run_sensitive_api")
    observer.on_block_start("wf", "fail_secret", "CodeBlock")
    state = WorkflowState(input_redactor=make_sensitive_redactor(secret))

    try:
        raise RuntimeError(f"failed while handling {serialized}")
    except RuntimeError as exc:
        observer.on_block_error("wf", "fail_secret", "CodeBlock", 0.1, exc, state=state)

    with Session(engine) as session:
        node = session.get(RunNode, "run_sensitive_api:fail_secret")
    persisted = "\n".join(
        [
            node.error if node is not None else "",
            node.error_traceback if node is not None else "",
            *collect_sensitive_log_messages(engine),
        ]
    )

    assert node is not None
    assert escaped_secret not in persisted
    assert secret not in persisted
    assert REDACTED in persisted
