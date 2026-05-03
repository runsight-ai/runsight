"""RunRepository exposes direct child-run lookup for nested run drill-down."""


def test_run_repository_has_list_children_method():
    from runsight_api.data.repositories.run_repo import RunRepository

    assert hasattr(RunRepository, "list_children")
