from ...domain.errors import SoulNotFound
from ...domain.value_objects import SoulEntity
from ._base_yaml_repo import BaseYamlRepository


class SoulRepository(BaseYamlRepository[SoulEntity]):
    entity_type = SoulEntity
    root_dir = "custom"
    subdir = "souls"
    not_found_error = SoulNotFound
    entity_label = "Soul"

    @property
    def souls_dir(self):
        """Backward-compat alias for entity_dir."""
        return self.entity_dir
