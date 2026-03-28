from typing import List, Optional, Dict, Any
from ...data.filesystem.workflow_repo import WorkflowRepository
from ...domain.value_objects import WorkflowEntity
from ...domain.errors import WorkflowNotFound


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

    def _auto_commit(self, message: str, files: list) -> None:
        if not self.git_service:
            return
        self.git_service.commit_to_branch("main", files, message)

    def delete_workflow(self, id: str) -> bool:
        success = self.workflow_repo.delete(id)
        if not success:
            raise WorkflowNotFound(f"Workflow {id} not found")
        return success
