"""Fixture builders for workflow simulation input schema transport tests."""

from __future__ import annotations

from unittest.mock import Mock

from runsight_api.logic.services.workflow_service import WorkflowService

SIM_BRANCH = "sim/wf_dirty_simulation/20260419/abc12"
SIM_SHA = "1234567890abcdef1234567890abcdef12345678"
WORKFLOW_SLUG = "wf_dirty_simulation"
WORKFLOW_YAML_PATH = "custom/workflows/wf_dirty_simulation.yaml"


def make_workflow_service(*, git_service: Mock | None = None) -> WorkflowService:
    workflow_repo = Mock()
    run_repo = Mock()
    return WorkflowService(workflow_repo, run_repo, git_service=git_service or Mock())


def make_git_service_with_sim_branch() -> Mock:
    git_service = Mock()
    git_service.create_sim_branch.return_value = Mock(branch=SIM_BRANCH, sha=SIM_SHA)
    return git_service


def dirty_workflow_yaml(*, input_type: str = "string") -> str:
    return f"""version: "1.0"
id: wf_dirty_simulation
kind: workflow
inputs:
  query:
    type: {input_type}
    description: Search query
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {{"ok": True}}
workflow:
  name: Dirty workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def dirty_workflow_yaml_without_inputs() -> str:
    return """version: "1.0"
id: wf_dirty_simulation
kind: workflow
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {\"ok\": True}
workflow:
  name: Dirty workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def dirty_workflow_yaml_with_invalid_workflow_input_ref() -> str:
    return """version: "1.0"
id: wf_dirty_simulation
kind: workflow
inputs:
  query:
    type: string
blocks:
  start:
    type: code
    inputs:
      prompt:
        from: workflow.missing
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: Dirty workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def dirty_workflow_yaml_with_sensitive_default() -> str:
    return """version: "1.0"
id: wf_dirty_simulation
kind: workflow
inputs:
  api_key:
    type: string
    sensitive: true
    default: SECRET_LEAKED=True
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: Dirty workflow
  entry: start
  transitions:
    - from: start
      to: null
"""


def dirty_workflow_yaml_with_legacy_interface() -> str:
    return """version: "1.0"
id: wf_dirty_simulation
kind: workflow
interface:
  inputs:
    - name: query
      target: shared_memory.query
blocks:
  start:
    type: code
    code: |
      def main(data):
          return {"ok": True}
workflow:
  name: Dirty workflow
  entry: start
  transitions:
    - from: start
      to: null
"""
