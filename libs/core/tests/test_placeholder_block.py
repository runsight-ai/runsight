"""
Tests for PlaceholderBlock implementation.
"""

import pytest

from runsight_core.state import WorkflowState
from runsight_core.blocks.implementations import PlaceholderBlock


@pytest.mark.asyncio
async def test_placeholder_block_results_key_equals_description():
    """
    AC-2: PlaceholderBlock(block_id='pb', description='desc').execute(state)
    returns state with results['pb'] == 'desc'
    """
    block = PlaceholderBlock(block_id="pb", description="desc")
    state = WorkflowState()

    result_state = await block.execute(state)

    assert result_state.results["pb"] == "desc"


@pytest.mark.asyncio
async def test_placeholder_block_message_appended_with_correct_format():
    """
    AC-3: execute() appends exactly one message with role='system'
    and content matching '[Block pb] PlaceholderBlock: desc'
    """
    block = PlaceholderBlock(block_id="pb", description="desc")
    state = WorkflowState()

    result_state = await block.execute(state)

    assert len(result_state.messages) == 1
    message = result_state.messages[0]
    assert message["role"] == "system"
    assert message["content"] == "[Block pb] PlaceholderBlock: desc"


@pytest.mark.asyncio
async def test_placeholder_block_shared_memory_and_metadata_unchanged():
    """
    AC-4: execute() does not modify state.shared_memory or state.metadata
    """
    block = PlaceholderBlock(block_id="pb", description="desc")
    original_shared_memory = {"key": "value"}
    original_metadata = {"meta_key": "meta_value"}
    state = WorkflowState(shared_memory=original_shared_memory, metadata=original_metadata)

    result_state = await block.execute(state)

    assert result_state.shared_memory == original_shared_memory
    assert result_state.metadata == original_metadata


@pytest.mark.asyncio
async def test_placeholder_block_current_task_none_does_not_raise():
    """
    AC-5: execute() does not require state.current_task to be set
    (current_task=None is valid)
    """
    block = PlaceholderBlock(block_id="pb", description="desc")
    state = WorkflowState(current_task=None)

    # Should not raise any exception
    result_state = await block.execute(state)

    assert result_state.results["pb"] == "desc"


@pytest.mark.asyncio
async def test_placeholder_block_returns_new_instance_via_model_copy():
    """
    AC-6: execute() returns a new WorkflowState via model_copy,
    not the same object
    """
    block = PlaceholderBlock(block_id="pb", description="desc")
    state = WorkflowState()

    result_state = await block.execute(state)

    assert result_state is not state


@pytest.mark.asyncio
async def test_placeholder_block_preserves_existing_results():
    """
    PlaceholderBlock preserves existing results when adding new ones.
    """
    block = PlaceholderBlock(block_id="pb", description="desc")
    state = WorkflowState(results={"previous_block": "previous_output"})

    result_state = await block.execute(state)

    assert result_state.results["previous_block"] == "previous_output"
    assert result_state.results["pb"] == "desc"


@pytest.mark.asyncio
async def test_placeholder_block_appends_to_existing_messages():
    """
    PlaceholderBlock appends to existing messages without replacing them.
    """
    block = PlaceholderBlock(block_id="pb", description="desc")
    existing_messages = [{"role": "system", "content": "Previous message"}]
    state = WorkflowState(messages=existing_messages)

    result_state = await block.execute(state)

    assert len(result_state.messages) == 2
    assert result_state.messages[0]["content"] == "Previous message"
    assert result_state.messages[1]["content"] == "[Block pb] PlaceholderBlock: desc"


@pytest.mark.asyncio
async def test_placeholder_block_with_empty_description():
    """
    PlaceholderBlock handles empty description correctly.
    """
    block = PlaceholderBlock(block_id="pb", description="")
    state = WorkflowState()

    result_state = await block.execute(state)

    assert result_state.results["pb"] == ""
    assert result_state.messages[0]["content"] == "[Block pb] PlaceholderBlock: "


@pytest.mark.asyncio
async def test_placeholder_block_with_long_description():
    """
    PlaceholderBlock handles long descriptions correctly.
    """
    long_desc = "A" * 500
    block = PlaceholderBlock(block_id="pb", description=long_desc)
    state = WorkflowState()

    result_state = await block.execute(state)

    assert result_state.results["pb"] == long_desc
    assert result_state.messages[0]["content"] == f"[Block pb] PlaceholderBlock: {long_desc}"


@pytest.mark.asyncio
async def test_placeholder_block_with_special_characters_in_description():
    """
    PlaceholderBlock handles special characters in description correctly.
    """
    special_desc = "Special chars: !@#$%^&*() '\""
    block = PlaceholderBlock(block_id="pb", description=special_desc)
    state = WorkflowState()

    result_state = await block.execute(state)

    assert result_state.results["pb"] == special_desc
    assert result_state.messages[0]["content"] == f"[Block pb] PlaceholderBlock: {special_desc}"
