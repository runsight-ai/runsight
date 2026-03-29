"""
RUN-280 — Red tests: Delete HttpRequestBlock and FileWriterBlock.

These tests verify that both block modules have been fully removed:
- files deleted from disk
- classes no longer importable
- type strings removed from block registries
- YAML with these types fails to parse
- surviving block types (gate, loop, linear, code) still work
- no stale imports remain in source tree
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CORE_SRC = Path(__file__).resolve().parents[2] / "src" / "runsight_core"
REPO_ROOT = Path(__file__).resolve().parents[4]  # runsight/
CUSTOM_WORKFLOWS = REPO_ROOT / "custom" / "workflows"


def _make_minimal_yaml(block_type: str, **extra_fields: str) -> dict:
    """Build a minimal workflow dict with a single block of the given type."""
    block = {"type": block_type, **extra_fields}
    return {
        "version": "1.0",
        "blocks": {"test_block": block},
        "workflow": {
            "name": "test_wf",
            "entry": "test_block",
            "transitions": [{"from": "test_block", "to": None}],
        },
    }


# ===== 1. File existence checks ============================================


class TestFilesDontExist:
    """Both block source files must be deleted from disk."""

    def test_http_request_py_deleted(self):
        path = CORE_SRC / "blocks" / "http_request.py"
        assert not path.exists(), (
            f"http_request.py still exists at {path} — it should have been deleted"
        )

    def test_file_writer_py_deleted(self):
        path = CORE_SRC / "blocks" / "file_writer.py"
        assert not path.exists(), (
            f"file_writer.py still exists at {path} — it should have been deleted"
        )


# ===== 2. Registry checks ==================================================


class TestRegistryCleanup:
    """Block type strings must not appear in the global block-def registry."""

    def test_http_request_not_in_block_def_registry(self):
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        assert "http_request" not in BLOCK_DEF_REGISTRY, (
            "'http_request' is still registered in BLOCK_DEF_REGISTRY"
        )

    def test_file_writer_not_in_block_def_registry(self):
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        assert "file_writer" not in BLOCK_DEF_REGISTRY, (
            "'file_writer' is still registered in BLOCK_DEF_REGISTRY"
        )

    def test_http_request_not_in_block_builder_registry(self):
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        assert "http_request" not in BLOCK_BUILDER_REGISTRY, (
            "'http_request' is still registered in BLOCK_BUILDER_REGISTRY"
        )

    def test_file_writer_not_in_block_builder_registry(self):
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        assert "file_writer" not in BLOCK_BUILDER_REGISTRY, (
            "'file_writer' is still registered in BLOCK_BUILDER_REGISTRY"
        )


# ===== 3. Import checks ====================================================


class TestImportsFail:
    """Attempting to import the deleted classes must raise ImportError."""

    def test_import_http_request_block_fails(self):
        with pytest.raises(ImportError):
            from runsight_core.blocks.http_request import HttpRequestBlock  # noqa: F401

    def test_import_file_writer_block_fails(self):
        with pytest.raises(ImportError):
            from runsight_core.blocks.file_writer import FileWriterBlock  # noqa: F401

    def test_top_level_import_http_request_block_fails(self):
        """HttpRequestBlock must not be importable from any sub-package path."""
        with pytest.raises(ImportError):
            importlib.import_module("runsight_core.blocks.http_request")

    def test_top_level_import_file_writer_block_fails(self):
        """FileWriterBlock must not be importable from any sub-package path."""
        with pytest.raises(ImportError):
            importlib.import_module("runsight_core.blocks.file_writer")


# ===== 4. YAML parse errors ================================================


class TestYamlParseFails:
    """Workflow YAML referencing deleted block types must fail validation."""

    def test_yaml_http_request_raises(self):
        yaml_dict = _make_minimal_yaml(
            "http_request",
            url="https://example.com",
        )
        from runsight_core.yaml.parser import parse_workflow_yaml

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            parse_workflow_yaml(yaml_dict)
        assert "http_request" in str(exc_info.value), (
            f"Expected error message to mention 'http_request', got: {exc_info.value}"
        )

    def test_yaml_file_writer_raises(self):
        yaml_dict = _make_minimal_yaml(
            "file_writer",
            output_path="/tmp/test.txt",
            content_key="some_key",
        )
        from runsight_core.yaml.parser import parse_workflow_yaml

        with pytest.raises((ValidationError, ValueError)) as exc_info:
            parse_workflow_yaml(yaml_dict)
        assert "file_writer" in str(exc_info.value), (
            f"Expected error message to mention 'file_writer', got: {exc_info.value}"
        )


# ===== 5. Surviving block types still work ==================================


class TestSurvivingBlocksWork:
    """Other block types must remain registered and functional."""

    @pytest.mark.parametrize(
        "block_type",
        ["gate", "loop", "linear", "code"],
    )
    def test_block_type_still_in_registry(self, block_type: str):
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        assert block_type in BLOCK_DEF_REGISTRY, (
            f"'{block_type}' was accidentally removed from BLOCK_DEF_REGISTRY"
        )

    @pytest.mark.parametrize(
        "block_type",
        ["gate", "loop", "linear", "code"],
    )
    def test_block_type_has_builder(self, block_type: str):
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        assert block_type in BLOCK_BUILDER_REGISTRY, (
            f"'{block_type}' builder was accidentally removed from BLOCK_BUILDER_REGISTRY"
        )


# ===== 6. No stale imports in source tree ===================================


class TestNoStaleImports:
    """No remaining imports of the deleted blocks in source files."""

    STALE_PATTERNS = [
        "HttpRequestBlock",
        "FileWriterBlock",
        "HttpRequestBlockDef",
        "FileWriterBlockDef",
        "from runsight_core.blocks.http_request",
        "from runsight_core.blocks.file_writer",
        "from .blocks.http_request",
        "from .blocks.file_writer",
    ]

    # Block type strings that must not appear as YAML block types in custom workflows
    YAML_BLOCK_TYPE_PATTERNS = [
        "type: http_request",
        "type: file_writer",
    ]

    def _collect_python_files(self) -> list[Path]:
        """Recursively collect .py files under CORE_SRC, excluding test files."""
        files = []
        for dirpath, _dirnames, filenames in os.walk(CORE_SRC):
            for fname in filenames:
                if fname.endswith(".py"):
                    files.append(Path(dirpath) / fname)
        return files

    def _collect_yaml_files(self) -> list[Path]:
        """Recursively collect .yaml/.yml files under custom/workflows/."""
        files = []
        if not CUSTOM_WORKFLOWS.exists():
            return files
        for dirpath, _dirnames, filenames in os.walk(CUSTOM_WORKFLOWS):
            for fname in filenames:
                if fname.endswith(".yaml") or fname.endswith(".yml"):
                    files.append(Path(dirpath) / fname)
        return files

    def test_no_stale_references_in_source(self):
        violations: list[str] = []
        for py_file in self._collect_python_files():
            try:
                content = py_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for pattern in self.STALE_PATTERNS:
                if pattern in content:
                    rel = py_file.relative_to(CORE_SRC)
                    violations.append(f"  {rel}: contains '{pattern}'")
        assert not violations, "Stale references to deleted blocks found in source:\n" + "\n".join(
            violations
        )

    def test_no_stale_block_types_in_custom_workflows(self):
        """Deleted block types must not appear as 'type:' values in custom workflow YAML files."""
        violations: list[str] = []
        for yaml_file in self._collect_yaml_files():
            try:
                content = yaml_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for pattern in self.YAML_BLOCK_TYPE_PATTERNS:
                if pattern in content:
                    rel = yaml_file.relative_to(REPO_ROOT)
                    violations.append(f"  {rel}: contains '{pattern}'")
        assert not violations, (
            "Deleted block types still referenced in custom workflow YAML files:\n"
            + "\n".join(violations)
        )
