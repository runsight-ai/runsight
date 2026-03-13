from fastapi.testclient import TestClient
from unittest.mock import Mock
from runsight_api.main import app
from runsight_api.transport.deps import get_git_service

client = TestClient(app)


def test_git_status():
    mock_service = Mock()
    mock_service.get_status.return_value = {
        "branch": "main",
        "files": [],
        "is_clean": True,
    }
    app.dependency_overrides[get_git_service] = lambda: mock_service

    response = client.get("/api/git/status")
    assert response.status_code == 200
    data = response.json()
    assert "branch" in data
    assert "files" in data
    assert "is_clean" in data
    app.dependency_overrides.clear()


def test_git_status_500():
    mock_service = Mock()
    mock_service.get_status.side_effect = Exception("Not a git repo")
    app.dependency_overrides[get_git_service] = lambda: mock_service

    response = client.get("/api/git/status")
    assert response.status_code == 500
    app.dependency_overrides.clear()


def test_git_diff():
    mock_service = Mock()
    mock_service.get_diff.return_value = ""
    app.dependency_overrides[get_git_service] = lambda: mock_service

    response = client.get("/api/git/diff")
    assert response.status_code == 200
    data = response.json()
    assert "diff" in data
    app.dependency_overrides.clear()


def test_git_log():
    mock_service = Mock()
    mock_service.get_log.return_value = []
    app.dependency_overrides[get_git_service] = lambda: mock_service

    response = client.get("/api/git/log?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    app.dependency_overrides.clear()


def test_git_commit():
    mock_service = Mock()
    mock_service.commit.return_value = {"hash": "abc123", "message": "test"}
    app.dependency_overrides[get_git_service] = lambda: mock_service

    response = client.post("/api/git/commit", json={"message": "test commit"})
    assert response.status_code == 200
    app.dependency_overrides.clear()


def test_git_commit_422():
    app.dependency_overrides.clear()
    response = client.post("/api/git/commit", json={})  # message required
    assert response.status_code == 422
