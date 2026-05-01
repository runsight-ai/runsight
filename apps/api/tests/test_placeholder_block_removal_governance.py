"""
Placeholder-block removal governance.

Owner: apps/api test-fixture owners, packages/core schema/runtime owners, and
apps/gui canvas owners for the explicitly allowed frontend removal check.
Boundary: generated schemas, API fixtures, and tracked source files must not
reintroduce PlaceholderBlock, PlaceholderBlockDef, _build_placeholder, or
type: placeholder fixtures after the block type was removed.
Exit criteria: delete this governance suite once placeholder-block support has
been absent for a release cycle and normal schema/fixture behavior suites own
linear-block coverage.
"""

import json
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
CORE_ROOT = REPO_ROOT / "packages" / "core"
API_TESTS = REPO_ROOT / "apps" / "api" / "tests"
JSON_SCHEMA = CORE_ROOT / "runsight-workflow-schema.json"
PYTHON_SOURCE_ROOTS = (
    REPO_ROOT / "apps",
    REPO_ROOT / "packages",
)
FRONTEND_SOURCE_ROOT = REPO_ROOT / "apps" / "gui" / "src"
YAML_ROOTS = (
    REPO_ROOT / ".github",
    REPO_ROOT / "apps",
    REPO_ROOT / "packages",
    REPO_ROOT / "testing",
    REPO_ROOT / "tools",
)

# Files that are ALLOWED to mention PlaceholderBlock (removal verification tests)
EXCLUSIONS = {
    # Placeholder removal test (verifies PlaceholderBlock was removed from core)
    str(CORE_ROOT / "tests" / "test_remove_placeholder_block.py"),
    # Frontend placeholder removal test
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


def _iter_files(roots: tuple[pathlib.Path, ...], suffixes: tuple[str, ...]) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*") if path.is_file() and path.suffix in suffixes)
    return sorted(files)


def _files_containing(
    pattern: str,
    roots: tuple[pathlib.Path, ...],
    suffixes: tuple[str, ...],
) -> list[str]:
    hits: list[str] = []
    for path in _iter_files(roots, suffixes):
        if str(path.resolve()) in EXCLUSIONS:
            continue
        if pattern in path.read_text(encoding="utf-8", errors="ignore"):
            hits.append(str(path))
    return hits


# ===========================================================================
# 1. JSON Schema: no PlaceholderBlockDef or "placeholder" type
# ===========================================================================


class TestCoreSchemaPlaceholderBlockRemovalGovernance:
    """Owner: packages/core schema. Exit: core schema tests own removed block coverage."""

    def test_schema_file_exists(self):
        """runsight-workflow-schema.json must exist."""
        assert JSON_SCHEMA.exists(), f"JSON schema not found at {JSON_SCHEMA}"

    def test_schema_no_placeholder_block_def_key(self):
        """Schema $defs must NOT contain a PlaceholderBlockDef key."""
        schema = json.loads(JSON_SCHEMA.read_text(encoding="utf-8"))
        defs = schema.get("$defs", schema.get("definitions", {}))
        assert "PlaceholderBlockDef" not in defs, (
            "PlaceholderBlockDef must be removed from JSON schema $defs"
        )

    def test_schema_no_placeholder_string_anywhere(self):
        """The raw JSON text must not contain the string 'placeholder' (case-insensitive)."""
        raw = JSON_SCHEMA.read_text(encoding="utf-8")
        assert "placeholderblockdef" not in raw.lower(), (
            "PlaceholderBlockDef string found in JSON schema"
        )
        assert '"placeholder"' not in raw.lower(), '"placeholder" type string found in JSON schema'

    def test_schema_no_dangling_refs(self):
        """Every $ref in the schema must resolve to an existing $defs entry."""
        schema = json.loads(JSON_SCHEMA.read_text(encoding="utf-8"))
        defs = schema.get("$defs", schema.get("definitions", {}))
        raw = JSON_SCHEMA.read_text(encoding="utf-8")

        # Find all $ref values
        import re

        refs = re.findall(r'"\$ref"\s*:\s*"#/\$defs/(\w+)"', raw)
        refs += re.findall(r'"\$ref"\s*:\s*"#/definitions/(\w+)"', raw)

        missing = [r for r in refs if r not in defs]
        assert not missing, f"Dangling $ref(s) in JSON schema: {missing}"


# ===========================================================================
# 2. API test files: no `type: placeholder` or PlaceholderBlock references
# ===========================================================================


class TestApiFixturePlaceholderBlockRemovalGovernance:
    """Owner: apps/api fixtures. Exit: fixture behavior tests own linear-block coverage."""

    API_TEST_FILES = [
        API_TESTS / "logic" / "test_execution_service.py",
        API_TESTS / "logic" / "test_execution_service_concurrency.py",
        API_TESTS / "logic" / "test_execution_observer.py",
        API_TESTS / "logic" / "test_execution_service_api_keys.py",
        API_TESTS / "data" / "test_workflow_repo_entity_name.py",
        API_TESTS / "logic" / "test_state_flow.py",
    ]

    @pytest.mark.parametrize(
        "test_file",
        API_TEST_FILES,
        ids=[str(f.relative_to(API_TESTS)) for f in API_TEST_FILES],
    )
    def test_no_type_placeholder_in_yaml_fixtures(self, test_file: pathlib.Path):
        """YAML fixture strings must use `type: linear` instead of `type: placeholder`."""
        assert test_file.exists(), f"Test file not found: {test_file}"
        content = test_file.read_text(encoding="utf-8")
        assert "type: placeholder" not in content, (
            f"{test_file.name} still contains 'type: placeholder' - "
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
        content = test_file.read_text(encoding="utf-8")
        assert "PlaceholderBlock" not in content, (
            f"{test_file.name} still contains 'PlaceholderBlock' string - "
            "the migrated fixture should use 'LinearBlock' or equivalent"
        )


# ===========================================================================
# 3. test_debate_messagebus_removal.py was intentionally deleted as obsolete
#    placeholder-block removal verification noise (e9133698). No test remains.
# ===========================================================================


# ===========================================================================
# 4. Owned source scan: zero PlaceholderBlock references
# ===========================================================================


class TestTrackedSourcePlaceholderBlockRemovalGovernance:
    """Owner: source workspace owners. Exit: retired names stay absent for one release."""

    PATTERNS = [
        "PlaceholderBlock",
        "PlaceholderBlockDef",
        "_build_placeholder",
    ]

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_references_in_source_files(self, pattern: str):
        """Python source files (excluding tests and allowed files) must have zero hits."""
        hits = _files_containing(pattern, PYTHON_SOURCE_ROOTS, (".py",))

        assert not hits, (
            f"Found '{pattern}' in source/test files after placeholder-block removal:\n"
            + "\n".join(f"  - {h}" for h in hits)
        )

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_references_in_frontend_files(self, pattern: str):
        """TypeScript/JavaScript files (excluding allowed files) must have zero hits."""
        hits = _files_containing(pattern, (FRONTEND_SOURCE_ROOT,), (".js", ".jsx", ".ts", ".tsx"))

        assert not hits, (
            f"Found '{pattern}' in frontend files after placeholder-block removal:\n"
            + "\n".join(f"  - {h}" for h in hits)
        )

    def test_no_type_placeholder_in_yaml_files(self):
        """No owned workspace YAML file should contain 'type: placeholder'."""
        hits = _files_containing("type: placeholder", YAML_ROOTS, (".yaml", ".yml"))

        assert not hits, "Found 'type: placeholder' in YAML files:\n" + "\n".join(
            f"  - {h}" for h in hits
        )


# ===========================================================================
# 5. API test files use `soul_ref` after placeholder removal
# ===========================================================================


class TestApiFixtureSoulRefGovernance:
    """Owner: apps/api fixtures. Exit: linear fixture tests validate soul_ref directly."""

    FILES_WITH_YAML_FIXTURES = [
        API_TESTS / "logic" / "test_execution_service.py",
        API_TESTS / "logic" / "test_execution_service_concurrency.py",
        API_TESTS / "logic" / "test_execution_service_api_keys.py",
        API_TESTS / "data" / "test_workflow_repo_entity_name.py",
        API_TESTS / "logic" / "test_state_flow.py",
    ]

    @pytest.mark.parametrize(
        "test_file",
        FILES_WITH_YAML_FIXTURES,
        ids=[str(f.relative_to(API_TESTS)) for f in FILES_WITH_YAML_FIXTURES],
    )
    def test_yaml_fixtures_contain_soul_ref(self, test_file: pathlib.Path):
        """YAML fixture strings with `type: linear` must include `soul_ref`."""
        content = test_file.read_text(encoding="utf-8")
        # If the file contains "type: linear" it should also contain "soul_ref"
        if "type: linear" in content:
            assert "soul_ref" in content, (
                f"{test_file.name} has 'type: linear' but is missing 'soul_ref' - "
                "linear blocks require a soul_ref field"
            )
        else:
            # File hasn't been migrated yet (type: placeholder still present),
            # so this test should fail to flag it
            pytest.fail(
                f"{test_file.name} does not contain 'type: linear' - "
                "YAML fixtures have not been migrated from placeholder to linear"
            )
