from ...domain.errors import TaskNotFound
from ...domain.value_objects import TaskEntity
from ._base_yaml_repo import BaseYamlRepository


class TaskRepository(BaseYamlRepository[TaskEntity]):
    entity_type = TaskEntity
    subdir = "tasks"
    not_found_error = TaskNotFound
    entity_label = "Task"
