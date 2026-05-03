from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from runsight_core.yaml.discovery import WorkflowScanner
from runsight_core.yaml.schema import RunsightWorkflowFile


def _workflow_payload(
    *,
    workflow_id: str,
    kind: str = "workflow",
    name: str = "Research & Review",
) -> dict:
    return {
        "version": "1.0",
        "id": workflow_id,
        "kind": kind,
        "blocks": {"review": {"type": "linear", "soul_ref": "researcher"}},
        "workflow": {"name": name, "entry": "review"},
    }


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


class TestRunsightWorkflowFileIdentity:
    def test_accepts_embedded_workflow_identity(self) -> None:
        wf = RunsightWorkflowFile.model_validate(_workflow_payload(workflow_id="research-review"))

        assert wf.id == "research-review"
        assert wf.kind == "workflow"
        assert wf.workflow.name == "Research & Review"

    @pytest.mark.parametrize(
        ("payload", "expected_field"),
        [
            (
                {
                    "kind": "workflow",
                    "blocks": {},
                    "workflow": {"name": "Research & Review", "entry": "review"},
                },
                "id",
            ),
            (
                {
                    "id": "research-review",
                    "blocks": {},
                    "workflow": {"name": "Research & Review", "entry": "review"},
                },
                "kind",
            ),
        ],
    )
    def test_rejects_missing_identity_fields(self, payload: dict, expected_field: str) -> None:
        with pytest.raises(ValidationError, match=expected_field):
            RunsightWorkflowFile.model_validate({"version": "1.0", **payload})

    @pytest.mark.parametrize("workflow_id", ["Research Review", "rw", "workflow/http"])
    def test_rejects_invalid_workflow_id(self, workflow_id: str) -> None:
        with pytest.raises(ValidationError, match="id"):
            RunsightWorkflowFile.model_validate(_workflow_payload(workflow_id=workflow_id))

    @pytest.mark.parametrize("kind", ["tool", "soul", "provider"])
    def test_rejects_wrong_workflow_kind(self, kind: str) -> None:
        with pytest.raises(ValidationError, match="kind"):
            RunsightWorkflowFile.model_validate(
                _workflow_payload(workflow_id="research-review", kind=kind)
            )


class TestWorkflowScannerIdentity:
    def test_scanner_uses_embedded_workflow_id(self, tmp_path: Path) -> None:
        workflow_path = tmp_path / "custom" / "workflows" / "research-review.yaml"
        _write_yaml(
            workflow_path,
            _workflow_payload(
                workflow_id="research-review",
                name="Research & Review",
            ),
        )

        scan_index = WorkflowScanner(tmp_path).scan()
        result = scan_index.get("research-review")

        assert result is not None
        assert result.item.id == "research-review"
        assert result.item.kind == "workflow"
        assert result.stem == "research-review"

    @pytest.mark.parametrize("workflow_id", ["research-review-fw2ry", "research-review_embedded"])
    def test_scanner_rejects_embedded_id_when_filename_stem_differs(
        self, tmp_path: Path, workflow_id: str
    ) -> None:
        workflow_path = tmp_path / "custom" / "workflows" / "research-review.yaml"
        _write_yaml(
            workflow_path,
            _workflow_payload(
                workflow_id=workflow_id,
                name="Research & Review",
            ),
        )

        with pytest.raises(
            ValueError,
            match=(
                f"embedded workflow id '{workflow_id}' does not match "
                "filename stem 'research-review'"
            ),
        ):
            WorkflowScanner(tmp_path).scan()
