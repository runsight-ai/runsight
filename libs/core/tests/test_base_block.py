"""
Tests for BaseBlock pause/kill mechanism.

Acceptance Criteria:
- AC-054: test_pause_event_initialized
- AC-055: test_kill_flag_default_false
- AC-056: test_check_pause_raises_on_kill
- AC-057: test_node_killed_exception_has_block_id
"""

import asyncio
import pytest
from unittest.mock import MagicMock

from runsight_core.state import WorkflowState
from runsight_core.blocks.base import BaseBlock, NodeKilledException
from runsight_core.blocks.implementations import LinearBlock
from runsight_core.primitives import Soul


class SimpleTestBlock(BaseBlock):
    """Simple BaseBlock subclass for testing pause/kill mechanism."""

    async def execute(self, state: WorkflowState) -> WorkflowState:
        """Minimal execute implementation for testing."""
        return state


@pytest.fixture
def mock_runner():
    """Mock RunsightTeamRunner for testing."""
    runner = MagicMock()
    return runner


@pytest.fixture
def sample_soul():
    """Sample soul for testing."""
    return Soul(id="test_soul", role="Tester", system_prompt="You test things.")


def test_pause_event_initialized(sample_soul, mock_runner):
    """AC-054: _pause_event is set (not paused) on block construction."""
    block = LinearBlock("test", sample_soul, mock_runner)
    assert block._pause_event.is_set() is True


def test_kill_flag_default_false(sample_soul, mock_runner):
    """AC-055: _kill_flag is False by default on block construction."""
    block = LinearBlock("test", sample_soul, mock_runner)
    assert block._kill_flag is False


@pytest.mark.asyncio
async def test_check_pause_raises_on_kill():
    """AC-056: _check_pause() raises NodeKilledException when kill_flag is True."""
    block = SimpleTestBlock("test-block")
    # Verify block is in normal state
    assert block._kill_flag is False
    assert block._pause_event.is_set() is True

    # Set kill flag and clear pause event
    block._kill_flag = True
    block._pause_event.clear()

    # When pause event is set (unpaused) and kill flag is true, should raise
    block._pause_event.set()

    with pytest.raises(NodeKilledException):
        await block._check_pause()


@pytest.mark.asyncio
async def test_check_pause_blocks_when_paused():
    """Verify _check_pause() blocks when pause event is cleared."""
    block = SimpleTestBlock("test-block")
    block._pause_event.clear()  # Paused

    async def check_and_signal():
        """Try to check pause, then signal to continue."""
        await asyncio.sleep(0.1)
        block._pause_event.set()  # Resume

    # Set up concurrent task to resume after a delay
    resume_task = asyncio.create_task(check_and_signal())

    # This should block until the event is set
    await block._check_pause()

    await resume_task
    assert block._pause_event.is_set() is True


def test_node_killed_exception_has_block_id():
    """AC-057: NodeKilledException stores block_id attribute."""
    block_id = "test-block"
    exc = NodeKilledException(block_id)
    assert exc.block_id == "test-block"
    assert str(exc) == f"Node '{block_id}' was killed"


def test_simple_test_block_pause_event_initialized():
    """Verify pause_event is initialized on custom BaseBlock subclass."""
    block = SimpleTestBlock("custom-block")
    assert block._pause_event.is_set() is True


def test_simple_test_block_kill_flag_default():
    """Verify kill_flag is False by default on custom BaseBlock subclass."""
    block = SimpleTestBlock("custom-block")
    assert block._kill_flag is False


@pytest.mark.asyncio
async def test_check_pause_succeeds_when_not_killed():
    """Verify _check_pause() succeeds when not killed."""
    block = SimpleTestBlock("test-block")
    assert block._kill_flag is False
    assert block._pause_event.is_set() is True

    # Should complete without exception
    await block._check_pause()


@pytest.mark.asyncio
async def test_check_pause_with_linear_block():
    """Verify _check_pause() works with LinearBlock."""
    soul = Soul(id="test_soul", role="Tester", system_prompt="You test things.")
    runner = MagicMock()
    block = LinearBlock("linear-test", soul, runner)

    assert block._pause_event.is_set() is True
    assert block._kill_flag is False

    # Should complete without exception
    await block._check_pause()


@pytest.mark.asyncio
async def test_check_pause_raises_immediately_on_kill_if_not_paused():
    """Verify _check_pause() raises immediately if kill flag is set and event is set."""
    block = SimpleTestBlock("test-block")
    block._kill_flag = True
    # Event is already set by default

    with pytest.raises(NodeKilledException) as exc_info:
        await block._check_pause()

    assert exc_info.value.block_id == "test-block"
