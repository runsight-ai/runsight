"""RUN-404: list_runs_paginated must accept and filter by workflow_id.

Bug: The router passes workflow_id to run_service.list_runs_paginated()
but the method signature does not accept it, causing TypeError at runtime.

AC:
- GET /api/runs?workflow_id=X returns only runs for that workflow
- GET /api/runs without workflow_id still works (no regression)
- No TypeError at runtime
"""

from unittest.mock import Mock

import pytest

from runsight_api.logic.services.run_service import RunService
from runsight_api.domain.entities.run import Run, RunStatus


# --- Fixtures ---


@pytest.fixture
def run_repo():
    return Mock()


@pytest.fixture
def workflow_repo():
    return Mock()


@pytest.fixture
def run_service(run_repo, workflow_repo):
    return RunService(run_repo, workflow_repo)


# --- Helpers ---


def _make_run(run_id: str, workflow_id: str) -> Run:
    return Run(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=workflow_id,
        status=RunStatus.pending,
        task_json="{}",
    )


# --- AC 3: No TypeError — list_runs_paginated accepts workflow_id param ---


class TestWorkflowIdParamAccepted:
    """list_runs_paginated must accept workflow_id without raising TypeError."""

    def test_passing_workflow_id_does_not_raise_type_error(self, run_service, run_repo):
        """Calling list_runs_paginated(workflow_id='wf_1') must not raise TypeError."""
        run_repo.list_runs_paginated.return_value = ([], 0)

        # This is the exact call the router makes — currently raises TypeError
        # because list_runs_paginated does not accept workflow_id.
        run_service.list_runs_paginated(offset=0, limit=20, workflow_id="wf_1")

    def test_passing_workflow_id_none_does_not_raise_type_error(self, run_service, run_repo):
        """Calling list_runs_paginated(workflow_id=None) must not raise TypeError."""
        run_repo.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, workflow_id=None)


# --- AC 1: workflow_id is forwarded to repo for filtering ---


class TestWorkflowIdForwardedToRepo:
    """When workflow_id is provided, it must be forwarded to the repo layer."""

    def test_workflow_id_forwarded_to_repo(self, run_service, run_repo):
        """list_runs_paginated must pass workflow_id through to run_repo."""
        run_repo.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, workflow_id="wf_abc")

        # The repo must receive workflow_id so it can filter the SQL query
        run_repo.list_runs_paginated.assert_called_once()
        _, kwargs = run_repo.list_runs_paginated.call_args
        assert kwargs.get("workflow_id") == "wf_abc", (
            "run_repo.list_runs_paginated must be called with workflow_id='wf_abc'"
        )

    def test_workflow_id_none_not_required_in_repo_call(self, run_service, run_repo):
        """When workflow_id is None, repo may be called without it or with None."""
        run_repo.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, workflow_id=None)

        run_repo.list_runs_paginated.assert_called_once()


# --- AC 2: No regression — without workflow_id still works ---


class TestNoRegressionWithoutWorkflowId:
    """Calling list_runs_paginated without workflow_id must still work."""

    def test_without_workflow_id_returns_all_runs(self, run_service, run_repo):
        """Omitting workflow_id returns the full paginated result (no filtering)."""
        runs = [_make_run("r1", "wf_1"), _make_run("r2", "wf_2")]
        run_repo.list_runs_paginated.return_value = (runs, 2)

        items, total = run_service.list_runs_paginated(offset=0, limit=20)

        assert total == 2
        assert len(items) == 2

    def test_with_status_only_still_works(self, run_service, run_repo):
        """Passing status without workflow_id must still work (existing behavior)."""
        runs = [_make_run("r1", "wf_1")]
        run_repo.list_runs_paginated.return_value = (runs, 1)

        items, total = run_service.list_runs_paginated(offset=0, limit=20, status=["pending"])

        assert total == 1
        assert len(items) == 1

    def test_with_status_and_workflow_id_together(self, run_service, run_repo):
        """Both status and workflow_id can be provided simultaneously."""
        runs = [_make_run("r1", "wf_1")]
        run_repo.list_runs_paginated.return_value = (runs, 1)

        items, total = run_service.list_runs_paginated(
            offset=0, limit=20, status=["pending"], workflow_id="wf_1"
        )

        assert total == 1
        assert len(items) == 1
