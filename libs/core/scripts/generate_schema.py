#!/usr/bin/env python3
"""
Generate the Runsight Workflow JSON Schema from Pydantic models.

Usage:
    python scripts/generate_schema.py          # Write schema to disk
    python scripts/generate_schema.py --check  # CI mode: exit 1 if out of sync
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Resolve output path relative to this script's parent (libs/core/)
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "runsight-workflow-schema.json"


def generate_schema() -> str:
    """Return the JSON Schema string for RunsightWorkflowFile."""
    from runsight_core.yaml.schema import RunsightWorkflowFile

    schema = RunsightWorkflowFile.model_json_schema()
    return json.dumps(schema, indent=2) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Runsight Workflow JSON Schema")
    parser.add_argument(
        "--check",
        action="store_true",
        help="CI mode: compare generated schema with existing file, exit 1 if out of sync",
    )
    args = parser.parse_args()

    generated = generate_schema()

    if args.check:
        if not SCHEMA_PATH.exists():
            print(f"FAIL: {SCHEMA_PATH} does not exist. Run without --check to generate it.")
            sys.exit(1)
        existing = SCHEMA_PATH.read_text()
        if existing != generated:
            print(f"FAIL: {SCHEMA_PATH} is out of sync with schema models.")
            print("Run `python scripts/generate_schema.py` to regenerate.")
            sys.exit(1)
        print(f"OK: {SCHEMA_PATH} is up to date.")
    else:
        SCHEMA_PATH.write_text(generated)
        print(f"Schema written to {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
