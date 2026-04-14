"""RED phase tests for RUN-331: Normalize error responses — HTTPException to RunsightError.

All error responses must use the RunsightError shape:
    {"error": "...", "error_code": "...", "status_code": ...}

No router should return the HTTPException shape:
    {"detail": "..."}

Tests cover all six affected routers:
    steps, tasks, settings, git, sse_stream, eval
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from runsight_api.core.config import settings
from runsight_api.main import app
from runsight_api.transport.deps import (
    get_eval_service,
    get_execution_service,
    get_provider_service,
    get_registry_service,
    get_run_service,
    get_step_repo,
    get_task_repo,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helper: assert RunsightError response shape
# ---------------------------------------------------------------------------


def assert_runsight_error_shape(response, expected_status: int):
    """Verify error response has the RunsightError shape, NOT HTTPException shape."""
    assert response.status_code == expected_status
    body = response.json()
    # Must have RunsightError fields
    assert "error" in body, f"Missing 'error' key in response: {body}"
    assert "error_code" in body, f"Missing 'error_code' key in response: {body}"
    assert "code" not in body, f"Found deprecated 'code' key in response: {body}"
    # Must NOT have HTTPException field
    assert "detail" not in body, f"Found 'detail' key (HTTPException shape) in response: {body}"
    return body


# ===========================================================================
# 1. New error subclasses exist
# ===========================================================================


class TestNewErrorSubclasses:
    """RUN-331 requires new error subclasses for domains that lack them."""

    def test_git_error_exists(self):
        from runsight_api.domain.errors import GitError

        assert GitError.status_code == 400
        assert GitError.error_code == "GIT_ERROR"

    def test_git_error_is_runsight_error(self):
        from runsight_api.domain.errors import GitError, RunsightError

        assert issubclass(GitError, RunsightError)

    def test_eval_not_found_exists(self):
        from runsight_api.domain.errors import EvalNotFound

        assert EvalNotFound.status_code == 404
        assert EvalNotFound.error_code == "EVAL_NOT_FOUND"

    def test_eval_not_found_is_runsight_error(self):
        from runsight_api.domain.errors import EvalNotFound, RunsightError

        assert issubclass(EvalNotFound, RunsightError)

    def test_service_unavailable_error_exists(self):
        from runsight_api.domain.errors import ServiceUnavailable

        assert ServiceUnavailable.status_code == 503
        assert ServiceUnavailable.error_code == "SERVICE_UNAVAILABLE"

    def test_service_unavailable_is_runsight_error(self):
        from runsight_api.domain.errors import RunsightError, ServiceUnavailable

        assert issubclass(ServiceUnavailable, RunsightError)

    def test_validation_error_exists(self):
        from runsight_api.domain.errors import InputValidationError

        assert InputValidationError.status_code == 400
        assert InputValidationError.error_code == "VALIDATION_ERROR"

    def test_validation_error_is_runsight_error(self):
        from runsight_api.domain.errors import InputValidationError, RunsightError

        assert issubclass(InputValidationError, RunsightError)


# ===========================================================================
# 2. Steps router — error response shape
# ===========================================================================


class TestStepsErrorShape:
    """Steps router errors must use RunsightError shape."""

    def test_get_step_404_has_runsight_shape(self):
        mock_registry = Mock()
        mock_registry.discover_steps.return_value = []
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None
        app.dependency_overrides[get_registry_service] = lambda: mock_registry
        app.dependency_overrides[get_step_repo] = lambda: mock_repo
        try:
            response = client.get("/api/steps/nonexistent")
            body = assert_runsight_error_shape(response, 404)
            assert body["error_code"] == "STEP_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()

    def test_update_step_404_has_runsight_shape(self):
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None
        app.dependency_overrides[get_step_repo] = lambda: mock_repo
        try:
            response = client.put("/api/steps/missing", json={"name": "Updated"})
            body = assert_runsight_error_shape(response, 404)
            assert body["error_code"] == "STEP_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 3. Tasks router — error response shape
# ===========================================================================


class TestTasksErrorShape:
    """Tasks router errors must use RunsightError shape."""

    def test_get_task_404_has_runsight_shape(self):
        mock_registry = Mock()
        mock_registry.discover_tasks.return_value = []
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None
        app.dependency_overrides[get_registry_service] = lambda: mock_registry
        app.dependency_overrides[get_task_repo] = lambda: mock_repo
        try:
            response = client.get("/api/tasks/nonexistent")
            body = assert_runsight_error_shape(response, 404)
            assert body["error_code"] == "TASK_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()

    def test_update_task_404_has_runsight_shape(self):
        mock_repo = Mock()
        mock_repo.get_by_id.return_value = None
        app.dependency_overrides[get_task_repo] = lambda: mock_repo
        try:
            response = client.put("/api/tasks/missing", json={"name": "Updated"})
            body = assert_runsight_error_shape(response, 404)
            assert body["error_code"] == "TASK_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 4. Settings router — error response shape
# ===========================================================================


class TestSettingsErrorShape:
    """Settings router errors must use RunsightError shape."""

    def test_get_provider_404_has_runsight_shape(self):
        mock_service = Mock()
        mock_service.get_provider.return_value = None
        app.dependency_overrides[get_provider_service] = lambda: mock_service
        try:
            response = client.get("/api/settings/providers/missing")
            body = assert_runsight_error_shape(response, 404)
            assert body["error_code"] == "PROVIDER_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()

    def test_update_provider_404_has_runsight_shape(self):
        mock_service = Mock()
        mock_service.update_provider.return_value = None
        app.dependency_overrides[get_provider_service] = lambda: mock_service
        try:
            response = client.put(
                "/api/settings/providers/missing",
                json={"id": "missing", "kind": "provider", "name": "Updated"},
            )
            body = assert_runsight_error_shape(response, 404)
            assert body["error_code"] == "PROVIDER_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()

    def test_delete_provider_404_has_runsight_shape(self):
        mock_service = Mock()
        mock_service.delete_provider.return_value = False
        app.dependency_overrides[get_provider_service] = lambda: mock_service
        try:
            response = client.delete("/api/settings/providers/missing")
            body = assert_runsight_error_shape(response, 404)
            assert body["error_code"] == "PROVIDER_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 5. Git router — error response shape
# ===========================================================================


def _init_git_repo(tmp: Path) -> Path:
    """Initialise a throwaway git repo."""
    (tmp / "custom" / "workflows").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@runsight.dev"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    (tmp / "README.md").write_text("init")
    subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp,
        check=True,
        capture_output=True,
    )
    return tmp


@pytest.fixture()
def git_repo(tmp_path):
    repo = _init_git_repo(tmp_path)
    original = settings.base_path
    settings.base_path = str(repo)
    yield repo
    settings.base_path = original


@pytest.fixture()
def non_git_dir(tmp_path):
    original = settings.base_path
    settings.base_path = str(tmp_path)
    yield tmp_path
    settings.base_path = original


class TestGitErrorShape:
    """Git router errors must use RunsightError shape."""

    def test_not_git_repo_has_runsight_shape(self, non_git_dir):
        response = client.get("/api/git/status")
        body = assert_runsight_error_shape(response, 400)
        assert body["error_code"] == "GIT_ERROR"

    def test_commit_empty_message_has_runsight_shape(self, git_repo):
        """Commit message empty after sanitization -> RunsightError shape."""
        (git_repo / "test.txt").write_text("x")
        response = client.post("/api/git/commit", json={"message": "   "})
        if response.status_code == 400:
            body = assert_runsight_error_shape(response, 400)
            assert body["error_code"] == "GIT_ERROR"

    def test_commit_failed_has_runsight_shape(self, git_repo):
        """Committing with nothing to commit -> RunsightError shape."""
        response = client.post("/api/git/commit", json={"message": "empty commit"})
        body = assert_runsight_error_shape(response, 400)
        assert body["error_code"] == "GIT_ERROR"

    def test_git_log_non_repo_has_runsight_shape(self, non_git_dir):
        response = client.get("/api/git/log")
        body = assert_runsight_error_shape(response, 400)
        assert body["error_code"] == "GIT_ERROR"

    def test_path_validation_empty_has_runsight_shape(self, git_repo):
        response = client.post(
            "/api/git/commit",
            json={"message": "test", "files": [""]},
        )
        body = assert_runsight_error_shape(response, 400)
        assert "error_code" in body

    def test_path_traversal_has_runsight_shape(self, git_repo):
        response = client.post(
            "/api/git/commit",
            json={"message": "test", "files": ["../../etc/passwd"]},
        )
        body = assert_runsight_error_shape(response, 400)
        assert "error_code" in body

    def test_flag_injection_has_runsight_shape(self, git_repo):
        response = client.post(
            "/api/git/commit",
            json={"message": "test", "files": ["-rf"]},
        )
        body = assert_runsight_error_shape(response, 400)
        assert "error_code" in body


# ===========================================================================
# 6. SSE Stream router — error response shape
# ===========================================================================


class TestSSEStreamErrorShape:
    """SSE stream router errors must use RunsightError shape."""

    def test_run_not_found_has_runsight_shape(self):
        mock_run_service = Mock()
        mock_run_service.get_run.return_value = None
        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        try:
            response = client.get("/api/runs/nonexistent/stream")
            body = assert_runsight_error_shape(response, 404)
            assert body["error_code"] == "RUN_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()

    def test_execution_service_unavailable_has_runsight_shape(self):
        mock_run_service = Mock()
        mock_run = Mock()
        mock_run.id = "run_1"
        mock_run_service.get_run.return_value = mock_run
        app.dependency_overrides[get_run_service] = lambda: mock_run_service
        app.dependency_overrides[get_execution_service] = lambda: None
        try:
            response = client.get("/api/runs/run_1/stream")
            body = assert_runsight_error_shape(response, 503)
            assert body["error_code"] == "SERVICE_UNAVAILABLE"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 7. Eval router — error response shape
# ===========================================================================


class TestEvalErrorShape:
    """Eval router errors must use RunsightError shape."""

    def test_run_eval_404_has_runsight_shape(self):
        mock_service = Mock()
        mock_service.get_run_eval.return_value = None
        app.dependency_overrides[get_eval_service] = lambda: mock_service
        try:
            response = client.get("/api/runs/nonexistent/eval")
            body = assert_runsight_error_shape(response, 404)
            assert body["error_code"] == "EVAL_NOT_FOUND"
        finally:
            app.dependency_overrides.clear()


# ===========================================================================
# 8. Zero HTTPException raises in router files (static check)
# ===========================================================================


class TestNoHTTPExceptionInRouters:
    """AC1: No router file should raise HTTPException."""

    ROUTER_FILES = [
        "steps.py",
        "tasks.py",
        "settings.py",
        "git.py",
        "sse_stream.py",
        "eval.py",
    ]

    @pytest.mark.parametrize("filename", ROUTER_FILES)
    def test_no_http_exception_raise(self, filename):
        """Router file must not contain 'raise HTTPException'."""
        router_dir = (
            Path(__file__).parent.parent.parent / "src" / "runsight_api" / "transport" / "routers"
        )
        content = (router_dir / filename).read_text()
        assert "raise HTTPException" not in content, f"{filename} still raises HTTPException"
