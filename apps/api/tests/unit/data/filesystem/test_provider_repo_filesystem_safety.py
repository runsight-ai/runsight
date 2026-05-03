"""FileSystemProviderRepo rejects unsafe paths and writes atomically."""

import os

import pytest

from tests.unit.data.filesystem.provider_repo_builders import (
    _make_provider_data,
)

pytest_plugins = ("tests.unit.data.filesystem.provider_repo_fixtures",)


class TestPathTraversalProtection:
    MALICIOUS_IDS = [
        "../etc/passwd",
        "../../etc/shadow",
        "foo/../../../etc/passwd",
        "..",
        "../",
        "..\\",
        "foo/bar",
        "foo\\bar",
        "/etc/passwd",
        "%2e%2e%2fetc%2fpasswd",
    ]

    @pytest.mark.parametrize("malicious_id", MALICIOUS_IDS)
    def test_get_by_id_rejects_traversal(self, repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            repo.get_by_id(malicious_id)

    @pytest.mark.parametrize("malicious_id", MALICIOUS_IDS)
    def test_update_rejects_traversal(self, repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            repo.update(malicious_id, {"status": "error"})

    @pytest.mark.parametrize("malicious_id", MALICIOUS_IDS)
    def test_delete_rejects_traversal(self, repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            repo.delete(malicious_id)

    def test_normal_id_accepted(self, repo):
        """Safe IDs must not trigger path traversal errors."""
        # Should not raise — provider just doesn't exist
        result = repo.get_by_id("totally-safe-id")
        assert result is None


# ===========================================================================
# Atomic writes via temp file + rename
# ===========================================================================


class TestAtomicWrites:
    def test_create_uses_atomic_write(self, repo, providers_dir, monkeypatch):
        """create() must write via temp file + os.rename, not direct write."""
        renames = []
        original_rename = os.rename

        def tracking_rename(src, dst):
            renames.append((src, dst))
            return original_rename(src, dst)

        monkeypatch.setattr(os, "rename", tracking_rename)

        repo.create(_make_provider_data(name="Atomic Test"))

        # At least one rename must have happened targeting the providers dir
        assert len(renames) >= 1, "No os.rename calls detected — write is not atomic"
        dst_paths = [dst for _, dst in renames]
        assert any(str(providers_dir) in str(p) for p in dst_paths), (
            f"Rename destination not in providers dir: {dst_paths}"
        )

    def test_update_uses_atomic_write(self, repo, providers_dir, monkeypatch):
        """update() must also use atomic writes."""
        created = repo.create(_make_provider_data(name="Atomic Update"))

        renames = []
        original_rename = os.rename

        def tracking_rename(src, dst):
            renames.append((src, dst))
            return original_rename(src, dst)

        monkeypatch.setattr(os, "rename", tracking_rename)

        repo.update(created.id, {"id": created.id, "kind": "provider", "status": "offline"})

        assert len(renames) >= 1, "No os.rename calls detected — write is not atomic"


# ===========================================================================
# list_all skips malformed YAML files with logged warning
# ===========================================================================
