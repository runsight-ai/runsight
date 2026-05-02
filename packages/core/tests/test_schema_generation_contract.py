"""
JSON schema publishing and validation behavior.

Tests exercise the Pydantic schema models from runsight_core.yaml.schema,
covering:
- Type discrimination (correct type -> correct model, wrong fields rejected)
- output_conditions validation (operators, case_id, empty lists)
- inputs validation (from path structure)
- extra="forbid" enforcement on every block type
- JSON schema generation script in --check mode
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pydantic import TypeAdapter
from runsight_core.yaml.schema import (
    BlockDef,
)

# Shared TypeAdapter for the discriminated union
block_adapter = TypeAdapter(BlockDef)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_block(data: dict):
    """Validate a dict as a BlockDef via the discriminated union."""
    return block_adapter.validate_python(data)


# ===========================================================================
# 1. Type discrimination tests
# ===========================================================================


class TestSchemaGenerationScript:
    """Test the generate_schema.py script in --check mode."""

    SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_schema.py"
    SCHEMA_PATH = Path(__file__).resolve().parent.parent / "runsight-workflow-schema.json"

    def test_check_passes_when_in_sync(self):
        """--check should exit 0 when the schema file matches."""
        result = subprocess.run(
            [sys.executable, str(self.SCRIPT_PATH), "--check"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "OK" in result.stdout

    def test_schema_file_exists(self):
        """The schema file should exist after generation."""
        assert self.SCHEMA_PATH.exists(), f"{self.SCHEMA_PATH} not found"

    def test_schema_is_valid_json(self):
        """The schema file must be valid JSON."""
        content = self.SCHEMA_PATH.read_text()
        schema = json.loads(content)
        assert "$defs" in schema or "properties" in schema
