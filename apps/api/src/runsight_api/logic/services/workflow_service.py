from typing import Any, Dict, List, Optional
import logging

import yaml as yaml_mod
from pydantic import ValidationError as PydanticValidationError
from runsight_core.identity import EntityKind, EntityRef
from runsight_core.yaml.schema import RunsightWorkflowFile

from ...data.filesystem.workflow_repo import WorkflowRepository
from ...data.repositories.run_repo import RunRepository
from ...domain.errors import InputValidationError, WorkflowNotFound
from ...domain.value_objects import WorkflowEntity

logger = logging.getLogger(__name__)


def _workflow_ref(workflow_id: str) -> str:
    return str(EntityRef(EntityKind.WORKFLOW, workflow_id))


class WorkflowService:
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        run_repo: RunRepository,
        git_service=None,
    ):
        self.workflow_repo = workflow_repo
        self.run_repo = run_repo
        self.git_service = git_service

    def list_workflows(self, query: Optional[str] = None) -> List[WorkflowEntity]:
        workflows = self.workflow_repo.list_all()
        if query:
            query = query.lower()
            workflows = [
                w
                for w in workflows
                if query in w.id.lower() or (getattr(w, "name", "") and query in w.name.lower())
            ]

        health_by_workflow = self.run_repo.get_workflow_health_metrics([w.id for w in workflows])
        enriched_workflows: list[WorkflowEntity] = []

        for workflow in workflows:
            yaml_path = f"custom/workflows/{workflow.id}.yaml"
            enriched_workflows.append(
                workflow.model_copy(
                    update={
                        "block_count": self.workflow_repo.get_block_count(workflow.id),
                        "modified_at": self.workflow_repo.get_file_mtime(workflow.id),
                        "enabled": bool(getattr(workflow, "enabled", False)),
                        "commit_sha": self._get_workflow_commit_sha(yaml_path),
                        "health": health_by_workflow.get(
                            workflow.id,
                            {
                                "run_count": 0,
                                "eval_pass_pct": None,
                                "eval_health": None,
                                "total_cost_usd": 0.0,
                                "regression_count": 0,
                            },
                        ),
                    }
                )
            )

        return enriched_workflows

    def get_workflow(self, id: str) -> Optional[WorkflowEntity]:
        return self.workflow_repo.get_by_id(id)

    def get_workflow_detail(self, id: str) -> Optional[WorkflowEntity]:
        workflow = self.workflow_repo.get_by_id(id)
        if workflow is None:
            return None

        yaml_path = f"custom/workflows/{workflow.id}.yaml"
        return workflow.model_copy(
            update={
                "commit_sha": self._get_workflow_commit_sha_on_main(yaml_path),
            }
        )

    def create_workflow(self, data: Dict[str, Any], *, commit: bool = True) -> WorkflowEntity:
        try:
            result = self.workflow_repo.create(data)
        except ValueError as exc:
            raise InputValidationError(str(exc)) from exc
        if commit:
            self._auto_commit(
                f"Create workflow: {result.name}",
                [f"custom/workflows/{result.id}.yaml"],
            )
        return result

    def update_workflow(self, id: str, data: Dict[str, Any]) -> WorkflowEntity:
        try:
            return self.workflow_repo.update(id, data)
        except ValueError as exc:
            raise InputValidationError(str(exc)) from exc

    def commit_workflow(
        self,
        workflow_id: str,
        draft: Dict[str, Any],
        message: str,
    ) -> Dict[str, str]:
        if self.git_service is None:
            raise RuntimeError("Git service not configured")

        previous = self.workflow_repo.get_by_id(workflow_id)
        try:
            self.update_workflow(workflow_id, draft)
        except InputValidationError:
            raise

        files = [f"custom/workflows/{workflow_id}.yaml"]
        if draft.get("canvas_state") is not None:
            files.append(f"custom/workflows/.canvas/{workflow_id}.canvas.json")

        try:
            commit_hash = self.git_service.commit_to_branch("main", files, message)
        except Exception:
            if previous is not None:
                rollback = {"yaml": previous.yaml}
                if previous.canvas_state is not None:
                    if hasattr(previous.canvas_state, "model_dump"):
                        rollback["canvas_state"] = previous.canvas_state.model_dump()
                    else:
                        rollback["canvas_state"] = previous.canvas_state
                self.workflow_repo.update(workflow_id, rollback)
            raise
        return {"hash": commit_hash, "message": message}

    def create_simulation(self, workflow_id: str, yaml: str) -> Dict[str, str]:
        if self.git_service is None:
            raise RuntimeError("Git service not configured")

        self._validate_simulation_yaml_identity(workflow_id, yaml)

        yaml_path = f"custom/workflows/{workflow_id}.yaml"
        result = self.git_service.create_sim_branch(
            workflow_slug=workflow_id,
            yaml_content=yaml,
            yaml_path=yaml_path,
        )
        return {"branch": result.branch, "commit_sha": result.sha}

    def _validate_simulation_yaml_identity(self, workflow_id: str, raw_yaml: str) -> None:
        try:
            data = yaml_mod.safe_load(raw_yaml)
        except yaml_mod.YAMLError as exc:
            raise InputValidationError("Malformed YAML") from exc
        if not isinstance(data, dict):
            raise InputValidationError("YAML content is not a mapping")
        try:
            workflow_file = RunsightWorkflowFile.model_validate(data)
        except PydanticValidationError as exc:
            raise InputValidationError(str(exc)) from exc
        if workflow_file.id != workflow_id:
            raise InputValidationError(
                f"embedded workflow id '{workflow_file.id}' does not match requested "
                f"{_workflow_ref(workflow_id)}"
            )

    def _auto_commit(self, message: str, files: list) -> None:
        if not self.git_service:
            return
        if self.git_service.is_clean():
            return  # nothing changed, skip empty commit
        try:
            self.git_service.commit_to_branch("main", files, message)
        except Exception:
            # Creating a workflow should still succeed even when local git state
            # prevents the convenience auto-commit from completing.
            logger.warning("Skipping workflow auto-commit after create", exc_info=True)

    def _get_workflow_commit_sha(self, path: str) -> str | None:
        if self.git_service is None:
            return None
        try:
            branch = self.git_service.current_branch()
        except Exception:
            branch = "main"
        return self.git_service.get_sha(branch, path)

    def _get_workflow_commit_sha_on_main(self, path: str) -> str | None:
        if self.git_service is None:
            return None
        return self.git_service.get_sha("main", path)

    def set_enabled(self, workflow_id: str, enabled: bool) -> WorkflowEntity:
        """Toggle the enabled field for a workflow."""
        return self.workflow_repo.patch_yaml_field(workflow_id, "enabled", enabled)

    def delete_workflow(self, id: str, force: bool = False) -> dict[str, Any]:
        workflow = self.workflow_repo.get_by_id(id)
        if workflow is None:
            raise WorkflowNotFound(f"Workflow {_workflow_ref(id)} not found")

        runs_deleted = self.run_repo.delete_runs_for_workflow(id, force=force)
        success = self.workflow_repo.delete(id)
        if not success:
            raise WorkflowNotFound(f"Workflow {_workflow_ref(id)} not found")
        self._auto_commit(
            f"Delete workflow: {workflow.name if workflow and workflow.name else id}",
            [
                f"custom/workflows/{id}.yaml",
                f"custom/workflows/.canvas/{id}.canvas.json",
            ],
        )
        return {"id": id, "deleted": True, "runs_deleted": runs_deleted}
