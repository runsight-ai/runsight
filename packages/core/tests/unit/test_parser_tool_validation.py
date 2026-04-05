"""
Failing tests for RUN-279: parser tool validation and resolution.

Tests target the new tool resolution phase (Step 6.6) in parse_workflow_yaml():
1. Validate ToolDef.source exists in BUILTIN_TOOL_CATALOG
2. Validate soul.tools entries exist in file_def.tools keys
3. Resolve ToolInstance objects per soul from catalog
4. Delegate tool: pass block exits to delegate factory
5. Attach resolved_tools to Soul primitive

All tests should FAIL until the parser is updated with tool validation logic.
"""

from __future__ import annotations

from textwrap import dedent

import pytest
import runsight_core.yaml.parser as parser_module
import yaml
from pydantic import ValidationError
from runsight_core.tools import ToolInstance
from runsight_core.yaml.parser import _resolve_soul_tool_definition, parse_workflow_yaml
from runsight_core.yaml.schema import RunsightWorkflowFile

# ---------------------------------------------------------------------------
# Helper: minimal YAML builder for tool-validation tests
# ---------------------------------------------------------------------------


def _make_yaml(
    *,
    tools: str = "",
    souls: str = "",
    blocks: str = "",
    transitions: str = "",
    entry: str = "my_block",
) -> str:
    """Build a complete workflow YAML string for tool-validation tests."""
    return f"""\
version: "1.0"
config:
  model_name: gpt-4o
{tools}
{souls}
blocks:
{blocks}
workflow:
  name: tool_test
  entry: {entry}
  transitions:
{transitions}
"""


def _write_workflow_file(tmp_path, yaml_str: str) -> str:
    """Persist a workflow YAML file so parse_workflow_yaml can infer checkout-local context."""
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(yaml_str, encoding="utf-8")
    return str(workflow_file)


def _write_custom_tool_file(tmp_path, slug: str, contents: str) -> None:
    """Create a custom tool metadata file under custom/tools for parser tests."""
    tools_dir = tmp_path / "custom" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / f"{slug}.yaml").write_text(dedent(contents), encoding="utf-8")


# ===========================================================================
# AC1: Valid YAML — soul.resolved_tools populated with ToolInstance objects
# ===========================================================================


class TestToolResolutionHappyPath:
    """After parsing, souls with declared tools get resolved_tools populated."""

    def test_soul_resolved_tools_is_list_of_tool_instance(self):
        """AC1: Soul referencing valid tools gets resolved_tools as list of ToolInstance."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)
        block = workflow.blocks["my_block"]
        soul = block.soul

        assert soul.resolved_tools is not None
        assert isinstance(soul.resolved_tools, list)
        assert len(soul.resolved_tools) == 1
        assert isinstance(soul.resolved_tools[0], ToolInstance)

    def test_soul_resolved_tools_contains_correct_tool_name(self):
        """AC1: Resolved ToolInstance has the expected name from the factory."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)
        block = workflow.blocks["my_block"]
        soul = block.soul

        assert soul.resolved_tools is not None
        assert soul.resolved_tools[0].name == "http_request"

    def test_multiple_tools_all_resolved(self):
        """AC1: Soul with multiple tools gets all of them resolved."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http
  - file_io""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http
      - file_io""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)
        block = workflow.blocks["my_block"]
        soul = block.soul

        assert soul.resolved_tools is not None
        assert len(soul.resolved_tools) == 2
        resolved_names = {t.name for t in soul.resolved_tools}
        assert "http_request" in resolved_names
        assert "file_io" in resolved_names

    def test_direct_builtin_soul_tools_require_workflow_tool_declarations(self):
        """RUN-490: direct soul refs must be rejected when the workflow tools whitelist omits them."""
        yaml_str = _make_yaml(
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http
      - file_io""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(
            ValueError,
            match=r"undeclared tool 'http'.*Declared tools: \[\]",
        ):
            parse_workflow_yaml(yaml_str)


# ===========================================================================
# RUN-490: Workflow tool governance helpers
# ===========================================================================


class TestWorkflowToolGovernanceHelpers:
    """Tool governance must be reusable outside parse_workflow_yaml()."""

    def test_parser_no_longer_exports_user_assignable_bypass_constant(self):
        """RUN-490: the obsolete direct-assignment bypass constant should be removed entirely."""
        assert not hasattr(parser_module, "USER_ASSIGNABLE_SOUL_TOOL_SOURCES"), (
            "Parser still exposes USER_ASSIGNABLE_SOUL_TOOL_SOURCES, leaving the bypass easy to resurrect"
        )

    def test_resolve_soul_tool_definition_only_uses_workflow_tools(self):
        """RUN-490: _resolve_soul_tool_definition must not bypass workflow_tools for built-ins."""
        assert _resolve_soul_tool_definition("http", {}) is None

    def test_validate_tool_governance_exists_for_api_layer_reuse(self):
        """RUN-490: validate_tool_governance() remains callable for API-layer reuse."""
        yaml_str = _make_yaml(
            souls="""\
souls:
  reviewer:
    id: reviewer
    role: Reviewer
    system_prompt: Review the draft.
    tools:
      - http""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: reviewer""",
            transitions="""\
    - from: my_block
      to: null""",
        )
        validator = getattr(parser_module, "validate_tool_governance", None)
        assert callable(validator), (
            "Expected parser.validate_tool_governance() for API-layer governance validation reuse"
        )

        file_def = RunsightWorkflowFile.model_validate(yaml.safe_load(yaml_str))
        validator(file_def)

    def test_validate_tool_governance_accepts_declared_tool_id_refs_from_whitelist(self):
        """RUN-577: governance should only care that soul refs stay within the workflow tool ID list."""
        raw = yaml.safe_load(
            _make_yaml(
                tools="""\
tools:
  - http
  - lookup_profile
  - delegate""",
                souls="""\
souls:
  reviewer:
    id: reviewer
    role: Reviewer
    system_prompt: Review the draft.
    tools:
      - http
      - lookup_profile""",
                blocks="""\
  my_block:
    type: linear
    soul_ref: reviewer""",
                transitions="""\
    - from: my_block
      to: null""",
            )
        )
        file_def = RunsightWorkflowFile.model_validate(raw)

        parser_module.validate_tool_governance(file_def)


# ===========================================================================
# RUN-577: Canonical workflow tool ID contract
# ===========================================================================


class TestCanonicalWorkflowToolIds:
    """Workflow tools should be authored as stable IDs only."""

    def test_canonical_builtin_tool_ids_parse_and_resolve(self):
        """Builtins should be declared and referenced by reserved IDs like http/file_io."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http
  - file_io""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http
      - file_io""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)
        soul = workflow.blocks["my_block"].soul

        assert soul.tools == ["http", "file_io"]
        assert soul.resolved_tools is not None
        assert {tool.name for tool in soul.resolved_tools} == {"http_request", "file_io"}

    def test_duplicate_workflow_tool_ids_raise_explicit_valueerror(self):
        """Workflow whitelist must reject duplicate tool IDs like repeated http entries."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http
  - http""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValueError, match=r"duplicate.*http"):
            parse_workflow_yaml(yaml_str)

    def test_unknown_workflow_tool_id_raises_explicit_valueerror(self):
        """Unknown workflow tool IDs must be rejected during parser validation."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - missing_lookup""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - missing_lookup""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValueError, match=r"unknown tool id 'missing_lookup'"):
            parse_workflow_yaml(yaml_str)

    def test_empty_tools_list_with_soul_reference_raises_undeclared_tool_error(self):
        """Souls still need workflow-declared IDs even when the whitelist is explicitly empty."""
        yaml_str = _make_yaml(
            tools="""\
tools: []""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValueError, match=r"undeclared tool 'http'.*Declared tools: \[\]"):
            parse_workflow_yaml(yaml_str)

    def test_missing_custom_tool_id_raises_actionable_valueerror(self, tmp_path):
        """Custom IDs declared in the workflow must resolve to checkout-local metadata files."""
        workflow_file = _write_workflow_file(
            tmp_path,
            _make_yaml(
                tools="""\
tools:
  - lookup_profile""",
                souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - lookup_profile""",
                blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
                transitions="""\
    - from: my_block
      to: null""",
            ),
        )

        with pytest.raises(
            ValueError,
            match=r"lookup_profile.*custom/tools/lookup_profile\.yaml",
        ):
            parse_workflow_yaml(workflow_file)

    def test_reserved_builtin_id_collision_with_custom_slug_raises_valueerror(self, tmp_path):
        """Reserved builtin IDs must reject custom tool files that try to reuse the same slug."""
        _write_custom_tool_file(
            tmp_path,
            "http",
            """
            version: "1.0"
            type: custom
            executor: python
            name: Shadow HTTP
            description: Shadows the builtin http tool id.
            parameters:
              type: object
            code: |
              def main(args):
                  return {"shadowed": True}
            """,
        )
        workflow_file = _write_workflow_file(
            tmp_path,
            _make_yaml(
                tools="""\
tools:
  - http""",
                souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http""",
                blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
                transitions="""\
    - from: my_block
      to: null""",
            ),
        )

        with pytest.raises(
            ValueError, match=r"reserved.*http.*custom/tools/http\.yaml|collision.*http"
        ):
            parse_workflow_yaml(workflow_file)

    def test_legacy_typed_tool_definitions_fail_clearly(self):
        """Workflow authoing must reject builtin/custom/http dict definitions outright."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  http:
    type: builtin
    source: runsight/http""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValidationError, match="list"):
            parse_workflow_yaml(yaml_str)

    def test_inline_http_tool_definitions_fail_clearly(self):
        """Inline HTTP tool authoring must fail instead of being normalized."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  http:
    type: http
    method: GET
    url: https://example.com/users/{{ user_id }}""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValidationError, match="list"):
            parse_workflow_yaml(yaml_str)


# ===========================================================================
# AC2: Soul references undeclared tool -> ValueError at parse time
# ===========================================================================


class TestUndeclaredToolReference:
    """Soul referencing a tool not in the tools section raises ValueError."""

    def test_soul_references_undeclared_tool_raises_valueerror(self):
        """AC2: Soul references tool 'foo' not in tools section -> ValueError."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - foo""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValueError, match="undeclared tool"):
            parse_workflow_yaml(yaml_str)

    def test_undeclared_tool_error_mentions_soul_name(self):
        """AC2: Error message includes the soul name and declared tool keys."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http
  - file_io""",
            souls="""\
souls:
  researcher_agent:
    id: researcher_agent
    role: Researcher
    system_prompt: Research stuff.
    tools:
      - nonexistent_tool""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: researcher_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValueError, match="researcher_agent"):
            parse_workflow_yaml(yaml_str)

    def test_direct_system_tool_source_still_rejected_for_soul_level_assignment(self):
        """System-owned tools like runsight/delegate must not be directly assignable on souls."""
        yaml_str = _make_yaml(
            souls="""\
souls:
  gate_agent:
    id: gate_agent
    role: Gate Agent
    system_prompt: Evaluate and delegate.
    tools:
      - runsight/delegate""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: gate_agent
    exits:
      - id: approve
        label: Approve
      - id: reject
        label: Reject""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValueError, match="runsight/delegate"):
            parse_workflow_yaml(yaml_str)


# ===========================================================================
# AC3: Unknown tool IDs -> ValueError at parse time
# ===========================================================================


class TestUnknownToolIdStrings:
    """Source-like workflow entries must fail as unknown canonical IDs."""

    def test_legacy_builtin_source_string_in_workflow_tools_raises_valueerror(self):
        """Old source strings must not be accepted as workflow tool IDs."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - runsight/unknown""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - runsight/unknown""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValueError, match=r"unknown tool id 'runsight/unknown'"):
            parse_workflow_yaml(yaml_str)

    def test_unknown_tool_id_error_mentions_available_canonical_ids(self):
        """Unknown ID errors should point callers back to the canonical whitelist."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - runsight/nonexistent""",
            souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - runsight/nonexistent""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValueError, match="Available"):
            parse_workflow_yaml(yaml_str)


# ===========================================================================
# RUN-528: Parser governance for discovered custom tool IDs
# ===========================================================================


class TestCanonicalDiscoveredToolValidation:
    """Parser validation should stay actionable with ID-only workflow authoring."""

    def test_custom_tool_missing_yaml_file_raises_actionable_valueerror(self, tmp_path):
        """A declared custom tool ID should fail when its custom/tools YAML is missing."""
        workflow_file = _write_workflow_file(
            tmp_path,
            _make_yaml(
                tools="""\
tools:
  - missing_lookup""",
                souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - missing_lookup""",
                blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
                transitions="""\
    - from: my_block
      to: null""",
            ),
        )

        with pytest.raises(ValueError, match=r"missing_lookup.*custom/tools.*yaml"):
            parse_workflow_yaml(workflow_file)

    @pytest.mark.parametrize(
        ("slug", "tool_yaml", "expected_message"),
        [
            (
                "blocked_import_tool",
                """
                version: "1.0"
                type: custom
                executor: python
                name: Blocked Import Tool
                description: Imports a blocked module.
                parameters:
                  type: object
                code: |
                  import os

                  def main(args):
                      return {}
                """,
                r"blocked_import_tool.*not allowed",
            ),
            (
                "missing_main_tool",
                """
                version: "1.0"
                type: custom
                executor: python
                name: Missing Main Tool
                description: Omits the required main(args) entrypoint.
                parameters:
                  type: object
                code: |
                  def helper(args):
                      return {}
                """,
                r"missing_main_tool.*main",
            ),
        ],
    )
    def test_custom_tool_invalid_code_raises_actionable_valueerror(
        self, tmp_path, slug, tool_yaml, expected_message
    ):
        """Blocked imports and missing main() should fail for discovered custom tool IDs."""
        _write_custom_tool_file(tmp_path, slug, tool_yaml)
        workflow_file = _write_workflow_file(
            tmp_path,
            _make_yaml(
                tools=f"""\
tools:
  - {slug}""",
                souls=f"""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - {slug}""",
                blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
                transitions="""\
    - from: my_block
      to: null""",
            ),
        )

        with pytest.raises(ValueError, match=expected_message):
            parse_workflow_yaml(workflow_file)

    def test_valid_builtin_and_discovered_custom_tool_ids_parse_successfully(self, tmp_path):
        """A workflow mixing canonical builtin and discovered custom IDs should parse cleanly."""
        _write_custom_tool_file(
            tmp_path,
            "echo_tool",
            """
            version: "1.0"
            type: custom
            executor: python
            name: Echo Tool
            description: Echoes the provided message.
            parameters:
              type: object
              properties:
                message:
                  type: string
              required:
                - message
            code: |
              def main(args):
                  return {"echo": args["message"]}
            """,
        )
        workflow_file = _write_workflow_file(
            tmp_path,
            _make_yaml(
                tools="""\
tools:
  - http
  - echo_tool""",
                souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - http
      - echo_tool""",
                blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
                transitions="""\
    - from: my_block
      to: null""",
            ),
        )

        workflow = parse_workflow_yaml(workflow_file)
        soul = workflow.blocks["my_block"].soul

        assert soul.resolved_tools is not None
        assert len(soul.resolved_tools) == 2
        assert soul.tools == ["http", "echo_tool"]

    def test_request_backed_custom_tool_file_parses_successfully(self, tmp_path):
        """Canonical request-backed tool files should resolve from their filename-derived IDs."""
        _write_custom_tool_file(
            tmp_path,
            "fetch_answer",
            """
            version: "1.0"
            type: custom
            executor: request
            name: Fetch Answer
            description: Fetches an answer by item id.
            parameters:
              type: object
              properties:
                item_id:
                  type: integer
              required:
                - item_id
            request:
              method: GET
              url: https://example.com/items/{{ item_id }}
              headers:
                X-Test: runsight
              response_path: data.answer
            timeout_seconds: 9
            """,
        )
        workflow_file = _write_workflow_file(
            tmp_path,
            _make_yaml(
                tools="""\
tools:
  - fetch_answer""",
                souls="""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - fetch_answer""",
                blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
                transitions="""\
    - from: my_block
      to: null""",
            ),
        )

        workflow = parse_workflow_yaml(workflow_file)
        soul = workflow.blocks["my_block"].soul

        assert soul.resolved_tools is not None
        assert [tool.name for tool in soul.resolved_tools] == ["fetch_answer"]

    @pytest.mark.parametrize(
        ("slug", "tool_yaml", "expected_message"),
        [
            (
                "legacy_http",
                """
                version: "1.0"
                type: http
                """,
                r"legacy_http.*type.*custom|legacy_http.*unsupported",
            ),
            (
                "missing_request_url",
                """
                version: "1.0"
                type: custom
                executor: request
                name: Missing Request URL
                description: Missing nested request.url.
                parameters:
                  type: object
                request:
                  method: GET
                """,
                r"missing_request_url.*url",
            ),
            (
                "python_with_request",
                """
                version: "1.0"
                type: custom
                executor: python
                name: Python With Request
                description: Python executors must reject request metadata.
                parameters:
                  type: object
                request:
                  method: GET
                  url: https://example.com/items/{{ item_id }}
                code: |
                  def main(args):
                      return args
                """,
                r"python_with_request.*request",
            ),
        ],
    )
    def test_invalid_custom_tool_metadata_surfaces_file_specific_errors(
        self, tmp_path, slug, tool_yaml, expected_message
    ):
        """Parser errors should preserve the offending filename for invalid custom tool files."""
        _write_custom_tool_file(tmp_path, slug, tool_yaml)
        workflow_file = _write_workflow_file(
            tmp_path,
            _make_yaml(
                tools=f"""\
tools:
  - {slug}""",
                souls=f"""\
souls:
  my_agent:
    id: my_agent
    role: Agent
    system_prompt: Do things.
    tools:
      - {slug}""",
                blocks="""\
  my_block:
    type: linear
    soul_ref: my_agent""",
                transitions="""\
    - from: my_block
      to: null""",
            ),
        )

        with pytest.raises(ValueError, match=expected_message):
            parse_workflow_yaml(workflow_file)


# ===========================================================================
# AC4: Delegate tool — port enum generated from block exits
# ===========================================================================


class TestDelegateToolWithExits:
    """Delegate tool gets port enum from the block's declared exits."""

    def test_delegate_tool_resolves_with_exit_enum(self):
        """AC4: Block with exits + soul with delegate tool -> ToolInstance has port enum."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - delegate""",
            souls="""\
souls:
  gate_agent:
    id: gate_agent
    role: Gate Agent
    system_prompt: Evaluate and delegate.
    tools:
      - delegate""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: gate_agent
    exits:
      - id: approve
        label: Approve
      - id: reject
        label: Reject""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)
        block = workflow.blocks["my_block"]
        soul = block.soul

        assert soul.resolved_tools is not None
        delegate = next(t for t in soul.resolved_tools if t.name == "delegate")
        port_schema = delegate.parameters["properties"]["port"]
        assert "enum" in port_schema
        assert set(port_schema["enum"]) == {"approve", "reject"}

    def test_delegate_tool_with_three_exits(self):
        """AC4: Delegate with three exits -> port enum has all three exit IDs."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - delegate""",
            souls="""\
souls:
  router_agent:
    id: router_agent
    role: Router
    system_prompt: Route to exit.
    tools:
      - delegate""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: router_agent
    exits:
      - id: done
        label: Done
      - id: retry
        label: Retry
      - id: escalate
        label: Escalate""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)
        block = workflow.blocks["my_block"]
        soul = block.soul

        assert soul.resolved_tools is not None
        delegate = next(t for t in soul.resolved_tools if t.name == "delegate")
        port_schema = delegate.parameters["properties"]["port"]
        assert set(port_schema["enum"]) == {"done", "retry", "escalate"}


# ===========================================================================
# AC5: Soul with delegate but block without exits -> ValueError
# ===========================================================================


class TestDelegateWithoutExits:
    """Delegate tool on a soul whose block has no exits -> ValueError."""

    def test_delegate_tool_without_block_exits_raises_valueerror(self):
        """AC5: Soul has delegate tool but block has no exits defined -> ValueError."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - delegate""",
            souls="""\
souls:
  gate_agent:
    id: gate_agent
    role: Gate Agent
    system_prompt: Evaluate and delegate.
    tools:
      - delegate""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: gate_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        with pytest.raises(ValueError, match="no exits"):
            parse_workflow_yaml(yaml_str)

    def test_delegate_without_exits_error_mentions_soul_and_block(self):
        """AC5: Error message mentions the soul name and block ID."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - delegate""",
            souls="""\
souls:
  my_evaluator:
    id: my_evaluator
    role: Evaluator
    system_prompt: Evaluate.
    tools:
      - delegate""",
            blocks="""\
  eval_block:
    type: linear
    soul_ref: my_evaluator""",
            entry="eval_block",
            transitions="""\
    - from: eval_block
      to: null""",
        )

        with pytest.raises(ValueError, match="my_evaluator|eval_block"):
            parse_workflow_yaml(yaml_str)


# ===========================================================================
# AC6: Soul with no tools -> resolved_tools is None
# ===========================================================================


class TestSoulWithNoTools:
    """Soul without tools field -> resolved_tools stays None."""

    def test_soul_without_tools_has_none_resolved_tools(self):
        """AC6: Soul with no tools field -> resolved_tools is None after parsing."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http""",
            souls="""\
souls:
  plain_agent:
    id: plain_agent
    role: Plain Agent
    system_prompt: Do plain things.""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: plain_agent""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)
        block = workflow.blocks["my_block"]
        soul = block.soul

        assert soul.resolved_tools is None

    def test_defined_soul_without_tools_has_none_resolved_tools(self):
        """AC6: Explicitly defined soul (no tools) -> resolved_tools is None."""
        yaml_str = _make_yaml(
            souls="""\
souls:
  researcher:
    id: researcher
    role: Senior Researcher
    system_prompt: You research topics.""",
            blocks="""\
  my_block:
    type: linear
    soul_ref: researcher""",
            transitions="""\
    - from: my_block
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)
        block = workflow.blocks["my_block"]
        soul = block.soul

        assert soul.resolved_tools is None


# ===========================================================================
# Multiple souls, different tools — each soul gets only its declared tools
# ===========================================================================


class TestMultipleSoulsDifferentTools:
    """Each soul gets only its own declared tools resolved, not all tools."""

    def test_two_souls_get_different_resolved_tools(self):
        """Two souls with different tool sets each get only their own tools."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http
  - file_io""",
            souls="""\
souls:
  http_agent:
    id: http_agent
    role: HTTP Agent
    system_prompt: Make HTTP calls.
    tools:
      - http
  file_agent:
    id: file_agent
    role: File Agent
    system_prompt: Read files.
    tools:
      - file_io""",
            blocks="""\
  block_a:
    type: linear
    soul_ref: http_agent
  block_b:
    type: linear
    soul_ref: file_agent""",
            entry="block_a",
            transitions="""\
    - from: block_a
      to: block_b
    - from: block_b
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)

        soul_a = workflow.blocks["block_a"].soul
        soul_b = workflow.blocks["block_b"].soul

        # Soul A: only http
        assert soul_a.resolved_tools is not None
        assert len(soul_a.resolved_tools) == 1
        assert soul_a.resolved_tools[0].name == "http_request"

        # Soul B: only file_io
        assert soul_b.resolved_tools is not None
        assert len(soul_b.resolved_tools) == 1
        assert soul_b.resolved_tools[0].name == "file_io"

    def test_soul_with_tools_and_soul_without_tools(self):
        """One soul with tools and one without -> only the first gets resolved_tools."""
        yaml_str = _make_yaml(
            tools="""\
tools:
  - http""",
            souls="""\
souls:
  tool_agent:
    id: tool_agent
    role: Tool Agent
    system_prompt: Use tools.
    tools:
      - http
  plain_agent:
    id: plain_agent
    role: Plain Agent
    system_prompt: No tools.""",
            blocks="""\
  block_a:
    type: linear
    soul_ref: tool_agent
  block_b:
    type: linear
    soul_ref: plain_agent""",
            entry="block_a",
            transitions="""\
    - from: block_a
      to: block_b
    - from: block_b
      to: null""",
        )

        workflow = parse_workflow_yaml(yaml_str)

        soul_a = workflow.blocks["block_a"].soul
        soul_b = workflow.blocks["block_b"].soul

        # Soul A: has resolved tools
        assert soul_a.resolved_tools is not None
        assert len(soul_a.resolved_tools) == 1

        # Soul B: no tools -> resolved_tools is None
        assert soul_b.resolved_tools is None
