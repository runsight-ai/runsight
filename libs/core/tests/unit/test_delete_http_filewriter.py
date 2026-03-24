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
        """HttpRequestBlock must not be importable from the top-level package."""
        rc = importlib.import_module("runsight_core")
        assert not hasattr(rc, "HttpRequestBlock"), "runsight_core still exports HttpRequestBlock"

    def test_top_level_import_file_writer_block_fails(self):
        """FileWriterBlock must not be importable from the top-level package."""
        rc = importlib.import_module("runsight_core")
        assert not hasattr(rc, "FileWriterBlock"), "runsight_core still exports FileWriterBlock"


# ===== 4. YAML parse errors ================================================


class TestYamlParseFails:
    """Workflow YAML referencing deleted block types must fail validation."""

    def test_yaml_http_request_raises(self):
        yaml_dict = _make_minimal_yaml(
            "http_request",
            url="https://example.com",
        )
        with pytest.raises((ValidationError, ValueError)):
            from runsight_core.yaml.parser import parse_workflow_yaml

            parse_workflow_yaml(yaml_dict)

    def test_yaml_file_writer_raises(self):
        yaml_dict = _make_minimal_yaml(
            "file_writer",
            output_path="/tmp/test.txt",
            content_key="some_key",
        )
        with pytest.raises((ValidationError, ValueError)):
            from runsight_core.yaml.parser import parse_workflow_yaml

            parse_workflow_yaml(yaml_dict)


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

    # Directories to scan (relative to CORE_SRC)
    SCAN_DIRS = [CORE_SRC]

    def _collect_python_files(self) -> list[Path]:
        """Recursively collect .py files under CORE_SRC, excluding test files."""
        files = []
        for dirpath, _dirnames, filenames in os.walk(CORE_SRC):
            for fname in filenames:
                if fname.endswith(".py"):
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
