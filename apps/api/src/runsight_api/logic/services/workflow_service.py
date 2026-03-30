from typing import Any, Dict, List, Optional

from ...data.filesystem.workflow_repo import WorkflowRepository
from ...domain.errors import WorkflowNotFound
from ...domain.value_objects import WorkflowEntity


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
        result = self.workflow_repo.update(id, data)
        self._auto_commit(f"Update workflow: {result.name}", [result.id])
        return result

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
        self.git_service.commit_to_branch("main", files, message)

    def delete_workflow(self, id: str) -> bool:
        success = self.workflow_repo.delete(id)
        if not success:
            raise WorkflowNotFound(f"Workflow {id} not found")
        return success
