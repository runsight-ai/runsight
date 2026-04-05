from ...domain.errors import SoulNotFound
from ...domain.value_objects import SoulEntity
from ._base_yaml_repo import BaseYamlRepository


class SoulRepository(BaseYamlRepository[SoulEntity]):
    entity_type = SoulEntity
    root_dir = "custom"
    subdir = "souls"
    not_found_error = SoulNotFound
    entity_label = "Soul"

    def get_file_mtime(self, soul_id: str) -> float | None:
        yaml_path = self._resolve_existing_path(soul_id)
        if not yaml_path.exists():
            return None
        return yaml_path.stat().st_mtime
