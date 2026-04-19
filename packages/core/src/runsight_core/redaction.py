"""Runtime-only redaction helpers for sensitive workflow inputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REDACTED_VALUE = "[redacted]"


class RunRedactor:
    """Redacts runtime values registered from sensitive workflow inputs."""

    def __init__(self, values: list[object] | None = None) -> None:
        self._values: set[str] = set()
        for value in values or []:
            self.register(value)

    def register(self, value: object) -> None:
        """Register non-empty string leaves from a JSON-compatible value."""
        for item in self._iter_string_leaves(value):
            if item:
                self._values.add(item)

    def redact(self, value: object) -> Any:
        """Redact exact scalar matches while preserving nested container shape."""
        if isinstance(value, str):
            return REDACTED_VALUE if value in self._values else value
        if isinstance(value, dict):
            return {key: self.redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact(item) for item in value)
        return value

    def redact_text(self, value: str) -> str:
        """Redact registered values embedded inside runtime text surfaces."""
        redacted = value
        for item in sorted(self._values, key=len, reverse=True):
            redacted = redacted.replace(item, REDACTED_VALUE)
        return redacted

    def redact_runtime_value(self, value: object) -> Any:
        """Redact values before persistence or external emission."""
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, dict):
            return {key: self.redact_runtime_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.redact_runtime_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact_runtime_value(item) for item in value)
        return value

    @staticmethod
    def _iter_string_leaves(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            leaves: list[str] = []
            for item in value.values():
                leaves.extend(RunRedactor._iter_string_leaves(item))
            return leaves
        if isinstance(value, list | tuple):
            leaves = []
            for item in value:
                leaves.extend(RunRedactor._iter_string_leaves(item))
            return leaves
        return []


SensitiveValueRedactor = RunRedactor


@dataclass(slots=True)
class RedactionContext:
    """Runtime-only redaction context carried alongside workflow state."""

    redactor: RunRedactor = field(default_factory=RunRedactor)

    @classmethod
    def from_values(cls, values: list[object]) -> "RedactionContext":
        redactor = RunRedactor()
        for value in values:
            redactor.register(value)
        return cls(redactor=redactor)


def redactor_from_state(state: object | None) -> RunRedactor | None:
    redactor = getattr(state, "input_redactor", None)
    return redactor if isinstance(redactor, RunRedactor) else None


def redact_text_for_state(value: str, state: object | None) -> str:
    redactor = redactor_from_state(state)
    return redactor.redact_text(value) if redactor is not None else value


def redact_runtime_value_for_state(value: object, state: object | None) -> Any:
    redactor = redactor_from_state(state)
    return redactor.redact_runtime_value(value) if redactor is not None else value
