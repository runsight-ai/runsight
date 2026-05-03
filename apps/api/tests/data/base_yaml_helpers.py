"""Fixture builders for BaseYamlRepository tests."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from runsight_api.data.filesystem._base_yaml_repo import BaseYamlRepository
from runsight_api.domain.errors import RunsightError

MALFORMED_YAML = ":\n  - :\n    invalid: [unclosed"


class DummyEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "allow"}


class DummyNotFound(RunsightError):
    pass


class DummyRepository(BaseYamlRepository[DummyEntity]):
    entity_type = DummyEntity
    subdir = "dummies"
    not_found_error = DummyNotFound
    entity_label = "Dummy"


class StrictDummyEntity(BaseModel):
    id: str
    name: Optional[str] = None
    model_config = {"extra": "forbid"}


class StrictDummyRepository(BaseYamlRepository[StrictDummyEntity]):
    entity_type = StrictDummyEntity
    subdir = "strict-dummies"
    not_found_error = DummyNotFound
    entity_label = "StrictDummy"


def write_yaml_payload(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload))
