"""
RUN-228: Path traversal validation tests for all 4 filesystem repositories.

Every repo's _get_path() must reject IDs that could escape the base directory.
These tests are expected to FAIL until the validation is implemented.
"""

import pytest

from runsight_api.data.filesystem.soul_repo import SoulRepository
from runsight_api.data.filesystem.step_repo import StepRepository
from runsight_api.data.filesystem.workflow_repo import WorkflowRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def soul_repo(tmp_path):
    return SoulRepository(base_path=str(tmp_path))


@pytest.fixture
def step_repo(tmp_path):
    return StepRepository(base_path=str(tmp_path))


@pytest.fixture
def workflow_repo(tmp_path):
    return WorkflowRepository(base_path=str(tmp_path))


# ---------------------------------------------------------------------------
# Malicious IDs to test against
# ---------------------------------------------------------------------------

# IDs containing ".." directory traversal
DOTDOT_IDS = [
    "../etc/passwd",
    "../../etc/shadow",
    "foo/../../../etc/passwd",
    "..",
    "../",
    "..\\",
]

# IDs containing path separators
SEPARATOR_IDS = [
    "foo/bar",
    "foo\\bar",
    "sub/dir/file",
    "sub\\dir\\file",
]

# Absolute paths
ABSOLUTE_IDS = [
    "/etc/passwd",
    "/tmp/evil",
]

# URL-encoded traversal sequences
URL_ENCODED_IDS = [
    "%2e%2e%2fetc%2fpasswd",  # ../etc/passwd
    "%2e%2e/etc/passwd",  # ../etc/passwd (partial encode)
    "..%2fetc%2fpasswd",  # ../etc/passwd (partial encode)
    "%2e%2e%5cetc%5cpasswd",  # ..\etc\passwd
]

# Combine all malicious IDs for parametrized tests
ALL_MALICIOUS_IDS = DOTDOT_IDS + SEPARATOR_IDS + ABSOLUTE_IDS + URL_ENCODED_IDS


# ---------------------------------------------------------------------------
# Normal IDs should be accepted (sanity checks)
# ---------------------------------------------------------------------------


class TestNormalIdsAccepted:
    """Ensure normal, safe IDs do not raise errors."""

    SAFE_IDS = [
        "my-soul-123",
        "test_soul",
        "simple",
        "CamelCase",
        "with-dashes-and-123",
        "UPPER_CASE_ID",
        "a",
        "soul-with-many-dashes-in-name",
    ]

    @pytest.mark.parametrize("safe_id", SAFE_IDS)
    def test_soul_repo_accepts_normal_ids(self, soul_repo, safe_id):
        """SoulRepository._get_path should not raise for safe IDs."""
        path = soul_repo._get_path(safe_id)
        assert path.name == f"{safe_id}.yaml"

    @pytest.mark.parametrize("safe_id", SAFE_IDS)
    def test_step_repo_accepts_normal_ids(self, step_repo, safe_id):
        """StepRepository._get_path should not raise for safe IDs."""
        path = step_repo._get_path(safe_id)
        assert path.name == f"{safe_id}.yaml"

    @pytest.mark.parametrize("safe_id", SAFE_IDS)
    def test_workflow_repo_accepts_normal_ids(self, workflow_repo, safe_id):
        """WorkflowRepository._get_path should not raise for safe IDs."""
        path = workflow_repo._get_path(safe_id)
        assert path.name == f"{safe_id}.yaml"


# ---------------------------------------------------------------------------
# _get_path must reject malicious IDs with ValueError
# ---------------------------------------------------------------------------


class TestSoulRepoRejectsTraversal:
    """SoulRepository._get_path must raise ValueError for path-traversal IDs."""

    @pytest.mark.parametrize("malicious_id", DOTDOT_IDS, ids=lambda x: f"dotdot:{x}")
    def test_rejects_dotdot_traversal(self, soul_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            soul_repo._get_path(malicious_id)

    @pytest.mark.parametrize("malicious_id", SEPARATOR_IDS, ids=lambda x: f"sep:{x}")
    def test_rejects_path_separators(self, soul_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            soul_repo._get_path(malicious_id)

    @pytest.mark.parametrize("malicious_id", ABSOLUTE_IDS, ids=lambda x: f"abs:{x}")
    def test_rejects_absolute_paths(self, soul_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            soul_repo._get_path(malicious_id)

    @pytest.mark.parametrize("malicious_id", URL_ENCODED_IDS, ids=lambda x: f"url:{x}")
    def test_rejects_url_encoded_traversal(self, soul_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            soul_repo._get_path(malicious_id)


class TestStepRepoRejectsTraversal:
    """StepRepository._get_path must raise ValueError for path-traversal IDs."""

    @pytest.mark.parametrize("malicious_id", DOTDOT_IDS, ids=lambda x: f"dotdot:{x}")
    def test_rejects_dotdot_traversal(self, step_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            step_repo._get_path(malicious_id)

    @pytest.mark.parametrize("malicious_id", SEPARATOR_IDS, ids=lambda x: f"sep:{x}")
    def test_rejects_path_separators(self, step_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            step_repo._get_path(malicious_id)

    @pytest.mark.parametrize("malicious_id", ABSOLUTE_IDS, ids=lambda x: f"abs:{x}")
    def test_rejects_absolute_paths(self, step_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            step_repo._get_path(malicious_id)

    @pytest.mark.parametrize("malicious_id", URL_ENCODED_IDS, ids=lambda x: f"url:{x}")
    def test_rejects_url_encoded_traversal(self, step_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            step_repo._get_path(malicious_id)


class TestWorkflowRepoRejectsTraversal:
    """WorkflowRepository._get_path must raise ValueError for path-traversal IDs."""

    @pytest.mark.parametrize("malicious_id", DOTDOT_IDS, ids=lambda x: f"dotdot:{x}")
    def test_rejects_dotdot_traversal(self, workflow_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            workflow_repo._get_path(malicious_id)

    @pytest.mark.parametrize("malicious_id", SEPARATOR_IDS, ids=lambda x: f"sep:{x}")
    def test_rejects_path_separators(self, workflow_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            workflow_repo._get_path(malicious_id)

    @pytest.mark.parametrize("malicious_id", ABSOLUTE_IDS, ids=lambda x: f"abs:{x}")
    def test_rejects_absolute_paths(self, workflow_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            workflow_repo._get_path(malicious_id)

    @pytest.mark.parametrize("malicious_id", URL_ENCODED_IDS, ids=lambda x: f"url:{x}")
    def test_rejects_url_encoded_traversal(self, workflow_repo, malicious_id):
        with pytest.raises(ValueError, match="[Pp]ath|[Ii]nvalid|[Tt]raversal"):
            workflow_repo._get_path(malicious_id)


# ---------------------------------------------------------------------------
# Integration tests: ensure traversal is blocked through public API methods
# ---------------------------------------------------------------------------


class TestPublicApiRejectsTraversal:
    """Traversal must be blocked at the public API level (get_by_id, create, etc.)."""

    def test_soul_get_by_id_rejects_traversal(self, soul_repo):
        with pytest.raises(ValueError):
            soul_repo.get_by_id("../../../etc/passwd")

    def test_soul_create_rejects_traversal(self, soul_repo):
        with pytest.raises(ValueError):
            soul_repo.create({"id": "../../../evil", "name": "Evil"})

    def test_soul_update_rejects_traversal(self, soul_repo):
        with pytest.raises(ValueError):
            soul_repo.update("../../../evil", {"name": "Evil"})

    def test_soul_delete_rejects_traversal(self, soul_repo):
        with pytest.raises(ValueError):
            soul_repo.delete("../../../evil")

    def test_step_get_by_id_rejects_traversal(self, step_repo):
        with pytest.raises(ValueError):
            step_repo.get_by_id("../../../etc/passwd")

    def test_step_create_rejects_traversal(self, step_repo):
        with pytest.raises(ValueError):
            step_repo.create({"id": "../../../evil", "name": "Evil"})

    def test_step_delete_rejects_traversal(self, step_repo):
        with pytest.raises(ValueError):
            step_repo.delete("../../../evil")

    def test_workflow_get_by_id_rejects_traversal(self, workflow_repo):
        with pytest.raises(ValueError):
            workflow_repo.get_by_id("../../../etc/passwd")

    def test_workflow_delete_rejects_traversal(self, workflow_repo):
        with pytest.raises(ValueError):
            workflow_repo.delete("../../../evil")


# ---------------------------------------------------------------------------
# Containment check: resolved path must stay within base directory
# ---------------------------------------------------------------------------


class TestResolvedPathContainment:
    """
    Even if an ID somehow bypasses character checks, the resolved path
    must stay within the repo's base directory (defense in depth).
    """

    def test_soul_path_stays_within_base(self, soul_repo):
        """_get_path result must always be under the canonical entity_dir."""
        path = soul_repo._get_path("normal-id")
        resolved = path.resolve()
        base_resolved = soul_repo.entity_dir.resolve()
        assert str(resolved).startswith(str(base_resolved)), (
            f"Path {resolved} escapes base directory {base_resolved}"
        )

    def test_step_path_stays_within_base(self, step_repo):
        path = step_repo._get_path("normal-id")
        resolved = path.resolve()
        base_resolved = step_repo.entity_dir.resolve()
        assert str(resolved).startswith(str(base_resolved)), (
            f"Path {resolved} escapes base directory {base_resolved}"
        )

    def test_workflow_path_stays_within_base(self, workflow_repo):
        path = workflow_repo._get_path("normal-id")
        resolved = path.resolve()
        base_resolved = workflow_repo.workflows_dir.resolve()
        assert str(resolved).startswith(str(base_resolved)), (
            f"Path {resolved} escapes base directory {base_resolved}"
        )
