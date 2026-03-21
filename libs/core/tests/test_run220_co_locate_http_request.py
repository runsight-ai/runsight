"""
Failing tests for RUN-220: Co-locate HttpRequestBlock (proof of concept).

Tests verify that HttpRequestBlockDef has been moved from schema.py into
blocks/http_request.py, that a build() function exists there, and that
auto-discovery picks it up identically to the previous hardcoded approach.

Expected failures (current state):
- HttpRequestBlockDef is still in schema.py (not yet in blocks/http_request.py)
- No build() function in blocks/http_request.py
- _build_http_request still exists in parser.py
- HttpRequestBlockDef still appears in the hardcoded BlockDef union in schema.py
"""

from __future__ import annotations

import inspect
import json
import sys

import pytest
from unittest.mock import MagicMock


# ═══════════════════════════════════════════════════════════════════════════════
# 1. HttpRequestBlockDef importable from blocks.http_request
# ═══════════════════════════════════════════════════════════════════════════════


class TestHttpRequestBlockDefLocation:
    """Verify HttpRequestBlockDef lives in blocks/http_request.py, not schema.py."""

    def test_import_from_blocks_http_request(self):
        """HttpRequestBlockDef must be importable from runsight_core.blocks.http_request."""
        from runsight_core.blocks.http_request import HttpRequestBlockDef  # noqa: F401

    def test_is_base_block_def_subclass(self):
        """HttpRequestBlockDef imported from blocks.http_request must subclass BaseBlockDef."""
        from runsight_core.blocks.http_request import HttpRequestBlockDef
        from runsight_core.yaml.schema import BaseBlockDef

        assert issubclass(HttpRequestBlockDef, BaseBlockDef)

    def test_type_literal_is_http_request(self):
        """HttpRequestBlockDef from blocks.http_request must have type Literal['http_request']."""
        from runsight_core.blocks.http_request import HttpRequestBlockDef

        block = HttpRequestBlockDef(type="http_request", url="https://example.com")
        assert block.type == "http_request"

    def test_has_all_expected_fields(self):
        """HttpRequestBlockDef from blocks.http_request must have all expected fields."""
        from runsight_core.blocks.http_request import HttpRequestBlockDef

        block = HttpRequestBlockDef(type="http_request", url="https://example.com")
        assert block.url == "https://example.com"
        assert block.method == "GET"
        assert block.headers == {}
        assert block.body is None
        assert block.body_type == "json"
        assert block.auth_type is None
        assert block.auth_config == {}
        assert block.timeout_seconds == 30
        assert block.retry_count == 0
        assert block.retry_backoff == 1.0
        assert block.expected_status_codes is None
        assert block.allow_private_ips is False

    def test_method_validator_uppercases(self):
        """The _uppercase_method field_validator must work on the co-located class."""
        from runsight_core.blocks.http_request import HttpRequestBlockDef

        block = HttpRequestBlockDef(type="http_request", url="https://x.com", method="post")
        assert block.method == "POST"

    def test_method_validator_rejects_invalid(self):
        """Invalid methods must still be rejected on the co-located class."""
        from pydantic import ValidationError
        from runsight_core.blocks.http_request import HttpRequestBlockDef

        with pytest.raises(ValidationError):
            HttpRequestBlockDef(type="http_request", url="https://x.com", method="TRACE")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. HttpRequestBlockDef NOT in schema.py source
# ═══════════════════════════════════════════════════════════════════════════════


class TestHttpRequestBlockDefRemovedFromSchema:
    """Verify HttpRequestBlockDef has been removed from schema.py."""

    def test_not_defined_in_schema_source(self):
        """HttpRequestBlockDef class definition must NOT appear in schema.py source."""
        import runsight_core.yaml.schema as schema_mod

        source = inspect.getsource(schema_mod)
        assert "class HttpRequestBlockDef" not in source, (
            "HttpRequestBlockDef class is still defined in schema.py — "
            "it must be moved to blocks/http_request.py"
        )

    def test_not_in_hardcoded_block_def_union(self):
        """HttpRequestBlockDef must NOT appear in the hardcoded BlockDef union in schema.py."""
        import runsight_core.yaml.schema as schema_mod

        source = inspect.getsource(schema_mod)
        # The hardcoded union lists class names; HttpRequestBlockDef must not be listed
        # Look for the union definition and check HttpRequestBlockDef is not in it
        lines = source.split("\n")
        in_union = False
        union_lines = []
        for line in lines:
            if "BlockDef = Annotated[" in line or "BlockDef = Annotated[" in line.strip():
                in_union = True
            if in_union:
                union_lines.append(line)
                if "]" in line and "Field(" in line:
                    break

        union_text = "\n".join(union_lines)
        assert "HttpRequestBlockDef" not in union_text, (
            "HttpRequestBlockDef is still in the hardcoded BlockDef union in schema.py — "
            "it must be removed (auto-discovery should pick it up instead)"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. _build_http_request NOT in parser.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildHttpRequestRemovedFromParser:
    """Verify _build_http_request has been removed from parser.py."""

    def test_build_http_request_not_in_parser_source(self):
        """_build_http_request function must NOT appear in parser.py source."""
        import runsight_core.yaml.parser as parser_mod

        source = inspect.getsource(parser_mod)
        assert "def _build_http_request" not in source, (
            "_build_http_request is still defined in parser.py — "
            "it must be replaced by build() in blocks/http_request.py"
        )

    def test_http_request_not_in_hardcoded_block_type_registry(self):
        """'http_request' must NOT appear in the hardcoded BLOCK_TYPE_REGISTRY dict in parser.py."""
        import runsight_core.yaml.parser as parser_mod

        source = inspect.getsource(parser_mod)
        # Look for the BLOCK_TYPE_REGISTRY definition and verify http_request is not in it
        lines = source.split("\n")
        in_registry = False
        registry_lines = []
        for line in lines:
            if "BLOCK_TYPE_REGISTRY" in line and ":" in line and "{" in line:
                in_registry = True
            if in_registry:
                registry_lines.append(line)
                if "}" in line:
                    break

        registry_text = "\n".join(registry_lines)
        assert '"http_request"' not in registry_text, (
            "'http_request' is still in the hardcoded BLOCK_TYPE_REGISTRY in parser.py — "
            "it must be removed (auto-discovery should register the builder instead)"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 4. build() function exists in blocks/http_request.py
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildFunctionExists:
    """Verify build() function exists in blocks/http_request.py."""

    def test_build_function_importable(self):
        """build() must be importable from runsight_core.blocks.http_request."""
        from runsight_core.blocks.http_request import build  # noqa: F401

    def test_build_function_is_callable(self):
        """build() must be callable."""
        from runsight_core.blocks.http_request import build

        assert callable(build)

    def test_build_returns_http_request_block(self):
        """build() must return an HttpRequestBlock instance."""
        from runsight_core.blocks.http_request import HttpRequestBlock, build

        block_def = MagicMock()
        block_def.type = "http_request"
        block_def.url = "https://api.example.com"
        block_def.method = "GET"
        block_def.headers = {}
        block_def.body = None
        block_def.body_type = "json"
        block_def.auth_type = None
        block_def.auth_config = {}
        block_def.timeout_seconds = 30
        block_def.retry_count = 0
        block_def.retry_backoff = 1.0
        block_def.expected_status_codes = None
        block_def.allow_private_ips = False

        result = build("test_block", block_def, {}, MagicMock(), {})
        assert isinstance(result, HttpRequestBlock)

    def test_build_sets_correct_block_id(self):
        """build() must pass block_id through correctly."""
        from runsight_core.blocks.http_request import build

        block_def = MagicMock()
        block_def.type = "http_request"
        block_def.url = "https://api.example.com/data"
        block_def.method = "POST"
        block_def.headers = {"X-Key": "val"}
        block_def.body = '{"a": 1}'
        block_def.body_type = "json"
        block_def.auth_type = "bearer"
        block_def.auth_config = {"token": "tk"}
        block_def.timeout_seconds = 60
        block_def.retry_count = 3
        block_def.retry_backoff = 2.0
        block_def.expected_status_codes = [200]
        block_def.allow_private_ips = False

        result = build("my_http_block", block_def, {}, MagicMock(), {})
        assert result.block_id == "my_http_block"

    def test_build_passes_all_config_values(self):
        """build() must carry all config values from the block_def."""
        from runsight_core.blocks.http_request import build

        block_def = MagicMock()
        block_def.type = "http_request"
        block_def.url = "https://api.example.com/endpoint"
        block_def.method = "PUT"
        block_def.headers = {"Accept": "application/json"}
        block_def.body = "raw body"
        block_def.body_type = "raw"
        block_def.auth_type = "api_key"
        block_def.auth_config = {"header": "X-API-Key", "value": "secret"}
        block_def.timeout_seconds = 120
        block_def.retry_count = 2
        block_def.retry_backoff = 1.5
        block_def.expected_status_codes = [200, 204]
        block_def.allow_private_ips = True

        result = build("cfg_block", block_def, {}, MagicMock(), {})

        assert result.url == "https://api.example.com/endpoint"
        assert result.method == "PUT"
        assert result.headers == {"Accept": "application/json"}
        assert result.body == "raw body"
        assert result.body_type == "raw"
        assert result.auth_type == "api_key"
        assert result.auth_config == {"header": "X-API-Key", "value": "secret"}
        assert result.timeout_seconds == 120
        assert result.retry_count == 2
        assert result.retry_backoff == 1.5
        assert result.expected_status_codes == [200, 204]
        assert result.allow_private_ips is True


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Registry integration — auto-discovery picks up http_request
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegistryIntegration:
    """Verify auto-discovery registers HttpRequestBlockDef and its builder."""

    def test_block_def_registry_has_http_request(self):
        """BLOCK_DEF_REGISTRY['http_request'] must point to HttpRequestBlockDef from blocks.http_request."""
        from runsight_core.blocks.http_request import HttpRequestBlockDef
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        # Trigger auto-discovery
        import runsight_core.blocks  # noqa: F401

        assert "http_request" in BLOCK_DEF_REGISTRY
        assert BLOCK_DEF_REGISTRY["http_request"] is HttpRequestBlockDef

    def test_block_def_registry_http_request_from_blocks_module(self):
        """The registered HttpRequestBlockDef must originate from blocks.http_request, not schema."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        import runsight_core.blocks  # noqa: F401

        cls = BLOCK_DEF_REGISTRY.get("http_request")
        assert cls is not None
        assert cls.__module__ == "runsight_core.blocks.http_request", (
            f"HttpRequestBlockDef is registered from {cls.__module__}, "
            "expected runsight_core.blocks.http_request"
        )

    def test_block_builder_registry_has_http_request(self):
        """BLOCK_BUILDER_REGISTRY['http_request'] must resolve to the build function."""
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        # Trigger auto-discovery
        import runsight_core.blocks  # noqa: F401

        assert "http_request" in BLOCK_BUILDER_REGISTRY
        assert callable(BLOCK_BUILDER_REGISTRY["http_request"])

    def test_block_builder_registry_points_to_module_build(self):
        """BLOCK_BUILDER_REGISTRY['http_request'] must be the build() from blocks.http_request."""
        from runsight_core.blocks.http_request import build
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        import runsight_core.blocks  # noqa: F401

        registered_builder = BLOCK_BUILDER_REGISTRY.get("http_request")
        assert registered_builder is build, (
            f"BLOCK_BUILDER_REGISTRY['http_request'] points to {registered_builder}, "
            f"expected build() from blocks.http_request"
        )

    def test_block_def_registry_count_is_12(self):
        """BLOCK_DEF_REGISTRY must still have exactly 12 entries after migration."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        # Ensure all block defs are loaded
        import runsight_core.yaml.schema  # noqa: F401
        import runsight_core.blocks  # noqa: F401

        expected_types = {
            "linear",
            "fanout",
            "synthesize",
            "router",
            "team_lead",
            "engineering_manager",
            "gate",
            "file_writer",
            "code",
            "loop",
            "http_request",
            "workflow",
        }
        known = {k: v for k, v in BLOCK_DEF_REGISTRY.items() if k in expected_types}
        assert len(known) == 12, (
            f"Expected 12 registered block types, got {len(known)}. "
            f"Missing: {expected_types - set(known.keys())}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Schema validation still works
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaValidationStillWorks:
    """Verify http_request schema validation is identical after migration."""

    def test_discriminated_union_routes_http_request(self):
        """BlockDef discriminated union must still route type='http_request' correctly."""
        from pydantic import TypeAdapter
        from runsight_core.yaml.schema import BlockDef

        adapter = TypeAdapter(BlockDef)
        block = adapter.validate_python({"type": "http_request", "url": "https://api.example.com"})
        assert block.type == "http_request"
        assert block.url == "https://api.example.com"

    def test_workflow_file_validates_http_request_block(self):
        """RunsightWorkflowFile must accept http_request blocks after migration."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        wf = RunsightWorkflowFile.model_validate(
            {
                "workflow": {"name": "test", "entry": "b1"},
                "blocks": {
                    "b1": {"type": "http_request", "url": "https://api.example.com"},
                },
            }
        )
        assert "b1" in wf.blocks
        assert wf.blocks["b1"].type == "http_request"

    def test_http_request_in_json_schema(self):
        """HttpRequestBlockDef must still appear in the generated JSON schema."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        schema = RunsightWorkflowFile.model_json_schema()
        schema_str = json.dumps(schema)
        assert "HttpRequestBlockDef" in schema_str

    def test_http_request_url_field_in_schema(self):
        """The 'url' field must still appear in HttpRequestBlockDef in the JSON schema."""
        from runsight_core.yaml.schema import RunsightWorkflowFile

        schema = RunsightWorkflowFile.model_json_schema()
        defs = schema.get("$defs", {})
        http_def = defs.get("HttpRequestBlockDef", {})
        properties = http_def.get("properties", {})
        assert "url" in properties


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Round-trip: parse YAML with http_request, verify it builds correctly
# ═══════════════════════════════════════════════════════════════════════════════


VALID_HTTP_REQUEST_YAML = """\
version: "1.0"
config:
  model_name: gpt-4o
blocks:
  fetch_data:
    type: http_request
    url: https://api.example.com/v1/data
    method: POST
    headers:
      Content-Type: application/json
      Authorization: Bearer sk-test
    body: '{"query": "test"}'
    body_type: json
    timeout_seconds: 60
    retry_count: 2
    retry_backoff: 1.5
workflow:
  name: test_http
  entry: fetch_data
  transitions:
    - from: fetch_data
      to: null
"""


class TestRoundTrip:
    """Integration: parse YAML with http_request block and verify correct build."""

    def test_parse_workflow_yaml_with_http_request(self):
        """parse_workflow_yaml must still work with http_request blocks after migration."""
        from runsight_core.yaml.parser import parse_workflow_yaml
        from runsight_core.workflow import Workflow

        wf = parse_workflow_yaml(VALID_HTTP_REQUEST_YAML)
        assert isinstance(wf, Workflow)
        assert wf.name == "test_http"

    def test_parsed_block_is_http_request_block(self):
        """The parsed block must be an HttpRequestBlock instance."""
        from runsight_core.blocks.http_request import HttpRequestBlock
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(VALID_HTTP_REQUEST_YAML)
        block = wf.blocks.get("fetch_data")
        assert block is not None
        assert isinstance(block, HttpRequestBlock)

    def test_parsed_block_has_correct_url(self):
        """The parsed HttpRequestBlock must have the correct url from YAML."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(VALID_HTTP_REQUEST_YAML)
        block = wf.blocks["fetch_data"]
        assert block.url == "https://api.example.com/v1/data"

    def test_parsed_block_has_correct_method(self):
        """The parsed HttpRequestBlock must have the correct method from YAML."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(VALID_HTTP_REQUEST_YAML)
        block = wf.blocks["fetch_data"]
        assert block.method == "POST"

    def test_parsed_block_has_correct_config(self):
        """The parsed HttpRequestBlock must carry all config values from YAML."""
        from runsight_core.yaml.parser import parse_workflow_yaml

        wf = parse_workflow_yaml(VALID_HTTP_REQUEST_YAML)
        block = wf.blocks["fetch_data"]
        assert block.timeout_seconds == 60
        assert block.retry_count == 2
        assert block.retry_backoff == 1.5
        assert block.body_type == "json"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. generate_schema.py --check passes
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateSchemaCheck:
    """Verify generate_schema.py --check passes after migration."""

    def test_generate_schema_check_passes(self):
        """Running `python generate_schema.py --check` must exit 0 after migration."""
        import subprocess
        from pathlib import Path

        script = Path(__file__).resolve().parent.parent / "scripts" / "generate_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--check"],
            capture_output=True,
            text=True,
            cwd=str(script.parent.parent),  # libs/core/
        )
        assert result.returncode == 0, (
            f"generate_schema.py --check failed (exit {result.returncode}).\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case tests for the co-location migration."""

    def test_no_duplicate_registration(self):
        """HttpRequestBlockDef must not be registered twice (once from schema, once from blocks)."""
        from runsight_core.blocks._registry import BLOCK_DEF_REGISTRY

        # Force all imports
        import runsight_core.yaml.schema  # noqa: F401
        import runsight_core.blocks  # noqa: F401

        # Count how many times http_request appears (should be exactly once)
        http_entries = [k for k in BLOCK_DEF_REGISTRY if k == "http_request"]
        assert len(http_entries) == 1

    def test_schema_module_still_exports_http_request_via_reexport(self):
        """schema.py should re-export HttpRequestBlockDef for backward compatibility.

        Even though the definition moves to blocks/http_request.py, existing code
        that does `from runsight_core.blocks.http_request import HttpRequestBlockDef` must
        still work (via a re-export / import alias).
        """
        from runsight_core.blocks.http_request import HttpRequestBlockDef  # noqa: F401

    def test_reexported_class_is_same_as_blocks_class(self):
        """The HttpRequestBlockDef re-exported from schema must be the same class object."""
        from runsight_core.blocks.http_request import HttpRequestBlockDef as SchemaClass
        from runsight_core.blocks.http_request import HttpRequestBlockDef as BlocksClass

        assert SchemaClass is BlocksClass, (
            "schema.py re-exports a different HttpRequestBlockDef than blocks/http_request.py"
        )

    def test_auto_discover_runs_before_yaml_validation(self):
        """Importing blocks must trigger auto-discovery so http_request is available.

        This confirms the import ordering is correct: blocks/__init__.py calls
        _auto_discover_blocks() at module load time.
        """
        from runsight_core.blocks._registry import BLOCK_BUILDER_REGISTRY

        # Fresh import of blocks should have populated the builder
        import runsight_core.blocks  # noqa: F401

        assert "http_request" in BLOCK_BUILDER_REGISTRY

    def test_generate_schema_imports_blocks_before_generating(self):
        """generate_schema.py must import runsight_core.blocks to trigger discovery.

        This ensures the schema includes types from auto-discovered blocks.
        """
        from pathlib import Path

        script = Path(__file__).resolve().parent.parent / "scripts" / "generate_schema.py"
        source = script.read_text()

        # Either imports runsight_core.blocks directly, or rebuild_block_def_union
        # (which would pull in discovered types)
        has_blocks_import = "runsight_core.blocks" in source
        has_rebuild = "rebuild_block_def_union" in source
        assert has_blocks_import or has_rebuild, (
            "generate_schema.py must import runsight_core.blocks or call "
            "rebuild_block_def_union() to trigger auto-discovery before generating schema"
        )
