"""Block schema, builder registry, and parser round-trip contracts."""

from __future__ import annotations

import os
from pathlib import Path

from workflow_fixture_helpers import workflow_fixture_text

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
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

# All 7 block types (after removing http_request, file_writer, team_lead, engineering_manager)
ALL_BLOCK_TYPES = {
    "code",
    "linear",
    "gate",
    "dispatch",
    "synthesize",
    "loop",
    "workflow",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Co-located BlockDef imports
# ═══════════════════════════════════════════════════════════════════════════════


class TestMigratedBlockRoundTripIntegration:
    """Integration: parse YAML with migrated block types, verify correct runtime blocks."""

    def test_parse_linear_block(self):
        """parse_workflow_yaml must work with linear blocks."""
        from runsight_core import LinearBlock
        from runsight_core.isolation import IsolatedBlockWrapper
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(workflow_fixture_text("migrated-linear-block-roundtrip.yaml"))
        assert isinstance(wf, Workflow)
        assert wf.name == "linear_roundtrip_workflow"
        block = wf.blocks.get("write_step")
        assert block is not None
        assert isinstance(block, IsolatedBlockWrapper)
        assert isinstance(block.inner_block, LinearBlock)

    def test_parse_loop_block(self):
        """parse_workflow_yaml must work with loop blocks."""
        from runsight_core import LoopBlock
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(workflow_fixture_text("migrated-loop-block-roundtrip.yaml"))
        assert isinstance(wf, Workflow)
        assert wf.name == "loop_roundtrip_workflow"
        block = wf.blocks.get("loop_step")
        assert block is not None
        assert isinstance(block, LoopBlock)

    def test_parse_code_block(self):
        """parse_workflow_yaml must work with code blocks."""
        from runsight_core import CodeBlock
        from runsight_core.workflow import Workflow
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(workflow_fixture_text("migrated-code-block-roundtrip.yaml"))
        assert isinstance(wf, Workflow)
        assert wf.name == "code_roundtrip_workflow"
        block = wf.blocks.get("transform")
        assert block is not None
        assert isinstance(block, CodeBlock)
