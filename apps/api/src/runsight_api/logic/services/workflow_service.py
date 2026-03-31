from typing import Any, Dict, List, Optional
import logging

from ...data.filesystem.workflow_repo import WorkflowRepository
from ...domain.errors import WorkflowNotFound
from ...domain.value_objects import WorkflowEntity

logger = logging.getLogger(__name__)


class WorkflowService:
    def __init__(self, workflow_repo: WorkflowRepository, git_service=None):
        self.workflow_repo = workflow_repo
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
        return workflows

    def get_workflow(self, id: str) -> Optional[WorkflowEntity]:
        return self.workflow_repo.get_by_id(id)

    def create_workflow(self, data: Dict[str, Any]) -> WorkflowEntity:
        result = self.workflow_repo.create(data)
        self._auto_commit(f"Create workflow: {result.name}", [result.id])
        return result

    def update_workflow(self, id: str, data: Dict[str, Any]) -> WorkflowEntity:
        return self.workflow_repo.update(id, data)

    def commit_workflow(
        self,
        workflow_id: str,
        draft: Dict[str, Any],
        message: str,
    ) -> Dict[str, str]:
        if self.git_service is None:
            raise RuntimeError("Git service not configured")

        previous = self.workflow_repo.get_by_id(workflow_id)
        self.workflow_repo.update(workflow_id, draft)

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

        yaml_path = f"custom/workflows/{workflow_id}.yaml"
        result = self.git_service.create_sim_branch(
            workflow_slug=workflow_id,
            yaml_content=yaml,
            yaml_path=yaml_path,
        )
        return {"branch": result.branch, "commit_sha": result.sha}

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

    def delete_workflow(self, id: str) -> bool:
        success = self.workflow_repo.delete(id)
        if not success:
            raise WorkflowNotFound(f"Workflow {id} not found")
        return success
