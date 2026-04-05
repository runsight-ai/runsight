from pathlib import Path

from runsight_core.yaml.parser import parse_workflow_yaml

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository
from runsight_api.logic.services.execution_service import ExecutionService


REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOWS_DIR = REPO_ROOT / "custom" / "workflows"


def _parse_runtime_workflow(workflow_stem: str):
    workflow_path = WORKFLOWS_DIR / f"{workflow_stem}.yaml"
    raw_yaml = workflow_path.read_text(encoding="utf-8")
    repo = WorkflowRepository(base_path=str(REPO_ROOT))
    registry = repo.build_runnable_workflow_registry(workflow_stem, raw_yaml)
    return parse_workflow_yaml(str(workflow_path), workflow_registry=registry)


def test_provider_pulse_orchestrator_enables_block_level_eval_configs():
    wf = _parse_runtime_workflow("multi-provider-release-digest-orchestrator")

    configs = ExecutionService._build_assertion_configs(wf)

    assert configs is not None
    assert set(configs) == set(wf._blocks)
    assert [cfg["type"] for cfg in configs["prepare_manifest"]] == ["contains-json"]
    assert [cfg["type"] for cfg in configs["merge_round_outputs"]] == ["regex", "word-count"]
    assert [cfg["type"] for cfg in configs["round_gate"]] == ["contains-any"]
    assert [cfg["type"] for cfg in configs["parent_review_loop"]] == ["regex"]
    assert [cfg["type"] for cfg in configs["finalize_run"]] == ["contains-json"]


def test_provider_pulse_subflow_enables_block_level_eval_configs():
    wf = _parse_runtime_workflow("reusable-release-trace-subflow")

    configs = ExecutionService._build_assertion_configs(wf)

    assert configs is not None
    assert set(configs) == set(wf._blocks)
    assert [cfg["type"] for cfg in configs["dispatch_child_views"]] == ["contains-json"]
    assert [cfg["type"] for cfg in configs["child_merge"]] == ["regex", "word-count"]
    assert [cfg["type"] for cfg in configs["child_quality_gate"]] == ["contains-any"]
    assert [cfg["type"] for cfg in configs["child_revision_loop"]] == ["regex"]
    assert [cfg["type"] for cfg in configs["package_child_result"]] == ["contains-json"]
