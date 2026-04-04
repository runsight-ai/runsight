"""
RED tests for RUN-166: Full codebase audit for debate/messagebus cleanup.

This ticket verifies that all traces of DebateBlock and MessageBusBlock have
been removed from the ENTIRE codebase — not just core engine source, but also
JSON schema, YAML workflows, README, TypeScript frontend, and stale build
artifacts.

Every test MUST FAIL against the current (pre-cleanup) codebase and PASS once
the Green agent implements the fixes.
"""

import json
import pathlib
import subprocess

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
CORE_ROOT = REPO_ROOT / "packages" / "core"
CORE_SRC = CORE_ROOT / "src"
CORE_TESTS = CORE_ROOT / "tests"
APPS_ROOT = REPO_ROOT / "apps"
GUI_SRC = APPS_ROOT / "gui" / "src"
API_ROOT = APPS_ROOT / "api"
CUSTOM_DIR = REPO_ROOT / "custom"
JSON_SCHEMA = CORE_ROOT / "runsight-workflow-schema.json"
README = REPO_ROOT / "README.md"

# Files that are allowed to reference debate/messagebus terms because they
# exist specifically to verify the removal (meta-verification tests), or
# because they reference those test files by name (cross-ticket verification).
EXCLUDED_VERIFICATION_FILES = {
    str(CORE_TESTS / "test_debate_messagebus_removal.py"),
    str(GUI_SRC / "features" / "canvas" / "__tests__" / "test_debate_messagebus_removal.test.ts"),
    str(pathlib.Path(__file__).resolve()),  # this file itself
    # RUN-203 references test_debate_messagebus_removal.py by name for cross-validation
    str(API_ROOT / "tests" / "test_run203_placeholder_migration_cleanup.py"),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# Directories to always exclude from grep scans — generated artifacts, caches,
# binary databases, and version-control internals.
_DEFAULT_EXCLUDE_DIRS = (
    "node_modules",
    ".git",
    "dist",
    ".claude",
    ".mypy_cache",
    "__pycache__",
    ".pytest_cache",
    ".phalanx",
)


def _grep_files(
    pattern: str,
    search_dir: pathlib.Path,
    include_glob: str,
    *,
    exclude_dirs: tuple[str, ...] = _DEFAULT_EXCLUDE_DIRS,
) -> list[str]:
    """
    Run grep recursively for *pattern* in *search_dir*, filtered by
    *include_glob*.  Returns a list of matching lines (empty if no hits).

    Binary files, generated skeleton files, and matches from
    EXCLUDED_VERIFICATION_FILES are automatically stripped.
    """
    if not search_dir.exists():
        return []

    cmd = [
        "grep",
        "-r",
        "-n",
        "--binary-files=without-match",
        "--include",
        include_glob,
        pattern,
        str(search_dir),
    ]
    for d in exclude_dirs:
        cmd.extend(["--exclude-dir", d])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []

    hits: list[str] = []
    for line in result.stdout.strip().splitlines():
        filepath = line.split(":")[0]
        real = str(pathlib.Path(filepath).resolve())
        if real in EXCLUDED_VERIFICATION_FILES:
            continue
        hits.append(line)
    return hits


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. JSON Schema must NOT contain DebateBlockDef / MessageBusBlockDef
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestJsonSchemaClean:
    """JSON schema must have zero references to debate or messagebus definitions."""

    def test_json_schema_exists(self):
        """Precondition: the JSON schema file must exist."""
        assert JSON_SCHEMA.exists(), f"JSON schema not found at {JSON_SCHEMA}"

    def test_no_debate_block_def_in_json_schema(self):
        """DebateBlockDef must NOT appear in the JSON schema."""
        content = JSON_SCHEMA.read_text()
        assert "DebateBlockDef" not in content, "JSON schema still contains 'DebateBlockDef'"

    def test_no_message_bus_block_def_in_json_schema(self):
        """MessageBusBlockDef must NOT appear in the JSON schema."""
        content = JSON_SCHEMA.read_text()
        assert "MessageBusBlockDef" not in content, (
            "JSON schema still contains 'MessageBusBlockDef'"
        )

    def test_no_debate_type_in_json_schema_enum(self):
        """The block type enum in the JSON schema must not include 'debate'."""
        schema = json.loads(JSON_SCHEMA.read_text())
        schema_str = json.dumps(schema)
        # Check that "debate" doesn't appear as a value in any enum list
        assert '"debate"' not in schema_str, (
            "JSON schema still has '\"debate\"' as a block type enum value"
        )

    def test_no_message_bus_type_in_json_schema_enum(self):
        """The block type enum in the JSON schema must not include 'message_bus'."""
        schema = json.loads(JSON_SCHEMA.read_text())
        schema_str = json.dumps(schema)
        assert '"message_bus"' not in schema_str, (
            "JSON schema still has '\"message_bus\"' as a block type enum value"
        )

    def test_json_schema_validates_successfully(self):
        """The JSON schema file must be valid JSON (no dangling refs from removal)."""
        try:
            schema = json.loads(JSON_SCHEMA.read_text())
        except json.JSONDecodeError as exc:
            pytest.fail(f"JSON schema is not valid JSON after cleanup: {exc}")

        # Basic structural sanity: $defs should exist and not be empty
        assert "$defs" in schema, "JSON schema missing '$defs' key"
        assert len(schema["$defs"]) > 0, "JSON schema '$defs' is empty"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Python source files must NOT reference debate/messagebus
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestPythonSourceClean:
    """No .py file (outside verification tests) should reference debate/messagebus."""

    PATTERNS = [
        "DebateBlock",
        "MessageBusBlock",
        "DebateBlockDef",
        "MessageBusBlockDef",
        "_build_debate",
        "_build_message_bus",
        "soul_a_ref",
        "soul_b_ref",
    ]

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_pattern_in_python_files(self, pattern: str):
        """'{pattern}' must not appear in any .py file across the repo."""
        hits = _grep_files(pattern, REPO_ROOT, "*.py")
        assert len(hits) == 0, (
            f"Found forbidden pattern '{pattern}' in Python source:\n" + "\n".join(hits)
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. TypeScript/TSX source files must NOT reference debate/messagebus
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestTypeScriptSourceClean:
    """No .ts/.tsx file (outside verification tests) should reference debate/messagebus."""

    PATTERNS = [
        "DebateBlock",
        "MessageBusBlock",
        "DebateBlockDef",
        "MessageBusBlockDef",
        "debate",
        "message_bus",
        "messageBus",
    ]

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_pattern_in_ts_files(self, pattern: str):
        """'{pattern}' must not appear in any .ts file across the repo."""
        hits = _grep_files(pattern, REPO_ROOT, "*.ts")
        assert len(hits) == 0, f"Found forbidden pattern '{pattern}' in .ts source:\n" + "\n".join(
            hits
        )

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_pattern_in_tsx_files(self, pattern: str):
        """'{pattern}' must not appear in any .tsx file across the repo."""
        hits = _grep_files(pattern, REPO_ROOT, "*.tsx")
        assert len(hits) == 0, f"Found forbidden pattern '{pattern}' in .tsx source:\n" + "\n".join(
            hits
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. YAML files must NOT contain debate/messagebus block type references
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestYamlFilesClean:
    """No .yaml file should reference debate or message_bus block types."""

    PATTERNS = [
        "type: debate",
        "type: message_bus",
        "DebateBlock",
        "MessageBusBlock",
        "debate transcript",
    ]

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_pattern_in_yaml_files(self, pattern: str):
        """'{pattern}' must not appear in any .yaml file across the repo."""
        hits = _grep_files(pattern, REPO_ROOT, "*.yaml")
        assert len(hits) == 0, f"Found forbidden pattern '{pattern}' in YAML files:\n" + "\n".join(
            hits
        )

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_pattern_in_yml_files(self, pattern: str):
        """'{pattern}' must not appear in any .yml file across the repo."""
        hits = _grep_files(pattern, REPO_ROOT, "*.yml")
        assert len(hits) == 0, f"Found forbidden pattern '{pattern}' in YAML files:\n" + "\n".join(
            hits
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. JSON files must NOT contain debate/messagebus references
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestJsonFilesClean:
    """No .json file (excluding node_modules) should reference debate/messagebus."""

    PATTERNS = [
        "DebateBlockDef",
        "MessageBusBlockDef",
        "DebateBlock",
        "MessageBusBlock",
    ]

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_no_pattern_in_json_files(self, pattern: str):
        """'{pattern}' must not appear in any .json file across the repo."""
        hits = _grep_files(pattern, REPO_ROOT, "*.json")
        assert len(hits) == 0, f"Found forbidden pattern '{pattern}' in JSON files:\n" + "\n".join(
            hits
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. README.md must NOT reference "debate" as a current feature
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestReadmeClean:
    """README.md must not advertise debate as a current capability."""

    def test_readme_exists(self):
        """Precondition: README.md must exist."""
        assert README.exists(), f"README.md not found at {README}"

    def test_readme_no_debate_in_live_dag_line(self):
        """Line ~23: 'Watch your agents think, debate, and act' must be updated."""
        content = README.read_text()
        assert "think, debate, and act" not in content, (
            "README still says 'Watch your agents think, debate, and act in real-time'"
        )

    def test_readme_no_multi_agent_debate_patterns(self):
        """Line ~34: 'multi-agent debate patterns' must be removed or reworded."""
        content = README.read_text()
        assert "multi-agent debate patterns" not in content, (
            "README still references 'multi-agent debate patterns' as a feature"
        )

    def test_readme_no_debate_keyword(self):
        """The word 'debate' should not appear anywhere in README as a feature reference."""
        content = README.read_text().lower()
        assert "debate" not in content, (
            "README still contains the word 'debate' — all references should be "
            "removed or replaced with current terminology"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. custom/souls/gate_evaluator.yaml must NOT reference "debate transcript"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGateEvaluatorYamlClean:
    """gate_evaluator.yaml must not mention debate transcript."""

    GATE_EVAL = CUSTOM_DIR / "souls" / "gate_evaluator.yaml"

    def test_gate_evaluator_exists(self):
        """Precondition: gate_evaluator.yaml must exist."""
        assert self.GATE_EVAL.exists(), f"gate_evaluator.yaml not found at {self.GATE_EVAL}"

    def test_no_debate_transcript_reference(self):
        """The prompt in gate_evaluator.yaml must not mention 'debate transcript'."""
        content = self.GATE_EVAL.read_text()
        assert "debate transcript" not in content.lower(), (
            "custom/souls/gate_evaluator.yaml still references 'debate transcript'"
        )

    def test_no_debate_keyword_in_gate_evaluator(self):
        """The word 'debate' should not appear at all in gate_evaluator.yaml."""
        content = self.GATE_EVAL.read_text()
        assert "debate" not in content.lower(), (
            "custom/souls/gate_evaluator.yaml still contains the word 'debate'"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. packages/core/build/ must NOT exist
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestBuildDirectoryRemoved:
    """The stale build directory must not exist."""

    def test_core_build_directory_does_not_exist(self):
        """packages/core/build/ must be deleted."""
        build_dir = CORE_ROOT / "build"
        assert not build_dir.exists(), (
            f"Stale build directory still exists at {build_dir} — it must be deleted"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 9. Comprehensive cross-file-type grep (the "final grep" from DoD)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFinalGrepZeroHits:
    """
    The Definition of Done requires a final grep that returns ZERO hits for
    debate/messagebus terms across the entire codebase (excluding node_modules,
    .git, dist, .claude, .mypy_cache, and the dedicated verification test files).

    Also excludes binary files, __pycache__, .pytest_cache, and generated
    artifacts (skeleton XML, codebones DB) which are not source-of-truth files.
    """

    FORBIDDEN_TERMS = [
        "DebateBlock",
        "MessageBusBlock",
        "DebateBlockDef",
        "MessageBusBlockDef",
        "_build_debate",
        "_build_message_bus",
    ]

    # Generated/non-source files that should be excluded from the final grep.
    # These are regenerated from source and will be cleaned up automatically
    # once all source references are removed.
    _GENERATED_FILE_PATTERNS = (
        "skeleton.xml",
        "repo-skeleton.xml",
        "codebones.db",
        "phalanx.db",
    )

    @pytest.mark.parametrize("term", FORBIDDEN_TERMS)
    def test_zero_hits_across_entire_codebase(self, term: str):
        """'{term}' must return zero grep hits across the entire repo."""
        cmd = [
            "grep",
            "-r",
            "-n",
            "--binary-files=without-match",
            term,
            str(REPO_ROOT),
        ]
        for d in _DEFAULT_EXCLUDE_DIRS:
            cmd.extend(["--exclude-dir", d])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            # No matches found — test passes
            return

        # Filter out allowed verification files and generated artifacts
        remaining: list[str] = []
        for line in result.stdout.strip().splitlines():
            filepath = line.split(":")[0]
            basename = pathlib.Path(filepath).name
            real = str(pathlib.Path(filepath).resolve())

            if real in EXCLUDED_VERIFICATION_FILES:
                continue
            if basename in self._GENERATED_FILE_PATTERNS:
                continue
            remaining.append(line)

        assert len(remaining) == 0, (
            f"Final grep found '{term}' in the codebase "
            f"({len(remaining)} hit(s)):\n" + "\n".join(remaining)
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 10. Stale test file must be removed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestStaleTestFilesRemoved:
    """Integration test files for debate must be deleted."""

    def test_debate_type_safety_integration_file_deleted(self):
        """test_integration_debate_block_type_safety.py must not exist."""
        stale = CORE_TESTS / "test_integration_debate_block_type_safety.py"
        assert not stale.exists(), f"Stale debate integration test still exists: {stale}"
