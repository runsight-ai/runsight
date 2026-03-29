"""Credential reference resolution for process-isolated tool configs (ISO-008)."""

from __future__ import annotations

import os
import re
from typing import Any

_ENV_REF_PATTERN = re.compile(r"\$\{([^}]+)\}")


def resolve_credential_refs(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve ``${ENV_VAR}`` patterns in a credential config dict.

    Recursively walks the dict and replaces every ``${VAR_NAME}`` token with
    the value of the corresponding environment variable.

    Raises:
        ValueError: If a referenced environment variable is not defined.
    """
    return {k: _resolve_value(v) for k, v in config.items()}


def _resolve_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_value(v) for k, v in value.items()}
    if isinstance(value, str):
        return _resolve_string(value)
    return value


def _resolve_string(text: str) -> str:
    def _replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        val = os.environ.get(var_name)
        if val is None:
            raise ValueError(
                f"Undefined environment variable '${{{var_name}}}': {var_name} is not set"
            )
        return val

    return _ENV_REF_PATTERN.sub(_replacer, text)
