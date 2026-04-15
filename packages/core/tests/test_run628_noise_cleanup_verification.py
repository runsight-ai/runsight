"""
RUN-628 — Red tests: Noise test cleanup verification.

Verifies that ~50 migration-verification tests have been removed from the suite:
1. 12 entire files deleted (they verify completed migrations, not live behavior)
2. 6 files partially cleaned (named noise classes removed, behavioral classes kept)
3. Stale xfail markers removed from test_exit_ports_integration.py
4. No new xfail markers introduced in touched files

All tests here should FAIL against the current codebase (the noise still exists)
and PASS once Green Team completes the cleanup.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CORE_TESTS = Path(__file__).resolve().parent
UNIT_TESTS = CORE_TESTS / "unit"


# ===========================================================================
# 1. File deletion — 12 files must NOT exist
# ===========================================================================

FILES_TO_DELETE = [
    "test_debate_messagebus_removal.py",
    "test_delete_teamlead_em.py",
    "test_run166_debate_cleanup.py",
    "test_run182_execution_log_rename.py",
    "test_run223_cleanup.py",
    "test_run127_api_key_threading.py",
    "test_run141_parser_api_keys.py",
    "test_mutable_default_callstack.py",
    "test_run353_template_yaml.py",
    "test_run471_soul_fields.py",
    "test_run575_template_alignment.py",
    "test_integration_kwargs_compatibility.py",
]


class TestFileDeletion:
    """Each of the 12 migration-verification test files must be deleted."""

    @pytest.mark.parametrize("filename", FILES_TO_DELETE)
    def test_file_does_not_exist(self, filename: str) -> None:
        path = CORE_TESTS / filename
        assert not path.exists(), (
            f"{filename} still exists — it verifies a completed migration and should be deleted"
        )


# ===========================================================================
# 2. Partial cleanup — noise classes removed, behavioral classes kept
# ===========================================================================


class TestRemovePlaceholderBlockCleanup:
    """test_remove_placeholder_block.py: 4 noise classes deleted, 2 behavioral kept."""

    FILE = CORE_TESTS / "test_remove_placeholder_block.py"

    NOISE_CLASSES = [
        "TestPlaceholderBlockRemoved",
        "TestPlaceholderBlockDefRemoved",
        "TestPlaceholderNotInRegistry",
        "TestPlaceholderYamlRejected",
    ]

    KEEP_CLASSES = [
        "TestDynamicInjectionRaisesValueError",
        "TestConfTestInfrastructure",
    ]

    @pytest.mark.parametrize("class_name", NOISE_CLASSES)
    def test_noise_class_removed(self, class_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert class_name not in names, (
            f"{class_name} still exists in test_remove_placeholder_block.py — "
            f"it is migration noise and should be deleted"
        )

    @pytest.mark.parametrize("class_name", KEEP_CLASSES)
    def test_behavioral_class_kept(self, class_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert class_name in names, (
            f"{class_name} must remain in test_remove_placeholder_block.py — it tests live behavior"
        )


class TestRun222MigrateBlocksCleanup:
    """test_run222_migrate_blocks.py: 4 noise classes deleted, 5 behavioral kept."""

    FILE = CORE_TESTS / "test_run222_migrate_blocks.py"

    NOISE_CLASSES = [
        "TestSchemaCleanup",
        "TestParserCleanup",
        "TestBlockFileExistence",
        "TestSchemaReExports",
    ]

    KEEP_CLASSES = [
        "TestBuildFunctionExists",
        "TestBlockDefImportable",
        "TestCarryContextConfigMigration",
        "TestEndToEndRoundTrip",
        "TestRegistryCounts",
    ]

    @pytest.mark.parametrize("class_name", NOISE_CLASSES)
    def test_noise_class_removed(self, class_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert class_name not in names, (
            f"{class_name} still exists in test_run222_migrate_blocks.py — "
            f"it is migration noise and should be deleted"
        )

    @pytest.mark.parametrize("class_name", KEEP_CLASSES)
    def test_behavioral_class_kept(self, class_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert class_name in names, (
            f"{class_name} must remain in test_run222_migrate_blocks.py — it tests live behavior"
        )


class TestRun377YamlEnabledCleanup:
    """test_run377_yaml_enabled.py: 2 xfail parser tests deleted, schema+engine kept."""

    FILE = CORE_TESTS / "test_run377_yaml_enabled.py"

    NOISE_CLASSES_OR_METHODS = [
        # The entire TestEnabledFieldParser class has only xfail tests — delete both methods.
        # We check the class still exists but its xfail test methods are gone.
    ]

    def test_xfail_parser_tests_removed(self) -> None:
        """The 2 xfail-marked parser tests in TestEnabledFieldParser must be deleted."""
        source = self.FILE.read_text()
        tree = ast.parse(source)

        # Find TestEnabledFieldParser class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "TestEnabledFieldParser":
                # Collect test method names
                methods = [
                    n.name
                    for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name.startswith("test_")
                ]
                assert len(methods) == 0, (
                    f"TestEnabledFieldParser still has test methods {methods} — "
                    f"the 2 xfail parser tests should be deleted "
                    f"(leaving the class empty or removed entirely)"
                )
                return

        # If the class itself was removed, that's also acceptable
        # (Green Team may choose to delete the empty class)

    def test_schema_class_kept(self) -> None:
        names = _get_top_level_names(self.FILE)
        assert "TestEnabledFieldSchema" in names, (
            "TestEnabledFieldSchema must remain — it tests live schema behavior"
        )

    def test_engine_class_kept(self) -> None:
        names = _get_top_level_names(self.FILE)
        assert "TestEngineIgnoresEnabled" in names, (
            "TestEngineIgnoresEnabled must remain — it tests live engine behavior"
        )


class TestRun415NoBuiltinSoulsCleanup:
    """test_run415_no_builtin_souls.py: 2 noise classes deleted, 2 behavioral kept."""

    FILE = CORE_TESTS / "test_run415_no_builtin_souls.py"

    NOISE_CLASSES = [
        "TestBuiltInSoulsRemoved",
        "TestExplicitSoulsStillWork",
    ]

    KEEP_CLASSES = [
        "TestEmptySoulsMapByDefault",
        "TestNoPreviouslyBuiltInNamesAreSpecial",
    ]

    @pytest.mark.parametrize("class_name", NOISE_CLASSES)
    def test_noise_class_removed(self, class_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert class_name not in names, (
            f"{class_name} still exists in test_run415_no_builtin_souls.py — "
            f"it is migration noise and should be deleted"
        )

    @pytest.mark.parametrize("class_name", KEEP_CLASSES)
    def test_behavioral_class_kept(self, class_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert class_name in names, (
            f"{class_name} must remain in test_run415_no_builtin_souls.py — it tests live behavior"
        )


class TestRetryblockMigrationCleanup:
    """test_retryblock_migration.py: 1 noise class deleted, 3 behavioral kept."""

    FILE = CORE_TESTS / "test_retryblock_migration.py"

    NOISE_CLASSES = [
        "TestStaleRetryBlockComments",
    ]

    KEEP_CLASSES = [
        "TestLoopBlockUpstreamWorkflowIntegration",
        "TestLoopBlockWithRetryConfig",
        "TestLoopBlockStateFlowBetweenRounds",
    ]

    @pytest.mark.parametrize("class_name", NOISE_CLASSES)
    def test_noise_class_removed(self, class_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert class_name not in names, (
            f"{class_name} still exists in test_retryblock_migration.py — "
            f"it is migration noise and should be deleted"
        )

    @pytest.mark.parametrize("class_name", KEEP_CLASSES)
    def test_behavioral_class_kept(self, class_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert class_name in names, (
            f"{class_name} must remain in test_retryblock_migration.py — it tests live behavior"
        )


class TestIntegrationMergeValidationCleanup:
    """test_integration_merge_validation.py: 4 trivial/deletion-check tests deleted, 3 behavioral kept."""

    FILE = CORE_TESTS / "test_integration_merge_validation.py"

    NOISE_FUNCTIONS = [
        "test_workflow_class_exists_and_instantiates",
        "test_skill_not_exported_from_runsight_core",
        "test_primitives_only_exports_soul_task_step",
        "test_step_primitive_works_independently",
    ]

    KEEP_FUNCTIONS = [
        "test_workflow_fluent_api_chain",
        "test_workflow_execution_renamed_class",
        "test_workflow_terminal_block_no_transition",
    ]

    @pytest.mark.parametrize("func_name", NOISE_FUNCTIONS)
    def test_noise_function_removed(self, func_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert func_name not in names, (
            f"{func_name} still exists in test_integration_merge_validation.py — "
            f"it is a trivial/deletion-check test and should be deleted"
        )

    @pytest.mark.parametrize("func_name", KEEP_FUNCTIONS)
    def test_behavioral_function_kept(self, func_name: str) -> None:
        names = _get_top_level_names(self.FILE)
        assert func_name in names, (
            f"{func_name} must remain in test_integration_merge_validation.py — "
            f"it tests live behavior"
        )


# ===========================================================================
# 3. Stale xfail markers removed from TestYamlExitPortRoundTrip
# ===========================================================================


class TestStaleXfailRemoval:
    """test_exit_ports_integration.py::TestYamlExitPortRoundTrip must not have xfail markers."""

    def _get_source(self) -> str:
        path = UNIT_TESTS / "test_exit_ports_integration.py"
        return path.read_text()

    def test_gate_exits_round_trip_no_xfail(self) -> None:
        """test_gate_exits_survive_schema_round_trip must not be xfail-marked."""
        source = self._get_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "TestYamlExitPortRoundTrip":
                for item in node.body:
                    if (
                        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name == "test_gate_exits_survive_schema_round_trip"
                    ):
                        xfail_markers = [d for d in item.decorator_list if _is_xfail_decorator(d)]
                        assert len(xfail_markers) == 0, (
                            "test_gate_exits_survive_schema_round_trip still has an "
                            "@pytest.mark.xfail marker — inline souls are re-enabled, "
                            "remove the stale xfail"
                        )
                        return

        pytest.fail(
            "Could not find test_gate_exits_survive_schema_round_trip in TestYamlExitPortRoundTrip"
        )

    def test_loop_break_on_exit_round_trip_no_xfail(self) -> None:
        """test_loop_break_on_exit_survives_schema_round_trip must not be xfail-marked."""
        source = self._get_source()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "TestYamlExitPortRoundTrip":
                for item in node.body:
                    if (
                        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name == "test_loop_break_on_exit_survives_schema_round_trip"
                    ):
                        xfail_markers = [d for d in item.decorator_list if _is_xfail_decorator(d)]
                        assert len(xfail_markers) == 0, (
                            "test_loop_break_on_exit_survives_schema_round_trip still has an "
                            "@pytest.mark.xfail marker — inline souls are re-enabled, "
                            "remove the stale xfail"
                        )
                        return

        pytest.fail(
            "Could not find test_loop_break_on_exit_survives_schema_round_trip in TestYamlExitPortRoundTrip"
        )


# ===========================================================================
# 4. No new xfail markers introduced in touched files
# ===========================================================================


# NOTE: test_remove_placeholder_block.py, test_run222_migrate_blocks.py, and
# test_exit_ports_integration.py are excluded — they have pre-existing xfails on
# KEPT behavioral classes. Their noise-class cleanup is already covered by
# dedicated test classes above (and TestStaleXfailRemoval for exit ports).
PARTIALLY_CLEANED_FILES = [
    CORE_TESTS / "test_run377_yaml_enabled.py",
    CORE_TESTS / "test_run415_no_builtin_souls.py",
    CORE_TESTS / "test_retryblock_migration.py",
    CORE_TESTS / "test_integration_merge_validation.py",
]
PARTIALLY_CLEANED_FILES = tuple(path for path in PARTIALLY_CLEANED_FILES if path.exists())


class TestNoNewXfailMarkers:
    """After cleanup, no new xfail markers should be introduced in touched files."""

    @pytest.mark.parametrize(
        "filepath",
        PARTIALLY_CLEANED_FILES,
        ids=[p.name for p in PARTIALLY_CLEANED_FILES],
    )
    def test_no_xfail_in_cleaned_file(self, filepath: Path) -> None:
        """Touched files must not contain any xfail markers after cleanup."""
        source = filepath.read_text()
        tree = ast.parse(source)

        xfail_locations = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if _is_xfail_decorator(decorator):
                        xfail_locations.append(f"{node.name} (line {decorator.lineno})")

        assert len(xfail_locations) == 0, (
            f"{filepath.name} still has xfail markers on: {', '.join(xfail_locations)}. "
            f"After cleanup, no xfail markers should remain in touched files."
        )


# ===========================================================================
# Helpers
# ===========================================================================


def _get_top_level_names(filepath: Path) -> set[str]:
    """Parse a Python source file and return all top-level class and function names."""
    source = filepath.read_text()
    tree = ast.parse(source)
    return {
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _is_xfail_decorator(node: ast.expr) -> bool:
    """Check if an AST decorator node is a pytest.mark.xfail (with or without call args)."""
    # @pytest.mark.xfail
    if isinstance(node, ast.Attribute) and node.attr == "xfail":
        return True
    # @pytest.mark.xfail(reason=..., strict=True)
    if isinstance(node, ast.Call):
        return _is_xfail_decorator(node.func)
    return False
