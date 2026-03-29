import uuid
from typing import Any, Dict, List, Optional

from ...data.filesystem.soul_repo import SoulRepository
from ...domain.errors import SoulNotFound
from ...domain.value_objects import SoulEntity


class SoulService:
    def __init__(self, soul_repo: SoulRepository, git_service=None):
        self.soul_repo = soul_repo
        self.git_service = git_service

    def list_souls(self, query: Optional[str] = None) -> List[SoulEntity]:
        souls = self.soul_repo.list_all()
        if query:
            query = query.lower()
            souls = [
                s
                for s in souls
                if query in s.id.lower() or (getattr(s, "name", "") and query in s.name.lower())
            ]
        return souls

    def get_soul(self, id: str) -> Optional[SoulEntity]:
        return self.soul_repo.get_by_id(id)

    def create_soul(self, data: Dict[str, Any]) -> SoulEntity:
        if "id" not in data or not data["id"]:
            data["id"] = f"soul_{uuid.uuid4().hex[:8]}"
        result = self.soul_repo.create(data)
        self._auto_commit(f"Create soul: {result.id}", [result.id])
        return result

    def update_soul(self, id: str, data: Dict[str, Any], copy_on_edit: bool = False) -> SoulEntity:
        existing = self.soul_repo.get_by_id(id)
        if not existing:
            raise SoulNotFound(f"Soul {id} not found")

        if copy_on_edit:
            # Create a new soul with a new ID
            new_id = f"{id}_copy_{uuid.uuid4().hex[:4]}"
            data["id"] = new_id
            return self.soul_repo.create(data)

        result = self.soul_repo.update(id, data)
        self._auto_commit(f"Update soul: {id}", [result.id])
        return result

    def delete_soul(self, id: str) -> bool:
        success = self.soul_repo.delete(id)
        if not success:
            raise SoulNotFound(f"Soul {id} not found")
        self._auto_commit(f"Delete soul: {id}", [id])
        return True

    def _auto_commit(self, message: str, files: list) -> None:
        if not self.git_service:
            return
        if self.git_service.is_clean():
            return  # nothing changed, skip empty commit
        self.git_service.commit_to_branch("main", files, message)
