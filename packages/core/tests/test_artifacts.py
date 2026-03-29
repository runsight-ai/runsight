"""
Failing tests for RUN-183: ArtifactStore ABC + InMemoryArtifactStore.

Tests cover:
- ArtifactStore ABC cannot be instantiated directly
- InMemoryArtifactStore.write() stores content and returns ref string
- InMemoryArtifactStore.read() retrieves stored content by ref
- InMemoryArtifactStore.list_artifacts() returns list of artifact info dicts
- InMemoryArtifactStore.cleanup() clears all stored data
- Edge cases: non-existent ref, duplicate key overwrite, empty content, metadata handling
"""

import pytest


# ==============================================================================
# ArtifactStore ABC Tests
# ==============================================================================


class TestArtifactStoreABC:
    """Tests for the ArtifactStore abstract base class."""

    def test_abc_cannot_be_instantiated(self):
        """ArtifactStore ABC cannot be instantiated directly."""
        from runsight_core.artifacts import ArtifactStore

        with pytest.raises(TypeError):
            ArtifactStore(run_id="run123")

    def test_abc_is_importable(self):
        """ArtifactStore is importable from runsight_core.artifacts."""
        from runsight_core.artifacts import ArtifactStore

        assert ArtifactStore is not None

    def test_abc_defines_write_method(self):
        """ArtifactStore defines an abstract write method."""
        from runsight_core.artifacts import ArtifactStore

        assert hasattr(ArtifactStore, "write")

    def test_abc_defines_read_method(self):
        """ArtifactStore defines an abstract read method."""
        from runsight_core.artifacts import ArtifactStore

        assert hasattr(ArtifactStore, "read")

    def test_abc_defines_list_artifacts_method(self):
        """ArtifactStore defines an abstract list_artifacts method."""
        from runsight_core.artifacts import ArtifactStore

        assert hasattr(ArtifactStore, "list_artifacts")

    def test_abc_defines_cleanup_method(self):
        """ArtifactStore defines an abstract cleanup method."""
        from runsight_core.artifacts import ArtifactStore

        assert hasattr(ArtifactStore, "cleanup")


# ==============================================================================
# InMemoryArtifactStore Construction Tests
# ==============================================================================


class TestInMemoryArtifactStoreConstruction:
    """Tests for InMemoryArtifactStore instantiation."""

    def test_construction_with_run_id(self):
        """InMemoryArtifactStore can be constructed with a run_id."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        assert store is not None

    def test_run_id_stored(self):
        """InMemoryArtifactStore stores the run_id."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        assert store.run_id == "run123"

    def test_is_subclass_of_artifact_store(self):
        """InMemoryArtifactStore is a subclass of ArtifactStore."""
        from runsight_core.artifacts import ArtifactStore, InMemoryArtifactStore

        assert issubclass(InMemoryArtifactStore, ArtifactStore)

    def test_starts_empty(self):
        """Freshly constructed store has no artifacts."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        # Verify via list_artifacts being empty — tested async below
        assert store is not None


# ==============================================================================
# InMemoryArtifactStore.write() Tests
# ==============================================================================


class TestInMemoryArtifactStoreWrite:
    """Tests for the write method."""

    async def test_write_returns_ref_string(self):
        """write() returns a ref string in mem://{run_id}/{key} format."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        ref = await store.write("research_output", "long text...")
        assert ref == "mem://run123/research_output"

    async def test_write_returns_string_type(self):
        """write() return value is a string."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        ref = await store.write("key1", "content1")
        assert isinstance(ref, str)

    async def test_write_with_metadata(self):
        """write() accepts optional metadata dict."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        ref = await store.write("output", "content", metadata={"model": "gpt-4", "tokens": 100})
        assert ref == "mem://run123/output"

    async def test_write_without_metadata(self):
        """write() works without metadata (defaults to None)."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        ref = await store.write("key1", "content1")
        assert ref == "mem://run123/key1"

    async def test_write_empty_content(self):
        """write() with empty string content is valid."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        ref = await store.write("empty_artifact", "")
        assert ref == "mem://run123/empty_artifact"
        # Verify empty content is retrievable
        content = await store.read(ref)
        assert content == ""

    async def test_write_duplicate_key_overwrites(self):
        """Writing the same key twice overwrites (last write wins)."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "first version")
        await store.write("key1", "second version")
        content = await store.read("mem://run123/key1")
        assert content == "second version"

    async def test_write_multiple_keys(self):
        """Multiple different keys can be written."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        ref1 = await store.write("key1", "content1")
        ref2 = await store.write("key2", "content2")
        assert ref1 == "mem://run123/key1"
        assert ref2 == "mem://run123/key2"
        assert ref1 != ref2


# ==============================================================================
# InMemoryArtifactStore.read() Tests
# ==============================================================================


class TestInMemoryArtifactStoreRead:
    """Tests for the read method."""

    async def test_read_returns_stored_content(self):
        """read() returns the content that was written."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("research_output", "long text...")
        content = await store.read("mem://run123/research_output")
        assert content == "long text..."

    async def test_read_returns_string_type(self):
        """read() return value is a string."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "content1")
        content = await store.read("mem://run123/key1")
        assert isinstance(content, str)

    async def test_read_nonexistent_ref_raises(self):
        """read() with a non-existent ref raises KeyError or ValueError."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        with pytest.raises((KeyError, ValueError)):
            await store.read("mem://run123/nonexistent")

    async def test_read_after_overwrite_returns_latest(self):
        """read() after overwrite returns the latest content."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "v1")
        await store.write("key1", "v2")
        content = await store.read("mem://run123/key1")
        assert content == "v2"


# ==============================================================================
# InMemoryArtifactStore.list_artifacts() Tests
# ==============================================================================


class TestInMemoryArtifactStoreListArtifacts:
    """Tests for the list_artifacts method."""

    async def test_list_artifacts_empty_store(self):
        """list_artifacts() returns empty list for a fresh store."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        artifacts = await store.list_artifacts()
        assert artifacts == []

    async def test_list_artifacts_returns_list(self):
        """list_artifacts() returns a list type."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        artifacts = await store.list_artifacts()
        assert isinstance(artifacts, list)

    async def test_list_artifacts_after_write(self):
        """list_artifacts() returns info for each written artifact."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("research_output", "long text...")
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 1
        assert isinstance(artifacts[0], dict)

    async def test_list_artifacts_contains_key_and_ref(self):
        """Each artifact info dict contains at least 'key' and 'ref'."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("research_output", "long text...")
        artifacts = await store.list_artifacts()
        artifact = artifacts[0]
        assert "key" in artifact
        assert "ref" in artifact
        assert artifact["key"] == "research_output"
        assert artifact["ref"] == "mem://run123/research_output"

    async def test_list_artifacts_multiple(self):
        """list_artifacts() returns all written artifacts."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "content1")
        await store.write("key2", "content2")
        await store.write("key3", "content3")
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 3
        keys = {a["key"] for a in artifacts}
        assert keys == {"key1", "key2", "key3"}

    async def test_list_artifacts_after_overwrite_no_duplicates(self):
        """Overwriting a key does not create a duplicate entry."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "v1")
        await store.write("key1", "v2")
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 1
        assert artifacts[0]["key"] == "key1"


# ==============================================================================
# InMemoryArtifactStore.cleanup() Tests
# ==============================================================================


class TestInMemoryArtifactStoreCleanup:
    """Tests for the cleanup method."""

    async def test_cleanup_empties_store(self):
        """cleanup() removes all stored artifacts."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "content1")
        await store.write("key2", "content2")
        await store.cleanup()
        artifacts = await store.list_artifacts()
        assert artifacts == []

    async def test_cleanup_makes_read_fail(self):
        """After cleanup(), read() for previously stored ref raises."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        ref = await store.write("key1", "content1")
        await store.cleanup()
        with pytest.raises((KeyError, ValueError)):
            await store.read(ref)

    async def test_cleanup_on_empty_store_is_noop(self):
        """cleanup() on an already-empty store does not raise."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.cleanup()  # Should not raise
        artifacts = await store.list_artifacts()
        assert artifacts == []

    async def test_write_after_cleanup(self):
        """Store can be used normally after cleanup()."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "before cleanup")
        await store.cleanup()
        ref = await store.write("key2", "after cleanup")
        assert ref == "mem://run123/key2"
        content = await store.read(ref)
        assert content == "after cleanup"
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 1


# ==============================================================================
# Metadata Handling Tests
# ==============================================================================


class TestInMemoryArtifactStoreMetadata:
    """Tests for metadata storage and retrieval."""

    async def test_metadata_stored_with_artifact(self):
        """Metadata passed to write() is preserved in list_artifacts()."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "content1", metadata={"model": "gpt-4", "tokens": 100})
        artifacts = await store.list_artifacts()
        artifact = artifacts[0]
        assert "metadata" in artifact
        assert artifact["metadata"] == {"model": "gpt-4", "tokens": 100}

    async def test_metadata_none_when_not_provided(self):
        """When metadata is not provided, it defaults to None in listing."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "content1")
        artifacts = await store.list_artifacts()
        artifact = artifacts[0]
        assert artifact.get("metadata") is None

    async def test_metadata_overwritten_with_key(self):
        """When a key is overwritten, metadata is also replaced."""
        from runsight_core.artifacts import InMemoryArtifactStore

        store = InMemoryArtifactStore(run_id="run123")
        await store.write("key1", "v1", metadata={"version": 1})
        await store.write("key1", "v2", metadata={"version": 2})
        artifacts = await store.list_artifacts()
        assert len(artifacts) == 1
        assert artifacts[0]["metadata"] == {"version": 2}
