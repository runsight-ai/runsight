"""
RUN-134: Type contract codegen — Pydantic -> OpenAPI -> TypeScript + Zod

Red-team tests: these MUST fail until the codegen pipeline is implemented.

Tests cover:
  1. OpenAPI spec can be extracted from FastAPI app
  2. OpenAPI spec contains schemas for workflow, run, soul, step, block entities
  3. A codegen script exists and is executable
  4. Generated TypeScript types file exists at expected path
  5. CI freshness check script exists
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]  # apps/api/tests -> repo root
API_ROOT = REPO_ROOT / "apps" / "api"
SHARED_ROOT = REPO_ROOT / "packages" / "shared"
GENERATED_TYPES_DIR = SHARED_ROOT / "src"


# ---------------------------------------------------------------------------
# 1. OpenAPI spec extraction
# ---------------------------------------------------------------------------

class TestOpenAPISpecExtraction:
    """The FastAPI app should expose an OpenAPI spec that codegen can consume."""

    def test_openapi_json_endpoint_exists(self):
        """GET /openapi.json should return a valid OpenAPI 3.x spec."""
        from fastapi.testclient import TestClient
        from runsight_api.main import app

        client = TestClient(app)
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert "openapi" in spec
        assert spec["openapi"].startswith("3.")

    def test_openapi_spec_contains_workflow_schemas(self):
        """The spec must include WorkflowResponse, WorkflowCreate, WorkflowUpdate schemas."""
        from runsight_api.main import app

        spec = app.openapi()
        schema_names = set(spec.get("components", {}).get("schemas", {}).keys())
        for expected in ["WorkflowResponse", "WorkflowCreate", "WorkflowUpdate"]:
            assert expected in schema_names, f"Missing schema: {expected}"

    def test_openapi_spec_contains_run_schemas(self):
        """The spec must include RunResponse, RunCreate, RunNodeResponse schemas."""
        from runsight_api.main import app

        spec = app.openapi()
        schema_names = set(spec.get("components", {}).get("schemas", {}).keys())
        for expected in ["RunResponse", "RunCreate", "RunNodeResponse"]:
            assert expected in schema_names, f"Missing schema: {expected}"

    def test_openapi_spec_contains_soul_schemas(self):
        """The spec must include SoulResponse, SoulCreate, SoulUpdate schemas."""
        from runsight_api.main import app

        spec = app.openapi()
        schema_names = set(spec.get("components", {}).get("schemas", {}).keys())
        for expected in ["SoulResponse", "SoulCreate", "SoulUpdate"]:
            assert expected in schema_names, f"Missing schema: {expected}"

    def test_openapi_spec_contains_step_schemas(self):
        """The spec must include StepEntity or equivalent step schemas."""
        from runsight_api.main import app

        spec = app.openapi()
        schema_names = set(spec.get("components", {}).get("schemas", {}).keys())
        step_schemas = [s for s in schema_names if "step" in s.lower()]
        assert len(step_schemas) > 0, f"No step-related schemas found. Have: {schema_names}"


# ---------------------------------------------------------------------------
# 2. Codegen script existence and structure
# ---------------------------------------------------------------------------

class TestCodegenScriptExists:
    """A script/command must exist to regenerate TypeScript types from OpenAPI."""

    def test_codegen_script_exists(self):
        """tools/generate-types.sh (or similar) must exist at repo root."""
        candidates = [
            REPO_ROOT / "tools" / "generate-types.sh",
            REPO_ROOT / "tools" / "generate-types.ts",
            REPO_ROOT / "tools" / "codegen.sh",
        ]
        found = [p for p in candidates if p.exists()]
        assert found, (
            f"No codegen script found. Checked: {[str(p) for p in candidates]}"
        )

    def test_codegen_script_is_executable(self):
        """The codegen script must have executable permissions."""
        script = REPO_ROOT / "tools" / "generate-types.sh"
        assert script.exists(), f"{script} does not exist"
        assert os.access(script, os.X_OK), f"{script} is not executable"

    def test_shared_package_json_has_codegen_script(self):
        """packages/shared/package.json must have a 'generate:types' script."""
        pkg_json = SHARED_ROOT / "package.json"
        assert pkg_json.exists()
        pkg = json.loads(pkg_json.read_text())
        scripts = pkg.get("scripts", {})
        assert "generate:types" in scripts, (
            f"Missing 'generate:types' script in package.json. "
            f"Current scripts: {list(scripts.keys())}"
        )

    def test_openapi_typescript_is_a_dev_dependency(self):
        """packages/shared must own the openapi-typescript dependency."""
        pkg_json = SHARED_ROOT / "package.json"
        assert pkg_json.exists()
        pkg = json.loads(pkg_json.read_text())
        dev_deps = pkg.get("devDependencies", {})
        assert "openapi-typescript" in dev_deps, (
            f"Missing 'openapi-typescript' in devDependencies. "
            f"Current devDeps: {list(dev_deps.keys())}"
        )


# ---------------------------------------------------------------------------
# 3. Generated types file existence and content
# ---------------------------------------------------------------------------

class TestGeneratedTypesExist:
    """Generated TypeScript + Zod files must exist at the expected location."""

    def test_generated_types_directory_has_generated_files(self):
        """packages/shared/src/ must contain generated .ts files (not just test scaffolding)."""
        assert GENERATED_TYPES_DIR.is_dir(), (
            f"Generated types directory does not exist: {GENERATED_TYPES_DIR}"
        )
        ts_files = [
            f for f in GENERATED_TYPES_DIR.iterdir()
            if f.suffix == ".ts" and f.name != "__tests__"
        ]
        assert len(ts_files) > 0, (
            f"Generated types directory exists but contains no .ts files: {GENERATED_TYPES_DIR}"
        )

    def test_generated_openapi_types_file_exists(self):
        """A generated .ts file with OpenAPI types must exist."""
        candidates = [
            GENERATED_TYPES_DIR / "api.ts",
            GENERATED_TYPES_DIR / "openapi.ts",
            GENERATED_TYPES_DIR / "schema.ts",
            GENERATED_TYPES_DIR / "index.ts",
        ]
        found = [p for p in candidates if p.exists()]
        assert found, (
            f"No generated types file found in {GENERATED_TYPES_DIR}. "
            f"Checked: {[p.name for p in candidates]}"
        )

    def test_generated_types_contain_workflow_interface(self):
        """Generated types must define WorkflowResponse interface/type."""
        gen_file = GENERATED_TYPES_DIR / "api.ts"
        assert gen_file.exists(), f"{gen_file} does not exist yet"
        content = gen_file.read_text()
        assert "WorkflowResponse" in content, (
            "Generated types file does not contain WorkflowResponse"
        )

    def test_generated_types_contain_run_interface(self):
        """Generated types must define RunResponse interface/type."""
        gen_file = GENERATED_TYPES_DIR / "api.ts"
        assert gen_file.exists(), f"{gen_file} does not exist yet"
        content = gen_file.read_text()
        assert "RunResponse" in content, (
            "Generated types file does not contain RunResponse"
        )

    def test_generated_types_contain_soul_interface(self):
        """Generated types must define SoulResponse interface/type."""
        gen_file = GENERATED_TYPES_DIR / "api.ts"
        assert gen_file.exists(), f"{gen_file} does not exist yet"
        content = gen_file.read_text()
        assert "SoulResponse" in content, (
            "Generated types file does not contain SoulResponse"
        )

    def test_generated_zod_schemas_file_exists(self):
        """A generated Zod schemas file must exist alongside the TS types."""
        candidates = [
            GENERATED_TYPES_DIR / "zod.ts",
            GENERATED_TYPES_DIR / "schemas.ts",
            GENERATED_TYPES_DIR / "api.zod.ts",
        ]
        found = [p for p in candidates if p.exists()]
        assert found, (
            f"No generated Zod schemas file found in {GENERATED_TYPES_DIR}. "
            f"Checked: {[p.name for p in candidates]}"
        )


# ---------------------------------------------------------------------------
# 4. CI freshness check
# ---------------------------------------------------------------------------

class TestCIFreshnessCheck:
    """A CI script must exist that regenerates types and diffs to catch drift."""

    def test_ci_check_script_exists(self):
        """A CI check script for type freshness must exist."""
        candidates = [
            REPO_ROOT / "tools" / "check-types-fresh.sh",
            REPO_ROOT / "tools" / "ci-check-types.sh",
            REPO_ROOT / ".github" / "workflows" / "check-types.yml",
            REPO_ROOT / ".github" / "workflows" / "codegen.yml",
        ]
        found = [p for p in candidates if p.exists()]
        assert found, (
            f"No CI type-check script/workflow found. "
            f"Checked: {[str(p) for p in candidates]}"
        )

    def test_openapi_spec_snapshot_exists(self):
        """A committed openapi.json snapshot must exist for CI diffing."""
        candidates = [
            REPO_ROOT / "openapi.json",
            API_ROOT / "openapi.json",
            REPO_ROOT / "schemas" / "openapi.json",
        ]
        found = [p for p in candidates if p.exists()]
        assert found, (
            f"No committed openapi.json snapshot found. "
            f"Checked: {[str(p) for p in candidates]}"
        )
