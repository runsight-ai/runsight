"""RunService delegates direct child-run queries to the repository."""

from unittest.mock import Mock

from tests.transport.child_run_helpers import _make_mock_run


class TestRunServiceListChildren:
    """RunService must expose a list_children(parent_run_id) method that queries
    the repository for runs with a matching parent_run_id."""

    def test_run_service_has_list_children_method(self):
        """RunService must have a list_children method."""
        from runsight_api.logic.services.run_service import RunService

        assert hasattr(RunService, "list_children"), (
            "RunService must expose a list_children method for the children endpoint"
        )

    def test_run_service_list_children_returns_only_direct_children(self):
        """list_children must query and return only runs with matching parent_run_id."""
        from runsight_api.logic.services.run_service import RunService

        mock_repo = Mock()
        mock_workflow_repo = Mock()

        child = _make_mock_run(
            "run_child",
            parent_run_id="run_parent",
            root_run_id="run_parent",
            depth=1,
        )
        mock_repo.list_children.return_value = [child]

        service = RunService(mock_repo, mock_workflow_repo)
        children = service.list_children("run_parent")

        assert len(children) == 1
        assert children[0].id == "run_child"
        mock_repo.list_children.assert_called_once_with("run_parent")
