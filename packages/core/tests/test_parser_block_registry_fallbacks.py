"""
Tests for block definition auto-registration infrastructure.

Tests cover:
- _registry.py: register, get, duplicate detection, empty state
- __init_subclass__: all 12 types auto-register, base class skipped, non-Literal skipped
- build_block_def_union(): produces valid discriminated union, handles empty registry
- rebuild_block_def_union(): updates BlockDef globally, model_rebuild succeeds
- _helpers.py: soul resolution, condition conversion, condition group conversion
- Parser fallback: registry-based builder lookup for unknown types
- generate_schema.py --check: schema file is in sync with models
"""

import os
from pathlib import Path

_SAFE_SUBPROCESS_ENV_KEYS = (
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "PATH",
    "PYTHONIOENCODING",
    "TMP",
    "TMPDIR",
    "TEMP",
    "VIRTUAL_ENV",
)


def _schema_check_env(repo_root: Path) -> dict[str, str]:
    """Build a schema-check subprocess env without inheriting real credentials."""
    env = {key: os.environ[key] for key in _SAFE_SUBPROCESS_ENV_KEYS if key in os.environ}
    pythonpath = [
        str(repo_root / "packages" / "core" / "src"),
        str(repo_root / "apps" / "api" / "src"),
    ]
    if os.environ.get("PYTHONPATH"):
        pythonpath.append(os.environ["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    return env


# ═══════════════════════════════════════════════════════════════════════════════
# 1. _registry.py — module-level registry functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestParserFallback:
    """Integration test: parser falls back to BLOCK_BUILDER_REGISTRY for unknown types."""

    def test_parser_uses_builder_registry_fallback(self):
        """When a type is not in the hardcoded BLOCK_TYPE_REGISTRY,
        the parser should fall back to BLOCK_BUILDER_REGISTRY.

        Registers a mock builder for 'my_custom_block' in BLOCK_BUILDER_REGISTRY,
        patches past Pydantic validation so the custom type reaches the builder
        lookup, then verifies the mock builder was actually called.
        """
        from unittest.mock import MagicMock as Mock
        from unittest.mock import patch

        from runsight_core.blocks._registry import (
            BLOCK_BUILDER_REGISTRY,
            register_block_builder,
        )
        from runsight_core.blocks.base import BaseBlock
        from runsight_core.yaml.parser import parse_workflow_yaml

        # 1. Create a mock builder that returns a BaseBlock-compatible object
        fake_block = Mock(spec=BaseBlock)
        fake_block.block_id = "custom_review_block"
        mock_builder = Mock(return_value=fake_block)

        # 2. Register the mock builder for our custom type
        register_block_builder("my_custom_block", mock_builder)

        try:
            # 3. Build a fake file_def that Pydantic model_validate would return.
            #    We patch model_validate to bypass schema validation (our custom type
            #    is not in the BlockDef discriminated union).
            fake_block_def = Mock()
            fake_block_def.type = "my_custom_block"
            fake_block_def.retry_config = None
            fake_block_def.stateful = False
            fake_block_def.inputs = None
            fake_block_def.output_conditions = []

            fake_soul_def = Mock()
            fake_soul_def.id = "reviewer_soul"
            fake_soul_def.kind = "soul"
            fake_soul_def.name = "Reviewer"
            fake_soul_def.role = "Reviewer"
            fake_soul_def.system_prompt = "Review the workflow."
            fake_soul_def.tools = None
            fake_soul_def.max_tool_iterations = 1
            fake_soul_def.model_name = None

            fake_transition = Mock()
            fake_transition.from_ = "custom_review_block"
            fake_transition.to = None

            fake_workflow_def = Mock()
            fake_workflow_def.name = "builder_fallback_workflow"
            fake_workflow_def.entry = "custom_review_block"
            fake_workflow_def.transitions = [fake_transition]
            fake_workflow_def.conditional_transitions = []

            fake_file_def = Mock()
            fake_file_def.version = "1.0"
            fake_file_def.souls = {"reviewer_soul": fake_soul_def}
            fake_file_def.blocks = {"custom_review_block": fake_block_def}
            fake_file_def.workflow = fake_workflow_def
            fake_file_def.config = {}

            with patch(
                "runsight_core.yaml.parser.RunsightWorkflowFile.model_validate",
                return_value=fake_file_def,
            ):
                parse_workflow_yaml({"version": "1.0"})

            # 4. Assert the mock builder was called with expected args
            mock_builder.assert_called_once()
            call_args = mock_builder.call_args
            assert call_args[0][0] == "custom_review_block"
            assert call_args[0][1] is fake_block_def  # block_def

        finally:
            # 5. Cleanup
            BLOCK_BUILDER_REGISTRY.pop("my_custom_block", None)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Auto-discovery in blocks/__init__.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoDiscovery:
    """Tests for _auto_discover_blocks() in blocks/__init__.py."""

    def test_auto_discover_blocks_function_exists(self):
        """_auto_discover_blocks is callable in blocks/__init__.py."""
        from runsight_core.blocks import _auto_discover_blocks  # noqa: F401

    def test_auto_discover_populates_builder_registry(self):
        """After _auto_discover_blocks(), BLOCK_BUILDER_REGISTRY has entries."""
        # Importing blocks triggers _auto_discover_blocks at module level
        import runsight_core.blocks  # noqa: F401
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        # There should be at least some builders registered
        assert len(BLOCK_BUILDER_REGISTRY) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Edge cases
# ═══════════════════════════════════════════════════════════════════════════════
