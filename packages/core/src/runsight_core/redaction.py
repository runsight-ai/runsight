"""Runtime-only redaction helpers for sensitive workflow inputs."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

REDACTED_VALUE = "[redacted]"


class RunRedactor:
    """Redacts runtime values registered from sensitive workflow inputs."""

    def __init__(self, values: list[object] | None = None) -> None:
        self._values: set[str] = set()
        self._scalar_values: set[tuple[str, str]] = set()
        self._named_values: dict[str, set[str]] = {}
        self._named_scalar_values: dict[str, set[tuple[str, str]]] = {}
        self._structured_named_values: dict[str, object] = {}
        for value in values or []:
            self.register(value)

    def register(self, value: object) -> None:
        """Register non-empty scalar leaves from a JSON-compatible value."""
        for item in self._iter_string_leaves(value):
            if item:
                self._values.add(item)
        for item in self._iter_non_string_scalar_leaves(value):
            self._scalar_values.add(self._scalar_key(item))

    def register_named(self, name: str, value: object) -> None:
        """Register non-empty scalar leaves for one sensitive structured value."""
        named_values = self._named_values.setdefault(name, set())
        named_scalars = self._named_scalar_values.setdefault(name, set())
        if isinstance(value, dict | list | tuple):
            self._structured_named_values[name] = value
            for item in self._iter_non_string_scalar_leaves(value):
                named_scalars.add(self._scalar_key(item))
            leaves = [item for item in self._iter_string_leaves(value) if item]
            if not leaves:
                return
            counts = Counter(leaves)
            if any(count > 1 for count in counts.values()):
                for item, count in counts.items():
                    if count > 1:
                        named_values.add(item)
                return
            for item in leaves:
                named_values.add(item)
            return
        for item in self._iter_string_leaves(value):
            if item:
                named_values.add(item)
        for item in self._iter_non_string_scalar_leaves(value):
            named_scalars.add(self._scalar_key(item))

    def redact(self, value: object) -> Any:
        """Redact exact scalar matches while preserving nested container shape."""
        scope_name = self._structured_scope_for_value(value)
        return self._redact(value, field_name=None, scope_name=scope_name)

    def redact_named(self, name: str, value: object) -> Any:
        """Redact a value using a sensitive workflow input name as its scope."""
        return self._redact(value, field_name=name, scope_name=name)

    def _redact(
        self,
        value: object,
        *,
        field_name: str | None,
        scope_name: str | None,
        strict: bool = False,
    ) -> Any:
        if isinstance(value, str):
            if strict:
                return REDACTED_VALUE if value else value
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
                    strict=(
                        (
                            isinstance(key, str)
                            and key in self._structured_named_values
                            and len(value) > 1
                        )
                        or (strict and isinstance(item, str))
                    ),
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self._redact(
                    item,
                    field_name=None,
                    scope_name=scope_name,
                    strict=strict if isinstance(item, str) else False,
                )
                for item in value
            ]
        if isinstance(value, tuple):
            return tuple(
                self._redact(
                    item,
                    field_name=None,
                    scope_name=scope_name,
                    strict=strict if isinstance(item, str) else False,
                )
                for item in value
            )
        if self._is_sensitive_scalar(value, field_name=field_name, scope_name=scope_name):
            return REDACTED_VALUE
        return value

    def redact_text(self, value: str) -> str:
        """Redact registered values embedded inside runtime text surfaces."""
        redacted = value
        for item in sorted(self._all_values(), key=len, reverse=True):
            redacted = redacted.replace(item, REDACTED_VALUE)
        return redacted

    def redact_runtime_value(self, value: object) -> Any:
        """Redact values before persistence or external emission."""
        scope_name = self._structured_scope_for_value(value)
        return self._redact_runtime_value(
            value,
            field_name=None,
            scope_name=scope_name,
            strict=False,
        )

    def _all_values(self) -> set[str]:
        values = set(self._values)
        values.update(self._scalar_text_values(self._scalar_values))
        for named_values in self._named_values.values():
            values.update(named_values)
        for named_scalars in self._named_scalar_values.values():
            values.update(self._scalar_text_values(named_scalars))
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

    @staticmethod
    def _iter_non_string_scalar_leaves(value: object) -> list[object]:
        if value is None or isinstance(value, str):
            return []
        if isinstance(value, bool | int | float):
            return [value]
        if isinstance(value, dict):
            leaves: list[object] = []
            for item in value.values():
                leaves.extend(RunRedactor._iter_non_string_scalar_leaves(item))
            return leaves
        if isinstance(value, list | tuple):
            leaves = []
            for item in value:
                leaves.extend(RunRedactor._iter_non_string_scalar_leaves(item))
            return leaves
        return []

    @staticmethod
    def _scalar_key(value: object) -> tuple[str, str]:
        if isinstance(value, bool):
            return ("boolean", "true" if value else "false")
        if isinstance(value, int | float):
            return ("number", repr(value))
        return (type(value).__name__, repr(value))

    @staticmethod
    def _scalar_text_values(values: set[tuple[str, str]]) -> set[str]:
        text_values: set[str] = set()
        for value_type, raw_value in values:
            if value_type == "boolean":
                text_values.add("True" if raw_value == "true" else "False")
                text_values.add(raw_value)
                continue
            text_values.add(raw_value)
        return text_values

    def _is_sensitive_scalar(
        self,
        value: object,
        *,
        field_name: str | None,
        scope_name: str | None,
    ) -> bool:
        if value is None or isinstance(value, str | dict | list | tuple):
            return False
        scalar_key = self._scalar_key(value)
        if scalar_key in self._scalar_values:
            return True
        scoped_values = set(self._named_scalar_values.get(field_name or "", set()))
        scoped_values.update(self._named_scalar_values.get(scope_name or "", set()))
        return scalar_key in scoped_values

    def _is_sensitive_runtime_scalar(
        self,
        value: object,
        *,
        field_name: str | None,
        scope_name: str | None,
    ) -> bool:
        if self._is_sensitive_scalar(value, field_name=field_name, scope_name=scope_name):
            return True
        if value is None or isinstance(value, str | dict | list | tuple):
            return False
        scalar_key = self._scalar_key(value)
        return any(
            scalar_key in named_values for named_values in self._named_scalar_values.values()
        )

    @staticmethod
    def _contains_redacted_marker(value: object) -> bool:
        if isinstance(value, str):
            return value == REDACTED_VALUE
        if isinstance(value, dict):
            return any(RunRedactor._contains_redacted_marker(item) for item in value.values())
        if isinstance(value, list | tuple):
            return any(RunRedactor._contains_redacted_marker(item) for item in value)
        return False

    def _redact_runtime_value(
        self,
        value: object,
        *,
        field_name: str | None,
        scope_name: str | None,
        strict: bool,
    ) -> Any:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return REDACTED_VALUE if strict and value else self.redact_text(value)
            if isinstance(parsed, dict | list | tuple):
                parsed_scope = self._structured_scope_for_value(parsed)
                next_strict = strict or self._contains_redacted_marker(parsed)
                return self._redact_runtime_value(
                    parsed,
                    field_name=None,
                    scope_name=parsed_scope if parsed_scope is not None else scope_name,
                    strict=next_strict,
                )
            return REDACTED_VALUE if strict and value else self.redact_text(value)
        if isinstance(value, dict):
            return {
                key: self._redact_runtime_value(
                    item,
                    field_name=key if isinstance(key, str) else None,
                    scope_name=(
                        key
                        if key in self._named_values
                        or key in self._named_scalar_values
                        or key in self._structured_named_values
                        else scope_name
                    ),
                    strict=(
                        (
                            isinstance(key, str)
                            and key in self._structured_named_values
                            and len(value) > 1
                        )
                        or (strict and isinstance(item, str))
                        or self._contains_redacted_marker(item)
                    ),
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self._redact_runtime_value(
                    item,
                    field_name=None,
                    scope_name=scope_name,
                    strict=(strict or self._contains_redacted_marker(item))
                    if isinstance(item, str)
                    else False,
                )
                for item in value
            ]
        if isinstance(value, tuple):
            return tuple(
                self._redact_runtime_value(
                    item,
                    field_name=None,
                    scope_name=scope_name,
                    strict=(strict or self._contains_redacted_marker(item))
                    if isinstance(item, str)
                    else False,
                )
                for item in value
            )
        if self._is_sensitive_runtime_scalar(value, field_name=field_name, scope_name=scope_name):
            return REDACTED_VALUE
        if strict and isinstance(value, str):
            return REDACTED_VALUE if value else value
        if isinstance(value, str):
            scoped_values = set(self._named_values.get(field_name or "", set()))
            scoped_values.update(self._named_values.get(scope_name or "", set()))
            return REDACTED_VALUE if value in self._values or value in scoped_values else value
        return value


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
