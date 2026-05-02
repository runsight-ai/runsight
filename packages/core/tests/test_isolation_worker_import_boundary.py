"""Worker import boundary behavior."""

from __future__ import annotations

from pathlib import Path


class TestWorkerImportBoundary:
    """Worker must not import runsight_core.workflow, observer, or api modules."""

    def test_no_workflow_import(self):
        """Worker source must not import runsight_core.workflow."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_core.workflow" not in source, (
            "Worker must not import runsight_core.workflow"
        )

    def test_no_observer_import(self):
        """Worker source must not import runsight_core.observer."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_core.observer" not in source, (
            "Worker must not import runsight_core.observer"
        )

    def test_no_api_import(self):
        """Worker source must not import runsight_api."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "runsight_api" not in source, "Worker must not import runsight_api"

    def test_no_sqlmodel_import(self):
        """Worker source must not import sqlmodel."""
        from runsight_core.isolation import worker

        source_file = Path(worker.__file__)
        source = source_file.read_text()
        assert "sqlmodel" not in source, "Worker must not import sqlmodel"
