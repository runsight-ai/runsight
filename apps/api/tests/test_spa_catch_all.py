"""constrain SPA catch-all to the configured static root."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient
import pytest


@pytest.fixture()
def spa_client(monkeypatch):
    """Build a fresh app whose catch-all serves from a test-controlled static root."""
    from runsight_api import main as main_module

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    def _make(static_dir: Path) -> TestClient:
        monkeypatch.setenv("RUNSIGHT_STATIC_DIR", str(static_dir))
        monkeypatch.setattr(main_module, "lifespan", noop_lifespan)
        return TestClient(main_module.create_app(), raise_server_exceptions=False)

    return _make


@pytest.fixture()
def static_site(tmp_path):
    """Create a minimal frontend build tree for catch-all route tests."""
    static_dir = tmp_path / "frontend"
    static_dir.mkdir()
    index_bytes = b"<html><body>runsight spa shell</body></html>"
    (static_dir / "index.html").write_bytes(index_bytes)
    return static_dir, index_bytes


def _assert_rejected(response, *, index_bytes: bytes) -> None:
    assert response.status_code == 404, (
        f"Expected SPA catch-all to reject with 404, got {response.status_code} "
        f"with body {response.content!r}"
    )
    assert response.content != index_bytes


class TestSpaCatchAllStaticRoot:
    def test_serves_real_in_root_file_reached_by_catch_all(self, spa_client, static_site):
        static_dir, _index_bytes = static_site
        docs_dir = static_dir / "docs"
        docs_dir.mkdir()
        file_bytes = b"catch-all served docs"
        (docs_dir / "guide.txt").write_bytes(file_bytes)

        with spa_client(static_dir) as client:
            response = client.get("/docs/guide.txt")

        assert response.status_code == 200
        assert response.content == file_bytes

    def test_serves_index_for_nested_spa_route_without_backing_file(self, spa_client, static_site):
        static_dir, index_bytes = static_site

        with spa_client(static_dir) as client:
            response = client.get("/app/settings/profile")

        assert response.status_code == 200
        assert response.content == index_bytes

    def test_returns_404_for_percent_encoded_traversal(self, spa_client, static_site):
        static_dir, index_bytes = static_site
        outside_bytes = b"outside static root"
        (static_dir.parent / "secret.txt").write_bytes(outside_bytes)

        with spa_client(static_dir) as client:
            response = client.get("/%2e%2e/secret.txt")

        _assert_rejected(response, index_bytes=index_bytes)

    def test_returns_404_for_sibling_prefix_escape(self, spa_client, static_site):
        static_dir, index_bytes = static_site
        sibling = static_dir.parent / f"{static_dir.name}-escape"
        sibling.mkdir()
        (sibling / "secret.txt").write_bytes(b"sibling prefix escape")

        with spa_client(static_dir) as client:
            response = client.get(f"/%2e%2e/{sibling.name}/secret.txt")

        _assert_rejected(response, index_bytes=index_bytes)

    def test_returns_404_for_symlink_escape(self, spa_client, static_site):
        static_dir, index_bytes = static_site
        outside_dir = static_dir.parent / "outside"
        outside_dir.mkdir()
        (outside_dir / "secret.txt").write_bytes(b"symlink escape")

        link = static_dir / "linked-outside"
        link.symlink_to(outside_dir, target_is_directory=True)

        with spa_client(static_dir) as client:
            response = client.get("/linked-outside/secret.txt")

        _assert_rejected(response, index_bytes=index_bytes)
