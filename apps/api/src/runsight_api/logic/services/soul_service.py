import uuid
from typing import List, Optional, Dict, Any

from ...data.filesystem.soul_repo import SoulRepository
from ...domain.value_objects import SoulEntity
from ...domain.errors import SoulNotFound


class SoulService:
    def __init__(self, soul_repo: SoulRepository):
        self.soul_repo = soul_repo

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
        return self.soul_repo.create(data)

    def update_soul(self, id: str, data: Dict[str, Any], copy_on_edit: bool = False) -> SoulEntity:
        existing = self.soul_repo.get_by_id(id)
        if not existing:
            raise SoulNotFound(f"Soul {id} not found")

        if copy_on_edit:
            # Create a new soul with a new ID
            new_id = f"{id}_copy_{uuid.uuid4().hex[:4]}"
            data["id"] = new_id
            return self.soul_repo.create(data)

        return self.soul_repo.update(id, data)

    def delete_soul(self, id: str) -> bool:
        success = self.soul_repo.delete(id)
        if not success:
            raise SoulNotFound(f"Soul {id} not found")
        return True
