"""RunService forwards source and branch filters to the read model."""

from unittest.mock import Mock

import pytest


class TestServiceAcceptsSourceAndBranch:
    """RunService.list_runs_paginated must accept source and branch kwargs."""

    @pytest.fixture
    def run_repo(self):
        return Mock()

    @pytest.fixture
    def workflow_repo(self):
        return Mock()

    @pytest.fixture
    def run_read_model(self):
        return Mock()

    @pytest.fixture
    def run_service(self, run_repo, workflow_repo, run_read_model):
        from runsight_api.logic.services.run_service import RunService

        return RunService(run_repo, workflow_repo, run_read_model=run_read_model)

    def test_service_accepts_source_param(self, run_service, run_read_model):
        """list_runs_paginated(source=['simulation']) must not raise TypeError."""
        run_read_model.list_runs_paginated.return_value = ([], 0)

        # Method must accept source without raising TypeError
        run_service.list_runs_paginated(offset=0, limit=20, source=["simulation"])

    def test_service_accepts_branch_param(self, run_service, run_read_model):
        """list_runs_paginated(branch='main') must not raise TypeError."""
        run_read_model.list_runs_paginated.return_value = ([], 0)

        # Method must accept branch without raising TypeError
        run_service.list_runs_paginated(offset=0, limit=20, branch="main")

    def test_service_forwards_source_to_repo(self, run_service, run_read_model):
        """Service must forward source to the run read model for SQL filtering."""
        run_read_model.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, source=["manual", "webhook"])

        run_read_model.list_runs_paginated.assert_called_once()
        _, kwargs = run_read_model.list_runs_paginated.call_args
        assert kwargs.get("source") == ["manual", "webhook"], (
            "run_read_model.list_runs_paginated must receive source=['manual', 'webhook']"
        )

    def test_service_forwards_branch_to_repo(self, run_service, run_read_model):
        """Service must forward branch to the run read model for SQL filtering."""
        run_read_model.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(offset=0, limit=20, branch="main")

        run_read_model.list_runs_paginated.assert_called_once()
        _, kwargs = run_read_model.list_runs_paginated.call_args
        assert kwargs.get("branch") == "main", (
            "run_read_model.list_runs_paginated must receive branch='main'"
        )

    def test_service_source_and_branch_with_existing_params(self, run_service, run_read_model):
        """source + branch work alongside existing status + workflow_id params."""
        run_read_model.list_runs_paginated.return_value = ([], 0)

        run_service.list_runs_paginated(
            offset=0,
            limit=20,
            status=["completed"],
            workflow_id="source-branch-workflow",
            source=["manual"],
            branch="main",
        )

        run_read_model.list_runs_paginated.assert_called_once()
        _, kwargs = run_read_model.list_runs_paginated.call_args
        assert kwargs.get("status") == ["completed"]
        assert kwargs.get("workflow_id") == "source-branch-workflow"
        assert kwargs.get("source") == ["manual"]
        assert kwargs.get("branch") == "main"
