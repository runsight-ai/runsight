from __future__ import annotations

import re
from enum import Enum
from typing import NamedTuple


class EntityKind(str, Enum):
    SOUL = "soul"
    WORKFLOW = "workflow"
    TOOL = "tool"
    PROVIDER = "provider"
    ASSERTION = "assertion"


class EntityRef(NamedTuple):
    kind: EntityKind
    id: str

    @property
    def entity_id(self) -> str:
        return self.id

    def __str__(self) -> str:
        return f"{self.kind.value}:{self.id}"


ENTITY_ID_PATTERN = re.compile(r"^[a-z](?:[a-z0-9_-]{1,98})[a-z0-9]$")
RESERVED_IDS = frozenset(
    {"pause", "resume", "kill", "cancel", "status", "http", "file_io", "delegate"}
)


def validate_entity_id(entity_id: str, kind: EntityKind) -> None:
    if not ENTITY_ID_PATTERN.fullmatch(entity_id):
        raise ValueError(
            f"{kind.value} id '{entity_id}' must start with a lowercase letter, "
            "be 3-100 characters long, end with a lowercase letter or digit, "
            "and contain only lowercase letters, digits, underscores, or hyphens."
        )
    if entity_id in RESERVED_IDS:
        raise ValueError(f"{kind.value} id '{entity_id}' is reserved")
