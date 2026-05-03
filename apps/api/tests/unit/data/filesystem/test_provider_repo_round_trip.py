"""FileSystemProviderRepo preserves provider data across read/write cycles."""

from tests.unit.data.filesystem.provider_repo_builders import (
    _make_provider_data,
)

pytest_plugins = ("tests.unit.data.filesystem.provider_repo_fixtures",)


class TestRoundTrip:
    def test_create_then_get_preserves_data(self, repo):
        """Data must survive a create -> get_by_id round trip."""
        data = _make_provider_data(name="Round Trip Provider")
        created = repo.create(data)
        fetched = repo.get_by_id(created.id)

        assert fetched.name == "Round Trip Provider"
        assert fetched.type == "fixture-provider"
        assert fetched.api_key == "${DUMMY_PROVIDER_KEY}"
        assert fetched.base_url == "http://localhost/fixture-provider/v1"
        assert fetched.is_active is True
        assert fetched.status == "connected"
        assert fetched.models == ["fixture-chat-model", "fixture-small-model"]

    def test_update_then_get_reflects_changes(self, repo):
        """Changes from update() must be visible in a subsequent get_by_id()."""
        created = repo.create(_make_provider_data(name="Updatable"))
        repo.update(
            created.id,
            {
                "id": created.id,
                "kind": "provider",
                "status": "error",
                "models": ["fixture-small-model"],
            },
        )

        fetched = repo.get_by_id(created.id)
        assert fetched.status == "error"
        assert fetched.models == ["fixture-small-model"]
        # Unchanged fields are preserved
        assert fetched.name == "Updatable"
        assert fetched.type == "fixture-provider"
