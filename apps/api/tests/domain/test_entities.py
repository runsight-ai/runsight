from runsight_api.domain.entities import Run, RunNode, RunStatus


def test_run_status_enum():
    assert RunStatus.pending == "pending"
    assert RunStatus.running == "running"
    assert RunStatus.completed == "completed"
    assert RunStatus.failed == "failed"
    assert RunStatus.cancelled == "cancelled"


def test_run_creation():
    run = Run(
        id="run-primary",
        workflow_id="wf-primary",
        workflow_name="WF 1",
        task_json='{"task": "do it"}',
        branch="main",
    )
    assert run.id == "run-primary"
    assert run.status == RunStatus.pending


def test_run_node_tokens():
    node = RunNode(
        id="run-primary:node-primary",
        run_id="run-primary",
        node_id="node-primary",
        block_type="llm",
    )
    assert node.tokens == {"prompt": 0, "completion": 0, "total": 0}
