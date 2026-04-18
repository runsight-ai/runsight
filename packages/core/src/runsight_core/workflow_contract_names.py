"""Validation helpers for workflow public contract names."""

from __future__ import annotations

import re
from collections.abc import Iterable

WORKFLOW_CONTRACT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

RESERVED_WORKFLOW_CONTRACT_NAMES = frozenset(
    {
        "workflow",
        "results",
        "shared_memory",
        "metadata",
        "blocks",
        "ctx",
        "call_stack",
        "workflow_registry",
        "observer",
    }
)


def validate_workflow_contract_name(name: str) -> str:
    """Return a valid workflow contract name unchanged."""
    if not isinstance(name, str):
        raise ValueError("workflow contract name must be a string")
    if WORKFLOW_CONTRACT_NAME_PATTERN.fullmatch(name) is None:
        raise ValueError(
            "workflow contract name must match '^[a-z][a-z0-9_]{0,63}$' without normalization"
        )
    if name in RESERVED_WORKFLOW_CONTRACT_NAMES:
        raise ValueError(f"workflow contract name is reserved: {name!r}")
    return name


def validate_workflow_contract_names(names: Iterable[str]) -> list[str]:
    """Validate a collection of workflow contract names and reject duplicates."""
    validated: list[str] = []
    seen: set[str] = set()
    for name in names:
        validated_name = validate_workflow_contract_name(name)
        if validated_name in seen:
            raise ValueError(f"duplicate workflow contract name: {validated_name!r}")
        seen.add(validated_name)
        validated.append(validated_name)
    return validated
