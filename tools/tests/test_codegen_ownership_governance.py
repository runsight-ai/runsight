"""
Repo tooling governance for OpenAPI type generation.

Owner: tools/tests owns repo-wide codegen tooling checks that scan scripts,
docs, and package metadata across workspaces.
Boundary: package tests verify committed generated contracts; repo tooling tests
verify the scripts, package wiring, and contributor-facing governance text.
Exit criteria: delete this suite once codegen scripts and docs are generated
from a single tooling manifest.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_PACKAGE_JSON = REPO_ROOT / "packages" / "shared" / "package.json"
GENERATE_TYPES_SCRIPT = REPO_ROOT / "tools" / "generate-types.sh"
CHECK_TYPES_FRESH_SCRIPT = REPO_ROOT / "tools" / "check-types-fresh.sh"
ZOD_GENERATOR_SCRIPT = REPO_ROOT / "tools" / "generate-zod-schemas.py"
OPENAPI_SNAPSHOT = REPO_ROOT / "openapi.json"
CONTEXT_GOVERNANCE_DOC = (
    REPO_ROOT
    / "apps"
    / "site"
    / "src"
    / "content"
    / "docs"
    / "docs"
    / "workflows"
    / "context-governance.mdx"
)


def test_repo_codegen_scripts_and_snapshot_are_present() -> None:
    assert GENERATE_TYPES_SCRIPT.exists()
    assert os.access(GENERATE_TYPES_SCRIPT, os.X_OK)
    assert CHECK_TYPES_FRESH_SCRIPT.exists()
    assert OPENAPI_SNAPSHOT.exists()


def test_shared_package_wires_codegen_commands_to_tools_workspace() -> None:
    package_json = json.loads(SHARED_PACKAGE_JSON.read_text(encoding="utf-8"))

    assert package_json["scripts"]["generate:types"] == "bash ../../tools/generate-types.sh"
    assert package_json["scripts"]["check:types-fresh"] == "bash ../../tools/check-types-fresh.sh"
    assert "openapi-typescript" in package_json["devDependencies"]


def test_generate_types_script_does_not_append_runtime_components_shim() -> None:
    script_source = GENERATE_TYPES_SCRIPT.read_text(encoding="utf-8")

    assert not re.search(r"export const components\s*=\s*\{\s*\};", script_source)


def test_context_governance_docs_do_not_expose_all_access_mode() -> None:
    docs_source = CONTEXT_GOVERNANCE_DOC.read_text(encoding="utf-8")

    assert "access: all" not in docs_source
    assert "all_access" not in docs_source


def test_zod_generator_emits_bare_literals_for_single_value_non_string_enums(
    tmp_path: Path,
) -> None:
    openapi_path = tmp_path / "openapi.json"
    generated_zod_path = tmp_path / "zod.ts"
    openapi_path.write_text(
        json.dumps(
            {
                "openapi": "3.1.0",
                "info": {"title": "enum fixture", "version": "1.0.0"},
                "paths": {},
                "components": {
                    "schemas": {
                        "SingleNumberEnum": {"type": "integer", "enum": [1]},
                        "SingleBooleanEnum": {"type": "boolean", "enum": [True]},
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ZOD_GENERATOR_SCRIPT),
            str(openapi_path),
            str(generated_zod_path),
        ],
        cwd=REPO_ROOT,
        check=True,
    )

    generated_zod = generated_zod_path.read_text(encoding="utf-8")
    assert "SingleNumberEnumSchema = z.literal(1)" in generated_zod
    assert "SingleBooleanEnumSchema = z.literal(true)" in generated_zod
    assert "z.union([z.literal(1)])" not in generated_zod
    assert "z.union([z.literal(true)])" not in generated_zod
