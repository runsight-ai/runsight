import yaml

from runsight_api.data.filesystem.workflow_repo import WorkflowRepository


def test_set_enabled_updates_only_the_enabled_key_in_workflow_yaml(tmp_path):
    repo = WorkflowRepository(base_path=str(tmp_path))
    workflow_id = "customer-intake-abc12"
    workflow_path = repo.workflows_dir / f"{workflow_id}.yaml"
    original = {
        "version": "1.0",
        "enabled": False,
        "workflow": {
            "name": "Customer Intake",
            "entry": "collect_brief",
        },
        "blocks": {
            "collect_brief": {
                "type": "linear",
                "soul_ref": "brief_collector",
            }
        },
    }
    workflow_path.write_text(yaml.safe_dump(original, sort_keys=False))

    updated = repo.set_enabled(workflow_id, True)

    on_disk = yaml.safe_load(workflow_path.read_text())
    assert on_disk == {**original, "enabled": True}
    assert updated.id == workflow_id
    assert updated.enabled is True
