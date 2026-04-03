"""
RED tests for RUN-167: Remove Debate & MessageBus from core engine.

Every test here asserts that DebateBlock, MessageBusBlock, and all related
definitions are fully removed from the codebase.  All tests MUST FAIL
against the current (pre-removal) code and PASS after Green implements
the removal.
"""

import pathlib
import subprocess

import pytest
from pydantic import ValidationError

# ─── Paths ────────────────────────────────────────────────────────────────────

CORE_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
CORE_TESTS = pathlib.Path(__file__).resolve().parent


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. DebateBlock / MessageBusBlock must NOT be importable from runsight_core
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestImportsRemoved:
    """DebateBlock and MessageBusBlock must not be importable."""

    def test_debate_block_not_importable_from_package(self):
        """DebateBlock must NOT exist in runsight_core top-level exports."""
        import runsight_core

        assert not hasattr(runsight_core, "DebateBlock"), "runsight_core still exports DebateBlock"

    def test_message_bus_block_not_importable_from_package(self):
        """MessageBusBlock must NOT exist in runsight_core top-level exports."""
        import runsight_core

        assert not hasattr(runsight_core, "MessageBusBlock"), (
            "runsight_core still exports MessageBusBlock"
        )

    def test_debate_block_not_in_implementations(self):
        """DebateBlock class must NOT exist in blocks package."""
        import runsight_core.blocks as blocks_pkg

        assert not hasattr(blocks_pkg, "DebateBlock"), "DebateBlock still exists in blocks package"

    def test_message_bus_block_not_in_implementations(self):
        """MessageBusBlock class must NOT exist in blocks package."""
        import runsight_core.blocks as blocks_pkg

        assert not hasattr(blocks_pkg, "MessageBusBlock"), (
            "MessageBusBlock still exists in blocks package"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. __all__ in runsight_core must NOT contain DebateBlock / MessageBusBlock
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAllExports:
    """__all__ must not list removed symbols."""

    def test_debate_block_not_in_all(self):
        import runsight_core

        assert "DebateBlock" not in runsight_core.__all__, "__all__ still contains 'DebateBlock'"

    def test_message_bus_block_not_in_all(self):
        import runsight_core

        assert "MessageBusBlock" not in runsight_core.__all__, (
            "__all__ still contains 'MessageBusBlock'"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Schema layer: DebateBlockDef / MessageBusBlockDef must be gone
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestSchemaRemoved:
    """Schema module must not define DebateBlockDef or MessageBusBlockDef."""

    def test_debate_block_def_not_in_schema(self):
        from runsight_core.yaml import schema

        assert not hasattr(schema, "DebateBlockDef"), "DebateBlockDef still exists in yaml.schema"

    def test_message_bus_block_def_not_in_schema(self):
        from runsight_core.yaml import schema

        assert not hasattr(schema, "MessageBusBlockDef"), (
            "MessageBusBlockDef still exists in yaml.schema"
        )

    def test_block_def_union_rejects_debate(self):
        """BlockDef discriminated union must reject type: 'debate'."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        yaml_data = {
            "version": "1.0",
            "souls": {
                "a": {"id": "a", "role": "A", "system_prompt": "A"},
                "b": {"id": "b", "role": "B", "system_prompt": "B"},
            },
            "blocks": {
                "d": {
                    "type": "debate",
                    "soul_a_ref": "a",
                    "soul_b_ref": "b",
                    "iterations": 3,
                }
            },
            "workflow": {"name": "test", "entry": "d"},
        }
        with pytest.raises(ValidationError):
            RunsightWorkflowFile.model_validate(yaml_data)

    def test_block_def_union_rejects_message_bus(self):
        """BlockDef discriminated union must reject type: 'message_bus'."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        yaml_data = {
            "version": "1.0",
            "souls": {
                "a": {"id": "a", "role": "A", "system_prompt": "A"},
            },
            "blocks": {
                "mb": {
                    "type": "message_bus",
                    "soul_refs": ["a"],
                    "iterations": 2,
                }
            },
            "workflow": {"name": "test", "entry": "mb"},
        }
        with pytest.raises(ValidationError):
            RunsightWorkflowFile.model_validate(yaml_data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. Parser registry must NOT contain "debate" or "message_bus"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestRegistryRemoved:
    """BLOCK_TYPE_REGISTRY must not have debate/message_bus entries."""

    def test_debate_not_in_registry(self):
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        assert "debate" not in BLOCK_TYPE_REGISTRY, "BLOCK_TYPE_REGISTRY still contains 'debate'"

    def test_message_bus_not_in_registry(self):
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        assert "message_bus" not in BLOCK_TYPE_REGISTRY, (
            "BLOCK_TYPE_REGISTRY still contains 'message_bus'"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. Parser builder functions must be removed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestParserBuildersRemoved:
    """_build_debate and _build_message_bus must not exist in parser module."""

    def test_build_debate_removed(self):
        from runsight_core.yaml import parser

        assert not hasattr(parser, "_build_debate"), "_build_debate still exists in yaml.parser"

    def test_build_message_bus_removed(self):
        from runsight_core.yaml import parser

        assert not hasattr(parser, "_build_message_bus"), (
            "_build_message_bus still exists in yaml.parser"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. Parser must reject YAML with type: debate or type: message_bus
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestParserRejectsRemovedTypes:
    """parse_workflow_yaml must error on debate / message_bus YAML."""

    def test_parser_rejects_debate_yaml(self):
        """Parsing a YAML with type: debate must raise an error."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  a:
    id: a
    role: A
    system_prompt: A
  b:
    id: b
    role: B
    system_prompt: B
blocks:
  d:
    type: debate
    soul_a_ref: a
    soul_b_ref: b
    iterations: 3
workflow:
  name: test
  entry: d
  transitions:
    - from: d
"""
        with pytest.raises((ValidationError, ValueError)):
            parse_workflow_yaml(yaml_str)

    def test_parser_rejects_message_bus_yaml(self):
        """Parsing a YAML with type: message_bus must raise an error."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        yaml_str = """\
version: "1.0"
souls:
  a:
    id: a
    role: A
    system_prompt: A
blocks:
  mb:
    type: message_bus
    soul_refs: [a]
    iterations: 2
workflow:
  name: test
  entry: mb
  transitions:
    - from: mb
"""
        with pytest.raises((ValidationError, ValueError)):
            parse_workflow_yaml(yaml_str)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. GateBlock docstring must NOT reference "debate"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestGateBlockDocstring:
    """GateBlock docstring must not mention 'debate'."""

    def test_gate_block_docstring_no_debate_reference(self):
        from runsight_core import GateBlock

        docstring = GateBlock.__doc__ or ""
        assert "debate" not in docstring.lower(), (
            f"GateBlock docstring still references 'debate': {docstring!r}"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. Deleted test file must NOT exist
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestStaleFilesRemoved:
    """Files that should be deleted as part of this ticket."""

    def test_debate_type_safety_integration_file_deleted(self):
        """test_integration_debate_block_type_safety.py must not exist."""
        stale_file = CORE_TESTS / "test_integration_debate_block_type_safety.py"
        assert not stale_file.exists(), f"Stale test file still exists: {stale_file}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 9. Grep-based: zero references in core engine source
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestNoStaleReferencesInSource:
    """
    Grep the core engine src/ tree for any lingering references to the
    removed primitives. This mirrors the DoD acceptance grep command.
    """

    FORBIDDEN_PATTERNS = [
        "DebateBlock",
        "MessageBusBlock",
        "DebateBlockDef",
        "MessageBusBlockDef",
        "soul_a_ref",
        "soul_b_ref",
        "_build_debate",
        "_build_message_bus",
    ]

    @pytest.mark.parametrize("pattern", FORBIDDEN_PATTERNS)
    def test_no_pattern_in_core_src(self, pattern: str):
        """No occurrence of {pattern} should appear in packages/core/src/."""
        result = subprocess.run(
            ["grep", "-r", pattern, str(CORE_SRC)],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            f"Found forbidden pattern '{pattern}' in core source:\n{result.stdout}"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 10. Other blocks must remain unaffected
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestOtherBlocksUnaffected:
    """
    Removal must NOT break any surviving block types.
    Verify they are still importable and present in the registry.
    """

    SURVIVING_BLOCK_CLASSES = [
        "LinearBlock",
        "DispatchBlock",
        "SynthesizeBlock",
        "LoopBlock",
        "GateBlock",
        "WorkflowBlock",
        "CodeBlock",
    ]

    SURVIVING_REGISTRY_KEYS = [
        "linear",
        "dispatch",
        "synthesize",
        "loop",
        "gate",
        "code",
    ]

    @pytest.mark.parametrize("class_name", SURVIVING_BLOCK_CLASSES)
    def test_surviving_block_importable(self, class_name: str):
        """All non-removed block classes must remain importable from runsight_core."""
        import runsight_core

        assert hasattr(runsight_core, class_name), (
            f"Surviving block {class_name} is no longer importable from runsight_core"
        )

    @pytest.mark.parametrize("key", SURVIVING_REGISTRY_KEYS)
    def test_surviving_registry_entry(self, key: str):
        """All non-removed block types must remain in BLOCK_TYPE_REGISTRY."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY as BLOCK_TYPE_REGISTRY

        assert key in BLOCK_TYPE_REGISTRY, (
            f"Surviving registry key '{key}' is missing from BLOCK_TYPE_REGISTRY"
        )
