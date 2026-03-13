from runsight_api.domain.entities import Provider, Run, RunNode, RunStatus


def test_run_status_enum():
    assert RunStatus.pending == "pending"
    assert RunStatus.running == "running"
    assert RunStatus.completed == "completed"
    assert RunStatus.failed == "failed"
    assert RunStatus.cancelled == "cancelled"


def test_provider_creation():
    provider = Provider(id="test-1", name="Test Provider")
    assert provider.id == "test-1"
    assert provider.name == "Test Provider"
    assert provider.type == "custom"
    assert provider.status == "unknown"


def test_run_creation():
    run = Run(id="run-1", workflow_id="wf-1", workflow_name="WF 1", task_json='{"task": "do it"}')
    assert run.id == "run-1"
    assert run.status == RunStatus.pending


def test_run_node_tokens():
    node = RunNode(id="run-1:node-1", run_id="run-1", node_id="node-1", block_type="llm")
    assert node.tokens == {"prompt": 0, "completion": 0, "total": 0}
