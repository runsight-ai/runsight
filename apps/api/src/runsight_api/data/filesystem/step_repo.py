from ...domain.errors import StepNotFound
from ...domain.value_objects import StepEntity
from ._base_yaml_repo import BaseYamlRepository


class StepRepository(BaseYamlRepository[StepEntity]):
    entity_type = StepEntity
    subdir = "steps"
    not_found_error = StepNotFound
    entity_label = "Step"

    @property
    def steps_dir(self):
        """Backward-compat alias for entity_dir."""
        return self.entity_dir
