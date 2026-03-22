"""SecretsEnvLoader — read/write .runsight/secrets.env for managed API key storage.

Resolution order: os.environ → secrets.env → None.
"""

from __future__ import annotations

import os
from pathlib import Path

from runsight_api.data.filesystem._utils import atomic_write

_HEADER = "# Managed by Runsight"


def _strip_ref(ref: str) -> str:
    """Strip ${...} wrapper from an env var reference, returning the bare name."""
    if ref.startswith("${") and ref.endswith("}"):
        return ref[2:-1]
    return ref


class SecretsEnvLoader:
    """Reads and writes .runsight/secrets.env for managed API key storage."""

    def __init__(self, base_path: str) -> None:
        self._secrets_path = Path(base_path) / ".runsight" / "secrets.env"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, ref: str) -> str | None:
        """Resolve an env var reference.  os.environ wins over secrets.env."""
        var_name = _strip_ref(ref)

        # 1. Real env var
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val

        # 2. secrets.env
        file_vals = self._read_file()
        return file_vals.get(var_name)

    def store_key(self, provider_type: str, api_key: str) -> str:
        """Write a key to secrets.env and return the ${ENV_VAR} reference."""
        var_name = f"{provider_type.upper()}_API_KEY"

        entries = self._read_file()
        entries[var_name] = api_key
        self._write_file(entries)

        return f"${{{var_name}}}"

    def remove_key(self, ref: str) -> None:
        """Remove a key from secrets.env.  No-op if missing."""
        if not self._secrets_path.exists():
            return

        var_name = _strip_ref(ref)
        entries = self._read_file()

        if var_name not in entries:
            return

        del entries[var_name]
        self._write_file(entries)

    def is_configured(self, ref: str) -> bool:
        """Return True if the key is resolvable from env or secrets.env."""
        return self.resolve(ref) is not None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_file(self) -> dict[str, str]:
        """Parse secrets.env into a {KEY: VALUE} dict."""
        if not self._secrets_path.exists():
            return {}

        entries: dict[str, str] = {}
        for line in self._secrets_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, _, value = stripped.partition("=")
            if key:
                entries[key] = value
        return entries

    def _write_file(self, entries: dict[str, str]) -> None:
        """Serialize entries to secrets.env with atomic write."""
        self._secrets_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [_HEADER]
        for key, value in entries.items():
            lines.append(f"{key}={value}")
        lines.append("")  # trailing newline

        atomic_write(self._secrets_path, "\n".join(lines))
