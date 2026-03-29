"""
Failing tests for RUN-189: Add conversation_histories to WorkflowState.

Tests cover:
- WorkflowState has conversation_histories field with empty dict default
- model_copy(update={"conversation_histories": ...}) works
- "conversation_histories" in WorkflowState.model_fields
- model_dump() includes conversation_histories
- model_dump_json() works with populated histories
- Serialization round-trip
"""

import json

from runsight_core.state import WorkflowState

# ===========================================================================
# 1. Field exists and defaults
# ===========================================================================


class TestConversationHistoriesFieldExists:
    """conversation_histories must be a Dict[str, List[Dict[str, Any]]] field."""

    def test_field_in_model_fields(self):
        """conversation_histories must be declared in WorkflowState.model_fields."""
        assert "conversation_histories" in WorkflowState.model_fields

    def test_default_is_empty_dict(self):
        """WorkflowState() should have conversation_histories == {}."""
        state = WorkflowState()
        assert state.conversation_histories == {}

    def test_default_is_not_shared_across_instances(self):
        """Each WorkflowState instance gets its own empty dict (no mutable default sharing)."""
        state1 = WorkflowState()
        state2 = WorkflowState()
        assert state1.conversation_histories is not state2.conversation_histories


# ===========================================================================
# 2. model_copy works with conversation_histories
# ===========================================================================


class TestConversationHistoriesModelCopy:
    """model_copy(update={"conversation_histories": ...}) must work."""

    def test_model_copy_with_conversation_histories(self):
        """model_copy can set conversation_histories and it appears in model_dump."""
        state = WorkflowState()
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        new_state = state.model_copy(update={"conversation_histories": {"block1_soul1": history}})
        assert new_state.conversation_histories == {"block1_soul1": history}
        # Must be a real field, not extra data
        dumped = new_state.model_dump()
        assert "conversation_histories" in dumped
        assert dumped["conversation_histories"] == {"block1_soul1": history}

    def test_model_copy_preserves_conversation_histories(self):
        """model_copy on other fields preserves conversation_histories."""
        history = [{"role": "user", "content": "test"}]
        state = WorkflowState(conversation_histories={"b1_s1": history})
        new_state = state.model_copy(update={"total_tokens": 100})
        assert new_state.conversation_histories == {"b1_s1": history}

    def test_model_copy_does_not_mutate_original(self):
        """model_copy must not mutate the original state."""
        state = WorkflowState()
        new_state = state.model_copy(
            update={"conversation_histories": {"k": [{"role": "user", "content": "x"}]}}
        )
        assert state.conversation_histories == {}
        assert len(new_state.conversation_histories) == 1


# ===========================================================================
# 3. Construction with populated histories
# ===========================================================================


class TestConversationHistoriesConstruction:
    """WorkflowState can be constructed with conversation_histories."""

    def test_construct_with_single_key(self):
        """A single block_soul key with messages."""
        history = [
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
        ]
        state = WorkflowState(conversation_histories={"block1_soul1": history})
        assert state.conversation_histories["block1_soul1"] == history

    def test_construct_with_multiple_keys(self):
        """Multiple block_soul keys."""
        histories = {
            "block1_soul1": [{"role": "user", "content": "hi"}],
            "block2_soul1": [{"role": "assistant", "content": "hello"}],
            "block1_soul2": [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
            ],
        }
        state = WorkflowState(conversation_histories=histories)
        assert len(state.conversation_histories) == 3
        assert len(state.conversation_histories["block1_soul2"]) == 2

    def test_construct_with_empty_list_value(self):
        """A key can map to an empty list."""
        state = WorkflowState(conversation_histories={"block1_soul1": []})
        assert state.conversation_histories["block1_soul1"] == []


# ===========================================================================
# 4. Serialization — model_dump and model_dump_json
# ===========================================================================


class TestConversationHistoriesSerialization:
    """Serialization must include conversation_histories."""

    def test_model_dump_includes_empty_conversation_histories(self):
        """model_dump() includes conversation_histories even when empty."""
        state = WorkflowState()
        dumped = state.model_dump()
        assert "conversation_histories" in dumped
        assert dumped["conversation_histories"] == {}

    def test_model_dump_includes_populated_conversation_histories(self):
        """model_dump() includes conversation_histories with data."""
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        state = WorkflowState(conversation_histories={"b1_s1": history})
        dumped = state.model_dump()
        assert dumped["conversation_histories"]["b1_s1"] == history

    def test_model_dump_json_empty(self):
        """model_dump_json() works with empty conversation_histories."""
        state = WorkflowState()
        json_str = state.model_dump_json()
        parsed = json.loads(json_str)
        assert "conversation_histories" in parsed
        assert parsed["conversation_histories"] == {}

    def test_model_dump_json_populated(self):
        """model_dump_json() works with populated conversation_histories."""
        histories = {
            "block1_soul1": [
                {"role": "user", "content": "question"},
                {"role": "assistant", "content": "answer"},
            ],
        }
        state = WorkflowState(conversation_histories=histories)
        json_str = state.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["conversation_histories"]["block1_soul1"][0]["role"] == "user"
        assert len(parsed["conversation_histories"]["block1_soul1"]) == 2

    def test_round_trip_via_model_dump(self):
        """model_dump -> WorkflowState(**dump) round-trip preserves conversation_histories."""
        histories = {
            "b1_s1": [{"role": "user", "content": "x"}],
            "b2_s1": [{"role": "assistant", "content": "y"}],
        }
        state = WorkflowState(conversation_histories=histories)
        dumped = state.model_dump()
        restored = WorkflowState(**dumped)
        assert restored.conversation_histories == histories
