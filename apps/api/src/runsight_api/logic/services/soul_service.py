import uuid
from typing import Any, Dict, List, Optional

import yaml

from ...data.filesystem.soul_repo import SoulRepository
from ...domain.errors import SoulAlreadyExists, SoulInUse, SoulNotFound
from ...domain.value_objects import SoulEntity, WorkflowEntity


class SoulService:
    def __init__(self, soul_repo: SoulRepository, git_service=None):
        self.soul_repo = soul_repo
        self.git_service = git_service

    @staticmethod
    def _soul_file_path(id: str) -> str:
        return f"custom/souls/{id}.yaml"

    @staticmethod
    def _extract_workflow_soul_ids(workflow: WorkflowEntity) -> List[str]:
        if not workflow.yaml:
            return []
        try:
            data = yaml.safe_load(workflow.yaml) or {}
        except Exception:
            return []

        souls_section = data.get("souls", {}) or {}
        if not isinstance(souls_section, dict):
            return []

        soul_ids: List[str] = []
        for value in souls_section.values():
            if isinstance(value, dict):
                soul_id = value.get("id")
                if isinstance(soul_id, str):
                    soul_ids.append(soul_id)
        return soul_ids

    def list_souls(self, query: Optional[str] = None, workflow_repo=None) -> List[SoulEntity]:
        souls = self.soul_repo.list_all()
        if query:
            query = query.lower()
            souls = [
                s for s in souls if query in s.id.lower() or (s.role and query in s.role.lower())
            ]
        if workflow_repo:
            counts = self._compute_workflow_counts(souls, workflow_repo)
            souls = [
                soul.model_copy(update={"workflow_count": counts.get(soul.id, 0)}) for soul in souls
            ]
        return souls

    def get_soul(self, id: str) -> Optional[SoulEntity]:
        return self.soul_repo.get_by_id(id)

    def get_soul_usages(self, id: str, workflow_repo) -> List[Dict[str, Optional[str]]]:
        soul = self.get_soul(id)
        if not soul:
            raise SoulNotFound(f"Soul {id} not found")
        return self._get_workflow_soul_refs(id, workflow_repo)

    def _get_workflow_soul_refs(
        self, soul_id: str, workflow_repo
    ) -> List[Dict[str, Optional[str]]]:
        usages: List[Dict[str, Optional[str]]] = []
        for workflow in workflow_repo.list_all():
            if soul_id in self._extract_workflow_soul_ids(workflow):
                usages.append({"workflow_id": workflow.id, "workflow_name": workflow.name})
        return usages

    def _compute_workflow_counts(self, souls: List[SoulEntity], workflow_repo) -> Dict[str, int]:
        counts = {soul.id: 0 for soul in souls}
        if not counts:
            return counts

        for workflow in workflow_repo.list_all():
            for soul_id in self._extract_workflow_soul_ids(workflow):
                if soul_id in counts:
                    counts[soul_id] += 1
        return counts

    def create_soul(self, data: Dict[str, Any]) -> SoulEntity:
        if "id" not in data or not data["id"]:
            data["id"] = f"soul_{uuid.uuid4().hex[:8]}"
        if self.soul_repo.get_by_id(data["id"]):
            raise SoulAlreadyExists(f"Soul {data['id']} already exists")
        result = self.soul_repo.create(data)
        self._auto_commit(f"Create {result.id}.yaml", [self._soul_file_path(result.id)])
        return result

    def update_soul(self, id: str, data: Dict[str, Any], copy_on_edit: bool = False) -> SoulEntity:
        existing = self.soul_repo.get_by_id(id)
        if not existing:
            raise SoulNotFound(f"Soul {id} not found")

        if copy_on_edit:
            # Create a new soul with a new ID
            new_id = f"{id}_copy_{uuid.uuid4().hex[:4]}"
            data["id"] = new_id
            result = self.soul_repo.create(data)
            self._auto_commit(f"Create {result.id}.yaml", [self._soul_file_path(result.id)])
            return result

        merged = existing.model_dump(exclude={"workflow_count"})
        merged.update(data)
        result = self.soul_repo.update(id, merged)
        self._auto_commit(f"Update {id}.yaml", [self._soul_file_path(id)])
        return result

    def delete_soul(self, id: str, force: bool = False, workflow_repo=None) -> bool:
        soul = self.get_soul(id)
        if not soul:
            raise SoulNotFound(f"Soul {id} not found")

        if workflow_repo and not force:
            usages = self._get_workflow_soul_refs(id, workflow_repo)
            if usages:
                raise SoulInUse(
                    f"Soul {id!r} is referenced by {len(usages)} workflow(s)",
                    details={"usages": usages},
                )

        success = self.soul_repo.delete(id)
        if not success:
            raise SoulNotFound(f"Soul {id} not found")
        self._auto_commit(f"Delete {id}.yaml", [self._soul_file_path(id)])
        return True

    def _auto_commit(self, message: str, files: list) -> None:
        if not self.git_service:
            return
        if self.git_service.is_clean():
            return  # nothing changed, skip empty commit
        self.git_service.commit_to_branch("main", files, message)
