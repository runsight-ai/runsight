"""BaseBlock artifact helper tests.

The suite verifies write/read delegation, in-memory roundtrips, metadata
forwarding, missing-store guards, edge cases, and inheritance from BaseBlock.
"""

from unittest.mock import AsyncMock

import pytest
from runsight_core.blocks.base import BaseBlock
from runsight_core.state import WorkflowState

# Test helper


class StubBlock(BaseBlock):
    """Minimal concrete BaseBlock subclass for testing helper methods."""

    async def execute(self, state: WorkflowState, **kwargs) -> WorkflowState:
        return state


# ==============================================================================
# write_artifact stores content and returns refs
# ==============================================================================


class TestWriteArtifact:
    """Tests for BaseBlock.write_artifact()."""

    @pytest.mark.asyncio
    async def test_write_artifact_returns_ref_string(self):
        """write_artifact() returns the ref string from store.write()."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")

        ref = await block.write_artifact(state, "my_key", "my content")

        assert ref == "mem://artifact-helper-run/my_key"

    @pytest.mark.asyncio
    async def test_write_artifact_return_type_is_str(self):
        """write_artifact() return value is a str."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")

        ref = await block.write_artifact(state, "k", "v")

        assert isinstance(ref, str)

    @pytest.mark.asyncio
    async def test_write_artifact_delegates_to_store_write(self):
        """write_artifact() calls state.artifact_store.write() with correct args."""
        mock_store = AsyncMock()
        mock_store.write = AsyncMock(return_value="mock-artifact-ref")

        state = WorkflowState(artifact_store=mock_store)
        block = StubBlock("artifact_block")

        ref = await block.write_artifact(state, "the_key", "the_content")

        mock_store.write.assert_awaited_once_with("the_key", "the_content", metadata=None)
        assert ref == "mock-artifact-ref"

    @pytest.mark.asyncio
    async def test_write_artifact_content_retrievable_via_store(self):
        """Content written via write_artifact() is retrievable from the store."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")

        ref = await block.write_artifact(state, "doc", "hello world")
        content = await store.read(ref)

        assert content == "hello world"


# ==============================================================================
# write_artifact forwards metadata
# ==============================================================================


class TestWriteArtifactMetadata:
    """Tests for metadata parameter forwarding in write_artifact()."""

    @pytest.mark.asyncio
    async def test_metadata_forwarded_to_store(self):
        """metadata dict is forwarded to store.write()."""
        mock_store = AsyncMock()
        mock_store.write = AsyncMock(return_value="ref")

        state = WorkflowState(artifact_store=mock_store)
        block = StubBlock("artifact_block")
        meta = {"model": "gpt-4", "tokens": 500}

        await block.write_artifact(state, "key", "content", metadata=meta)

        mock_store.write.assert_awaited_once_with("key", "content", metadata=meta)

    @pytest.mark.asyncio
    async def test_metadata_none_by_default(self):
        """When metadata is not provided, None is forwarded to store.write()."""
        mock_store = AsyncMock()
        mock_store.write = AsyncMock(return_value="ref")

        state = WorkflowState(artifact_store=mock_store)
        block = StubBlock("artifact_block")

        await block.write_artifact(state, "key", "content")

        mock_store.write.assert_awaited_once_with("key", "content", metadata=None)

    @pytest.mark.asyncio
    async def test_metadata_stored_in_artifact_store(self):
        """Metadata provided to write_artifact() is visible in store.list_artifacts()."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")
        meta = {"source": "research", "version": 2}

        await block.write_artifact(state, "doc", "content", metadata=meta)

        artifacts = await store.list_artifacts()
        assert len(artifacts) == 1
        assert artifacts[0]["metadata"] == meta


# ==============================================================================
# read_artifact returns stored content
# ==============================================================================


class TestReadArtifact:
    """Tests for BaseBlock.read_artifact()."""

    @pytest.mark.asyncio
    async def test_read_artifact_returns_content_string(self):
        """read_artifact() returns the content string from store.read()."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")

        ref = await store.write("doc", "the content")
        content = await block.read_artifact(state, ref)

        assert content == "the content"

    @pytest.mark.asyncio
    async def test_read_artifact_return_type_is_str(self):
        """read_artifact() return value is a str."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")

        ref = await store.write("key", "value")
        content = await block.read_artifact(state, ref)

        assert isinstance(content, str)

    @pytest.mark.asyncio
    async def test_read_artifact_delegates_to_store_read(self):
        """read_artifact() calls state.artifact_store.read() with the ref."""
        mock_store = AsyncMock()
        mock_store.read = AsyncMock(return_value="stored content")

        state = WorkflowState(artifact_store=mock_store)
        block = StubBlock("artifact_block")

        content = await block.read_artifact(state, "mem://artifact-helper-run/doc")

        mock_store.read.assert_awaited_once_with("mem://artifact-helper-run/doc")
        assert content == "stored content"


# ==============================================================================
# write and read roundtrips
# ==============================================================================


class TestWriteReadRoundtrip:
    """Tests for the full write_artifact -> read_artifact cycle."""

    @pytest.mark.asyncio
    async def test_write_then_read_returns_original_content(self):
        """ref = write_artifact(...); read_artifact(ref) returns original content."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")

        ref = await block.write_artifact(state, "research", "AI is powerful")
        content = await block.read_artifact(state, ref)

        assert content == "AI is powerful"

    @pytest.mark.asyncio
    async def test_multiple_write_read_roundtrips(self):
        """Multiple artifacts can be written and read back independently."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")

        ref1 = await block.write_artifact(state, "doc1", "content one")
        ref2 = await block.write_artifact(state, "doc2", "content two")

        assert await block.read_artifact(state, ref1) == "content one"
        assert await block.read_artifact(state, ref2) == "content two"


# ==============================================================================
# Missing artifact_store guards
# ==============================================================================


class TestArtifactStoreGuard:
    """Tests for RuntimeError guard when artifact_store is None."""

    @pytest.mark.asyncio
    async def test_write_artifact_raises_runtime_error_when_no_store(self):
        """write_artifact() raises RuntimeError if state.artifact_store is None."""
        state = WorkflowState()  # artifact_store defaults to None
        block = StubBlock("artifact_block")

        with pytest.raises(RuntimeError):
            await block.write_artifact(state, "key", "content")

    @pytest.mark.asyncio
    async def test_read_artifact_raises_runtime_error_when_no_store(self):
        """read_artifact() raises RuntimeError if state.artifact_store is None."""
        state = WorkflowState()  # artifact_store defaults to None
        block = StubBlock("artifact_block")

        with pytest.raises(RuntimeError):
            await block.read_artifact(state, "mem://artifact-helper-run/key")

    @pytest.mark.asyncio
    async def test_write_guard_error_message_mentions_artifact_store(self):
        """RuntimeError message should mention ArtifactStore for clarity."""
        state = WorkflowState()
        block = StubBlock("artifact_block")

        with pytest.raises(RuntimeError, match="(?i)artifactstore|artifact.store"):
            await block.write_artifact(state, "key", "content")

    @pytest.mark.asyncio
    async def test_read_guard_error_message_mentions_artifact_store(self):
        """RuntimeError message should mention ArtifactStore for clarity."""
        state = WorkflowState()
        block = StubBlock("artifact_block")

        with pytest.raises(RuntimeError, match="(?i)artifactstore|artifact.store"):
            await block.read_artifact(state, "some-ref")


# ==============================================================================
# Edge cases
# ==============================================================================


class TestArtifactHelperEdgeCases:
    """Edge case tests for artifact helpers."""

    @pytest.mark.asyncio
    async def test_read_invalid_ref_raises_key_error(self):
        """read_artifact with invalid ref delegates KeyError from store."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")

        with pytest.raises(KeyError):
            await block.read_artifact(state, "mem://artifact-helper-run/nonexistent")

    @pytest.mark.asyncio
    async def test_write_empty_content(self):
        """write_artifact with empty string content succeeds."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="artifact-helper-run")
        state = WorkflowState(artifact_store=store)
        block = StubBlock("artifact_block")

        ref = await block.write_artifact(state, "empty", "")

        assert isinstance(ref, str)
        content = await block.read_artifact(state, ref)
        assert content == ""


# ==============================================================================
# Inheritance exposes helpers on concrete blocks
# ==============================================================================


class TestInheritance:
    """Verify that concrete BaseBlock subclasses inherit the helpers automatically."""

    def test_write_artifact_available_on_subclass(self):
        """A concrete BaseBlock subclass should have write_artifact method."""
        block = StubBlock("artifact_block")
        assert hasattr(block, "write_artifact")
        assert callable(block.write_artifact)

    def test_read_artifact_available_on_subclass(self):
        """A concrete BaseBlock subclass should have read_artifact method."""
        block = StubBlock("artifact_block")
        assert hasattr(block, "read_artifact")
        assert callable(block.read_artifact)

    def test_helpers_come_from_base_block(self):
        """write_artifact and read_artifact should be defined on BaseBlock, not subclass."""
        assert hasattr(BaseBlock, "write_artifact")
        assert hasattr(BaseBlock, "read_artifact")

    def test_linear_block_inherits_helpers(self):
        """LinearBlock (a real concrete block) should inherit the artifact helpers."""
        from unittest.mock import MagicMock

        from runsight_core import LinearBlock
        from runsight_core.primitives import Soul

        soul = Soul(id="writer", kind="soul", name="Writer", role="Writer", system_prompt="Write.")
        runner = MagicMock()
        block = LinearBlock("lartifact_block", soul, runner)

        assert hasattr(block, "write_artifact")
        assert hasattr(block, "read_artifact")
