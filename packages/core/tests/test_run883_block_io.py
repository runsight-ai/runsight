"""
Failing tests for RUN-883: Define BlockContext, BlockOutput models and apply_block_output.

New file `block_io.py` in runsight_core. Tests import from `runsight_core.block_io`
which does not exist yet — all tests are expected to fail with ImportError.

AC coverage:
1. BlockContext model defined with all fields including `artifact_store`
2. BlockOutput model defined with all fields
3. apply_block_output correctly maps all BlockOutput fields to WorkflowState
4. BlockContext.conversation_history is a shallow copy, not a reference to state.conversation_histories
5. log_entries follows existing execution_log format: {'role': 'system', 'content': '...'}
6. shared_memory_updates supports retry metadata keys (`__retry__` prefix)
7. Unit tests for apply_block_output cover: idempotency, cost accumulation, shared_memory merge, log append
"""

import pytest
from runsight_core.artifacts import InMemoryArtifactStore
from runsight_core.block_io import (  # noqa: F401 (import under test — module does not exist yet)
    BlockContext,
    BlockOutput,
    apply_block_output,
)
from runsight_core.primitives import Soul
from runsight_core.state import BlockResult, WorkflowState

# ==============================================================================
# Helpers
# ==============================================================================


def make_soul() -> Soul:
    return Soul(
        id="soul_1",
        kind="soul",
        name="Test",
        role="Researcher",
        system_prompt="You are a researcher.",
    )


def make_artifact_store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore(run_id="run-test-001")


def make_state(**kwargs) -> WorkflowState:
    return WorkflowState(**kwargs)


def make_block_output(**kwargs) -> BlockOutput:
    defaults = dict(output="hello world", log_entries=[])
    defaults.update(kwargs)
    return BlockOutput(**defaults)


# ==============================================================================
# 1. BlockContext model tests
# ==============================================================================


class TestBlockContextModel:
    """BlockContext Pydantic model — field presence, types, defaults, and copy semantics."""

    def test_has_all_required_fields(self):
        """BlockContext.model_fields must include all specified fields."""
        fields = set(BlockContext.model_fields.keys())
        required = {
            "block_id",
            "instruction",
            "context",
            "inputs",
            "conversation_history",
            "soul",
            "model_name",
            "artifact_store",
            "state_snapshot",
        }
        assert required.issubset(fields), f"Missing fields: {required - fields}"

    def test_minimal_construction(self):
        """BlockContext can be constructed with only block_id and instruction."""
        ctx = BlockContext(block_id="b1", instruction="Do something")
        assert ctx.block_id == "b1"
        assert ctx.instruction == "Do something"

    def test_default_context_is_none(self):
        """context field defaults to None."""
        ctx = BlockContext(block_id="b1", instruction="x")
        assert ctx.context is None

    def test_default_inputs_is_empty_dict(self):
        """inputs field defaults to empty dict."""
        ctx = BlockContext(block_id="b1", instruction="x")
        assert ctx.inputs == {}

    def test_default_conversation_history_is_empty_list(self):
        """conversation_history field defaults to empty list."""
        ctx = BlockContext(block_id="b1", instruction="x")
        assert ctx.conversation_history == []

    def test_default_soul_is_none(self):
        """soul field defaults to None."""
        ctx = BlockContext(block_id="b1", instruction="x")
        assert ctx.soul is None

    def test_default_model_name_is_none(self):
        """model_name field defaults to None."""
        ctx = BlockContext(block_id="b1", instruction="x")
        assert ctx.model_name is None

    def test_default_artifact_store_is_none(self):
        """artifact_store field defaults to None."""
        ctx = BlockContext(block_id="b1", instruction="x")
        assert ctx.artifact_store is None

    def test_default_state_snapshot_is_none(self):
        """state_snapshot field defaults to None."""
        ctx = BlockContext(block_id="b1", instruction="x")
        assert ctx.state_snapshot is None

    def test_accepts_soul(self):
        """soul field accepts a Soul instance."""
        soul = make_soul()
        ctx = BlockContext(block_id="b1", instruction="x", soul=soul)
        assert ctx.soul is soul
        assert ctx.soul.id == "soul_1"

    def test_accepts_artifact_store(self):
        """artifact_store field accepts an ArtifactStore instance."""
        store = make_artifact_store()
        ctx = BlockContext(block_id="b1", instruction="x", artifact_store=store)
        assert ctx.artifact_store is store
        assert ctx.artifact_store.run_id == "run-test-001"

    def test_accepts_state_snapshot(self):
        """state_snapshot field accepts a WorkflowState instance."""
        snapshot = make_state(total_cost_usd=2.5)
        ctx = BlockContext(block_id="b1", instruction="x", state_snapshot=snapshot)
        assert ctx.state_snapshot is not None
        assert ctx.state_snapshot.total_cost_usd == 2.5

    def test_accepts_inputs_dict(self):
        """inputs field accepts a dict with arbitrary keys/values."""
        ctx = BlockContext(block_id="b1", instruction="x", inputs={"key": "val", "num": 42})
        assert ctx.inputs["key"] == "val"
        assert ctx.inputs["num"] == 42

    def test_accepts_model_name(self):
        """model_name field accepts a string."""
        ctx = BlockContext(block_id="b1", instruction="x", model_name="gpt-4o")
        assert ctx.model_name == "gpt-4o"

    def test_conversation_history_is_shallow_copy_not_same_reference(self):
        """conversation_history must be a shallow copy — not the same list object passed in.

        AC-4: BlockContext.conversation_history is a shallow copy, not a reference
        to state.conversation_histories.
        """
        original_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        ctx = BlockContext(
            block_id="b1",
            instruction="x",
            conversation_history=original_history,
        )
        # Must be a different list object
        assert ctx.conversation_history is not original_history, (
            "conversation_history must be a shallow copy, not the same reference"
        )

    def test_conversation_history_shallow_copy_same_values(self):
        """Shallow copy preserves the same message dicts (values are equal)."""
        original_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        ctx = BlockContext(
            block_id="b1",
            instruction="x",
            conversation_history=original_history,
        )
        assert ctx.conversation_history == original_history

    def test_mutation_of_original_does_not_affect_context(self):
        """Appending to the original list must not affect ctx.conversation_history."""
        original_history = [{"role": "user", "content": "Hello"}]
        ctx = BlockContext(
            block_id="b1",
            instruction="x",
            conversation_history=original_history,
        )
        original_history.append({"role": "assistant", "content": "Added later"})
        # ctx.conversation_history should still have only 1 entry
        assert len(ctx.conversation_history) == 1


# ==============================================================================
# 2. BlockOutput model tests
# ==============================================================================


class TestBlockOutputModel:
    """BlockOutput Pydantic model — field presence, types, and defaults."""

    def test_has_all_required_fields(self):
        """BlockOutput.model_fields must include all specified fields."""
        fields = set(BlockOutput.model_fields.keys())
        required = {
            "output",
            "exit_handle",
            "artifact_ref",
            "artifact_type",
            "metadata",
            "cost_usd",
            "total_tokens",
            "log_entries",
            "conversation_updates",
            "shared_memory_updates",
            "extra_results",
        }
        assert required.issubset(fields), f"Missing fields: {required - fields}"

    def test_minimal_construction(self):
        """BlockOutput can be constructed with only output."""
        bo = BlockOutput(output="result text")
        assert bo.output == "result text"

    def test_default_exit_handle_is_none(self):
        """exit_handle defaults to None."""
        bo = BlockOutput(output="x")
        assert bo.exit_handle is None

    def test_default_artifact_ref_is_none(self):
        """artifact_ref defaults to None."""
        bo = BlockOutput(output="x")
        assert bo.artifact_ref is None

    def test_default_artifact_type_is_none(self):
        """artifact_type defaults to None."""
        bo = BlockOutput(output="x")
        assert bo.artifact_type is None

    def test_default_metadata_is_empty_dict(self):
        """metadata defaults to empty dict."""
        bo = BlockOutput(output="x")
        assert bo.metadata == {}

    def test_default_cost_usd_is_zero(self):
        """cost_usd defaults to 0.0."""
        bo = BlockOutput(output="x")
        assert bo.cost_usd == 0.0

    def test_default_total_tokens_is_zero(self):
        """total_tokens defaults to 0."""
        bo = BlockOutput(output="x")
        assert bo.total_tokens == 0

    def test_default_log_entries_is_empty_list(self):
        """log_entries defaults to empty list."""
        bo = BlockOutput(output="x")
        assert bo.log_entries == []

    def test_default_conversation_updates_is_none(self):
        """conversation_updates defaults to None."""
        bo = BlockOutput(output="x")
        assert bo.conversation_updates is None

    def test_default_shared_memory_updates_is_none(self):
        """shared_memory_updates defaults to None."""
        bo = BlockOutput(output="x")
        assert bo.shared_memory_updates is None

    def test_default_extra_results_is_none(self):
        """extra_results defaults to None."""
        bo = BlockOutput(output="x")
        assert bo.extra_results is None

    def test_log_entries_format_matches_execution_log(self):
        """log_entries must follow the same format as execution_log: {'role': ..., 'content': ...}.

        AC-5: log_entries follows existing execution_log format.
        """
        entry = {"role": "system", "content": "Block b1 started"}
        bo = BlockOutput(output="x", log_entries=[entry])
        assert len(bo.log_entries) == 1
        assert bo.log_entries[0]["role"] == "system"
        assert bo.log_entries[0]["content"] == "Block b1 started"

    def test_accepts_exit_handle(self):
        """exit_handle field accepts a string."""
        bo = BlockOutput(output="x", exit_handle="success")
        assert bo.exit_handle == "success"

    def test_accepts_artifact_ref_and_type(self):
        """artifact_ref and artifact_type fields accept strings."""
        bo = BlockOutput(output="x", artifact_ref="s3://bucket/obj", artifact_type="json")
        assert bo.artifact_ref == "s3://bucket/obj"
        assert bo.artifact_type == "json"

    def test_accepts_cost_and_tokens(self):
        """cost_usd and total_tokens accept numeric values."""
        bo = BlockOutput(output="x", cost_usd=0.025, total_tokens=512)
        assert bo.cost_usd == 0.025
        assert bo.total_tokens == 512

    def test_accepts_conversation_updates(self):
        """conversation_updates accepts a dict of list-of-dicts."""
        updates = {"b1_soul1": [{"role": "user", "content": "hi"}]}
        bo = BlockOutput(output="x", conversation_updates=updates)
        assert bo.conversation_updates == updates

    def test_accepts_shared_memory_updates(self):
        """shared_memory_updates accepts arbitrary key/value pairs."""
        updates = {"my_key": "my_value", "count": 3}
        bo = BlockOutput(output="x", shared_memory_updates=updates)
        assert bo.shared_memory_updates == updates

    def test_accepts_extra_results(self):
        """extra_results accepts arbitrary key/value pairs."""
        extras = {"other_block": BlockResult(output="side effect")}
        bo = BlockOutput(output="x", extra_results=extras)
        assert bo.extra_results == extras


# ==============================================================================
# 3. apply_block_output tests
# ==============================================================================


class TestApplyBlockOutput:
    """apply_block_output(state, block_id, output) -> WorkflowState — full AC coverage."""

    # ------------------------------------------------------------------
    # 3a. Basic mapping: output -> state.results[block_id] as BlockResult
    # ------------------------------------------------------------------

    def test_maps_output_to_results_as_block_result(self):
        """BlockOutput.output is stored in state.results[block_id] as a BlockResult."""
        state = make_state()
        bo = make_block_output(output="the answer")
        new_state = apply_block_output(state, "block_a", bo)
        assert "block_a" in new_state.results
        result = new_state.results["block_a"]
        assert isinstance(result, BlockResult)
        assert result.output == "the answer"

    def test_maps_exit_handle_to_block_result(self):
        """BlockOutput.exit_handle is stored in state.results[block_id].exit_handle."""
        state = make_state()
        bo = make_block_output(output="x", exit_handle="success")
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.results["block_a"].exit_handle == "success"

    def test_maps_artifact_ref_to_block_result(self):
        """BlockOutput.artifact_ref is stored in state.results[block_id].artifact_ref."""
        state = make_state()
        bo = make_block_output(output="x", artifact_ref="s3://bucket/file.json")
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.results["block_a"].artifact_ref == "s3://bucket/file.json"

    def test_maps_artifact_type_to_block_result(self):
        """BlockOutput.artifact_type is stored in state.results[block_id].artifact_type."""
        state = make_state()
        bo = make_block_output(output="x", artifact_type="json")
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.results["block_a"].artifact_type == "json"

    def test_maps_metadata_to_block_result(self):
        """BlockOutput.metadata is stored in state.results[block_id].metadata."""
        state = make_state()
        meta = {"duration_ms": 300, "model": "gpt-4o"}
        bo = make_block_output(output="x", metadata=meta)
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.results["block_a"].metadata == meta

    # ------------------------------------------------------------------
    # 3b. Cost and token accumulation
    # ------------------------------------------------------------------

    def test_accumulates_cost_usd(self):
        """total_cost_usd is incremented by BlockOutput.cost_usd.

        AC-7: cost accumulation test.
        """
        state = make_state(total_cost_usd=1.0)
        bo = make_block_output(output="x", cost_usd=0.5)
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.total_cost_usd == pytest.approx(1.5)

    def test_accumulates_total_tokens(self):
        """total_tokens is incremented by BlockOutput.total_tokens.

        AC-7: token accumulation test.
        """
        state = make_state(total_tokens=100)
        bo = make_block_output(output="x", total_tokens=50)
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.total_tokens == 150

    def test_zero_cost_output_does_not_change_total(self):
        """When BlockOutput.cost_usd is 0.0, total_cost_usd is unchanged."""
        state = make_state(total_cost_usd=2.0)
        bo = make_block_output(output="x", cost_usd=0.0)
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.total_cost_usd == pytest.approx(2.0)

    # ------------------------------------------------------------------
    # 3c. log_entries appended to execution_log
    # ------------------------------------------------------------------

    def test_appends_log_entries_to_execution_log(self):
        """BlockOutput.log_entries are appended to state.execution_log.

        AC-7: log append test.
        """
        existing_entry = {"role": "system", "content": "Existing log"}
        state = make_state(execution_log=[existing_entry])
        new_entries = [
            {"role": "system", "content": "Block started"},
            {"role": "system", "content": "Block completed"},
        ]
        bo = make_block_output(output="x", log_entries=new_entries)
        new_state = apply_block_output(state, "block_a", bo)
        assert len(new_state.execution_log) == 3
        assert new_state.execution_log[0] == existing_entry
        assert new_state.execution_log[1] == new_entries[0]
        assert new_state.execution_log[2] == new_entries[1]

    def test_empty_log_entries_leaves_execution_log_unchanged(self):
        """If log_entries is empty, execution_log is not modified."""
        existing_entry = {"role": "system", "content": "Only entry"}
        state = make_state(execution_log=[existing_entry])
        bo = make_block_output(output="x", log_entries=[])
        new_state = apply_block_output(state, "block_a", bo)
        assert len(new_state.execution_log) == 1
        assert new_state.execution_log[0] == existing_entry

    # ------------------------------------------------------------------
    # 3d. shared_memory_updates merged into state.shared_memory
    # ------------------------------------------------------------------

    def test_merges_shared_memory_updates(self):
        """BlockOutput.shared_memory_updates are merged into state.shared_memory.

        AC-7: shared_memory merge test.
        """
        state = make_state(shared_memory={"existing_key": "existing_val"})
        bo = make_block_output(output="x", shared_memory_updates={"new_key": "new_val"})
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.shared_memory["existing_key"] == "existing_val"
        assert new_state.shared_memory["new_key"] == "new_val"

    def test_shared_memory_update_overwrites_existing_key(self):
        """A shared_memory_updates key that already exists is overwritten."""
        state = make_state(shared_memory={"key": "old_value"})
        bo = make_block_output(output="x", shared_memory_updates={"key": "new_value"})
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.shared_memory["key"] == "new_value"

    def test_shared_memory_updates_none_does_not_crash(self):
        """When shared_memory_updates is None, shared_memory is unchanged and no crash.

        AC-3: Handles None optional fields gracefully.
        """
        state = make_state(shared_memory={"keep": "this"})
        bo = make_block_output(output="x", shared_memory_updates=None)
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.shared_memory == {"keep": "this"}

    def test_shared_memory_updates_supports_retry_prefix_keys(self):
        """shared_memory_updates accepts __retry__ prefixed keys (retry metadata).

        AC-6: shared_memory_updates supports retry metadata keys.
        """
        state = make_state()
        retry_updates = {
            "__retry__block_a": {"attempt": 2, "reason": "timeout"},
            "normal_key": "normal_val",
        }
        bo = make_block_output(output="x", shared_memory_updates=retry_updates)
        new_state = apply_block_output(state, "block_a", bo)
        assert "__retry__block_a" in new_state.shared_memory
        assert new_state.shared_memory["__retry__block_a"]["attempt"] == 2
        assert new_state.shared_memory["normal_key"] == "normal_val"

    # ------------------------------------------------------------------
    # 3e. conversation_updates merged into state.conversation_histories
    # ------------------------------------------------------------------

    def test_merges_conversation_updates(self):
        """BlockOutput.conversation_updates are merged into state.conversation_histories."""
        state = make_state(
            conversation_histories={"block_a_soul1": [{"role": "user", "content": "Hi"}]}
        )
        new_turn = {"role": "assistant", "content": "Hello!"}
        bo = make_block_output(
            output="x",
            conversation_updates={"block_a_soul1": [new_turn]},
        )
        new_state = apply_block_output(state, "block_a", bo)
        # The new conversation_histories for this key should contain the update
        history = new_state.conversation_histories["block_a_soul1"]
        assert any(msg["content"] == "Hello!" for msg in history)

    def test_conversation_updates_none_does_not_crash(self):
        """When conversation_updates is None, conversation_histories is unchanged."""
        existing = {"soul_key": [{"role": "user", "content": "question"}]}
        state = make_state(conversation_histories=existing)
        bo = make_block_output(output="x", conversation_updates=None)
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state.conversation_histories == existing

    # ------------------------------------------------------------------
    # 3f. extra_results merged into state.results
    # ------------------------------------------------------------------

    def test_merges_extra_results_into_state_results(self):
        """BlockOutput.extra_results are merged into state.results."""
        state = make_state()
        side_result = BlockResult(output="side effect output")
        bo = make_block_output(
            output="primary output",
            extra_results={"sibling_block": side_result},
        )
        new_state = apply_block_output(state, "block_a", bo)
        assert "block_a" in new_state.results
        assert "sibling_block" in new_state.results
        assert new_state.results["sibling_block"].output == "side effect output"

    def test_extra_results_none_does_not_crash(self):
        """When extra_results is None, results only contains the primary block_id entry."""
        state = make_state()
        bo = make_block_output(output="x", extra_results=None)
        new_state = apply_block_output(state, "block_a", bo)
        assert list(new_state.results.keys()) == ["block_a"]

    # ------------------------------------------------------------------
    # 3g. Immutability — original state must not be mutated
    # ------------------------------------------------------------------

    def test_returns_new_workflow_state_instance(self):
        """apply_block_output must return a new WorkflowState, not mutate the original.

        AC-3: Returns new WorkflowState (immutable).
        """
        state = make_state()
        bo = make_block_output(output="x")
        new_state = apply_block_output(state, "block_a", bo)
        assert new_state is not state

    def test_original_state_results_unchanged(self):
        """The original state.results dict must not be modified by apply_block_output."""
        state = make_state()
        original_results = dict(state.results)
        bo = make_block_output(output="x")
        apply_block_output(state, "block_a", bo)
        assert state.results == original_results

    def test_original_state_shared_memory_unchanged(self):
        """The original state.shared_memory must not be modified."""
        state = make_state(shared_memory={"key": "val"})
        original_sm = dict(state.shared_memory)
        bo = make_block_output(output="x", shared_memory_updates={"new_key": "new_val"})
        apply_block_output(state, "block_a", bo)
        assert state.shared_memory == original_sm

    def test_original_state_execution_log_unchanged(self):
        """The original state.execution_log must not be modified."""
        entry = {"role": "system", "content": "existing"}
        state = make_state(execution_log=[entry])
        original_len = len(state.execution_log)
        bo = make_block_output(
            output="x",
            log_entries=[{"role": "system", "content": "new entry"}],
        )
        apply_block_output(state, "block_a", bo)
        assert len(state.execution_log) == original_len

    def test_original_state_cost_unchanged(self):
        """The original state.total_cost_usd must not be modified."""
        state = make_state(total_cost_usd=1.0)
        bo = make_block_output(output="x", cost_usd=5.0)
        apply_block_output(state, "block_a", bo)
        assert state.total_cost_usd == 1.0

    # ------------------------------------------------------------------
    # 3h. Idempotency — applying same output twice accumulates correctly
    # ------------------------------------------------------------------

    def test_idempotency_applying_twice_accumulates_cost(self):
        """Applying the same BlockOutput twice accumulates cost twice.

        AC-7: idempotency test — verifies deterministic accumulation.
        Note: apply_block_output is NOT idempotent; applying twice doubles.
        This test documents that behavior explicitly.
        """
        state = make_state(total_cost_usd=0.0)
        bo = make_block_output(output="x", cost_usd=0.5)
        state_after_first = apply_block_output(state, "block_a", bo)
        state_after_second = apply_block_output(state_after_first, "block_a", bo)
        # Second call overwrites block_a in results but doubles cost
        assert state_after_second.total_cost_usd == pytest.approx(1.0)

    def test_idempotency_applying_twice_overwrites_result(self):
        """Applying apply_block_output twice for the same block_id overwrites the result."""
        state = make_state()
        bo_first = make_block_output(output="first output")
        bo_second = make_block_output(output="second output")
        state_after_first = apply_block_output(state, "block_a", bo_first)
        state_after_second = apply_block_output(state_after_first, "block_a", bo_second)
        assert state_after_second.results["block_a"].output == "second output"

    # ------------------------------------------------------------------
    # 3i. Full integration — all fields in one call
    # ------------------------------------------------------------------

    def test_full_apply_all_fields(self):
        """apply_block_output with all fields set applies correctly in one call."""
        state = make_state(
            total_cost_usd=0.1,
            total_tokens=100,
            execution_log=[{"role": "system", "content": "bootstrap"}],
            shared_memory={"existing": True},
            conversation_histories={"block_a_soul1": []},
        )
        bo = BlockOutput(
            output="full output",
            exit_handle="done",
            artifact_ref="s3://bucket/result.txt",
            artifact_type="text",
            metadata={"model": "gpt-4o", "latency_ms": 123},
            cost_usd=0.25,
            total_tokens=300,
            log_entries=[{"role": "system", "content": "block_a ran"}],
            conversation_updates={"block_a_soul1": [{"role": "assistant", "content": "Reply"}]},
            shared_memory_updates={"result_summary": "done well"},
            extra_results={"post_block": BlockResult(output="post output")},
        )
        new_state = apply_block_output(state, "block_a", bo)

        # results
        assert new_state.results["block_a"].output == "full output"
        assert new_state.results["block_a"].exit_handle == "done"
        assert new_state.results["block_a"].artifact_ref == "s3://bucket/result.txt"
        assert new_state.results["block_a"].artifact_type == "text"
        assert new_state.results["block_a"].metadata == {"model": "gpt-4o", "latency_ms": 123}

        # extra_results
        assert "post_block" in new_state.results
        assert new_state.results["post_block"].output == "post output"

        # cost/tokens
        assert new_state.total_cost_usd == pytest.approx(0.35)
        assert new_state.total_tokens == 400

        # execution_log
        assert len(new_state.execution_log) == 2
        assert new_state.execution_log[1] == {"role": "system", "content": "block_a ran"}

        # shared_memory
        assert new_state.shared_memory["existing"] is True
        assert new_state.shared_memory["result_summary"] == "done well"

        # conversation_histories
        histories = new_state.conversation_histories["block_a_soul1"]
        assert any(m["content"] == "Reply" for m in histories)
