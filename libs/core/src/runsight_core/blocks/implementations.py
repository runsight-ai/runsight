"""
Concrete block implementations for workflow composition.

After migration (RUN-222), all block classes live in their own modules.
This file re-exports them for backward compatibility.
"""

import asyncio  # noqa: F401 — re-exported so existing test patches keep working

# Re-export windowing helpers so existing mock.patch targets keep working.
from runsight_core.memory.windowing import get_max_tokens, prune_messages  # noqa: F401

# Re-export all runtime block classes from their co-located modules.
from runsight_core.blocks.linear import LinearBlock  # noqa: F401
from runsight_core.blocks.fanout import FanOutBlock  # noqa: F401
from runsight_core.blocks.synthesize import SynthesizeBlock  # noqa: F401
from runsight_core.blocks.loop import LoopBlock  # noqa: F401
from runsight_core.blocks.team_lead import TeamLeadBlock  # noqa: F401
from runsight_core.blocks.engineering_manager import EngineeringManagerBlock  # noqa: F401
from runsight_core.blocks.router import RouterBlock  # noqa: F401
from runsight_core.blocks.gate import GateBlock  # noqa: F401
from runsight_core.blocks.file_writer import FileWriterBlock  # noqa: F401
from runsight_core.blocks.code import CodeBlock  # noqa: F401
from runsight_core.blocks.code import (  # noqa: F401
    DEFAULT_ALLOWED_IMPORTS,
    BLOCKED_BUILTINS,
    BLOCKED_MODULES,
    _validate_code_ast,
    _HARNESS_TEMPLATE,
)
from runsight_core.blocks.workflow_block import WorkflowBlock  # noqa: F401
from runsight_core.blocks.http_request import HttpRequestBlock  # noqa: F401
