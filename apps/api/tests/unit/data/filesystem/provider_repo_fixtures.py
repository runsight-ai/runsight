"""Shared FileSystemProviderRepo fixtures."""

import pytest

from runsight_api.data.filesystem.provider_repo import FileSystemProviderRepo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    """Create a FileSystemProviderRepo rooted at a temporary directory."""
    return FileSystemProviderRepo(base_path=str(tmp_path))


@pytest.fixture
def providers_dir(tmp_path):
    """Return the expected providers directory path."""
    return tmp_path / "custom" / "providers"


# ===========================================================================
# custom/providers/ remains lazy until provider persistence needs it
# ===========================================================================
