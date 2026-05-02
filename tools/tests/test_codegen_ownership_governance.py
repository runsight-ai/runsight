"""Smoke governance for OpenAPI codegen ownership.

Owner: tools/tests owns repo-wide codegen tooling ownership checks.
Boundary: packages/shared may expose npm commands, but the codegen scripts stay
in tools/. Generated contract behavior belongs to package-level tests.
Exit criteria: delete this suite once codegen scripts and package wiring are
generated from a single tooling manifest.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_PACKAGE_JSON = REPO_ROOT / "packages" / "shared" / "package.json"

CODEGEN_OWNERSHIP_TARGETS = (
    ("OpenAPI type generator", REPO_ROOT / "tools" / "generate-types.sh", True),
    ("types freshness checker", REPO_ROOT / "tools" / "check-types-fresh.sh", True),
    ("Zod schema generator", REPO_ROOT / "tools" / "generate-zod-schemas.py", False),
    ("OpenAPI snapshot", REPO_ROOT / "openapi.json", False),
)

SHARED_CODEGEN_COMMANDS = {
    "generate:types": "bash ../../tools/generate-types.sh",
    "check:types-fresh": "bash ../../tools/check-types-fresh.sh",
}

pytestmark = pytest.mark.governance


def test_codegen_assets_stay_in_the_tools_workspace() -> None:
    failures: list[str] = []

    for label, path, must_be_executable in CODEGEN_OWNERSHIP_TARGETS:
        if not path.exists():
            failures.append(f"{label} is missing at {path.relative_to(REPO_ROOT)}.")
        elif must_be_executable and not os.access(path, os.X_OK):
            failures.append(f"{label} must be executable: {path.relative_to(REPO_ROOT)}.")

    assert not failures, "\n".join(failures)


def test_shared_package_codegen_commands_point_to_tools() -> None:
    package_json = json.loads(SHARED_PACKAGE_JSON.read_text(encoding="utf-8"))
    scripts = package_json["scripts"]

    for script_name, command in SHARED_CODEGEN_COMMANDS.items():
        assert scripts[script_name] == command

    assert "openapi-typescript" in package_json["devDependencies"]
