"""Runtime-only redaction helpers for sensitive workflow inputs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

REDACTED_VALUE = "[redacted]"


class RunRedactor:
    """Redacts runtime values registered from sensitive workflow inputs."""

    def __init__(self, values: list[object] | None = None) -> None:
        self._values: set[str] = set()
        self._named_values: dict[str, set[str]] = {}
        self._structured_named_values: dict[str, object] = {}
        for value in values or []:
            self.register(value)

    def register(self, value: object) -> None:
        """Register non-empty string leaves from a JSON-compatible value."""
        for item in self._iter_string_leaves(value):
            if item:
                self._values.add(item)

    def register_named(self, name: str, value: object) -> None:
        """Register non-empty string leaves for one sensitive structured value."""
        named_values = self._named_values.setdefault(name, set())
        if isinstance(value, dict | list | tuple):
            self._structured_named_values[name] = value
            counts = Counter(self._iter_string_leaves(value))
            for item, count in counts.items():
                if item and count > 1:
                    named_values.add(item)
            return
        for item in self._iter_string_leaves(value):
            if item:
                named_values.add(item)

    def redact(self, value: object) -> Any:
        """Redact exact scalar matches while preserving nested container shape."""
        scope_name = self._structured_scope_for_value(value)
        return self._redact(value, field_name=None, scope_name=scope_name)

    def _redact(
        self,
        value: object,
        *,
        field_name: str | None,
        scope_name: str | None,
    ) -> Any:
        if isinstance(value, str):
            scoped_values = set(self._named_values.get(field_name or "", set()))
            scoped_values.update(self._named_values.get(scope_name or "", set()))
            return REDACTED_VALUE if value in self._values or value in scoped_values else value
        if isinstance(value, dict):
            next_scope = (
                field_name
                if field_name in self._named_values or field_name in self._structured_named_values
                else scope_name
            )
            return {
                key: self._redact(
                    item,
                    field_name=key if isinstance(key, str) else None,
                    scope_name=next_scope,
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact(item, field_name=None, scope_name=scope_name) for item in value]
        if isinstance(value, tuple):
            return tuple(
                self._redact(item, field_name=None, scope_name=scope_name) for item in value
            )
        return value

    def redact_text(self, value: str) -> str:
        """Redact registered values embedded inside runtime text surfaces."""
        redacted = value
        for item in sorted(self._all_values(), key=len, reverse=True):
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

    def _all_values(self) -> set[str]:
        values = set(self._values)
        for named_values in self._named_values.values():
            values.update(named_values)
        return values

    def _structured_scope_for_value(self, value: object) -> str | None:
        if not isinstance(value, dict | list | tuple):
            return None
        for name, structured_value in self._structured_named_values.items():
            if value == structured_value:
                return name
        return None

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
