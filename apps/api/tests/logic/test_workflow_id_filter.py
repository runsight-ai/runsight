"""Run list pagination filters by workflow_id.

- GET /api/runs?workflow_id=X returns only runs for that workflow
- GET /api/runs without workflow_id still returns the unfiltered page
- list_runs_paginated accepts and forwards workflow_id without runtime errors
"""

from unittest.mock import Mock

import pytest

from runsight_api.domain.entities.run import Run, RunStatus
from runsight_api.logic.services.run_service import RunService

# --- Fixtures ---


@pytest.fixture
def run_repo():
    return Mock()


@pytest.fixture
def workflow_repo():
    return Mock()


@pytest.fixture
def run_read_model():
    return Mock()


@pytest.fixture
def run_service(run_repo, workflow_repo, run_read_model):
    return RunService(run_repo, workflow_repo, run_read_model=run_read_model)


# --- Helpers ---


def _make_run(run_id: str, workflow_id: str) -> Run:
    return Run(
        id=run_id,
        workflow_id=workflow_id,
        workflow_name=workflow_id,
        status=RunStatus.pending,
        task_json="{}",
        branch="main",
    )


# --- list_runs_paginated accepts workflow_id param ---


class TestWorkflowIdParamAccepted:
    """list_runs_paginated must accept workflow_id without raising TypeError."""

    def test_passing_workflow_id_does_not_raise_type_error(self, run_service, run_read_model):
        """Calling list_runs_paginated(workflow_id=...) must not raise TypeError."""
        run_read_model.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, workflow_id="filtered-workflow")

    def test_passing_workflow_id_none_does_not_raise_type_error(self, run_service, run_read_model):
        """Calling list_runs_paginated(workflow_id=None) must not raise TypeError."""
        run_read_model.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, workflow_id=None)


# --- workflow_id is forwarded to repo for filtering ---


class TestWorkflowIdForwardedToRepo:
    """When workflow_id is provided, it must be forwarded to the repo layer."""

    def test_workflow_id_forwarded_to_repo(self, run_service, run_read_model):
        """list_runs_paginated must pass workflow_id through to the run read model."""
        run_read_model.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, workflow_id="forwarded-workflow")

        # The repo must receive workflow_id so it can filter the SQL query
        run_read_model.list_runs_paginated.assert_called_once()
        _, kwargs = run_read_model.list_runs_paginated.call_args
        assert kwargs.get("workflow_id") == "forwarded-workflow", (
            "run_read_model.list_runs_paginated must be called with "
            "workflow_id='forwarded-workflow'"
        )

    def test_workflow_id_none_not_required_in_repo_call(self, run_service, run_read_model):
        """When workflow_id is None, the read model may be called without it or with None."""
        run_read_model.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, workflow_id=None)

        run_read_model.list_runs_paginated.assert_called_once()


# --- Without workflow_id still works ---


class TestUnfilteredRunsWithoutWorkflowId:
    """Calling list_runs_paginated without workflow_id must still work."""

    def test_without_workflow_id_returns_all_runs(self, run_service, run_read_model):
        """Omitting workflow_id returns the full paginated result (no filtering)."""
        runs = [
            _make_run("manual-run", "filtered-workflow"),
            _make_run("webhook-run", "other-workflow"),
        ]
        run_read_model.list_runs_paginated.return_value = (runs, 2)

        items, total = run_service.list_runs_paginated(offset=0, limit=20)

        assert total == 2
        assert len(items) == 2

    def test_with_status_only_still_works(self, run_service, run_read_model):
        """Passing status without workflow_id must still work (existing behavior)."""
        runs = [_make_run("pending-run", "filtered-workflow")]
        run_read_model.list_runs_paginated.return_value = (runs, 1)

        items, total = run_service.list_runs_paginated(offset=0, limit=20, status=["pending"])

        assert total == 1
        assert len(items) == 1

    def test_with_status_and_workflow_id_together(self, run_service, run_read_model):
        """Both status and workflow_id can be provided simultaneously."""
        runs = [_make_run("pending-filtered-run", "filtered-workflow")]
        run_read_model.list_runs_paginated.return_value = (runs, 1)

        items, total = run_service.list_runs_paginated(
            offset=0, limit=20, status=["pending"], workflow_id="filtered-workflow"
        )

        assert total == 1
        assert len(items) == 1
