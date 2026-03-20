"""
RED tests for RUN-203: Migrate API test files + regenerate JSON schema + final cleanup.

Verifies that:
1. The JSON schema file does NOT contain PlaceholderBlockDef or "placeholder" block type
2. API test files do NOT contain `type: placeholder` or `PlaceholderBlock` string references
3. libs/core/tests/test_debate_messagebus_removal.py does NOT reference PlaceholderBlock
4. The entire codebase (excluding RUN-201 removal test and this file) has zero
   PlaceholderBlock / PlaceholderBlockDef / _build_placeholder references

These tests FAIL against the current codebase and PASS once Green Team completes
the migration and cleanup.
"""

import json
import pathlib
import subprocess

import pytest


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
CORE_ROOT = REPO_ROOT / "libs" / "core"
API_TESTS = REPO_ROOT / "apps" / "api" / "tests"
JSON_SCHEMA = CORE_ROOT / "runsight-workflow-schema.json"

# Files that are ALLOWED to mention PlaceholderBlock (removal verification tests)
EXCLUSIONS = {
    # RUN-201 removal test (verifies PlaceholderBlock was removed from core)
    str(CORE_ROOT / "tests" / "test_remove_placeholder_block.py"),
    # RUN-205 frontend removal test
    str(
        REPO_ROOT
        / "apps"
        / "gui"
        / "src"
        / "features"
        / "canvas"
        / "__tests__"
        / "removePlaceholder.test.ts"
    ),
    # This file itself
    str(pathlib.Path(__file__).resolve()),
}


# ===========================================================================
# 1. JSON Schema: no PlaceholderBlockDef or "placeholder" type
# ===========================================================================


class TestJsonSchemaClean:
    """The regenerated JSON schema must have no trace of PlaceholderBlock."""

    def test_schema_file_exists(self):
        """runsight-workflow-schema.json must exist."""
        assert JSON_SCHEMA.exists(), f"JSON schema not found at {JSON_SCHEMA}"

    def test_schema_no_placeholder_block_def_key(self):
        """Schema $defs must NOT contain a PlaceholderBlockDef key."""
        schema = json.loads(JSON_SCHEMA.read_text())
        defs = schema.get("$defs", schema.get("definitions", {}))
        assert "PlaceholderBlockDef" not in defs, (
            "PlaceholderBlockDef must be removed from JSON schema $defs"
        )

    def test_schema_no_placeholder_string_anywhere(self):
        """The raw JSON text must not contain the string 'placeholder' (case-insensitive)."""
        raw = JSON_SCHEMA.read_text()
        # Use lowercase comparison to catch any casing
        assert "placeholderblockdef" not in raw.lower(), (
            "PlaceholderBlockDef string found in JSON schema"
        )
        assert '"placeholder"' not in raw.lower(), '"placeholder" type string found in JSON schema'

    def test_schema_no_dangling_refs(self):
        """Every $ref in the schema must resolve to an existing $defs entry."""
        schema = json.loads(JSON_SCHEMA.read_text())
        defs = schema.get("$defs", schema.get("definitions", {}))
        raw = JSON_SCHEMA.read_text()

        # Find all $ref values
        import re

        refs = re.findall(r'"\$ref"\s*:\s*"#/\$defs/(\w+)"', raw)
        refs += re.findall(r'"\$ref"\s*:\s*"#/definitions/(\w+)"', raw)

        missing = [r for r in refs if r not in defs]
        assert not missing, f"Dangling $ref(s) in JSON schema: {missing}"


# ===========================================================================
# 2. API test files: no `type: placeholder` or PlaceholderBlock references
# ===========================================================================


class TestApiTestFilesMigrated:
    """Each API test file that previously used placeholder must be migrated."""

    API_TEST_FILES = [
        API_TESTS / "logic" / "test_execution_service.py",
        API_TESTS / "logic" / "test_execution_service_concurrency.py",
        API_TESTS / "logic" / "test_execution_observer.py",
        API_TESTS / "logic" / "test_run141_execution_service_api_keys.py",
        API_TESTS / "domain" / "test_run127_bug_fixes.py",
        API_TESTS / "logic" / "test_run200_state_flow.py",
    ]

    @pytest.mark.parametrize(
        "test_file",
        API_TEST_FILES,
        ids=[str(f.relative_to(API_TESTS)) for f in API_TEST_FILES],
    )
    def test_no_type_placeholder_in_yaml_fixtures(self, test_file: pathlib.Path):
        """YAML fixture strings must use `type: linear` instead of `type: placeholder`."""
        assert test_file.exists(), f"Test file not found: {test_file}"
        content = test_file.read_text()
        assert "type: placeholder" not in content, (
            f"{test_file.name} still contains 'type: placeholder' — "
            "must be migrated to 'type: linear' with soul_ref: \"test\""
        )

    @pytest.mark.parametrize(
        "test_file",
        API_TEST_FILES,
        ids=[str(f.relative_to(API_TESTS)) for f in API_TEST_FILES],
    )
    def test_no_placeholder_block_string_in_assertions(self, test_file: pathlib.Path):
        """No assertion or string literal should reference 'PlaceholderBlock'."""
        assert test_file.exists(), f"Test file not found: {test_file}"
        content = test_file.read_text()
        assert "PlaceholderBlock" not in content, (
            f"{test_file.name} still contains 'PlaceholderBlock' string — "
            "must be replaced with 'LinearBlock' or equivalent"
        )


# ===========================================================================
# 3. test_debate_messagebus_removal.py: no PlaceholderBlock reference
# ===========================================================================


class TestDebateRemovalFileClean:
    """libs/core/tests/test_debate_messagebus_removal.py must not reference PlaceholderBlock."""

    DEBATE_FILE = CORE_ROOT / "tests" / "test_debate_messagebus_removal.py"

    def test_file_exists(self):
        """The debate/messagebus removal test file must exist."""
        assert self.DEBATE_FILE.exists(), f"Expected file at {self.DEBATE_FILE}"

    def test_no_placeholder_block_reference(self):
        """test_debate_messagebus_removal.py must not mention PlaceholderBlock."""
        content = self.DEBATE_FILE.read_text()
        assert "PlaceholderBlock" not in content, (
            "test_debate_messagebus_removal.py still references PlaceholderBlock"
        )


# ===========================================================================
# 4. Codebase-wide grep: zero PlaceholderBlock references
# ===========================================================================


class TestCodebaseWideCleanup:
    """Comprehensive grep across the entire codebase must return zero hits
    for PlaceholderBlock-related strings, excluding allowed files."""

    PATTERNS = [
        "PlaceholderBlock",
        "PlaceholderBlockDef",
        "_build_placeholder",
    ]

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_references_in_source_files(self, pattern: str):
        """Python source files (excluding tests and allowed files) must have zero hits."""
        result = subprocess.run(
            [
                "grep",
                "-r",
                "--include=*.py",
                "-l",
                pattern,
                str(REPO_ROOT / "libs"),
                str(REPO_ROOT / "apps"),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            hits = [f for f in result.stdout.strip().split("\n") if f and f not in EXCLUSIONS]
        else:
            hits = []

        assert not hits, (
            f"Found '{pattern}' in source/test files that should have been cleaned up:\n"
            + "\n".join(f"  - {h}" for h in hits)
        )

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_references_in_frontend_files(self, pattern: str):
        """TypeScript/JavaScript files (excluding allowed files) must have zero hits."""
        result = subprocess.run(
            [
                "grep",
                "-r",
                "--include=*.ts",
                "--include=*.tsx",
                "--include=*.js",
                "--include=*.jsx",
                "-l",
                pattern,
                str(REPO_ROOT / "apps" / "gui" / "src"),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            hits = [f for f in result.stdout.strip().split("\n") if f and f not in EXCLUSIONS]
        else:
            hits = []

        assert not hits, (
            f"Found '{pattern}' in frontend files that should have been cleaned up:\n"
            + "\n".join(f"  - {h}" for h in hits)
        )

    def test_no_type_placeholder_in_yaml_files(self):
        """No YAML file in the repo should contain 'type: placeholder'."""
        result = subprocess.run(
            [
                "grep",
                "-r",
                "--include=*.yaml",
                "--include=*.yml",
                "-l",
                "type: placeholder",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            hits = [f for f in result.stdout.strip().split("\n") if f]
        else:
            hits = []

        assert not hits, "Found 'type: placeholder' in YAML files:\n" + "\n".join(
            f"  - {h}" for h in hits
        )


# ===========================================================================
# 5. API test files use `soul_ref` after migration
# ===========================================================================


class TestApiTestFilesUseSoulRef:
    """After migrating from `type: placeholder` to `type: linear`,
    the YAML fixtures must include `soul_ref` to remain valid."""

    FILES_WITH_YAML_FIXTURES = [
        API_TESTS / "logic" / "test_execution_service.py",
        API_TESTS / "logic" / "test_execution_service_concurrency.py",
        API_TESTS / "logic" / "test_run141_execution_service_api_keys.py",
        API_TESTS / "domain" / "test_run127_bug_fixes.py",
        API_TESTS / "logic" / "test_run200_state_flow.py",
    ]

    @pytest.mark.parametrize(
        "test_file",
        FILES_WITH_YAML_FIXTURES,
        ids=[str(f.relative_to(API_TESTS)) for f in FILES_WITH_YAML_FIXTURES],
    )
    def test_yaml_fixtures_contain_soul_ref(self, test_file: pathlib.Path):
        """YAML fixture strings with `type: linear` must include `soul_ref`."""
        content = test_file.read_text()
        # If the file contains "type: linear" it should also contain "soul_ref"
        if "type: linear" in content:
            assert "soul_ref" in content, (
                f"{test_file.name} has 'type: linear' but is missing 'soul_ref' — "
                "linear blocks require a soul_ref field"
            )
        else:
            # File hasn't been migrated yet (type: placeholder still present),
            # so this test should fail to flag it
            pytest.fail(
                f"{test_file.name} does not contain 'type: linear' — "
                "YAML fixtures have not been migrated from placeholder to linear"
            )
