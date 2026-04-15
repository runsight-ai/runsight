from textwrap import dedent
from unittest.mock import patch

from runsight_core.primitives import Soul


def test_validate_yaml_content_uses_public_soul_scanner(tmp_path, workflow_repo_module):
    raw_yaml = dedent(
        """\
        id: scanner-migration
        kind: workflow
        version: "1.0"
        blocks:
          step:
            type: linear
            soul_ref: researcher
        workflow:
          name: scanner_migration
          entry: step
          transitions:
            - from: step
              to: null
        """
    )

    with workflow_repo_module() as workflow_repo:
        repo = workflow_repo.WorkflowRepository(base_path=str(tmp_path))
        with patch.object(workflow_repo, "SoulScanner") as mock_scanner:
            mock_scanner.return_value.scan.return_value.ids.return_value = {
                "researcher": Soul(
                    id="researcher_1",
                    kind="soul",
                    name="Researcher",
                    role="Researcher",
                    system_prompt="Research",
                )
            }
            valid, error, warnings = repo._validate_yaml_content("scanner-migration", raw_yaml)

    assert valid is True
    assert error is None
    assert warnings == []
    mock_scanner.assert_called_once()
    mock_scanner.return_value.scan.assert_called_once()
    mock_scanner.return_value.scan.return_value.ids.assert_called_once()
